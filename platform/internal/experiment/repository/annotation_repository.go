// Annotation data access layer: Upsert and query for experiment_trace_annotations table.
// Each trace log has at most one annotation row containing feedbacks (JSON array) and expectation (JSON object).
package repository

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"deeppool/platform/internal/experiment/types"
)

// AnnotationRepository defines data access operations for trace log annotations.
type AnnotationRepository interface {
	// FindByLogID returns the annotation for a specific trace log. Returns nil if not found.
	FindByLogID(userID, traceID, logID uint64) (*types.AnnotationDTO, error)
	// Upsert creates or updates the annotation for a trace log.
	Upsert(userID, traceID, logID uint64, feedbacks []types.FeedbackItem, expectation *types.ExpectationItem) (*types.AnnotationDTO, error)
	// BatchGetSummaries returns lightweight annotation summaries for multiple log IDs.
	BatchGetSummaries(userID, traceID uint64, logIDs []uint64) (map[uint64]*types.AnnotationSummary, error)
	// AppendFeedback adds AI judge feedback to an annotation without overwriting human feedback.
	// It removes any existing feedback with source="ai_judge" and the given judgeName prefix, then appends new ones.
	AppendFeedback(userID, traceID, logID uint64, judgeName string, newFeedbacks []types.FeedbackItem) error
}

type mysqlAnnotationRepo struct {
	db *sql.DB
}

// NewMySQLAnnotationRepository creates a MySQL-backed AnnotationRepository.
func NewMySQLAnnotationRepository(db *sql.DB) AnnotationRepository {
	return &mysqlAnnotationRepo{db: db}
}

func (r *mysqlAnnotationRepo) FindByLogID(userID, traceID, logID uint64) (*types.AnnotationDTO, error) {
	var dto types.AnnotationDTO
	var feedbacksJSON, expectationJSON sql.NullString

	err := r.db.QueryRow(`
		SELECT id, user_id, trace_id, log_id, feedbacks, expectation, created_at, updated_at
		FROM experiment_trace_annotations
		WHERE user_id = ? AND trace_id = ? AND log_id = ?
	`, userID, traceID, logID).Scan(
		&dto.ID, &dto.UserID, &dto.TraceID, &dto.LogID,
		&feedbacksJSON, &expectationJSON, &dto.CreatedAt, &dto.UpdatedAt,
	)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}

	// Parse feedbacks JSON
	if feedbacksJSON.Valid && feedbacksJSON.String != "" {
		if err := json.Unmarshal([]byte(feedbacksJSON.String), &dto.Feedbacks); err != nil {
			log.Printf("[ERROR] annotation_repo: parse feedbacks json failed log_id=%d err=%v", logID, err)
		}
	}
	if dto.Feedbacks == nil {
		dto.Feedbacks = []types.FeedbackItem{}
	}

	// Parse expectation JSON
	if expectationJSON.Valid && expectationJSON.String != "" {
		var exp types.ExpectationItem
		if err := json.Unmarshal([]byte(expectationJSON.String), &exp); err != nil {
			log.Printf("[ERROR] annotation_repo: parse expectation json failed log_id=%d err=%v", logID, err)
		} else {
			dto.Expectation = &exp
		}
	}

	return &dto, nil
}

func (r *mysqlAnnotationRepo) Upsert(userID, traceID, logID uint64, feedbacks []types.FeedbackItem, expectation *types.ExpectationItem) (*types.AnnotationDTO, error) {
	// Marshal feedbacks to JSON
	feedbacksJSON, err := json.Marshal(feedbacks)
	if err != nil {
		return nil, err
	}

	// Marshal expectation to JSON (nullable)
	var expectationJSON sql.NullString
	if expectation != nil {
		b, err := json.Marshal(expectation)
		if err != nil {
			return nil, err
		}
		expectationJSON = sql.NullString{String: string(b), Valid: true}
	}

	now := time.Now().UTC()
	_, err = r.db.Exec(`
		INSERT INTO experiment_trace_annotations (user_id, trace_id, log_id, feedbacks, expectation, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE feedbacks = VALUES(feedbacks), expectation = VALUES(expectation), updated_at = VALUES(updated_at)
	`, userID, traceID, logID, string(feedbacksJSON), expectationJSON, now, now)
	if err != nil {
		log.Printf("[ERROR] annotation_repo: upsert failed uid=%d trace=%d log=%d err=%v", userID, traceID, logID, err)
		return nil, err
	}

	log.Printf("[INFO] annotation upserted uid=%d trace=%d log=%d feedbacks=%d has_expectation=%v",
		userID, traceID, logID, len(feedbacks), expectation != nil)

	// Return the saved annotation
	return r.FindByLogID(userID, traceID, logID)
}

