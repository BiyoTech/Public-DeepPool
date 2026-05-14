// Evaluation data access layer: CRUD for experiment_evaluations and experiment_evaluation_results tables.
package repository

import (
	"database/sql"
	"log"
	"time"

	"deeppool/platform/internal/experiment/types"
)

// EvaluationRepository defines data access operations for evaluation tasks and results.
type EvaluationRepository interface {
	Create(userID uint64, req types.CreateEvaluationRequest) (uint64, error)
	FindByID(id uint64) (*types.EvaluationDTO, error)
	FindByUserID(userID uint64) ([]types.EvaluationDTO, error)
	UpdateStatus(id uint64, status string) error
	UpdateProgress(id uint64, completed, failed int, avgScore float64) error
	Delete(id, userID uint64) error

	// Results
	CreateResult(result *types.EvaluationResultDTO) error
	ListResults(evalID uint64, page, pageSize int) ([]types.EvaluationResultDTO, int64, error)
}

type mysqlEvalRepo struct {
	db *sql.DB
}

// NewMySQLEvaluationRepository creates a MySQL-backed EvaluationRepository.
func NewMySQLEvaluationRepository(db *sql.DB) EvaluationRepository {
	return &mysqlEvalRepo{db: db}
}

func (r *mysqlEvalRepo) Create(userID uint64, req types.CreateEvaluationRequest) (uint64, error) {
	res, err := r.db.Exec(`
		INSERT INTO experiment_evaluations (user_id, name, dataset_id, model_name, apikey_id, status, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, UTC_TIMESTAMP(), UTC_TIMESTAMP())
	`, userID, req.Name, req.DatasetID, req.ModelName, req.APIKeyID, types.StatusPending)
	if err != nil {
		log.Printf("[ERROR] eval_repo: create failed uid=%d err=%v", userID, err)
		return 0, err
	}
	id, _ := res.LastInsertId()
	log.Printf("[INFO] evaluation created id=%d uid=%d name=%s", id, userID, req.Name)
	return uint64(id), nil
}

func (r *mysqlEvalRepo) FindByID(id uint64) (*types.EvaluationDTO, error) {
	var dto types.EvaluationDTO
	err := r.db.QueryRow(`
		SELECT id, user_id, name, dataset_id, model_name, apikey_id,
			status, total_count, completed_count, failed_count, avg_score, created_at, updated_at
		FROM experiment_evaluations WHERE id = ?
	`, id).Scan(
		&dto.ID, &dto.UserID, &dto.Name, &dto.DatasetID, &dto.ModelName, &dto.APIKeyID,
		&dto.Status, &dto.TotalCount, &dto.CompletedCount, &dto.FailedCount,
		&dto.AvgScore, &dto.CreatedAt, &dto.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return &dto, nil
}

func (r *mysqlEvalRepo) FindByUserID(userID uint64) ([]types.EvaluationDTO, error) {
	rows, err := r.db.Query(`
		SELECT id, user_id, name, dataset_id, model_name, apikey_id,
			status, total_count, completed_count, failed_count, avg_score, created_at, updated_at
		FROM experiment_evaluations WHERE user_id = ? ORDER BY created_at DESC
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var results []types.EvaluationDTO
	for rows.Next() {
		var dto types.EvaluationDTO
		if err := rows.Scan(
			&dto.ID, &dto.UserID, &dto.Name, &dto.DatasetID, &dto.ModelName, &dto.APIKeyID,
			&dto.Status, &dto.TotalCount, &dto.CompletedCount, &dto.FailedCount,
			&dto.AvgScore, &dto.CreatedAt, &dto.UpdatedAt,
		); err != nil {
			return nil, err
		}
		results = append(results, dto)
	}
	return results, nil
}

func (r *mysqlEvalRepo) UpdateStatus(id uint64, status string) error {
	_, err := r.db.Exec(`
		UPDATE experiment_evaluations SET status = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?
	`, status, id)
	return err
}

func (r *mysqlEvalRepo) UpdateProgress(id uint64, completed, failed int, avgScore float64) error {
	_, err := r.db.Exec(`
		UPDATE experiment_evaluations SET completed_count = ?, failed_count = ?, avg_score = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?
	`, completed, failed, avgScore, id)
	return err
}

func (r *mysqlEvalRepo) Delete(id, userID uint64) error {
	res, err := r.db.Exec(`DELETE FROM experiment_evaluations WHERE id = ? AND user_id = ?`, id, userID)
	if err != nil {
		return err
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		return sql.ErrNoRows
	}
	log.Printf("[INFO] evaluation deleted id=%d uid=%d", id, userID)
	return nil
}

func (r *mysqlEvalRepo) CreateResult(result *types.EvaluationResultDTO) error {
	_, err := r.db.Exec(`
		INSERT INTO experiment_evaluation_results
			(evaluation_id, item_id, model_output, score, duration_ms, success, error_message, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`, result.EvaluationID, result.ItemID, result.ModelOutput, result.Score,
		result.DurationMs, result.Success, result.ErrorMessage, time.Now().UTC())
	return err
}

func (r *mysqlEvalRepo) ListResults(evalID uint64, page, pageSize int) ([]types.EvaluationResultDTO, int64, error) {
	var total int64
	if err := r.db.QueryRow(`SELECT COUNT(*) FROM experiment_evaluation_results WHERE evaluation_id = ?`, evalID).Scan(&total); err != nil {
		return nil, 0, err
	}

	offset := (page - 1) * pageSize
	rows, err := r.db.Query(`
		SELECT id, evaluation_id, item_id, model_output, score, duration_ms, success, error_message, created_at
		FROM experiment_evaluation_results WHERE evaluation_id = ?
		ORDER BY created_at DESC LIMIT ? OFFSET ?
	`, evalID, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var results []types.EvaluationResultDTO
	for rows.Next() {
		var dto types.EvaluationResultDTO
		if err := rows.Scan(
			&dto.ID, &dto.EvaluationID, &dto.ItemID, &dto.ModelOutput, &dto.Score,
			&dto.DurationMs, &dto.Success, &dto.ErrorMessage, &dto.CreatedAt,
		); err != nil {
			return nil, 0, err
		}
		results = append(results, dto)
	}
	return results, total, nil
}
