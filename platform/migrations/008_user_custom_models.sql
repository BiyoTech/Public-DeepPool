-- Migration 008: user_custom_models table for consumer-defined hybrid and provider models.
-- Each row is a personal model visible only to its owner.
-- vendor_type: "hybrid" = multi-model routing, "provider" = user-registered external endpoint.
-- Provider models are user-isolated: cannot be referenced by other users' hybrid models or called directly.
CREATE TABLE IF NOT EXISTS user_custom_models (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL COMMENT 'owner user ID',
    model_name VARCHAR(128) NOT NULL COMMENT 'globally unique model name: u{uid}-{display_name}',
    display_name VARCHAR(64) NOT NULL COMMENT 'user-friendly display name',
    vendor_type VARCHAR(16) NOT NULL DEFAULT 'hybrid' COMMENT 'hybrid or provider',
    child_models JSON DEFAULT NULL COMMENT 'hybrid: child model names array',
    routing_policy TEXT DEFAULT NULL COMMENT 'hybrid: YAML routing policy',
    provider_type VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'provider: openai/anthropic/gemini/deepseek/qwen/kimi/glm/custom',
    endpoint VARCHAR(512) NOT NULL DEFAULT '' COMMENT 'provider: API base URL',
    upstream_model VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'provider: upstream model name',
    api_key_encrypted TEXT DEFAULT NULL COMMENT 'provider: AES-256-GCM encrypted API key',
    supports_reasoning TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'provider: reasoning capability',
    supports_vision TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'provider: vision capability',
    supports_function_call TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'provider: function call capability',
    tags JSON DEFAULT NULL COMMENT 'user-defined tags for categorization',
    enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'whether model is enabled',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_custom_model_name (model_name),
    INDEX idx_custom_model_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
