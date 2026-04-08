-- Migration: convert tunnel_infer_logs and token_usage_daily monetary fields
-- from BIGINT (fen) to DECIMAL(20,10) (yuan) for high-precision billing.
--
-- IMPORTANT: Run this migration BEFORE deploying the new Go code.
-- Existing fen values are divided by 100 to convert to yuan.

-- 1. tunnel_infer_logs: cost_fen/earning_fen → cost_yuan/earning_yuan
ALTER TABLE tunnel_infer_logs
  ADD COLUMN cost_yuan DECIMAL(20,10) NOT NULL DEFAULT 0 COMMENT 'consumer cost (yuan)' AFTER reasoning_tokens,
  ADD COLUMN earning_yuan DECIMAL(20,10) NOT NULL DEFAULT 0 COMMENT 'contributor earning (yuan)' AFTER cost_yuan;

UPDATE tunnel_infer_logs SET cost_yuan = cost_fen / 100.0, earning_yuan = earning_fen / 100.0;

ALTER TABLE tunnel_infer_logs DROP COLUMN cost_fen, DROP COLUMN earning_fen;

-- 2. token_usage_daily: cost_fen/earning_fen → cost_yuan/earning_yuan
-- (may already have cost_yuan/earning_yuan from migration 002; skip if columns exist)
-- Check: if cost_fen still exists, migrate it.
SET @has_cost_fen = (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'token_usage_daily' AND COLUMN_NAME = 'cost_fen'
);

-- Only run if cost_fen still exists (migration 002 may have already handled this)
-- Use a stored procedure for conditional DDL
DELIMITER //
CREATE PROCEDURE _migrate_daily_fen_to_yuan()
BEGIN
  DECLARE has_old INT DEFAULT 0;
  SELECT COUNT(*) INTO has_old FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'token_usage_daily' AND COLUMN_NAME = 'cost_fen';
  IF has_old > 0 THEN
    -- Add new columns
    SET @has_new = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'token_usage_daily' AND COLUMN_NAME = 'cost_yuan');
    IF @has_new = 0 THEN
      ALTER TABLE token_usage_daily
        ADD COLUMN cost_yuan DECIMAL(20,10) NOT NULL DEFAULT 0 AFTER request_count,
        ADD COLUMN earning_yuan DECIMAL(20,10) NOT NULL DEFAULT 0 AFTER cost_yuan;
    END IF;
    -- Migrate data
    UPDATE token_usage_daily SET cost_yuan = cost_fen / 100.0, earning_yuan = earning_fen / 100.0;
    -- Drop old columns
    ALTER TABLE token_usage_daily DROP COLUMN cost_fen, DROP COLUMN earning_fen;
  END IF;
END //
DELIMITER ;

CALL _migrate_daily_fen_to_yuan();
DROP PROCEDURE IF EXISTS _migrate_daily_fen_to_yuan;
