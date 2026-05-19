// Judge service: business logic for creating and executing judge evaluation tasks.
// Each "Run" creates an independent record in experiment_judge_runs; results are scoped to a run.
// The latest run's summary (status, counts) is synced back to the parent judge for quick display.
package service

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"deeppool/platform/internal/experiment/repository"
	"deeppool/platform/internal/experiment/types"
)

// JudgeService defines business operations for judge tasks.
type JudgeService interface {
	CreateJudge(userID uint64, req types.CreateJudgeRequest) (*types.JudgeDTO, error)
	UpdateJudge(userID, judgeID uint64, req types.UpdateJudgeRequest) (*types.JudgeDTO, error)
	GetJudge(userID, judgeID uint64) (*types.JudgeDTO, error)
	ListJudges(userID uint64) ([]types.JudgeDTO, error)
	RunJudge(userID, judgeID uint64) (*types.JudgeRunDTO, error)
	ListJudgeRuns(judgeID uint64) ([]types.JudgeRunDTO, error)
	GetJudgeRunResults(runID uint64, page, pageSize int) ([]types.JudgeResultDTO, bool, error)
	DeleteJudge(userID, judgeID uint64) error
	ListBuiltinScorers(lang string) []BuiltinScorer
}

type judgeService struct {
	repo           repository.JudgeRepository
	annotationRepo repository.AnnotationRepository
	traceReader    types.TraceReader
	llmClient      types.LLMClient
	keyResolver    types.APIKeyResolver
	workerPool     int
}

// NewJudgeService creates a JudgeService.
func NewJudgeService(
	repo repository.JudgeRepository,
	annotationRepo repository.AnnotationRepository,
	traceReader types.TraceReader,
	llmClient types.LLMClient,
	keyResolver types.APIKeyResolver,
	workerPool int,
) JudgeService {
	return &judgeService{
		repo:           repo,
		annotationRepo: annotationRepo,
		traceReader:    traceReader,
		llmClient:      llmClient,
		keyResolver:    keyResolver,
		workerPool:     workerPool,
	}
}

func (s *judgeService) CreateJudge(userID uint64, req types.CreateJudgeRequest) (*types.JudgeDTO, error) {
	if req.Name == "" {
		return nil, errors.New("name is required")
	}
	if err := validateScope(req.Scope, req.ScopeValue, req.TraceID); err != nil {
		return nil, err
	}
	if req.JudgeModel == "" {
		return nil, errors.New("judge_model is required")
	}
	if req.JudgeAPIKeyID == 0 {
		return nil, errors.New("judge_apikey_id is required")
	}
	if req.PromptTemplate == "" {
		return nil, errors.New("prompt_template is required")
	}

	// For builtin scorer, validate name exists
	if req.ScorerType == types.ScorerTypeBuiltin {
		if req.ScorerName == "" {
			return nil, errors.New("scorer_name is required for builtin scorer")
		}
		if GetBuiltinScorer(req.ScorerName) == nil {
			return nil, fmt.Errorf("unknown builtin scorer: %s", req.ScorerName)
		}
	} else {
		req.ScorerType = types.ScorerTypeCustom
	}

	id, err := s.repo.Create(userID, req)
	if err != nil {
		return nil, err
	}
	return s.repo.FindByID(id)
}

// UpdateJudge applies partial config updates to an existing judge task.
func (s *judgeService) UpdateJudge(userID, judgeID uint64, req types.UpdateJudgeRequest) (*types.JudgeDTO, error) {
	dto, err := s.repo.FindByID(judgeID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errors.New("judge not found")
		}
		return nil, err
	}
	if dto.UserID != userID {
		return nil, errors.New("judge not found")
	}
	if dto.Status == types.StatusRunning {
		return nil, errors.New("cannot update a running judge")
	}

	if err := s.repo.Update(judgeID, req); err != nil {
		return nil, err
	}
	return s.repo.FindByID(judgeID)
}

func (s *judgeService) GetJudge(userID, judgeID uint64) (*types.JudgeDTO, error) {
	dto, err := s.repo.FindByID(judgeID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errors.New("judge not found")
		}
		return nil, err
	}
	if dto.UserID != userID {
		return nil, errors.New("judge not found")
	}
	return dto, nil
}

func (s *judgeService) ListJudges(userID uint64) ([]types.JudgeDTO, error) {
	return s.repo.FindByUserID(userID)
}

