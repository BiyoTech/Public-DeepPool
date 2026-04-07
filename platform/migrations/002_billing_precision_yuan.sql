-- Migration: convert all monetary fields from BIGINT (fen) to DECIMAL(20,10) (yuan).
-- Precision: 10 integer digits + 10 decimal digits, sufficient for high-precision billing.
--
-- IMPORTANT: Run this migration BEFORE deploying the new Go code.
-- Existing fen values are divided by 100 to convert to yuan.

-- 1. token_usage_daily: rename cost_fen/earning_fen → cost_yuan/earning_yuan
ALTER TABLE token_usage_daily
  ADD COLUMN cost_yuan DECIMAL(20,10) NOT NULL DEFAULT 0 AFTER request_count,
  ADD COLUMN earning_yuan DECIMAL(20,10) NOT NULL DEFAULT 0 AFTER cost_yuan;

UPDATE token_usage_daily SET cost_yuan = cost_fen / 100.0, earning_yuan = earning_fen / 100.0;

ALTER TABLE token_usage_daily DROP COLUMN cost_fen, DROP COLUMN earning_fen;

-- 2. user_wallets: balance, total_earned, total_spent, frozen
ALTER TABLE user_wallets
  MODIFY COLUMN balance DECIMAL(20,10) NOT NULL DEFAULT 0,
  MODIFY COLUMN total_earned DECIMAL(20,10) NOT NULL DEFAULT 0,
  MODIFY COLUMN total_spent DECIMAL(20,10) NOT NULL DEFAULT 0,
  MODIFY COLUMN frozen DECIMAL(20,10) NOT NULL DEFAULT 0;

-- Convert existing fen values to yuan
UPDATE user_wallets SET
  balance = balance / 100.0,
  total_earned = total_earned / 100.0,
  total_spent = total_spent / 100.0,
  frozen = frozen / 100.0;

-- 3. wallet_transactions: amount, balance_after
ALTER TABLE wallet_transactions
  MODIFY COLUMN amount DECIMAL(20,10) NOT NULL DEFAULT 0,
  MODIFY COLUMN balance_after DECIMAL(20,10) NOT NULL DEFAULT 0;

-- Convert existing fen values to yuan
UPDATE wallet_transactions SET
  amount = amount / 100.0,
  balance_after = balance_after / 100.0;
