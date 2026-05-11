-- Migration: rename provider_type → model_family across 3 tables.
-- Safe to run multiple times (uses IF EXISTS / column check pattern via CHANGE).

ALTER TABLE model_registry CHANGE COLUMN provider_type model_family VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'model family: gpt/claude/gemini/deepseek/qwen/kimi/glm/qianfan/minimax/custom';

ALTER TABLE provider_endpoints CHANGE COLUMN provider_type model_family VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'model family: gpt/claude/gemini/deepseek/qwen/kimi/glm/qianfan/minimax/custom';

ALTER TABLE user_custom_models CHANGE COLUMN provider_type model_family VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'model family: gpt/claude/gemini/deepseek/qwen/kimi/glm/custom';

-- Migrate old model_family values to new naming convention.
UPDATE model_registry SET model_family = 'gpt' WHERE model_family = 'openai';
UPDATE model_registry SET model_family = 'claude' WHERE model_family = 'anthropic';

UPDATE provider_endpoints SET model_family = 'gpt' WHERE model_family = 'openai';
UPDATE provider_endpoints SET model_family = 'claude' WHERE model_family = 'anthropic';

UPDATE user_custom_models SET model_family = 'gpt' WHERE model_family = 'openai';
UPDATE user_custom_models SET model_family = 'claude' WHERE model_family = 'anthropic';
