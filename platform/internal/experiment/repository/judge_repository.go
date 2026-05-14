// Judge data access layer: CRUD for experiment_judges, experiment_judge_runs,
// and experiment_judge_results tables.
package repository

import (
	"database/sql"
	"log"
	"time"

	"deeppool/platform/internal/experiment/types"
)

// JudgeRepository defines data access operations for judge tasks, runs, and results.
type JudgeRepository interface {
	// Judge CRUD
	Create(userID uint64, req types.CreateJudgeRequest) (uint64, error)
	FindByID(id uint64) (*types.JudgeDTO, error)
	FindByUserID(userID uint64) ([]types.JudgeDTO, error)
	Update(id uint64, req types.UpdateJudgeRequest) error
	Delete(id, userID uint64) error

	// Run lifecycle
	CreateRun(judgeID uint64) (uint64, error)
	FindRunByID(runID uint64) (*types.JudgeRunDTO, error)
	ListRuns(judgeID uint64) ([]types.JudgeRunDTO, error)
	UpdateRunStatus(runID uint64, status string) error
	UpdateRunProgress(runID uint64, completed, failed int) error
	UpdateRunTotalCount(runID uint64, total int) error
	UpdateRunPassRate(runID uint64, passRate float64) error

	// Results (scoped to run)
	CreateResult(result *types.JudgeResultDTO) error
	ListResultsByRun(runID uint64, page, pageSize int) ([]types.JudgeResultDTO, bool, error)

	// Sync latest run summary back to judge for quick display
	SyncLatestRunToJudge(judgeID uint64) error
}

type mysqlJudgeRepo struct {
	db *sql.DB
}

// NewMySQLJudgeRepository creates a MySQL-backed JudgeRepository.
func NewMySQLJudgeRepository(db *sql.DB) JudgeRepository {
	return &mysqlJudgeRepo{db: db}
}

// --- Judge CRUD ---

func (r *mysqlJudgeRepo) Create(userID uint64, req types.CreateJudgeRequest) (uint64, error) {
	res, err := r.db.Exec(`
		INSERT INTO experiment_judges
			(user_id, name, scope, scope_value, trace_id, judge_model, judge_apikey_id,
			 scorer_type, scorer_name, prompt_template, status, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, UTC_TIMESTAMP(), UTC_TIMESTAMP())
	`, userID, req.Name, req.Scope, req.ScopeValue, req.TraceID,
		req.JudgeModel, req.JudgeAPIKeyID,
		req.ScorerType, req.ScorerName, req.PromptTemplate, types.StatusPending)
	if err != nil {
		log.Printf("[ERROR] judge_repo: create failed uid=%d err=%v", userID, err)
		return 0, err
	}
	id, _ := res.LastInsertId()
	log.Printf("[INFO] judge created id=%d uid=%d name=%s scope=%s", id, userID, req.Name, req.Scope)
	return uint64(id), nil
}

// scanJudgeColumns defines the column list used by FindByID and FindByUserID.
const scanJudgeColumns = `id, user_id, name, scope, scope_value, trace_id,
	judge_model, judge_apikey_id, scorer_type, scorer_name, prompt_template,
	status, total_count, completed_count, failed_count, created_at, updated_at`

