// TraceReader reads trace logs from user's external databases.
// Used by JudgeService to fetch the trace log entries that need evaluation.
package experiment

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/experiment/types"

	// MySQL driver for external DB connections
	_ "github.com/go-sql-driver/mysql"
)

type traceReader struct {
	db            *sql.DB // shared platform DB (for reading trace_configs)
	encryptionKey []byte  // AES-256 key for decrypting DSN
}

// NewTraceReader creates a TraceReader that reads trace configs from the platform DB
// and connects to user's external databases to read trace logs.
func NewTraceReader(db *sql.DB, encryptionKey []byte) types.TraceReader {
	return &traceReader{db: db, encryptionKey: encryptionKey}
}

func (r *traceReader) ReadLogs(ctx context.Context, traceID, userID uint64) ([]types.TraceLogEntry, error) {
	// Load trace config and verify ownership
	var dbType, dsnEncrypted string
	var ownerID uint64
	err := r.db.QueryRowContext(ctx, `
		SELECT user_id, db_type, dsn_encrypted FROM trace_configs WHERE id = ?
	`, traceID).Scan(&ownerID, &dbType, &dsnEncrypted)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, fmt.Errorf("trace config not found: id=%d", traceID)
		}
		return nil, fmt.Errorf("query trace config: %w", err)
	}
	if ownerID != userID {
		return nil, fmt.Errorf("trace config not found: id=%d", traceID) // ownership check
	}

	// Decrypt DSN
	dsn, err := common.DecryptAESGCM(dsnEncrypted, r.encryptionKey)
	if err != nil {
		return nil, fmt.Errorf("decrypt dsn: %w", err)
	}

	// Open external database connection
	driverName := driverForDBType(dbType)
	extDB, err := sql.Open(driverName, dsn)
	if err != nil {
		return nil, fmt.Errorf("open external db: %w", err)
	}
	defer extDB.Close()
	extDB.SetMaxOpenConns(3)
	extDB.SetConnMaxLifetime(30 * time.Second)

	// Query with timeout
	queryCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	rows, err := extDB.QueryContext(queryCtx, `
		SELECT id, request_id, model_name, user_query, request_body, response_body,
			is_stream, prompt_tokens, completion_tokens, total_tokens,
			duration_ms, success, error_message, created_at
		FROM trace_logs
		WHERE trace_id = ?
		ORDER BY created_at DESC
	`, traceID)
	if err != nil {
		return nil, fmt.Errorf("query trace logs: %w", err)
	}
	defer rows.Close()

	var entries []types.TraceLogEntry
	for rows.Next() {
		var e types.TraceLogEntry
		if err := rows.Scan(
			&e.ID, &e.RequestID, &e.ModelName, &e.UserQuery,
			&e.RequestBody, &e.ResponseBody,
			&e.IsStream, &e.PromptTokens, &e.CompletionTokens, &e.TotalTokens,
			&e.DurationMs, &e.Success, &e.ErrorMessage, &e.CreatedAt,
		); err != nil {
			return nil, fmt.Errorf("scan trace log: %w", err)
		}
		entries = append(entries, e)
	}

	log.Printf("[INFO] trace_reader: read %d logs for trace_id=%d", len(entries), traceID)
	return entries, nil
}

// ReadLogsWithScope reads trace logs filtered by scope criteria.
// scopeValue supports comma-separated values for multi-model and multi-log-id filtering.
// For scope "trace", reads all logs under the trace.
// For scope "trace_log", reads logs matching comma-separated log IDs.
// For scope "model", reads logs filtered by comma-separated model names.
// For scope "apikey", reads all logs under the trace (apikey filtering done at trace config level).
func (r *traceReader) ReadLogsWithScope(ctx context.Context, userID, traceID uint64, scope, scopeValue string) ([]types.TraceLogEntry, error) {
	// Validate scope
	switch scope {
	case types.ScopeModel, types.ScopeAPIKey, types.ScopeTrace, types.ScopeTraceLog:
		// valid
	default:
		return nil, fmt.Errorf("invalid scope: %s", scope)
	}

	// Read all logs from the trace's external database
	allLogs, err := r.ReadLogs(ctx, traceID, userID)
	if err != nil {
		return nil, err
	}

	// Apply scope filter
	switch scope {
	case types.ScopeTraceLog:
		// Filter by comma-separated log IDs
		idSet := parseCSVSet(scopeValue)
		var filtered []types.TraceLogEntry
		for _, entry := range allLogs {
			if idSet[fmt.Sprintf("%d", entry.ID)] {
				filtered = append(filtered, entry)
			}
		}
		log.Printf("[INFO] trace_reader: scope=trace_log ids=%s total=%d matched=%d", scopeValue, len(allLogs), len(filtered))
		return filtered, nil

	case types.ScopeModel:
		// Filter by comma-separated model names
		modelSet := parseCSVSet(scopeValue)
		var filtered []types.TraceLogEntry
		for _, entry := range allLogs {
			if modelSet[entry.ModelName] {
				filtered = append(filtered, entry)
			}
		}
		log.Printf("[INFO] trace_reader: scope=model filter=%s total=%d matched=%d", scopeValue, len(allLogs), len(filtered))
		return filtered, nil

	default:
		// scope=trace or scope=apikey — return all logs
		return allLogs, nil
	}
}

// parseCSVSet splits a comma-separated string into a set for O(1) lookups.
func parseCSVSet(csv string) map[string]bool {
	set := make(map[string]bool)
	for _, v := range strings.Split(csv, ",") {
		v = strings.TrimSpace(v)
		if v != "" {
			set[v] = true
		}
	}
	return set
}

// driverForDBType maps trace DB type to Go sql driver name.
func driverForDBType(dbType string) string {
	switch dbType {
	case "mysql":
		return "mysql"
	case "postgresql":
		return "postgres"
	case "clickhouse":
		return "clickhouse"
	default:
		return "mysql"
	}
}
