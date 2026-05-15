-- Migration 009: Remove legacy provider fields from model_registry.
-- These fields (endpoint, api_key, upstream_model) are now managed by
-- provider_endpoints + model_endpoints tables (Endpoint Pool architecture).
--
-- Prerequisites:
--   1. All provider models must have been migrated to use endpoint pool
--      (run scripts/migrate_provider_endpoints.sh first).
--   2. Verify no data loss: SELECT id, model_name, endpoint, upstream_model
--      FROM model_registry WHERE vendor_type='provider' AND endpoint != '';

ALTER TABLE model_registry DROP COLUMN endpoint;
ALTER TABLE model_registry DROP COLUMN api_key;
ALTER TABLE model_registry DROP COLUMN upstream_model;
