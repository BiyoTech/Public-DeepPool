#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

CONTROL_WEB_DIR="$PROJECT_ROOT/platform/control_web"
PORTAL_WEB_DIR="$PROJECT_ROOT/platform/portal_web"

usage() {
  echo "用法: $0 [control|portal|all]"
  echo ""
  echo "  control  - 启动管控后台前端 (端口 5173)"
  echo "  portal   - 启动用户门户前端 (端口 5174)"
  echo "  all      - 同时启动两个前端 (默认)"
  exit 1
}

start_control() {
  echo "启动 control web (管控后台, 端口 5173)..."
  cd "$CONTROL_WEB_DIR"
  if [ ! -d "node_modules" ]; then
    echo "安装 control_web 依赖..."
    npm install
  fi
  npm run dev
}

start_portal() {
  echo "启动 portal web (用户门户, 端口 5174)..."
  cd "$PORTAL_WEB_DIR"
  if [ ! -d "node_modules" ]; then
    echo "安装 portal_web 依赖..."
    npm install
  fi
  npm run dev
}

TARGET="${1:-all}"

case "$TARGET" in
  control)
    start_control
    ;;
  portal)
    start_portal
    ;;
  all)
    # 后台启动 control_web，前台启动 portal_web
    (start_control) &
    CONTROL_PID=$!
    start_portal
    # portal 退出后也终止 control
    kill $CONTROL_PID 2>/dev/null
    ;;
  *)
    usage
    ;;
esac