// RunJudge creates a new run record and starts asynchronous judge execution.
func (s *judgeService) RunJudge(userID, judgeID uint64) (*types.JudgeRunDTO, error) {
	dto, err := s.repo.FindByID(judgeID)
	if err != nil {
		return nil, errors.New("judge not found")
	}
	if dto.UserID != userID {
		return nil, errors.New("judge not found")
	}
	if dto.Status == types.StatusRunning {
		return nil, errors.New("judge is already running")
	}

	// Create a new run record
	runID, err := s.repo.CreateRun(judgeID)
	if err != nil {
		return nil, fmt.Errorf("create run failed: %w", err)
	}

	// Mark run as running
	if err := s.repo.UpdateRunStatus(runID, types.StatusRunning); err != nil {
		return nil, err
	}
	// Sync to judge for quick display
	_ = s.repo.SyncLatestRunToJudge(judgeID)

	// Launch async execution with run context
	go s.executeJudge(dto, runID)

	return s.repo.FindRunByID(runID)
}

func (s *judgeService) ListJudgeRuns(judgeID uint64) ([]types.JudgeRunDTO, error) {
	return s.repo.ListRuns(judgeID)
}

func (s *judgeService) GetJudgeRunResults(runID uint64, page, pageSize int) ([]types.JudgeResultDTO, bool, error) {
	return s.repo.ListResultsByRun(runID, page, pageSize)
}

func (s *judgeService) DeleteJudge(userID, judgeID uint64) error {
	err := s.repo.Delete(judgeID, userID)
	if errors.Is(err, sql.ErrNoRows) {
		return errors.New("judge not found")
	}
	return err
}

func (s *judgeService) ListBuiltinScorers(lang string) []BuiltinScorer {
	return GetBuiltinScorersForLang(lang)
}

// validateScope checks scope value validity.
// scope=trace with trace_id=0 means "all traces" (evaluate all logs across all trace tasks).
func validateScope(scope, scopeValue string, traceID uint64) error {
	switch scope {
	case types.ScopeModel:
		if scopeValue == "" {
			return errors.New("scope_value (model name) is required for model scope")
		}
		if traceID == 0 {
			return errors.New("trace_id is required for model scope")
		}
	case types.ScopeAPIKey:
		if scopeValue == "" {
			return errors.New("scope_value (apikey id) is required for apikey scope")
		}
		if traceID == 0 {
			return errors.New("trace_id is required for apikey scope")
		}
	case types.ScopeTrace:
		// trace_id=0 is allowed, meaning "all traces"
	case types.ScopeTraceLog:
		if traceID == 0 {
			return errors.New("trace_id is required for trace_log scope")
		}
		if scopeValue == "" {
			return errors.New("scope_value (log ids) is required for trace_log scope")
		}
	default:
		return fmt.Errorf("invalid scope: %s (must be model/apikey/trace/trace_log)", scope)
	}
	return nil
}

// executeJudge runs the judge evaluation asynchronously with a worker pool.
// All progress updates go to the run record; final status is synced to the judge.
func (s *judgeService) executeJudge(dto *types.JudgeDTO, runID uint64) {
	ctx := context.Background()
	judgeID := dto.ID

	// Read trace logs based on scope
	logs, err := s.traceReader.ReadLogsWithScope(ctx, dto.UserID, dto.TraceID, dto.Scope, dto.ScopeValue)
	if err != nil {
		log.Printf("[ERROR] judge_svc: read trace logs failed judge_id=%d run_id=%d scope=%s err=%v", judgeID, runID, dto.Scope, err)
		_ = s.repo.UpdateRunStatus(runID, types.StatusFailed)
		_ = s.repo.SyncLatestRunToJudge(judgeID)
		return
	}

	totalCount := len(logs)
	if totalCount == 0 {
		log.Printf("[INFO] judge_svc: no trace logs found judge_id=%d run_id=%d scope=%s scope_value=%s", judgeID, runID, dto.Scope, dto.ScopeValue)
		_ = s.repo.UpdateRunStatus(runID, types.StatusCompleted)
		_ = s.repo.SyncLatestRunToJudge(judgeID)
		return
	}

	// Update total count on run
	_ = s.repo.UpdateRunTotalCount(runID, totalCount)

	// Resolve actual API key value from encrypted storage
	apiKey, err := s.keyResolver.Resolve(dto.UserID, dto.JudgeAPIKeyID)
	if err != nil {
		log.Printf("[ERROR] judge_svc: resolve api key failed judge_id=%d run_id=%d apikey_id=%d uid=%d err=%v",
			judgeID, runID, dto.JudgeAPIKeyID, dto.UserID, err)
		_ = s.repo.UpdateRunStatus(runID, types.StatusFailed)
		_ = s.repo.SyncLatestRunToJudge(judgeID)
		return
	}

	// Worker pool execution
	var mu sync.Mutex
	completed, failed, passed := 0, 0, 0
	sem := make(chan struct{}, s.workerPool)

	var wg sync.WaitGroup
	for _, entry := range logs {
		wg.Add(1)
		sem <- struct{}{}
		go func(entry types.TraceLogEntry) {
			defer wg.Done()
			defer func() { <-sem }()

			result := s.evaluateSingleLog(ctx, dto, runID, entry, apiKey)

			// Write judge feedback to annotation
			if result.Success {
				s.writeFeedbackToAnnotation(dto, entry.ID, result)
			}

			mu.Lock()
			if result.Success {
				completed++
				if result.Passed {
					passed++
				}
			} else {
				failed++
			}
			_ = s.repo.UpdateRunProgress(runID, completed, failed)
			mu.Unlock()
		}(entry)
	}
	wg.Wait()

	// Compute pass rate: passed / successful_count * 100
	var passRate float64
	if completed > 0 {
		passRate = float64(passed) / float64(completed) * 100.0
	}
	_ = s.repo.UpdateRunPassRate(runID, passRate)

	// Mark run completed
	_ = s.repo.UpdateRunStatus(runID, types.StatusCompleted)
	// Sync summary to parent judge
	_ = s.repo.SyncLatestRunToJudge(judgeID)

	log.Printf("[INFO] judge_svc: run completed judge_id=%d run_id=%d total=%d completed=%d failed=%d passed=%d pass_rate=%.1f%%",
		judgeID, runID, totalCount, completed, failed, passed, passRate)
}