func (r *mysqlAnnotationRepo) BatchGetSummaries(userID, traceID uint64, logIDs []uint64) (map[uint64]*types.AnnotationSummary, error) {
	result := make(map[uint64]*types.AnnotationSummary, len(logIDs))
	if len(logIDs) == 0 {
		return result, nil
	}

	// Build parameterized IN clause
	placeholders := make([]string, len(logIDs))
	args := make([]interface{}, 0, len(logIDs)+2)
	args = append(args, userID, traceID)
	for i, id := range logIDs {
		placeholders[i] = "?"
		args = append(args, id)
	}

	query := fmt.Sprintf(`
		SELECT log_id, feedbacks, expectation
		FROM experiment_trace_annotations
		WHERE user_id = ? AND trace_id = ? AND log_id IN (%s)
	`, strings.Join(placeholders, ","))

	rows, err := r.db.Query(query, args...)
	if err != nil {
		log.Printf("[ERROR] annotation_repo: batch get summaries failed trace=%d err=%v", traceID, err)
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var logID uint64
		var feedbacksJSON, expectationJSON sql.NullString
		if err := rows.Scan(&logID, &feedbacksJSON, &expectationJSON); err != nil {
			log.Printf("[ERROR] annotation_repo: scan summary row failed err=%v", err)
			continue
		}

		summary := &types.AnnotationSummary{LogID: logID}

		// Parse feedbacks to compute passed status
		if feedbacksJSON.Valid && feedbacksJSON.String != "" && feedbacksJSON.String != "[]" {
			var feedbacks []types.FeedbackItem
			if err := json.Unmarshal([]byte(feedbacksJSON.String), &feedbacks); err == nil && len(feedbacks) > 0 {
				summary.HasFeedback = true
				summary.FeedbackCount = len(feedbacks)
				summary.FeedbackPassed = true
				for _, fb := range feedbacks {
					if !fb.Passed {
						summary.FeedbackPassed = false
						break
					}
				}
			}
		}

		// Check expectation presence
		if expectationJSON.Valid && expectationJSON.String != "" && expectationJSON.String != "null" {
			summary.HasExpectation = true
		}

		result[logID] = summary
	}

	return result, nil
}

// AppendFeedback reads existing feedbacks, removes old AI judge entries with matching judgeName,
// appends new feedback items, and upserts back. Preserves human feedback and other judges' feedback.
func (r *mysqlAnnotationRepo) AppendFeedback(userID, traceID, logID uint64, judgeName string, newFeedbacks []types.FeedbackItem) error {
	// Read existing annotation
	existing, err := r.FindByLogID(userID, traceID, logID)

	var feedbacks []types.FeedbackItem
	if err == nil && existing != nil {
		// Keep feedbacks that are NOT from this judge (preserve human + other judges)
		for _, fb := range existing.Feedbacks {
			if fb.Source == "ai_judge" && fb.Name == judgeName {
				continue // remove old entries from this specific judge
			}
			feedbacks = append(feedbacks, fb)
		}
	}

	// Append new AI judge feedbacks
	feedbacks = append(feedbacks, newFeedbacks...)

	// Marshal and upsert
	feedbacksJSON, err := json.Marshal(feedbacks)
	if err != nil {
		return err
	}

	now := time.Now().UTC()

	// Determine expectation value — preserve existing if any
	var expectationJSON sql.NullString
	if existing != nil && existing.Expectation != nil {
		b, err := json.Marshal(existing.Expectation)
		if err == nil {
			expectationJSON = sql.NullString{String: string(b), Valid: true}
		}
	}

	_, err = r.db.Exec(`
		INSERT INTO experiment_trace_annotations (user_id, trace_id, log_id, feedbacks, expectation, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		ON DUPLICATE KEY UPDATE feedbacks = VALUES(feedbacks), updated_at = VALUES(updated_at)
	`, userID, traceID, logID, string(feedbacksJSON), expectationJSON, now, now)
	if err != nil {
		log.Printf("[ERROR] annotation_repo: append feedback failed uid=%d trace=%d log=%d err=%v", userID, traceID, logID, err)
		return err
	}

	log.Printf("[INFO] annotation feedback appended uid=%d trace=%d log=%d judge=%s count=%d",
		userID, traceID, logID, judgeName, len(newFeedbacks))
	return nil
}
