// Dataset data access layer: CRUD for experiment_datasets and experiment_dataset_items tables.
package repository

import (
	"database/sql"
	"encoding/json"
	"log"

	"deeppool/platform/internal/experiment/types"
)

// DatasetRepository defines data access operations for datasets and items.
type DatasetRepository interface {
	Create(userID uint64, req types.CreateDatasetRequest) (uint64, error)
	FindByID(id uint64) (*types.DatasetDTO, error)
	FindByUserID(userID uint64) ([]types.DatasetDTO, error)
	Update(id, userID uint64, req types.UpdateDatasetRequest) error
	Delete(id, userID uint64) error
	UpdateItemCount(id uint64) error

	// Items
	AddItem(datasetID uint64, req types.AddDatasetItemRequest) (uint64, error)
	AddItems(datasetID uint64, items []types.AddDatasetItemRequest) error
	RemoveItem(datasetID, itemID uint64) error
	ListItems(datasetID uint64, page, pageSize int) ([]types.DatasetItemDTO, int64, error)
	CountItems(datasetID uint64) (int64, error)
}

type mysqlDatasetRepo struct {
	db *sql.DB
}

// NewMySQLDatasetRepository creates a MySQL-backed DatasetRepository.
func NewMySQLDatasetRepository(db *sql.DB) DatasetRepository {
	return &mysqlDatasetRepo{db: db}
}

func (r *mysqlDatasetRepo) Create(userID uint64, req types.CreateDatasetRequest) (uint64, error) {
	res, err := r.db.Exec(`
		INSERT INTO experiment_datasets (user_id, name, description, item_count, created_at, updated_at)
		VALUES (?, ?, ?, 0, UTC_TIMESTAMP(), UTC_TIMESTAMP())
	`, userID, req.Name, req.Description)
	if err != nil {
		log.Printf("[ERROR] dataset_repo: create failed uid=%d err=%v", userID, err)
		return 0, err
	}
	id, _ := res.LastInsertId()
	log.Printf("[INFO] dataset created id=%d uid=%d name=%s", id, userID, req.Name)
	return uint64(id), nil
}

func (r *mysqlDatasetRepo) FindByID(id uint64) (*types.DatasetDTO, error) {
	var dto types.DatasetDTO
	err := r.db.QueryRow(`
		SELECT id, user_id, name, description, item_count, created_at, updated_at
		FROM experiment_datasets WHERE id = ?
	`, id).Scan(&dto.ID, &dto.UserID, &dto.Name, &dto.Description, &dto.ItemCount, &dto.CreatedAt, &dto.UpdatedAt)
	if err != nil {
		return nil, err
	}
	return &dto, nil
}

