#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

cleanup() {
  echo "正在关闭服务..."
  [ -n "$PLATFORM_PID" ] && kill "$PLATFORM_PID" 2>/dev/null || true
  [ -n "$PLATFORM_WEB_PID" ] && kill "$PLATFORM_WEB_PID" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM EXIT

MODE="${1:-all}"
case "$MODE" in
  platform)
    "$PROJECT_ROOT/run_platformserver.sh"
    ;;
  platformweb)
    "$PROJECT_ROOT/run_platformweb.sh"
    ;;
  client|deepnode)
    "$PROJECT_ROOT/run_client.sh"
    ;;
  all)
    "$PROJECT_ROOT/run_platformserver.sh" &
    PLATFORM_PID=$!

    "$PROJECT_ROOT/run_platformweb.sh" &
    PLATFORM_WEB_PID=$!

    "$PROJECT_ROOT/run_client.sh"
    ;;
  *)
    echo "用法: ./dev.sh [platform|platformweb|client|deepnode|all]"
    exit 1
    ;;
esac
