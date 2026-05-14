// Package types defines request/response DTOs, interfaces, and constants for the experiment module.
package types

import (
	"context"
	"time"
)

// --- Core interfaces (defined here to avoid import cycles between experiment root and sub-packages) ---

// AuthService validates user session tokens.
type AuthService interface {
	AuthUserID(authHeader string) (uint64, error)
}

// ChatMessage represents a single message in OpenAI chat format.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatCompletionRequest is the request payload for /v1/chat/completions.
type ChatCompletionRequest struct {
	Model    string        `json:"model"`
	Messages []ChatMessage `json:"messages"`
}

// ChatCompletionResponse is the simplified response from /v1/chat/completions.
type ChatCompletionResponse struct {
	ID      string `json:"id"`
	Model   string `json:"model"`
	Choices []struct {
		Message ChatMessage `json:"message"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		TotalTokens      int `json:"total_tokens"`
	} `json:"usage"`
}

// LLMClient interface for calling LLM models via Manager Gateway.
type LLMClient interface {
	ChatCompletion(ctx context.Context, apiKey string, req ChatCompletionRequest) (*ChatCompletionResponse, error)
}

// APIKeyResolver resolves a decrypted API key value from its ID and user ownership.
type APIKeyResolver interface {
	Resolve(userID, keyID uint64) (string, error)
}

// TraceLogEntry represents a single trace log record read from the external database.
type TraceLogEntry struct {
	ID               uint64 `json:"id"`
	RequestID        string `json:"request_id"`
	ModelName        string `json:"model_name"`
	UserQuery        string `json:"user_query"`
	RequestBody      string `json:"request_body"`
	ResponseBody     string `json:"response_body"`
	IsStream         bool   `json:"is_stream"`
	PromptTokens     int64  `json:"prompt_tokens"`
	CompletionTokens int64  `json:"completion_tokens"`
	TotalTokens      int64  `json:"total_tokens"`
	DurationMs       int64  `json:"duration_ms"`
	Success          bool   `json:"success"`
	ErrorMessage     string `json:"error_message"`
	CreatedAt        string `json:"created_at"`
}

// TraceReader reads trace logs from user's external database.
// Supports multi-granularity filtering via ReadLogsWithScope.
type TraceReader interface {
	ReadLogs(ctx context.Context, traceID, userID uint64) ([]TraceLogEntry, error)
	// ReadLogsWithScope reads trace logs filtered by scope criteria.
	// scope: "model" / "apikey" / "trace" / "trace_log"
	// scopeValue: the entity identifier (model name / apikey id / trace id / log id)
	// traceID: required for trace/trace_log scope to locate the external DB
	ReadLogsWithScope(ctx context.Context, userID, traceID uint64, scope, scopeValue string) ([]TraceLogEntry, error)
}

// --- Status constants ---

const (
	StatusPending   = "pending"
	StatusRunning   = "running"
	StatusCompleted = "completed"
	StatusFailed    = "failed"
)

// --- Judge scope constants ---

const (
	ScopeModel    = "model"
	ScopeAPIKey   = "apikey"
	ScopeTrace    = "trace"
	ScopeTraceLog = "trace_log"
)

// --- Scorer type constants ---

const (
	ScorerTypeBuiltin = "builtin"
	ScorerTypeCustom  = "custom"
)

// --- Paginated response ---

// PaginatedResponse wraps paginated list results.
type PaginatedResponse struct {
	Total int64       `json:"total"`
	Items interface{} `json:"items"`
}

// --- Judge types ---

// CreateJudgeRequest is the request body for creating a judge task.
type CreateJudgeRequest struct {
	Name           string `json:"name"`
	Scope          string `json:"scope"`           // model / apikey / trace / trace_log
	ScopeValue     string `json:"scope_value"`     // entity identifier for the chosen scope
	TraceID        uint64 `json:"trace_id"`        // required for trace/trace_log scope
	JudgeModel     string `json:"judge_model"`
	JudgeAPIKeyID  uint64 `json:"judge_apikey_id"`
	ScorerType     string `json:"scorer_type"`     // builtin / custom
	ScorerName     string `json:"scorer_name"`     // builtin scorer name (empty for custom)
	PromptTemplate string `json:"prompt_template"` // final prompt with {{var}} placeholders
}

// UpdateJudgeRequest is the request body for updating a judge task config.
type UpdateJudgeRequest struct {
	Name           *string `json:"name,omitempty"`
	Scope          *string `json:"scope,omitempty"`
	ScopeValue     *string `json:"scope_value,omitempty"`
	TraceID        *uint64 `json:"trace_id,omitempty"`
	JudgeModel     *string `json:"judge_model,omitempty"`
	JudgeAPIKeyID  *uint64 `json:"judge_apikey_id,omitempty"`
	ScorerType     *string `json:"scorer_type,omitempty"`
	ScorerName     *string `json:"scorer_name,omitempty"`
	PromptTemplate *string `json:"prompt_template,omitempty"`
}

// JudgeDTO represents a judge task returned to the frontend.
// Status/counts reflect the latest run for quick display.
type JudgeDTO struct {
	ID             uint64    `json:"id"`
	UserID         uint64    `json:"user_id"`
	Name           string    `json:"name"`
	Scope          string    `json:"scope"`
	ScopeValue     string    `json:"scope_value"`
	TraceID        uint64    `json:"trace_id"`
	JudgeModel     string    `json:"judge_model"`
	JudgeAPIKeyID  uint64    `json:"judge_apikey_id"`
	ScorerType     string    `json:"scorer_type"`
	ScorerName     string    `json:"scorer_name"`
	PromptTemplate string    `json:"prompt_template"`
	Status         string    `json:"status"`
	TotalCount     int       `json:"total_count"`
	CompletedCount int       `json:"completed_count"`
	FailedCount    int       `json:"failed_count"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// JudgeRunDTO represents a single execution run of a judge task.
type JudgeRunDTO struct {
	ID             uint64    `json:"id"`
	JudgeID        uint64    `json:"judge_id"`
	Status         string    `json:"status"`
	TotalCount     int       `json:"total_count"`
	CompletedCount int       `json:"completed_count"`
	FailedCount    int       `json:"failed_count"`
	PassRate       float64   `json:"pass_rate"` // passed / successful_count * 100
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// JudgeResultDTO represents a single judge evaluation result.
type JudgeResultDTO struct {
	ID           uint64    `json:"id"`
	RunID        uint64    `json:"run_id"`
	JudgeID      uint64    `json:"judge_id"`
	TraceLogID   uint64    `json:"trace_log_id"`
	RequestID    string    `json:"request_id"`
	Passed       bool      `json:"passed"`
	Reason       string    `json:"reason"`
	RawOutput    string    `json:"raw_output"`
	DurationMs   int64     `json:"duration_ms"`
	Success      bool      `json:"success"`
	ErrorMessage string    `json:"error_message"`
	CreatedAt    time.Time `json:"created_at"`
}

// --- Dataset types ---

// CreateDatasetRequest is the request body for creating a dataset.
type CreateDatasetRequest struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}

// UpdateDatasetRequest is the request body for updating a dataset.
type UpdateDatasetRequest struct {
	Name        *string `json:"name"`
	Description *string `json:"description"`
}

// DatasetDTO represents a dataset returned to the frontend.
type DatasetDTO struct {
	ID          uint64    `json:"id"`
	UserID      uint64    `json:"user_id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	ItemCount   int       `json:"item_count"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// AddDatasetItemRequest is the request body for adding a single item to a dataset.
type AddDatasetItemRequest struct {
	Input          string      `json:"input"`
	ExpectedOutput string      `json:"expected_output"`
	Metadata       interface{} `json:"metadata"` // arbitrary JSON metadata
}

// AddDatasetItemsRequest is the request body for batch adding items.
type AddDatasetItemsRequest struct {
	Items []AddDatasetItemRequest `json:"items"`
}

// DatasetItemDTO represents a single dataset item.
type DatasetItemDTO struct {
	ID             uint64    `json:"id"`
	DatasetID      uint64    `json:"dataset_id"`
	Input          string    `json:"input"`
	ExpectedOutput string    `json:"expected_output"`
	Metadata       string    `json:"metadata"` // JSON string
	CreatedAt      time.Time `json:"created_at"`
}

// ImportDatasetRequest is the request body for importing items from JSON/CSV.
type ImportDatasetRequest struct {
	Format string `json:"format"` // "json" or "csv"
	Data   string `json:"data"`   // raw content
}

// --- Evaluation types ---

// CreateEvaluationRequest is the request body for creating an evaluation task.
type CreateEvaluationRequest struct {
	Name      string `json:"name"`
	DatasetID uint64 `json:"dataset_id"`
	ModelName string `json:"model_name"`
	APIKeyID  uint64 `json:"apikey_id"`
}

// EvaluationDTO represents an evaluation task returned to the frontend.
type EvaluationDTO struct {
	ID             uint64    `json:"id"`
	UserID         uint64    `json:"user_id"`
	Name           string    `json:"name"`
	DatasetID      uint64    `json:"dataset_id"`
	ModelName      string    `json:"model_name"`
	APIKeyID       uint64    `json:"apikey_id"`
	Status         string    `json:"status"`
	TotalCount     int       `json:"total_count"`
	CompletedCount int       `json:"completed_count"`
	FailedCount    int       `json:"failed_count"`
	AvgScore       float64   `json:"avg_score"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// EvaluationResultDTO represents a single evaluation result per dataset item.
type EvaluationResultDTO struct {
	ID           uint64    `json:"id"`
	EvaluationID uint64    `json:"evaluation_id"`
	ItemID       uint64    `json:"item_id"`
	ModelOutput  string    `json:"model_output"`
	Score        float64   `json:"score"`
	DurationMs   int64     `json:"duration_ms"`
	Success      bool      `json:"success"`
	ErrorMessage string    `json:"error_message"`
	CreatedAt    time.Time `json:"created_at"`
}

// --- Trace Log Annotation types (feedback + expectation) ---

// FeedbackItem represents a single feedback entry on a trace log.
// Source indicates the origin: "human" for manual annotation, "ai_judge" for automated evaluation.
type FeedbackItem struct {
	Name   string `json:"name"`
	Passed bool   `json:"passed"`
	Reason string `json:"reason"`
	Source string `json:"source"` // "human" or "ai_judge"
}

// ExpectationItem represents the expected output for a trace log.
type ExpectationItem struct {
	Name     string `json:"name"`
	DataType string `json:"data_type"` // text / number / bool / json
	Content  string `json:"content"`
	Reason   string `json:"reason"`
}

// AnnotationDTO represents the annotation (feedbacks + expectation) for a trace log.
type AnnotationDTO struct {
	ID          uint64          `json:"id"`
	UserID      uint64          `json:"user_id"`
	TraceID     uint64          `json:"trace_id"`
	LogID       uint64          `json:"log_id"`
	Feedbacks   []FeedbackItem  `json:"feedbacks"`
	Expectation *ExpectationItem `json:"expectation"`
	CreatedAt   time.Time       `json:"created_at"`
	UpdatedAt   time.Time       `json:"updated_at"`
}

// SaveAnnotationRequest is the request body for creating/updating an annotation.
type SaveAnnotationRequest struct {
	Feedbacks   []FeedbackItem  `json:"feedbacks"`
	Expectation *ExpectationItem `json:"expectation"`
}

// AnnotationSummary is a lightweight summary of annotation for list views.
type AnnotationSummary struct {
	LogID          uint64 `json:"log_id"`
	HasFeedback    bool   `json:"has_feedback"`
	FeedbackPassed bool   `json:"feedback_passed"` // true only if all feedbacks passed
	FeedbackCount  int    `json:"feedback_count"`
	HasExpectation bool   `json:"has_expectation"`
}

// --- Query parameters ---

// PageQuery holds common pagination parameters.
type PageQuery struct {
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
}

// NormalizePageQuery ensures page/pageSize are within valid ranges.
func (q *PageQuery) Normalize() {
	if q.Page < 1 {
		q.Page = 1
	}
	if q.PageSize < 1 || q.PageSize > 100 {
		q.PageSize = 20
	}
}
