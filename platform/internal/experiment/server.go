// Package experiment provides the Experiment gRPC Server: Judge (AI-based trace evaluation)
// and Evaluate (dataset-based model evaluation) capabilities.
//
// Architecture:
//   - Serves only gRPC (no HTTP). All web requests are proxied by Manager.
//   - llm_client: HTTP client for calling Manager Gateway LLM endpoints
//   - trace_reader: reads trace logs from user's external databases
//   - service/repository: standard layered architecture for Judge, Dataset, Evaluation
package experiment

import (
	"context"
	"database/sql"
	"encoding/hex"
	"fmt"
	"log"
	"net"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/config"
	"deeppool/platform/internal/experiment/repository"
	"deeppool/platform/internal/experiment/service"
	mysqlstore "deeppool/platform/internal/storage/mysql"

	experimentv1 "deeppool/libs/proto/experiment/v1"

	"google.golang.org/grpc"
)

// SchemaDDL contains idempotent CREATE TABLE statements for experiment module tables.
var SchemaDDL = []string{
	// Judge tasks: metadata for each judge evaluation run
	`CREATE TABLE IF NOT EXISTS experiment_judges (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		user_id BIGINT UNSIGNED NOT NULL,
		name VARCHAR(128) NOT NULL COMMENT 'judge task name',
		scope VARCHAR(16) NOT NULL DEFAULT 'trace' COMMENT 'evaluation granularity: model/apikey/trace/trace_log',
		scope_value VARCHAR(256) NOT NULL DEFAULT '' COMMENT 'entity identifier for the chosen scope',
		trace_id BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'associated trace config ID (required for trace/trace_log scope)',
		judge_model VARCHAR(128) NOT NULL COMMENT 'model used for judging',
		judge_apikey_id BIGINT UNSIGNED NOT NULL COMMENT 'API key ID used for judge model calls',
		scorer_type VARCHAR(16) NOT NULL DEFAULT 'custom' COMMENT 'builtin or custom',
		scorer_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'builtin scorer identifier (empty for custom)',
		prompt_template TEXT COMMENT 'evaluation prompt template with {{var}} placeholders',
		status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
		total_count INT NOT NULL DEFAULT 0,
		completed_count INT NOT NULL DEFAULT 0,
		failed_count INT NOT NULL DEFAULT 0,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		INDEX idx_judges_user (user_id),
		INDEX idx_judges_status (status)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Judge runs: each execution of a judge task creates a run record
	`CREATE TABLE IF NOT EXISTS experiment_judge_runs (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		judge_id BIGINT UNSIGNED NOT NULL,
		status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
		total_count INT NOT NULL DEFAULT 0,
		completed_count INT NOT NULL DEFAULT 0,
		failed_count INT NOT NULL DEFAULT 0,
		pass_rate FLOAT NOT NULL DEFAULT 0 COMMENT 'passed / successful_count * 100',
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		INDEX idx_judge_runs_judge (judge_id),
		CONSTRAINT fk_judge_runs_judge FOREIGN KEY (judge_id) REFERENCES experiment_judges(id) ON DELETE CASCADE
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Judge results: per-trace-log evaluation output, scoped to a run
	`CREATE TABLE IF NOT EXISTS experiment_judge_results (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		run_id BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'associated judge run ID',
		judge_id BIGINT UNSIGNED NOT NULL,
		trace_log_id BIGINT UNSIGNED NOT NULL COMMENT 'ID of the trace log entry being judged',
		request_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'request_id from trace log for reference',
		passed TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'whether the trace log passed evaluation',
		reason TEXT COMMENT 'judge model reasoning/explanation',
		raw_output TEXT COMMENT 'full raw output from judge model',
		duration_ms BIGINT NOT NULL DEFAULT 0,
		success TINYINT(1) NOT NULL DEFAULT 1,
		error_message TEXT,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		INDEX idx_judge_results_run (run_id),
		INDEX idx_judge_results_judge (judge_id),
		CONSTRAINT fk_judge_results_judge FOREIGN KEY (judge_id) REFERENCES experiment_judges(id) ON DELETE CASCADE
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Datasets: user-created evaluation datasets
	`CREATE TABLE IF NOT EXISTS experiment_datasets (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		user_id BIGINT UNSIGNED NOT NULL,
		name VARCHAR(128) NOT NULL COMMENT 'dataset name',
		description TEXT COMMENT 'dataset description',
		item_count INT NOT NULL DEFAULT 0 COMMENT 'cached count of items',
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		INDEX idx_datasets_user (user_id)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Dataset items: individual evaluation samples
	`CREATE TABLE IF NOT EXISTS experiment_dataset_items (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		dataset_id BIGINT UNSIGNED NOT NULL,
		input TEXT NOT NULL COMMENT 'input prompt/question',
		expected_output TEXT COMMENT 'expected/reference output',
		metadata JSON COMMENT 'additional metadata (tags, category, etc.)',
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		INDEX idx_dataset_items_dataset (dataset_id),
		CONSTRAINT fk_dataset_items_dataset FOREIGN KEY (dataset_id) REFERENCES experiment_datasets(id) ON DELETE CASCADE
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Evaluation tasks: metadata for dataset-based evaluation runs
	`CREATE TABLE IF NOT EXISTS experiment_evaluations (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		user_id BIGINT UNSIGNED NOT NULL,
		name VARCHAR(128) NOT NULL COMMENT 'evaluation task name',
		dataset_id BIGINT UNSIGNED NOT NULL COMMENT 'associated dataset ID',
		model_name VARCHAR(128) NOT NULL COMMENT 'model being evaluated',
		apikey_id BIGINT UNSIGNED NOT NULL COMMENT 'API key ID for model calls',
		status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed',
		total_count INT NOT NULL DEFAULT 0,
		completed_count INT NOT NULL DEFAULT 0,
		failed_count INT NOT NULL DEFAULT 0,
		avg_score FLOAT NOT NULL DEFAULT 0 COMMENT 'average evaluation score',
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		INDEX idx_evaluations_user (user_id),
		INDEX idx_evaluations_status (status)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Evaluation results: per-dataset-item evaluation output
	`CREATE TABLE IF NOT EXISTS experiment_evaluation_results (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		evaluation_id BIGINT UNSIGNED NOT NULL,
		item_id BIGINT UNSIGNED NOT NULL COMMENT 'dataset item ID',
		model_output TEXT COMMENT 'actual model output',
		score FLOAT NOT NULL DEFAULT 0 COMMENT 'evaluation score for this item',
		duration_ms BIGINT NOT NULL DEFAULT 0,
		success TINYINT(1) NOT NULL DEFAULT 1,
		error_message TEXT,
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		INDEX idx_eval_results_eval (evaluation_id),
		CONSTRAINT fk_eval_results_eval FOREIGN KEY (evaluation_id) REFERENCES experiment_evaluations(id) ON DELETE CASCADE
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,

	// Trace log annotations: human feedback and expectations per trace log entry
	`CREATE TABLE IF NOT EXISTS experiment_trace_annotations (
		id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
		user_id BIGINT UNSIGNED NOT NULL,
		trace_id BIGINT UNSIGNED NOT NULL COMMENT 'trace config ID',
		log_id BIGINT UNSIGNED NOT NULL COMMENT 'trace log entry ID',
		feedbacks JSON COMMENT 'array of feedback items [{name, passed, reason}]',
		expectation JSON COMMENT 'single expectation item {name, data_type, content, reason}',
		created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
		UNIQUE KEY uk_annotation_log (user_id, trace_id, log_id),
		INDEX idx_annotations_user_trace (user_id, trace_id)
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
}

// MigrateSchema applies idempotent column migrations for existing tables.
// This handles the case where tables already exist but lack new columns added in later versions.
func MigrateSchema(db *sql.DB, database string) error {
	log.Printf("[INFO] experiment: running schema migration for database=%s", database)

	// experiment_judges: new columns added for multi-scope + scorer support
	judgesMigrations := []struct {
		column    string
		columnDef string
	}{
		{"scope", "scope VARCHAR(16) NOT NULL DEFAULT 'trace' COMMENT 'evaluation granularity: model/apikey/trace/trace_log' AFTER name"},
		{"scope_value", "scope_value VARCHAR(256) NOT NULL DEFAULT '' COMMENT 'entity identifier for the chosen scope' AFTER scope"},
		{"scorer_type", "scorer_type VARCHAR(16) NOT NULL DEFAULT 'custom' COMMENT 'builtin or custom' AFTER judge_apikey_id"},
		{"scorer_name", "scorer_name VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'builtin scorer identifier (empty for custom)' AFTER scorer_type"},
	}
	for _, m := range judgesMigrations {
		if err := mysqlstore.AddColumnIfNotExists(db, database, "experiment_judges", m.column, m.columnDef); err != nil {
			log.Printf("[ERROR] experiment: migrate column experiment_judges.%s failed: %v", m.column, err)
			return fmt.Errorf("migrate experiment_judges.%s: %w", m.column, err)
		}
	}

	// experiment_judge_results: replace score/reasoning with passed/reason
	resultsMigrations := []struct {
		column    string
		columnDef string
	}{
		{"passed", "passed TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'whether the trace log passed evaluation' AFTER request_id"},
		{"reason", "reason TEXT COMMENT 'judge model reasoning/explanation' AFTER passed"},
	}
	for _, m := range resultsMigrations {
		if err := mysqlstore.AddColumnIfNotExists(db, database, "experiment_judge_results", m.column, m.columnDef); err != nil {
			log.Printf("[ERROR] experiment: migrate column experiment_judge_results.%s failed: %v", m.column, err)
			return fmt.Errorf("migrate experiment_judge_results.%s: %w", m.column, err)
		}
	}

	// experiment_judge_results: add run_id column for multi-run support
	if err := mysqlstore.AddColumnIfNotExists(db, database, "experiment_judge_results", "run_id",
		"run_id BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'associated judge run ID' AFTER id"); err != nil {
		log.Printf("[ERROR] experiment: migrate column experiment_judge_results.run_id failed: %v", err)
		return fmt.Errorf("migrate experiment_judge_results.run_id: %w", err)
	}

	log.Printf("[INFO] experiment: schema migration completed")
	return nil
}

// Server is the experiment gRPC server.
type Server struct {
	grpcAddr   string
	grpcServer *grpc.Server
}

// NewServer creates and wires the experiment gRPC server with all dependencies.
func NewServer(grpcAddr string, db *sql.DB, expCfg config.ExperimentConfig, tlsCfg config.TLSConfig) *Server {
	// Parse encryption key from hex string
	encryptionKey, err := hex.DecodeString(expCfg.APIKeyEncryptionKey)
	if err != nil || len(encryptionKey) != 32 {
		log.Fatalf("[FATAL] experiment: invalid api_key_encryption_key (must be 64 hex chars)")
	}

	workerPoolSize := expCfg.WorkerPoolSize
	if workerPoolSize <= 0 {
		workerPoolSize = 5
	}

	// --- Infrastructure components ---
	llmClient := NewLLMClient(expCfg.ManagerGatewayURL)
	traceReader := NewTraceReader(db, encryptionKey)
	keyResolver := NewAPIKeyResolver(db, encryptionKey)

	// Load builtin scorer templates from YAML files (i18n: en/zh)
	templateDir := expCfg.TemplateDir
	if templateDir == "" {
		templateDir = "internal/experiment/template"
	}
	service.InitScorerTemplates(templateDir)

	// --- Repository layer ---
	judgeRepo := repository.NewMySQLJudgeRepository(db)
	datasetRepo := repository.NewMySQLDatasetRepository(db)
	evalRepo := repository.NewMySQLEvaluationRepository(db)
	annotationRepo := repository.NewMySQLAnnotationRepository(db)

	// --- Service layer ---
	judgeSvc := service.NewJudgeService(judgeRepo, annotationRepo, traceReader, llmClient, keyResolver, workerPoolSize)
	datasetSvc := service.NewDatasetService(datasetRepo)
	evalSvc := service.NewEvaluationService(evalRepo, datasetRepo, llmClient, workerPoolSize)
	annotationSvc := service.NewAnnotationService(annotationRepo)

	// --- gRPC server ---
	var opts []grpc.ServerOption
	tlsOpt, err := common.NewGRPCServerOption(tlsCfg)
	if err != nil {
		log.Fatalf("[FATAL] experiment: load gRPC server TLS: %v", err)
	}
	if tlsOpt != nil {
		opts = append(opts, tlsOpt)
	}

	grpcServer := grpc.NewServer(opts...)
	svcImpl := NewGRPCService(judgeSvc, datasetSvc, evalSvc, annotationSvc)
	experimentv1.RegisterExperimentServiceServer(grpcServer, svcImpl)

	return &Server{
		grpcAddr:   grpcAddr,
		grpcServer: grpcServer,
	}
}

// Start begins listening for gRPC requests (blocking).
func (s *Server) Start() error {
	lis, err := net.Listen("tcp", s.grpcAddr)
	if err != nil {
		return err
	}
	log.Printf("[INFO] experiment gRPC listening on %s", s.grpcAddr)
	return s.grpcServer.Serve(lis)
}

// GracefulStop gracefully stops the gRPC server.
func (s *Server) GracefulStop(ctx context.Context) {
	done := make(chan struct{})
	go func() {
		s.grpcServer.GracefulStop()
		close(done)
	}()
	select {
	case <-done:
	case <-ctx.Done():
		s.grpcServer.Stop()
	}
}