func scanJudgeRow(scanner interface{ Scan(...interface{}) error }) (*types.JudgeDTO, error) {
	var dto types.JudgeDTO
	err := scanner.Scan(
		&dto.ID, &dto.UserID, &dto.Name, &dto.Scope, &dto.ScopeValue, &dto.TraceID,
		&dto.JudgeModel, &dto.JudgeAPIKeyID, &dto.ScorerType, &dto.ScorerName,
		&dto.PromptTemplate, &dto.Status, &dto.TotalCount, &dto.CompletedCount,
		&dto.FailedCount, &dto.CreatedAt, &dto.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return &dto, nil
}

func (r *mysqlJudgeRepo) FindByID(id uint64) (*types.JudgeDTO, error) {
	row := r.db.QueryRow(`SELECT `+scanJudgeColumns+` FROM experiment_judges WHERE id = ?`, id)
	dto, err := scanJudgeRow(row)
	if err != nil {
		log.Printf("[ERROR] judge_repo: FindByID failed id=%d: %v", id, err)
	}
	return dto, err
}

func (r *mysqlJudgeRepo) FindByUserID(userID uint64) ([]types.JudgeDTO, error) {
	rows, err := r.db.Query(
		`SELECT `+scanJudgeColumns+` FROM experiment_judges WHERE user_id = ? ORDER BY created_at DESC`,
		userID,
	)
	if err != nil {
		log.Printf("[ERROR] judge_repo: FindByUserID query failed uid=%d: %v", userID, err)
		return nil, err
	}
	defer rows.Close()

	var results []types.JudgeDTO
	for rows.Next() {
		dto, err := scanJudgeRow(rows)
		if err != nil {
			log.Printf("[ERROR] judge_repo: FindByUserID scan failed uid=%d: %v", userID, err)
			return nil, err
		}
		results = append(results, *dto)
	}
	return results, nil
}

// Update applies partial updates to a judge configuration.
func (r *mysqlJudgeRepo) Update(id uint64, req types.UpdateJudgeRequest) error {
	// Build dynamic SET clause
	setClauses := []string{}
	args := []interface{}{}

	if req.Name != nil {
		setClauses = append(setClauses, "name = ?")
		args = append(args, *req.Name)
	}
	if req.Scope != nil {
		setClauses = append(setClauses, "scope = ?")
		args = append(args, *req.Scope)
	}
	if req.ScopeValue != nil {
		setClauses = append(setClauses, "scope_value = ?")
		args = append(args, *req.ScopeValue)
	}
	if req.TraceID != nil {
		setClauses = append(setClauses, "trace_id = ?")
		args = append(args, *req.TraceID)
	}
	if req.JudgeModel != nil {
		setClauses = append(setClauses, "judge_model = ?")
		args = append(args, *req.JudgeModel)
	}
	if req.JudgeAPIKeyID != nil {
		setClauses = append(setClauses, "judge_apikey_id = ?")
		args = append(args, *req.JudgeAPIKeyID)
	}
	if req.ScorerType != nil {
		setClauses = append(setClauses, "scorer_type = ?")
		args = append(args, *req.ScorerType)
	}
	if req.ScorerName != nil {
		setClauses = append(setClauses, "scorer_name = ?")
		args = append(args, *req.ScorerName)
	}
	if req.PromptTemplate != nil {
		setClauses = append(setClauses, "prompt_template = ?")
		args = append(args, *req.PromptTemplate)
	}

	if len(setClauses) == 0 {
		return nil // nothing to update
	}

	setClauses = append(setClauses, "updated_at = UTC_TIMESTAMP()")
	args = append(args, id)

	query := "UPDATE experiment_judges SET " + joinStrings(setClauses, ", ") + " WHERE id = ?"
	_, err := r.db.Exec(query, args...)
	if err != nil {
		log.Printf("[ERROR] judge_repo: Update failed id=%d: %v", id, err)
	}
	return err
}

func (r *mysqlJudgeRepo) Delete(id, userID uint64) error {
	res, err := r.db.Exec(`DELETE FROM experiment_judges WHERE id = ? AND user_id = ?`, id, userID)
	if err != nil {
		log.Printf("[ERROR] judge_repo: Delete failed id=%d uid=%d: %v", id, userID, err)
		return err
	}
	affected, _ := res.RowsAffected()
	if affected == 0 {
		return sql.ErrNoRows
	}
	log.Printf("[INFO] judge deleted id=%d uid=%d", id, userID)
	return nil
}

// --- Run lifecycle ---

func (r *mysqlJudgeRepo) CreateRun(judgeID uint64) (uint64, error) {
	res, err := r.db.Exec(`
		INSERT INTO experiment_judge_runs (judge_id, status, created_at, updated_at)
		VALUES (?, ?, UTC_TIMESTAMP(), UTC_TIMESTAMP())
	`, judgeID, types.StatusPending)
	if err != nil {
		log.Printf("[ERROR] judge_repo: CreateRun failed judge_id=%d: %v", judgeID, err)
		return 0, err
	}
	id, _ := res.LastInsertId()
	log.Printf("[INFO] judge run created run_id=%d judge_id=%d", id, judgeID)
	return uint64(id), nil
}

func (r *mysqlJudgeRepo) FindRunByID(runID uint64) (*types.JudgeRunDTO, error) {
	var dto types.JudgeRunDTO
	err := r.db.QueryRow(`
		SELECT id, judge_id, status, total_count, completed_count, failed_count, pass_rate, created_at, updated_at
		FROM experiment_judge_runs WHERE id = ?
	`, runID).Scan(
		&dto.ID, &dto.JudgeID, &dto.Status, &dto.TotalCount, &dto.CompletedCount,
		&dto.FailedCount, &dto.PassRate, &dto.CreatedAt, &dto.UpdatedAt,
	)
	if err != nil {
		log.Printf("[ERROR] judge_repo: FindRunByID failed run_id=%d: %v", runID, err)
		return nil, err
	}
	return &dto, nil
}

func (r *mysqlJudgeRepo) ListRuns(judgeID uint64) ([]types.JudgeRunDTO, error) {
	rows, err := r.db.Query(`
		SELECT id, judge_id, status, total_count, completed_count, failed_count, pass_rate, created_at, updated_at
		FROM experiment_judge_runs WHERE judge_id = ?
		ORDER BY created_at DESC
	`, judgeID)
	if err != nil {
		log.Printf("[ERROR] judge_repo: ListRuns failed judge_id=%d: %v", judgeID, err)
		return nil, err
	}
	defer rows.Close()

	var results []types.JudgeRunDTO
	for rows.Next() {
		var dto types.JudgeRunDTO
		if err := rows.Scan(
			&dto.ID, &dto.JudgeID, &dto.Status, &dto.TotalCount, &dto.CompletedCount,
			&dto.FailedCount, &dto.PassRate, &dto.CreatedAt, &dto.UpdatedAt,
		); err != nil {
			log.Printf("[ERROR] judge_repo: ListRuns scan failed judge_id=%d: %v", judgeID, err)
			return nil, err
		}
		results = append(results, dto)
	}
	return results, nil
}

func (r *mysqlJudgeRepo) UpdateRunStatus(runID uint64, status string) error {
	_, err := r.db.Exec(
		`UPDATE experiment_judge_runs SET status = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?`,
		status, runID,
	)
	if err != nil {
		log.Printf("[ERROR] judge_repo: UpdateRunStatus failed run_id=%d status=%s: %v", runID, status, err)
	}
	return err
}

func (r *mysqlJudgeRepo) UpdateRunProgress(runID uint64, completed, failed int) error {
	_, err := r.db.Exec(
		`UPDATE experiment_judge_runs SET completed_count = ?, failed_count = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?`,
		completed, failed, runID,
	)
	if err != nil {
		log.Printf("[ERROR] judge_repo: UpdateRunProgress failed run_id=%d: %v", runID, err)
	}
	return err
}

func (r *mysqlJudgeRepo) UpdateRunTotalCount(runID uint64, total int) error {
	_, err := r.db.Exec(
		`UPDATE experiment_judge_runs SET total_count = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?`,
		total, runID,
	)
	if err != nil {
		log.Printf("[ERROR] judge_repo: UpdateRunTotalCount failed run_id=%d: %v", runID, err)
	}
	return err
}

func (r *mysqlJudgeRepo) UpdateRunPassRate(runID uint64, passRate float64) error {
	_, err := r.db.Exec(
		`UPDATE experiment_judge_runs SET pass_rate = ?, updated_at = UTC_TIMESTAMP() WHERE id = ?`,
		passRate, runID,
	)
	if err != nil {
		log.Printf("[ERROR] judge_repo: UpdateRunPassRate failed run_id=%d: %v", runID, err)
	}
	return err
}

// --- Results ---

func (r *mysqlJudgeRepo) CreateResult(result *types.JudgeResultDTO) error {
	_, err := r.db.Exec(`
		INSERT INTO experiment_judge_results
			(run_id, judge_id, trace_log_id, request_id, passed, reason, raw_output,
			 duration_ms, success, error_message, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, result.RunID, result.JudgeID, result.TraceLogID, result.RequestID, result.Passed,
		result.Reason, result.RawOutput, result.DurationMs, result.Success,
		result.ErrorMessage, time.Now().UTC())
	if err != nil {
		log.Printf("[ERROR] judge_repo: CreateResult failed run_id=%d judge_id=%d log_id=%d: %v",
			result.RunID, result.JudgeID, result.TraceLogID, err)
	}
	return err
}

// ListResultsByRun returns paginated results for a specific run.
// Uses has_more pattern (fetches pageSize+1) to avoid COUNT(*) queries.
func (r *mysqlJudgeRepo) ListResultsByRun(runID uint64, page, pageSize int) ([]types.JudgeResultDTO, bool, error) {
	offset := (page - 1) * pageSize
	// Fetch one extra row to determine if more pages exist
	rows, err := r.db.Query(`
		SELECT id, run_id, judge_id, trace_log_id, request_id, passed, reason, raw_output,
			duration_ms, success, error_message, created_at
		FROM experiment_judge_results WHERE run_id = ?
		ORDER BY created_at DESC LIMIT ? OFFSET ?
	`, runID, pageSize+1, offset)
	if err != nil {
		log.Printf("[ERROR] judge_repo: ListResultsByRun query failed run_id=%d: %v", runID, err)
		return nil, false, err
	}
	defer rows.Close()

	var results []types.JudgeResultDTO
	for rows.Next() {
		var dto types.JudgeResultDTO
		if err := rows.Scan(
			&dto.ID, &dto.RunID, &dto.JudgeID, &dto.TraceLogID, &dto.RequestID, &dto.Passed,
			&dto.Reason, &dto.RawOutput, &dto.DurationMs, &dto.Success,
			&dto.ErrorMessage, &dto.CreatedAt,
		); err != nil {
			log.Printf("[ERROR] judge_repo: ListResultsByRun scan failed run_id=%d: %v", runID, err)
			return nil, false, err
		}
		results = append(results, dto)
	}

	// If we got more than pageSize rows, there are more pages
	hasMore := len(results) > pageSize
	if hasMore {
		results = results[:pageSize]
	}
	return results, hasMore, nil
}

// SyncLatestRunToJudge copies the latest run's status and counts to the parent judge row.
func (r *mysqlJudgeRepo) SyncLatestRunToJudge(judgeID uint64) error {
	_, err := r.db.Exec(`
		UPDATE experiment_judges j
		INNER JOIN (
			SELECT judge_id, status, total_count, completed_count, failed_count
			FROM experiment_judge_runs
			WHERE judge_id = ?
			ORDER BY created_at DESC
			LIMIT 1
		) latest ON j.id = latest.judge_id
		SET j.status = latest.status,
		    j.total_count = latest.total_count,
		    j.completed_count = latest.completed_count,
		    j.failed_count = latest.failed_count,
		    j.updated_at = UTC_TIMESTAMP()
	`, judgeID)
	if err != nil {
		log.Printf("[ERROR] judge_repo: SyncLatestRunToJudge failed judge_id=%d: %v", judgeID, err)
	}
	return err
}

// joinStrings joins a slice of strings with a separator (avoids importing strings package).
func joinStrings(items []string, sep string) string {
	if len(items) == 0 {
		return ""
	}
	result := items[0]
	for _, s := range items[1:] {
		result += sep + s
	}
	return result
}
