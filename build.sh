#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

check_requirements() {
  command -v go >/dev/null || { echo "Go not found"; exit 1; }
  command -v node >/dev/null || { echo "Node.js not found"; exit 1; }
}

# Generate Go and Python protobuf/gRPC code
gen_proto() {
  echo "Generating protobuf/gRPC code..."
  command -v protoc >/dev/null || { echo "protoc not found, install: brew install protobuf"; exit 1; }

  local PROTO_DIR="$PROJECT_ROOT/libs/proto"

  # Go codegen (output follows go_package path under libs/)
  protoc \
    --proto_path="$PROTO_DIR" \
    --go_out="$PROJECT_ROOT/libs" --go_opt=module=deeppool/libs \
    --go-grpc_out="$PROJECT_ROOT/libs" --go-grpc_opt=module=deeppool/libs \
    "$PROTO_DIR"/*.proto

  # Python codegen (output to localserver/generated/)
  local PY_OUT="$PROJECT_ROOT/clients/deepnode/localserver/generated"
  if [ -d "$PROJECT_ROOT/env" ]; then
    local VENV_PATH="$PROJECT_ROOT/env"
    "$VENV_PATH/bin/python" -m grpc_tools.protoc \
      --proto_path="$PROTO_DIR" \
      --python_out="$PY_OUT" \
      --grpc_python_out="$PY_OUT" \
      "$PROTO_DIR"/*.proto

    # Fix bare imports to relative imports for package compatibility
    for f in "$PY_OUT"/*_pb2.py "$PY_OUT"/*_pb2_grpc.py; do
      [ -f "$f" ] && sed -i '' 's/^import \([a-zA-Z0-9_]*_pb2\) as/from . import \1 as/' "$f"
    done
  else
    echo "  [SKIP] Python venv not found, skipping Python codegen"
  fi

  echo "✓ Proto codegen completed"
}

# Build all platform Go backend services
build_backend() {
  echo "Building platform Go services..."
  mkdir -p "$PROJECT_ROOT/dist/platform"
  cd "$PROJECT_ROOT/platform"

  for svc in manager nodemanager experiment; do
    echo "  Building $svc ..."
    go build -trimpath -ldflags="-s -w" -o "$PROJECT_ROOT/dist/platform/$svc" "./cmd/$svc"
  done

  echo "✓ Platform backend build completed"
}

# Build portal_web frontend
build_portal_web() {
  echo "Building portal_web..."
  cd "$PROJECT_ROOT/platform/portal_web"
  npm install --silent
  npm run build
  rm -rf "$PROJECT_ROOT/dist/platform/portal_web"
  cp -R dist "$PROJECT_ROOT/dist/platform/portal_web"
  echo "✓ portal_web build completed"
}

# Build control_web frontend
build_control_web() {
  echo "Building control_web..."
  cd "$PROJECT_ROOT/platform/control_web"
  npm install --silent
  npm run build
  rm -rf "$PROJECT_ROOT/dist/platform/control_web"
  cp -R dist "$PROJECT_ROOT/dist/platform/control_web"
  echo "✓ control_web build completed"
}

MODE="${1:-all}"
check_requirements

case "$MODE" in
  proto)
    gen_proto
    ;;
  backend)
    gen_proto
    build_backend
    ;;
  web)
    build_portal_web
    build_control_web
    ;;
  all)
    gen_proto
    build_backend
    build_portal_web
    build_control_web
    ;;
  *)
    echo "Usage: ./build.sh [proto|backend|web|all]"
    exit 1
    ;;
esac

echo ""
echo "Build artifacts:"
echo "  Backend:     dist/platform/{manager,nodemanager,experiment}"
echo "  portal_web:  dist/platform/portal_web"
echo "  control_web: dist/platform/control_web"
