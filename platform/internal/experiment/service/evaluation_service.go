// Evaluation service: business logic for creating and executing dataset-based evaluations.
// Evaluation tasks asynchronously run model inference on each dataset item and compare results.
package service

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	"deeppool/platform/internal/experiment/repository"
	"deeppool/platform/internal/experiment/types"
)

// EvaluationService defines business operations for evaluation tasks.
type EvaluationService interface {
	CreateEvaluation(userID uint64, req types.CreateEvaluationRequest) (*types.EvaluationDTO, error)
	GetEvaluation(userID, evalID uint64) (*types.EvaluationDTO, error)
	ListEvaluations(userID uint64) ([]types.EvaluationDTO, error)
	RunEvaluation(userID, evalID uint64) error
	GetEvaluationResults(evalID uint64, page, pageSize int) ([]types.EvaluationResultDTO, int64, error)
	DeleteEvaluation(userID, evalID uint64) error
}

type evaluationService struct {
	repo        repository.EvaluationRepository
	datasetRepo repository.DatasetRepository
	llmClient   types.LLMClient
	workerPool  int
}

// NewEvaluationService creates an EvaluationService.
func NewEvaluationService(
	repo repository.EvaluationRepository,
	datasetRepo repository.DatasetRepository,
	llmClient types.LLMClient,
	workerPool int,
) EvaluationService {
	return &evaluationService{
		repo:        repo,
		datasetRepo: datasetRepo,
		llmClient:   llmClient,
		workerPool:  workerPool,
	}
}

func (s *evaluationService) CreateEvaluation(userID uint64, req types.CreateEvaluationRequest) (*types.EvaluationDTO, error) {
	if req.Name == "" {
		return nil, errors.New("name is required")
	}
	if req.DatasetID == 0 {
		return nil, errors.New("dataset_id is required")
	}
	if req.ModelName == "" {
		return nil, errors.New("model_name is required")
	}
	if req.APIKeyID == 0 {
		return nil, errors.New("apikey_id is required")
	}

	// Verify dataset exists and belongs to user
	ds, err := s.datasetRepo.FindByID(req.DatasetID)
	if err != nil || ds.UserID != userID {
		return nil, errors.New("dataset not found")
	}

	id, err := s.repo.Create(userID, req)
	if err != nil {
		return nil, err
	}
	return s.repo.FindByID(id)
}

func (s *evaluationService) GetEvaluation(userID, evalID uint64) (*types.EvaluationDTO, error) {
	dto, err := s.repo.FindByID(evalID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errors.New("evaluation not found")
		}
		return nil, err
	}
	if dto.UserID != userID {
		return nil, errors.New("evaluation not found")
	}
	return dto, nil
}

func (s *evaluationService) ListEvaluations(userID uint64) ([]types.EvaluationDTO, error) {
	return s.repo.FindByUserID(userID)
}

// RunEvaluation starts asynchronous evaluation execution.
func (s *evaluationService) RunEvaluation(userID, evalID uint64) error {
	dto, err := s.repo.FindByID(evalID)
	if err != nil {
		return errors.New("evaluation not found")
	}
	if dto.UserID != userID {
		return errors.New("evaluation not found")
	}
	if dto.Status == types.StatusRunning {
		return errors.New("evaluation is already running")
	}

	if err := s.repo.UpdateStatus(evalID, types.StatusRunning); err != nil {
		return err
	}

	go s.executeEvaluation(evalID, dto.DatasetID, dto.ModelName, dto.APIKeyID)
	return nil
}

func (s *evaluationService) GetEvaluationResults(evalID uint64, page, pageSize int) ([]types.EvaluationResultDTO, int64, error) {
	return s.repo.ListResults(evalID, page, pageSize)
}

func (s *evaluationService) DeleteEvaluation(userID, evalID uint64) error {
	err := s.repo.Delete(evalID, userID)
	if errors.Is(err, sql.ErrNoRows) {
		return errors.New("evaluation not found")
	}
	return err
}

// executeEvaluation runs the evaluation asynchronously with a worker pool.
func (s *evaluationService) executeEvaluation(evalID, datasetID uint64, model string, apiKeyID uint64) {
	// Load all dataset items (paginated read of all)
	allItems, total, err := s.datasetRepo.ListItems(datasetID, 1, 10000)
	if err != nil {
		log.Printf("[ERROR] eval_svc: load dataset items failed eval_id=%d err=%v", evalID, err)
		_ = s.repo.UpdateStatus(evalID, types.StatusFailed)
		return
	}

	if total == 0 {
		log.Printf("[INFO] eval_svc: empty dataset eval_id=%d dataset_id=%d", evalID, datasetID)
		_ = s.repo.UpdateStatus(evalID, types.StatusCompleted)
		return
	}

	log.Printf("[INFO] eval_svc: starting evaluation eval_id=%d items=%d", evalID, total)

	// TODO: Resolve actual API key value from apiKeyID
	apiKey := fmt.Sprintf("key-%d", apiKeyID)

	var mu sync.Mutex
	completed, failed := 0, 0
	var totalScore float64
	sem := make(chan struct{}, s.workerPool)

	var wg sync.WaitGroup
	for _, item := range allItems {
		wg.Add(1)
		sem <- struct{}{}
		go func(item types.DatasetItemDTO) {
			defer wg.Done()
			defer func() { <-sem }()

			result := s.evaluateSingleItem(evalID, item, model, apiKey)

			mu.Lock()
			if result.Success {
				completed++
				totalScore += result.Score
			} else {
				failed++
			}
			avgScore := float64(0)
			if completed > 0 {
				avgScore = totalScore / float64(completed)
			}
			_ = s.repo.UpdateProgress(evalID, completed, failed, avgScore)
			mu.Unlock()
		}(item)
	}
	wg.Wait()

	_ = s.repo.UpdateStatus(evalID, types.StatusCompleted)
	log.Printf("[INFO] eval_svc: completed eval_id=%d completed=%d failed=%d", evalID, completed, failed)
}

// evaluateSingleItem calls the model for a single dataset item.
func (s *evaluationService) evaluateSingleItem(
	evalID uint64, item types.DatasetItemDTO, model, apiKey string,
) *types.EvaluationResultDTO {
	start := time.Now()
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	req := types.ChatCompletionRequest{
		Model: model,
		Messages: []types.ChatMessage{
			{Role: "user", Content: item.Input},
		},
	}

	resp, err := s.llmClient.ChatCompletion(ctx, apiKey, req)
	duration := time.Since(start).Milliseconds()

	result := &types.EvaluationResultDTO{
		EvaluationID: evalID,
		ItemID:       item.ID,
		DurationMs:   duration,
		Success:      true,
	}

	if err != nil {
		result.Success = false
		result.ErrorMessage = err.Error()
	} else if len(resp.Choices) > 0 {
		result.ModelOutput = resp.Choices[0].Message.Content
		result.Score = computeScore(item.ExpectedOutput, result.ModelOutput)
	}

	_ = s.repo.CreateResult(result)
	return result
}

// computeScore computes a simple similarity score between expected and actual output.
// TODO: Implement more sophisticated scoring (exact match, semantic similarity, etc.)
func computeScore(expected, actual string) float64 {
	if expected == "" {
		return 5.0 // no expected output, neutral score
	}
	if expected == actual {
		return 10.0
	}
	return 5.0 // placeholder
}
