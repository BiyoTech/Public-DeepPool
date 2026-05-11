#!/bin/bash
# migrate_provider_endpoints.sh — One-time migration script.
#
# Converts existing provider models (model_registry rows with vendor_type='provider'
# and non-empty endpoint/api_key/upstream_model) into provider_endpoints table records,
# then creates model_endpoints associations.
#
# This script is idempotent: re-running it will skip endpoints that already exist
# (matched by name which is derived from model_name).
#
# Prerequisites:
#   - MySQL client (mysql) available on PATH
#   - Database credentials configured below or via environment variables
#
# Usage:
#   MYSQL_HOST=127.0.0.1 MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASS=xxx MYSQL_DB=deeppool ./migrate_provider_endpoints.sh
#
set -euo pipefail

# Database connection (override via environment variables)
DB_HOST="${MYSQL_HOST:-127.0.0.1}"
DB_PORT="${MYSQL_PORT:-3306}"
DB_USER="${MYSQL_USER:-root}"
DB_PASS="${MYSQL_PASS:-}"
DB_NAME="${MYSQL_DB:-deeppool}"

MYSQL_CMD="mysql -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} -N -B"
if [ -n "${DB_PASS}" ]; then
  MYSQL_CMD="${MYSQL_CMD} -p${DB_PASS}"
fi
MYSQL_CMD="${MYSQL_CMD} ${DB_NAME}"

echo "============================================================"
echo "  Provider Endpoints Migration"
echo "  Database: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "============================================================"
echo ""

# Step 1: Query all provider models with non-empty endpoint configuration.
echo "==> Querying provider models with legacy endpoint config..."
MODELS=$($MYSQL_CMD -e "
  SELECT id, model_name, provider_type, endpoint, api_key, upstream_model
  FROM model_registry
  WHERE vendor_type = 'provider'
    AND endpoint != ''
    AND api_key IS NOT NULL
    AND api_key != ''
    AND upstream_model != ''
  ORDER BY id ASC;
")

if [ -z "$MODELS" ]; then
  echo "    No provider models with legacy endpoint config found. Nothing to migrate."
  exit 0
fi

COUNT=$(echo "$MODELS" | wc -l | tr -d ' ')
echo "    Found ${COUNT} provider model(s) to migrate."
echo ""

# Step 2: For each model, create a provider_endpoint record and associate it.
MIGRATED=0
SKIPPED=0

while IFS=$'\t' read -r MODEL_ID MODEL_NAME PROVIDER_TYPE ENDPOINT API_KEY UPSTREAM_MODEL; do
  # Derive endpoint name from model_name (e.g. "gpt-4o-proxy" -> "ep-gpt-4o-proxy")
  EP_NAME="ep-${MODEL_NAME}"

  # Check if endpoint already exists (idempotent).
  EXISTING=$($MYSQL_CMD -e "SELECT id FROM provider_endpoints WHERE name = '${EP_NAME}' LIMIT 1;" 2>/dev/null || echo "")

  if [ -n "$EXISTING" ]; then
    echo "    [SKIP] endpoint '${EP_NAME}' already exists (id=${EXISTING}), ensuring association..."
    EP_ID="$EXISTING"
    SKIPPED=$((SKIPPED + 1))
  else
    # Insert new endpoint.
    $MYSQL_CMD -e "
      INSERT INTO provider_endpoints (name, provider_type, upstream_model, endpoint_url, api_key, source, rpm_limit, tpm_limit, price_level)
      VALUES ('${EP_NAME}', '${PROVIDER_TYPE}', '${UPSTREAM_MODEL}', '${ENDPOINT}', '${API_KEY}', 'custom', 60, 100000, 3);
    "
    EP_ID=$($MYSQL_CMD -e "SELECT id FROM provider_endpoints WHERE name = '${EP_NAME}' LIMIT 1;")
    echo "    [OK] created endpoint '${EP_NAME}' (id=${EP_ID}) from model '${MODEL_NAME}' (id=${MODEL_ID})"
    MIGRATED=$((MIGRATED + 1))
  fi

  # Ensure model-endpoint association exists.
  ASSOC_EXISTS=$($MYSQL_CMD -e "SELECT COUNT(*) FROM model_endpoints WHERE model_id = ${MODEL_ID} AND endpoint_id = ${EP_ID};" 2>/dev/null || echo "0")
  if [ "$ASSOC_EXISTS" = "0" ]; then
    $MYSQL_CMD -e "INSERT IGNORE INTO model_endpoints (model_id, endpoint_id) VALUES (${MODEL_ID}, ${EP_ID});"
    echo "         Associated model_id=${MODEL_ID} <-> endpoint_id=${EP_ID}"
  fi

done <<< "$MODELS"

echo ""
echo "============================================================"
echo "  Migration complete!"
echo "  Created: ${MIGRATED} endpoint(s)"
echo "  Skipped: ${SKIPPED} (already existed)"
echo "  Total:   ${COUNT} model(s) processed"
echo "============================================================"
echo ""
echo "  NOTE: The legacy endpoint/api_key/upstream_model fields on model_registry"
echo "  are preserved as fallback. They can be cleared manually after verifying"
echo "  that the new endpoint pool dispatch works correctly."