// resolveResponseFormat returns the system-controlled response format for a judge.
// For builtin scorers, it comes from the scorer's ResponseFormat field.
// For custom scorers, a default format is used to ensure parseable output.
func resolveResponseFormat(dto *types.JudgeDTO) string {
	if dto.ScorerType == types.ScorerTypeBuiltin && dto.ScorerName != "" {
		if scorer := GetBuiltinScorer(dto.ScorerName); scorer != nil && scorer.ResponseFormat != "" {
			return scorer.ResponseFormat
		}
	}
	// Default response format for custom scorers
	return `You MUST respond with a valid JSON object in the following format (no markdown, no extra text):
{"passed": true/false, "reason": "Brief explanation of your judgment"}`
}

// evaluateSingleLog calls the judge model for a single trace log entry.
func (s *judgeService) evaluateSingleLog(
	ctx context.Context, dto *types.JudgeDTO, runID uint64, entry types.TraceLogEntry, apiKey string,
) *types.JudgeResultDTO {
	start := time.Now()

	// Load expectation from annotation if available
	expectation := s.loadExpectation(dto.UserID, dto.TraceID, entry.ID)

	// Resolve system-controlled response format (not editable by user)
	responseFormat := resolveResponseFormat(dto)

	// Build judge prompt with template variable substitution + response format
	prompt := buildJudgePrompt(entry, dto.PromptTemplate, expectation, responseFormat)
	req := types.ChatCompletionRequest{
		Model: dto.JudgeModel,
		Messages: []types.ChatMessage{
			{Role: "system", Content: "You are an AI evaluation judge. You MUST respond with a valid JSON object: {\"passed\": true/false, \"reason\": \"...\"}. No markdown, no extra text."},
			{Role: "user", Content: prompt},
		},
	}

	callCtx, cancel := context.WithTimeout(ctx, 60*time.Second)
	defer cancel()

	resp, err := s.llmClient.ChatCompletion(callCtx, apiKey, req)
	duration := time.Since(start).Milliseconds()

	result := &types.JudgeResultDTO{
		RunID:      runID,
		JudgeID:    dto.ID,
		TraceLogID: entry.ID,
		RequestID:  entry.RequestID,
		DurationMs: duration,
		Success:    true,
	}

	if err != nil {
		result.Success = false
		result.ErrorMessage = err.Error()
		log.Printf("[ERROR] judge_svc: llm call failed judge_id=%d log_id=%d model=%s duration=%dms err=%v",
			dto.ID, entry.ID, dto.JudgeModel, duration, err)
	} else if len(resp.Choices) > 0 {
		result.RawOutput = resp.Choices[0].Message.Content
		result.Passed, result.Reason = parseJudgeOutput(resp.Choices[0].Message.Content)
	} else {
		result.Success = false
		result.ErrorMessage = "model returned empty response (no choices)"
		log.Printf("[WARN] judge_svc: empty response judge_id=%d log_id=%d model=%s", dto.ID, entry.ID, dto.JudgeModel)
	}

	_ = s.repo.CreateResult(result)
	return result
}

// loadExpectation fetches the human-annotated expectation for a trace log (if exists).
func (s *judgeService) loadExpectation(userID, traceID, logID uint64) string {
	annotation, err := s.annotationRepo.FindByLogID(userID, traceID, logID)
	if err != nil || annotation == nil || annotation.Expectation == nil {
		return "(no expected output provided)"
	}
	return annotation.Expectation.Content
}

