// Dataset service: business logic for managing evaluation datasets and their items.
package service

import (
	"database/sql"
	"errors"
	"strings"

	"deeppool/platform/internal/experiment/repository"
	"deeppool/platform/internal/experiment/types"
)

// DatasetService defines business operations for datasets.
type DatasetService interface {
	CreateDataset(userID uint64, req types.CreateDatasetRequest) (*types.DatasetDTO, error)
	GetDataset(userID, datasetID uint64) (*types.DatasetDTO, error)
	ListDatasets(userID uint64) ([]types.DatasetDTO, error)
	UpdateDataset(userID, datasetID uint64, req types.UpdateDatasetRequest) error
	DeleteDataset(userID, datasetID uint64) error

	AddItems(userID, datasetID uint64, items []types.AddDatasetItemRequest) error
	RemoveItem(userID, datasetID, itemID uint64) error
	ListItems(datasetID uint64, page, pageSize int) ([]types.DatasetItemDTO, int64, error)
}

type datasetService struct {
	repo repository.DatasetRepository
}

// NewDatasetService creates a DatasetService.
func NewDatasetService(repo repository.DatasetRepository) DatasetService {
	return &datasetService{repo: repo}
}

func (s *datasetService) CreateDataset(userID uint64, req types.CreateDatasetRequest) (*types.DatasetDTO, error) {
	name := strings.TrimSpace(req.Name)
	if name == "" {
		return nil, errors.New("name is required")
	}
	req.Name = name

	id, err := s.repo.Create(userID, req)
	if err != nil {
		return nil, err
	}
	return s.repo.FindByID(id)
}

func (s *datasetService) GetDataset(userID, datasetID uint64) (*types.DatasetDTO, error) {
	dto, err := s.repo.FindByID(datasetID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errors.New("dataset not found")
		}
		return nil, err
	}
	if dto.UserID != userID {
		return nil, errors.New("dataset not found")
	}
	return dto, nil
}

func (s *datasetService) ListDatasets(userID uint64) ([]types.DatasetDTO, error) {
	return s.repo.FindByUserID(userID)
}

func (s *datasetService) UpdateDataset(userID, datasetID uint64, req types.UpdateDatasetRequest) error {
	err := s.repo.Update(datasetID, userID, req)
	if errors.Is(err, sql.ErrNoRows) {
		return errors.New("dataset not found")
	}
	return err
}

func (s *datasetService) DeleteDataset(userID, datasetID uint64) error {
	err := s.repo.Delete(datasetID, userID)
	if errors.Is(err, sql.ErrNoRows) {
		return errors.New("dataset not found")
	}
	return err
}

func (s *datasetService) AddItems(userID, datasetID uint64, items []types.AddDatasetItemRequest) error {
	// Verify ownership
	dto, err := s.repo.FindByID(datasetID)
	if err != nil {
		return errors.New("dataset not found")
	}
	if dto.UserID != userID {
		return errors.New("dataset not found")
	}

	// Validate items
	for i, item := range items {
		if strings.TrimSpace(item.Input) == "" {
			return errors.New("item input cannot be empty at index " + strings.TrimSpace(string(rune('0'+i))))
		}
	}

	if len(items) == 1 {
		_, err = s.repo.AddItem(datasetID, items[0])
	} else {
		err = s.repo.AddItems(datasetID, items)
	}
	if err != nil {
		return err
	}

	// Update cached item count
	return s.repo.UpdateItemCount(datasetID)
}

func (s *datasetService) RemoveItem(userID, datasetID, itemID uint64) error {
	// Verify ownership
	dto, err := s.repo.FindByID(datasetID)
	if err != nil {
		return errors.New("dataset not found")
	}
	if dto.UserID != userID {
		return errors.New("dataset not found")
	}

	if err := s.repo.RemoveItem(datasetID, itemID); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return errors.New("item not found")
		}
		return err
	}
	return s.repo.UpdateItemCount(datasetID)
}

func (s *datasetService) ListItems(datasetID uint64, page, pageSize int) ([]types.DatasetItemDTO, int64, error) {
	return s.repo.ListItems(datasetID, page, pageSize)
}