func (r *mysqlDatasetRepo) FindByUserID(userID uint64) ([]types.DatasetDTO, error) {
	rows, err := r.db.Query(`
		SELECT id, user_id, name, description, item_count, created_at, updated_at
		FROM experiment_datasets WHERE user_id = ? ORDER BY created_at DESC
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []types.DatasetDTO
	for rows.Next() {
		var dto types.DatasetDTO
		if err := rows.Scan(&dto.ID, &dto.UserID, &dto.Name, &dto.Description, &dto.ItemCount, &dto.CreatedAt, &dto.UpdatedAt); err != nil {
			return nil, err
		}
		results = append(results, dto)
	}
	return results, nil
}

func (r *mysqlDatasetRepo) Update(id, userID uint64, req types.UpdateDatasetRequest) error {
	fields := ""
	args := make([]interface{}, 0, 3)
	if req.Name != nil {
		fields += "name = ?, "
		args = append(args, *req.Name)
	}
	if req.Description != nil {
		fields += "description = ?, "
		args = append(args, *req.Description)
	}
	if fields == "" {
		return nil
	}
	fields += "updated_at = UTC_TIMESTAMP()"
	args = append(args, id, userID)

	res, err := r.db.Exec("UPDATE experiment_datasets SET "+fields+" WHERE id = ? AND user_id = ?", args...)
	if err != nil {
		return err
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

func (r *mysqlDatasetRepo) Delete(id, userID uint64) error {
	res, err := r.db.Exec(`DELETE FROM experiment_datasets WHERE id = ? AND user_id = ?`, id, userID)
	if err != nil {
		return err
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		return sql.ErrNoRows
	}
	log.Printf("[INFO] dataset deleted id=%d uid=%d", id, userID)
	return nil
}

func (r *mysqlDatasetRepo) UpdateItemCount(id uint64) error {
	_, err := r.db.Exec(`
		UPDATE experiment_datasets SET item_count = (
			SELECT COUNT(*) FROM experiment_dataset_items WHERE dataset_id = ?
		), updated_at = UTC_TIMESTAMP() WHERE id = ?
	`, id, id)
	return err
}

func (r *mysqlDatasetRepo) AddItem(datasetID uint64, req types.AddDatasetItemRequest) (uint64, error) {
	metaJSON := "null"
	if req.Metadata != nil {
		if b, err := json.Marshal(req.Metadata); err == nil {
			metaJSON = string(b)
		}
	}

	res, err := r.db.Exec(`
		INSERT INTO experiment_dataset_items (dataset_id, input, expected_output, metadata, created_at)
		VALUES (?, ?, ?, ?, UTC_TIMESTAMP())
	`, datasetID, req.Input, req.ExpectedOutput, metaJSON)
	if err != nil {
		return 0, err
	}
	id, _ := res.LastInsertId()
	return uint64(id), nil
}

func (r *mysqlDatasetRepo) AddItems(datasetID uint64, items []types.AddDatasetItemRequest) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare(`
		INSERT INTO experiment_dataset_items (dataset_id, input, expected_output, metadata, created_at)
		VALUES (?, ?, ?, ?, UTC_TIMESTAMP())
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	for _, item := range items {
		metaJSON := "null"
		if item.Metadata != nil {
			if b, err := json.Marshal(item.Metadata); err == nil {
				metaJSON = string(b)
			}
		}
		if _, err := stmt.Exec(datasetID, item.Input, item.ExpectedOutput, metaJSON); err != nil {
			return err
		}
	}
	return tx.Commit()
}

func (r *mysqlDatasetRepo) RemoveItem(datasetID, itemID uint64) error {
	res, err := r.db.Exec(`DELETE FROM experiment_dataset_items WHERE id = ? AND dataset_id = ?`, itemID, datasetID)
	if err != nil {
		return err
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		return sql.ErrNoRows
	}
	return nil
}

func (r *mysqlDatasetRepo) ListItems(datasetID uint64, page, pageSize int) ([]types.DatasetItemDTO, int64, error) {
	var total int64
	if err := r.db.QueryRow(`SELECT COUNT(*) FROM experiment_dataset_items WHERE dataset_id = ?`, datasetID).Scan(&total); err != nil {
		return nil, 0, err
	}

	offset := (page - 1) * pageSize
	rows, err := r.db.Query(`
		SELECT id, dataset_id, input, expected_output, COALESCE(metadata, 'null'), created_at
		FROM experiment_dataset_items WHERE dataset_id = ?
		ORDER BY id ASC LIMIT ? OFFSET ?
	`, datasetID, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var results []types.DatasetItemDTO
	for rows.Next() {
		var dto types.DatasetItemDTO
		if err := rows.Scan(&dto.ID, &dto.DatasetID, &dto.Input, &dto.ExpectedOutput, &dto.Metadata, &dto.CreatedAt); err != nil {
			return nil, 0, err
		}
		results = append(results, dto)
	}
	return results, total, nil
}

func (r *mysqlDatasetRepo) CountItems(datasetID uint64) (int64, error) {
	var count int64
	err := r.db.QueryRow(`SELECT COUNT(*) FROM experiment_dataset_items WHERE dataset_id = ?`, datasetID).Scan(&count)
	return count, err
}
