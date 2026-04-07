#!/bin/bash
#
# run_client.sh — DeepNode Tauri Client 本地开发启动脚本
#
# 流程:
#   1. 创建 Python venv 并启动 localserver（后台）
#   2. 为 Tauri 编译放置 sidecar 占位文件（dev 模式不真正使用）
#   3. 启动 cargo tauri dev（含前端 HMR）
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/../.."

command -v cargo >/dev/null || { echo "未找到 Rust/Cargo，请先安装 Rust"; exit 1; }
command -v python3.13 >/dev/null || { echo "未找到 python3.13，请先安装 Python 3.13"; exit 1; }

ensure_tauri_cli() {
  if ! cargo tauri -V >/dev/null 2>&1; then
    echo "未检测到 tauri-cli，正在安装..."
    cargo install tauri-cli --locked --version "^2.0"
  fi
}

cleanup() {
  [ -n "$NODE_WORKER_PID" ] && kill "$NODE_WORKER_PID" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM EXIT

VENV_PATH="$PROJECT_ROOT/env"

cd "$SCRIPT_DIR/localserver"
if [ ! -d "$VENV_PATH" ]; then
  python3.13 -m venv "$VENV_PATH"
fi

"$VENV_PATH/bin/pip" install -r requirements.txt >/dev/null
"$VENV_PATH/bin/python" main.py &
NODE_WORKER_PID=$!

echo "DeepNode Python worker 已启动 (PID: $NODE_WORKER_PID)"

# ── 为 Tauri 编译放置 sidecar 占位文件 ──
TAURI_DIR="$SCRIPT_DIR/src-tauri"
BINARIES_DIR="$TAURI_DIR/binaries"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64)  TRIPLE="aarch64-apple-darwin" ;;
  x86_64) TRIPLE="x86_64-apple-darwin"  ;;
  *)      TRIPLE="$ARCH-apple-darwin"    ;;
esac
mkdir -p "$BINARIES_DIR"
if [ ! -f "$BINARIES_DIR/localserver-$TRIPLE" ]; then
  touch "$BINARIES_DIR/localserver-$TRIPLE"
  chmod +x "$BINARIES_DIR/localserver-$TRIPLE"
  echo "已创建 sidecar 占位文件: $BINARIES_DIR/localserver-$TRIPLE"
fi

cd "$SCRIPT_DIR"
echo "启动 DeepNode Tauri Client..."
npm --prefix app install >/dev/null
ensure_tauri_cli
cargo tauri dev
