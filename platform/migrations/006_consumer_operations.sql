-- Migration 006: add consumer operation tables for token grants, discounts, and platform config.
-- For fresh deployments, tables are auto-created by SchemaDDL in server.go.
-- Run this migration for existing databases BEFORE deploying the new Go code.

-- 1. Token grant packages (supports multiple grants per user, consumed by expiry order)
CREATE TABLE IF NOT EXISTS user_token_grants (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id          BIGINT UNSIGNED NOT NULL,
    grant_type       VARCHAR(32) NOT NULL COMMENT 'signup_bonus / manual_bonus',
    total_tokens     BIGINT NOT NULL COMMENT 'total token amount granted',
    used_tokens      BIGINT NOT NULL DEFAULT 0 COMMENT 'tokens already consumed',
    remaining_tokens BIGINT NOT NULL COMMENT 'remaining usable tokens',
    expires_at       DATETIME NULL COMMENT 'expiry time, NULL means never expires',
    remark           VARCHAR(500) DEFAULT '' COMMENT 'admin remark',
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_token_grants_user (user_id),
    INDEX idx_token_grants_expires (expires_at),
    CONSTRAINT fk_token_grants_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. User discount table (discount rate applied to billing formula)
CREATE TABLE IF NOT EXISTS user_discounts (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id        BIGINT UNSIGNED NOT NULL,
    discount_rate  DECIMAL(5,4) NOT NULL COMMENT 'discount rate, e.g. 0.8000 means 80% of original price',
    effective_from DATETIME NOT NULL COMMENT 'discount effective start time',
    effective_to   DATETIME NOT NULL COMMENT 'discount effective end time',
    remark         VARCHAR(500) DEFAULT '' COMMENT 'admin remark',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_discounts_user (user_id),
    INDEX idx_discounts_effective (effective_from, effective_to),
    CONSTRAINT fk_discounts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Platform configuration key-value store
CREATE TABLE IF NOT EXISTS platform_configs (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    config_key   VARCHAR(100) NOT NULL COMMENT 'unique config key',
    config_value TEXT NOT NULL COMMENT 'config value (string, parsed by application)',
    description  VARCHAR(500) DEFAULT '' COMMENT 'human-readable description',
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_platform_configs_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Insert default platform config for signup bonus
INSERT IGNORE INTO platform_configs (config_key, config_value, description)
VALUES ('signup_bonus_tokens', '0', 'Number of free tokens granted to new users on registration. 0 means disabled.');
