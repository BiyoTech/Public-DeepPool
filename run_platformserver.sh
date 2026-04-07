#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

command -v go >/dev/null || { echo "未找到 Go，请先安装 Go"; exit 1; }

cd "$PROJECT_ROOT/platform"

export DEEPPOOL_LOG_LEVEL="${DEEPPOOL_LOG_LEVEL:-debug}"

# 支持通过参数选择启动的组件：manager(默认) / scheduler / nodemanager
COMPONENT="${1:-manager}"

case "$COMPONENT" in
  manager)
    echo "启动 manager 服务... (log_level=$DEEPPOOL_LOG_LEVEL)"
    go run ./cmd/manager
    ;;
  scheduler)
    echo "启动 scheduler 服务... (log_level=$DEEPPOOL_LOG_LEVEL)"
    go run ./cmd/scheduler
    ;;
  nodemanager)
    echo "启动 nodemanager 服务... (region=${DEEPPOOL_REGION:-default}, log_level=$DEEPPOOL_LOG_LEVEL)"
    go run ./cmd/nodemanager
    ;;
  *)
    echo "用法: $0 [manager|scheduler|nodemanager]"
    exit 1
    ;;
esac
