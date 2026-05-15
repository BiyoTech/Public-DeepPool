-- Migration 011: Guardrail rules and evaluation results tables.
-- Guardrails provide input/output content safety evaluation on a per-API-Key basis.
-- Each guardrail rule is bound to an API Key and uses an LLM evaluator to assess content.
-- Results are stored either in the built-in table or an external user-specified database.

-- 1. Guardrail rules configuration table
CREATE TABLE IF NOT EXISTS guardrails (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    api_key_id BIGINT UNSIGNED NOT NULL COMMENT 'bound API Key ID',
    user_id BIGINT UNSIGNED NOT NULL COMMENT 'owner user ID',
    name VARCHAR(128) NOT NULL COMMENT 'guardrail rule name',
    phase VARCHAR(16) NOT NULL COMMENT 'input or output',
    action VARCHAR(16) NOT NULL COMMENT 'block or log',
    prompt TEXT NOT NULL COMMENT 'evaluation prompt (max 5000 chars)',
    evaluator_model VARCHAR(128) NOT NULL COMMENT 'model name used as evaluator',
    evaluator_api_key_id BIGINT UNSIGNED NOT NULL COMMENT 'API Key ID for calling evaluator model',
    storage_type VARCHAR(16) NOT NULL DEFAULT 'builtin' COMMENT 'builtin or external',
    db_type VARCHAR(16) NOT NULL DEFAULT '' COMMENT 'external: mysql / postgresql / clickhouse',
    db_host VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'external: database host',
    db_port INT NOT NULL DEFAULT 0 COMMENT 'external: database port',
    db_user VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'external: database username',
    db_password_encrypted TEXT DEFAULT NULL COMMENT 'external: AES-256-GCM encrypted password',
    db_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'external: database name',
    enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'whether guardrail is enabled',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_guardrails_apikey (api_key_id),
    INDEX idx_guardrails_user (user_id),
    CONSTRAINT fk_guardrails_apikey FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE,
    CONSTRAINT fk_guardrails_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Guardrail evaluation results table (builtin storage)
CREATE TABLE IF NOT EXISTS guardrail_results (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    guardrail_id BIGINT UNSIGNED NOT NULL COMMENT 'guardrail rule ID',
    api_key_id BIGINT UNSIGNED NOT NULL COMMENT 'API Key ID of the inference request',
    request_id VARCHAR(64) NOT NULL COMMENT 'inference request ID for correlation',
    phase VARCHAR(16) NOT NULL COMMENT 'input or output',
    action VARCHAR(16) NOT NULL COMMENT 'block or log',
    flagged TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'whether evaluator flagged the content',
    confidence DECIMAL(5,4) NOT NULL DEFAULT 0 COMMENT 'evaluator confidence score 0.0-1.0',
    evaluator_response TEXT COMMENT 'raw evaluator JSON response',
    blocked TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'whether request was actually blocked',
    duration_ms INT NOT NULL DEFAULT 0 COMMENT 'evaluation call latency in milliseconds',
    error_message TEXT DEFAULT NULL COMMENT 'evaluator call error message if any',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_gr_results_guardrail (guardrail_id),
    INDEX idx_gr_results_apikey (api_key_id),
    INDEX idx_gr_results_request (request_id),
    INDEX idx_gr_results_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