// writeFeedbackToAnnotation writes the judge result as an AI feedback to the trace log annotation.
func (s *judgeService) writeFeedbackToAnnotation(dto *types.JudgeDTO, logID uint64, result *types.JudgeResultDTO) {
	feedback := types.FeedbackItem{
		Name:   dto.Name,
		Passed: result.Passed,
		Reason: result.Reason,
		Source: "ai_judge",
	}

	err := s.annotationRepo.AppendFeedback(dto.UserID, dto.TraceID, logID, dto.Name, []types.FeedbackItem{feedback})
	if err != nil {
		log.Printf("[ERROR] judge_svc: write feedback to annotation failed judge_id=%d log_id=%d err=%v",
			dto.ID, logID, err)
	}
}

// buildJudgePrompt constructs the evaluation prompt by replacing template variables
// and appending the system-controlled response format instruction.
//
// Supported variables: {{inputs}}, {{outputs}}, {{conversations}}, {{expectations}}
//
// The responseFormat is always appended at the end to ensure parseable JSON output,
// regardless of user edits to the prompt template.
// For streaming trace logs (IsStream=true), the outputs are merged from SSE chunks
// into a single non-stream chat.completion JSON to reduce token waste.
func buildJudgePrompt(entry types.TraceLogEntry, tmpl, expectation, responseFormat string) string {
	// Prepare outputs: merge SSE chunks for streaming responses
	outputs := entry.ResponseBody
	if entry.IsStream {
		outputs = mergeStreamChunks(outputs)
	}

	if tmpl == "" {
		return fmt.Sprintf("Evaluate the following LLM interaction:\n\nUser Query: %s\n\nModel Response:\n%s\n\n## Response Format\n%s",
			entry.UserQuery, outputs, responseFormat)
	}

	// Extract conversations from request_body (messages array in OpenAI format)
	conversations := extractConversations(entry.RequestBody)

	result := tmpl
	result = strings.ReplaceAll(result, "{{inputs}}", entry.RequestBody)
	result = strings.ReplaceAll(result, "{{outputs}}", outputs)
	result = strings.ReplaceAll(result, "{{conversations}}", conversations)
	result = strings.ReplaceAll(result, "{{expectations}}", expectation)

	// Append system-controlled response format (user cannot modify this part)
	result = result + "\n\n## Response Format\n" + responseFormat

	return result
}

// extractConversations extracts a readable conversation from the request body.
// Attempts to parse OpenAI-format messages array; falls back to raw body.
func extractConversations(requestBody string) string {
	var payload struct {
		Messages []struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		} `json:"messages"`
	}
	if err := json.Unmarshal([]byte(requestBody), &payload); err != nil || len(payload.Messages) == 0 {
		return requestBody // fallback to raw body
	}

	var sb strings.Builder
	for _, msg := range payload.Messages {
		fmt.Fprintf(&sb, "[%s]: %s\n", msg.Role, msg.Content)
	}
	return sb.String()
}

// judgeOutputJSON is the expected JSON format from the judge model.
type judgeOutputJSON struct {
	Passed bool   `json:"passed"`
	Reason string `json:"reason"`
}

// parseJudgeOutput extracts passed/reason from judge model output.
// Expects JSON format: {"passed": bool, "reason": "..."}
// Falls back to treating entire output as reason with passed=false if parsing fails.
func parseJudgeOutput(output string) (bool, string) {
	// Try direct JSON parse
	var result judgeOutputJSON
	if err := json.Unmarshal([]byte(output), &result); err == nil {
		return result.Passed, result.Reason
	}

	// Try extracting JSON from markdown code blocks
	cleaned := extractJSONFromMarkdown(output)
	if cleaned != output {
		if err := json.Unmarshal([]byte(cleaned), &result); err == nil {
			return result.Passed, result.Reason
		}
	}

	// Fallback: parsing failed, return raw output as reason
	log.Printf("[WARN] judge_svc: failed to parse judge output as JSON, using raw output")
	return false, output
}

// extractJSONFromMarkdown removes markdown code block wrappers if present.
func extractJSONFromMarkdown(s string) string {
	s = strings.TrimSpace(s)
	if strings.HasPrefix(s, "```json") {
		s = strings.TrimPrefix(s, "```json")
		s = strings.TrimSuffix(s, "```")
		return strings.TrimSpace(s)
	}
	if strings.HasPrefix(s, "```") {
		s = strings.TrimPrefix(s, "```")
		s = strings.TrimSuffix(s, "```")
		return strings.TrimSpace(s)
	}
	return s
}
