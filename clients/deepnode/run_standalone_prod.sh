#!/bin/bash
#
# run_standalone_prod.sh — DeepNode Standalone production launch script
#
# Loads config_prod.yaml and starts localserver in standalone mode
# with DEEPPOOL_PROFILE=prod for production gRPC targets.
#
# Usage:
#   bash run_standalone_prod.sh                         # default start
#   bash run_standalone_prod.sh --skip-build            # skip frontend build
#   bash run_standalone_prod.sh -a <account> -p <pass>  # auto-login
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VENV_PATH="$PROJECT_ROOT/env"
APP_DIR="$SCRIPT_DIR/app"
LOCALSERVER_DIR="$SCRIPT_DIR/localserver"
PROD_CONFIG="$LOCALSERVER_DIR/config_prod.yaml"
PORT=8765

# ── Parse script arguments ──
SKIP_BUILD=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
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

# ── Pre-flight checks ──
# Find available Python 3.13
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
    echo "❌ Python 3.13 not found, please install it first"
    exit 1
fi
command -v node >/dev/null || { echo "❌ node not found, please install Node.js first"; exit 1; }

# Verify prod config exists
if [[ ! -f "$PROD_CONFIG" ]]; then
    echo "❌ Production config not found: $PROD_CONFIG"
    exit 1
fi

# ── Step 1: Python venv + dependency installation ──
echo "📦 Checking Python virtual environment..."
if [ ! -d "$VENV_PATH" ]; then
    echo "   Creating venv: $VENV_PATH"
    "$PYTHON_CMD" -m venv "$VENV_PATH"
fi

echo "📦 Checking and installing Python dependencies..."
source "$SCRIPT_DIR/install_deps.sh"
install_python_deps "$VENV_PATH/bin/pip" "$LOCALSERVER_DIR"

# ── Step 2: Build Vue frontend (standalone mode) ──
if [ "$SKIP_BUILD" = false ]; then
    echo "🔨 Building Vue frontend (standalone mode)..."
    cd "$APP_DIR"
    npm install --silent
    npm run build:standalone
    echo "   Build complete: $APP_DIR/dist-standalone/"
else
    echo "⏭️  Skipping frontend build (--skip-build)"
    if [ ! -f "$APP_DIR/dist-standalone/index.html" ]; then
        echo "⚠️  Warning: dist-standalone/index.html not found, page may not load"
        echo "   Please run once without --skip-build first"
    fi
fi

# ── Step 3: Start localserver with production config ──
cd "$LOCALSERVER_DIR"
echo ""
echo "🚀 Starting DeepNode Standalone Server (PRODUCTION)..."
echo "   Config: $PROD_CONFIG"
echo "   Address: http://127.0.0.1:$PORT/"
echo "   Press Ctrl+C to stop"
echo ""

# Set production profile for gRPC targets
export DEEPPOOL_PROFILE=prod

# Open browser after a short delay (wait for uvicorn startup)
(sleep 1 && open "http://127.0.0.1:$PORT/" 2>/dev/null || true) &

# Run localserver in standalone mode with prod config
exec "$VENV_PATH/bin/python" main.py --standalone --config "$PROD_CONFIG" "${EXTRA_ARGS[@]}"
