-- Migration 004: add tags column to model_registry for model characteristic labels.
-- Tags are stored as a JSON string array (e.g. ["multimodal", "reasoning", "low-latency"]).
ALTER TABLE model_registry ADD COLUMN tags TEXT DEFAULT NULL COMMENT 'model tags (JSON string array)' AFTER options;
