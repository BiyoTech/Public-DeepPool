-- Migration 007: add supports_vision column to model_registry for vision/multimodal capability flag.
-- Models that support visual understanding (e.g. GPT-4o, Qwen-VL, Gemma-4) should have this set to true.
ALTER TABLE model_registry ADD COLUMN supports_vision TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'whether the model supports vision/image understanding' AFTER supports_function_call;
