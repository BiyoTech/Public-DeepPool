#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

check_requirements() {
  command -v node >/dev/null || { echo "未找到 Node.js"; exit 1; }
  command -v cargo >/dev/null || { echo "未找到 Rust/Cargo"; exit 1; }
  command -v python3.13 >/dev/null || { echo "未找到 python3.13"; exit 1; }
}

# 生成 Go 和 Python 的 protobuf/gRPC 代码
gen_proto() {
  echo "生成 protobuf/gRPC 代码..."
  command -v protoc >/dev/null || { echo "未找到 protoc，请先安装: brew install protobuf"; exit 1; }

  local PROTO_DIR="$PROJECT_ROOT/libs/proto"

  # Go 端生成（输出到 libs/ 下按 go_package 路径）
  protoc \
    --proto_path="$PROTO_DIR" \
    --go_out="$PROJECT_ROOT/libs" --go_opt=module=deeppool/libs \
    --go-grpc_out="$PROJECT_ROOT/libs" --go-grpc_opt=module=deeppool/libs \
    "$PROTO_DIR"/*.proto

  # Python 端生成（输出到 localserver/generated/）
  local PY_OUT="$PROJECT_ROOT/clients/deepnode/localserver/generated"
  local VENV_PATH="$PROJECT_ROOT/env"
  "$VENV_PATH/bin/python" -m grpc_tools.protoc \
    --proto_path="$PROTO_DIR" \
    --python_out="$PY_OUT" \
    --grpc_python_out="$PY_OUT" \
    "$PROTO_DIR"/*.proto

  # grpc_tools.protoc 生成的 Python 代码使用裸导入（如 import llm_infer_pb2 as ...），
  # 需修正为包内相对导入（from . import llm_infer_pb2 as ...），
  # 否则运行目录不在 generated/ 时会报 ModuleNotFoundError。
  # 覆盖所有 *_pb2.py 和 *_pb2_grpc.py 文件。
  for f in "$PY_OUT"/*_pb2.py "$PY_OUT"/*_pb2_grpc.py; do
    [ -f "$f" ] && sed -i '' 's/^import \([a-zA-Z0-9_]*_pb2\) as/from . import \1 as/' "$f"
  done

  echo "✓ proto 代码生成完成"
}

ensure_tauri_cli() {
  if ! cargo tauri -V >/dev/null 2>&1; then
    echo "未检测到 tauri-cli，正在安装..."
    cargo install tauri-cli --locked --version "^2.0"
  fi
}

build_platform() {
  command -v go >/dev/null || { echo "未找到 Go，无法构建 platform 后端"; exit 1; }

  echo "构建 platform 后端..."
  mkdir -p "$PROJECT_ROOT/dist/platform"
  cd "$PROJECT_ROOT/platform"
  go build -o "$PROJECT_ROOT/dist/platform/controlplane" ./cmd/controlplane

  echo "构建 platform 管控前端..."
  cd "$PROJECT_ROOT"
  npm install
  npm --workspace platform/web run build
  rm -rf "$PROJECT_ROOT/dist/platform/web"
  cp -R "$PROJECT_ROOT/platform/web/dist" "$PROJECT_ROOT/dist/platform/web"

  echo "✓ platform 构建完成"
}

build_deepnode() {
  echo "构建 DeepNode 本地 Python worker..."
  local VENV_PATH="$PROJECT_ROOT/venv"

  cd "$PROJECT_ROOT/clients/deepnode/llm"
  if [ ! -d "$VENV_PATH" ]; then
    python3.13 -m venv "$VENV_PATH"
  fi
  "$VENV_PATH/bin/pip" install -r requirements.txt pyinstaller >/dev/null
  "$VENV_PATH/bin/pyinstaller" --clean --noconfirm --onefile --name deepnode-worker main.py

  local TARGET_TRIPLE
  TARGET_TRIPLE=$(rustc -vV | grep host | cut -d ' ' -f2)
  mkdir -p "$PROJECT_ROOT/clients/deepnode/src-tauri/binaries"
  cp "$PROJECT_ROOT/clients/deepnode/llm/dist/deepnode-worker" "$PROJECT_ROOT/clients/deepnode/src-tauri/binaries/deepnode-worker-$TARGET_TRIPLE"
  chmod +x "$PROJECT_ROOT/clients/deepnode/src-tauri/binaries/deepnode-worker-$TARGET_TRIPLE"

  echo "构建 DeepNode 桌面应用（macOS: .dmg / Windows: .exe）..."
  cd "$PROJECT_ROOT/clients/deepnode"
  npm --prefix app install
  ensure_tauri_cli
  cargo tauri build

  echo "✓ DeepNode 构建完成"
}

MODE="${1:-all}"
check_requirements

case "$MODE" in
  proto)
    gen_proto
    ;;
  platform)
    gen_proto
    build_platform
    ;;
  deepnode)
    gen_proto
    build_deepnode
    ;;
  all)
    gen_proto
    build_platform
    build_deepnode
    ;;
  *)
    echo "用法: ./build.sh [proto|platform|deepnode|all]"
    exit 1
    ;;
esac

echo "构建产物："
echo "- platform 后端: dist/platform/controlplane"
echo "- platform 前端: dist/platform/web"
echo "- DeepNode 安装包: clients/deepnode/src-tauri/target/release/bundle"
