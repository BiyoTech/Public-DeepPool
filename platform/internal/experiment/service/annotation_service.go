// Annotation service: business logic for trace log annotations (feedback + expectation).
package service

import (
	"errors"

	"deeppool/platform/internal/experiment/repository"
	"deeppool/platform/internal/experiment/types"
)

// AnnotationService defines business operations for trace log annotations.
type AnnotationService interface {
	// GetAnnotation returns the annotation for a specific trace log. Returns nil if not found.
	GetAnnotation(userID, traceID, logID uint64) (*types.AnnotationDTO, error)
	// SaveAnnotation creates or updates the annotation for a trace log.
	SaveAnnotation(userID, traceID, logID uint64, req types.SaveAnnotationRequest) (*types.AnnotationDTO, error)
	// BatchGetSummaries returns lightweight annotation summaries for multiple log IDs.
	BatchGetSummaries(userID, traceID uint64, logIDs []uint64) (map[uint64]*types.AnnotationSummary, error)
}

type annotationService struct {
	repo repository.AnnotationRepository
}

// NewAnnotationService creates an AnnotationService.
func NewAnnotationService(repo repository.AnnotationRepository) AnnotationService {
	return &annotationService{repo: repo}
}

func (s *annotationService) GetAnnotation(userID, traceID, logID uint64) (*types.AnnotationDTO, error) {
	if traceID == 0 || logID == 0 {
		return nil, errors.New("trace_id and log_id are required")
	}
	return s.repo.FindByLogID(userID, traceID, logID)
}

func (s *annotationService) SaveAnnotation(userID, traceID, logID uint64, req types.SaveAnnotationRequest) (*types.AnnotationDTO, error) {
	if traceID == 0 || logID == 0 {
		return nil, errors.New("trace_id and log_id are required")
	}

	// Validate feedbacks
	for i, fb := range req.Feedbacks {
		if fb.Name == "" {
			return nil, errors.New("feedback name is required at index " + string(rune('0'+i)))
		}
		// Default source to "human" if not specified
		if fb.Source == "" {
			req.Feedbacks[i].Source = "human"
		}
	}

	// Validate expectation if provided
	if req.Expectation != nil {
		if req.Expectation.Name == "" {
			return nil, errors.New("expectation name is required")
		}
		validTypes := map[string]bool{"text": true, "number": true, "bool": true, "json": true}
		if !validTypes[req.Expectation.DataType] {
			return nil, errors.New("expectation data_type must be one of: text, number, bool, json")
		}
	}

	return s.repo.Upsert(userID, traceID, logID, req.Feedbacks, req.Expectation)
}

func (s *annotationService) BatchGetSummaries(userID, traceID uint64, logIDs []uint64) (map[uint64]*types.AnnotationSummary, error) {
	if traceID == 0 {
		return nil, errors.New("trace_id is required")
	}
	return s.repo.BatchGetSummaries(userID, traceID, logIDs)
}
