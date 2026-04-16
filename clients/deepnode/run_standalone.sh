#!/bin/bash
#
# run_standalone.sh — DeepNode Standalone launcher (unified for all environments)
#
# Handles: venv creation -> dependency install -> frontend build -> server start
#
# Usage:
#   bash run_standalone.sh                              # dev (default)
#   bash run_standalone.sh --env test                   # test environment
#   bash run_standalone.sh --env prod                   # production environment
#   bash run_standalone.sh --env test --skip-build      # skip frontend build
#   bash run_standalone.sh --env prod -a <acct> -p <pw> # auto-login
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VENV_PATH="$PROJECT_ROOT/env"
APP_DIR="$SCRIPT_DIR/app"
LOCALSERVER_DIR="$SCRIPT_DIR/localserver"
PORT=8765

# ── Parse script arguments ──
SKIP_BUILD=false
ENV="dev"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV="$2"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# Validate environment
case "$ENV" in
  dev|test|prod) ;;
  *)
    echo "ERROR: unknown environment '$ENV'. Supported: dev, test, prod"
    exit 1
    ;;
esac

# Resolve config file for non-dev environments
CONFIG_ARGS=()
if [[ "$ENV" != "dev" ]]; then
  CONFIG_FILE="$LOCALSERVER_DIR/config_${ENV}.yaml"
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: config file not found: $CONFIG_FILE"
    exit 1
  fi
  CONFIG_ARGS=(--config "$CONFIG_FILE")
fi

ENV_UPPER=$(echo "$ENV" | tr '[:lower:]' '[:upper:]')

# ── Pre-flight checks ──
# Find Python 3.13
PYTHON_CMD=""
for cmd in python3.13 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "")
        if [[ "$ver" == "3.13" ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done
if [[ -z "$PYTHON_CMD" ]]; then
    echo "ERROR: Python 3.13 not found, please install it first"
    exit 1
fi
command -v node >/dev/null || { echo "ERROR: node not found, please install Node.js first"; exit 1; }

# ── Step 1: Python venv + dependency installation ──
echo "Checking Python virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    echo "   Creating venv: $VENV_PATH"
    "$PYTHON_CMD" -m venv "$VENV_PATH"
fi

echo "Checking and installing Python dependencies..."
source "$SCRIPT_DIR/install_deps.sh"
install_python_deps "$VENV_PATH/bin/pip" "$LOCALSERVER_DIR"

# ── Step 2: Build Vue frontend (standalone mode) ──
if [ "$SKIP_BUILD" = false ]; then
    echo "Building Vue frontend (standalone mode)..."
    cd "$APP_DIR"
    npm install --silent
    npm run build:standalone
    echo "   Build complete: $APP_DIR/dist-standalone/"
else
    echo "Skipping frontend build (--skip-build)"
    if [ ! -f "$APP_DIR/dist-standalone/index.html" ]; then
        echo "WARNING: dist-standalone/index.html not found, page may not load"
        echo "   Please run once without --skip-build first"
    fi
fi

# ── Step 3: Start localserver ──
cd "$LOCALSERVER_DIR"
echo ""
echo "Starting DeepNode Standalone Server (${ENV_UPPER})..."
if [[ ${#CONFIG_ARGS[@]} -gt 0 ]]; then
    echo "   Config: ${CONFIG_ARGS[1]}"
fi
echo "   Address: http://127.0.0.1:$PORT/"
echo "   Press Ctrl+C to stop"
echo ""

# Set profile env var so platform_defaults.py picks the right gRPC targets
export DEEPPOOL_PROFILE="$ENV"

# Open browser after a short delay (wait for uvicorn startup)
(sleep 1 && open "http://127.0.0.1:$PORT/" 2>/dev/null || true) &

# Run localserver in standalone mode
exec "$VENV_PATH/bin/python" main.py --standalone "${CONFIG_ARGS[@]}" "${EXTRA_ARGS[@]}"
