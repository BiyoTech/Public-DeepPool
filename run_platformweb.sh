#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

cd "$PROJECT_ROOT"

if [ ! -d "$PROJECT_ROOT/node_modules" ]; then
  npm install
fi

echo "启动 platform 管控前端..."
npm --workspace platform/web run dev
