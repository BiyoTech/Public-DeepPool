#!/usr/bin/env bash
#
# build_mac.sh — DeepNode macOS DMG 一键打包脚本
#
# 流程:
#   1. 用 PyInstaller 将 Python localserver 打包为单文件可执行程序
#   2. 将可执行文件放到 Tauri externalBin 约定路径 (src-tauri/binaries/)
#   3. 构建前端 Vue 应用
#   4. 用 cargo tauri build 生成 DMG 安装包
#
# 前置条件:
#   - Python 3.10+ (推荐 3.11)
#   - Node.js 18+ / npm
#   - Rust toolchain (rustup)
#   - Tauri CLI: cargo install tauri-cli --version "^2"
#
# 用法:
#   cd clients/deepnode
#   chmod +x build_mac.sh
#   ./build_mac.sh
#

set -euo pipefail

# ── 颜色输出 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 项目根目录 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOCALSERVER_DIR="$SCRIPT_DIR/localserver"
TAURI_DIR="$SCRIPT_DIR/src-tauri"
APP_DIR="$SCRIPT_DIR/app"

# ── 检测当前架构，用于 Tauri sidecar 命名 ──
ARCH="$(uname -m)"
case "$ARCH" in
    arm64)  TARGET_TRIPLE="aarch64-apple-darwin" ;;
    x86_64) TARGET_TRIPLE="x86_64-apple-darwin"  ;;
    *)      error "unsupported architecture: $ARCH" ;;
esac
info "detected architecture: $ARCH ($TARGET_TRIPLE)"

# ────────────────────────────────────────────────────
# 1. 环境检查
# ────────────────────────────────────────────────────
info "checking build dependencies..."

command -v node    >/dev/null 2>&1 || error "node not found"
command -v npm     >/dev/null 2>&1 || error "npm not found"
command -v cargo   >/dev/null 2>&1 || error "cargo not found (install Rust: https://rustup.rs)"

# 确保 Tauri CLI 可用
if ! cargo tauri --version >/dev/null 2>&1; then
    warn "tauri-cli not found, installing..."
    cargo install tauri-cli --version "^2"
fi

info "all dependencies OK"

# ────────────────────────────────────────────────────
# 2. 使用项目 Python 虚拟环境并安装依赖
# ────────────────────────────────────────────────────
# 复用项目根目录的 env/ 虚拟环境（与 run_client.sh 一致，Python 3.13）
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/env"

if [ ! -d "$VENV_DIR" ]; then
    # 优先使用 python3.13，其次 python3
    PYTHON_BIN="$(command -v python3.13 2>/dev/null || command -v python3)"
    [ -z "$PYTHON_BIN" ] && error "python3.13 or python3 not found"
    info "creating python venv at $VENV_DIR ..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# 校验 Python 版本 >= 3.10（MLX 硬性要求）
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MINOR" -lt 10 ]; then
    error "Python >= 3.10 required (found $PY_VERSION). MLX does not support older versions."
fi
info "python venv activated: Python $PY_VERSION ($(which python3))"

info "upgrading pip..."
pip3 install --quiet --upgrade pip

info "installing localserver dependencies..."
pip3 install --quiet -r "$LOCALSERVER_DIR/requirements.txt"

# 安装 macOS 平台特定的推理引擎依赖
# MLX 从 0.30 起拆分为 mlx + mlx-metal（macOS），需分步安装以确保依赖解析正确
if [ "$ARCH" = "arm64" ]; then
    info "Apple Silicon detected, installing MLX dependencies..."
    pip3 install --quiet "mlx>=0.30.4"
    pip3 install --quiet "mlx-lm>=0.31.0"
    pip3 install --quiet "mlx-vlm>=0.1.0"
else
    info "Intel Mac detected, installing llama.cpp dependencies..."
    pip3 install --quiet "llama-cpp-python>=0.3.0"
fi

info "installing PyInstaller..."
pip3 install --quiet pyinstaller

# 验证推理引擎依赖已正确安装（避免打包后运行时 ImportError）
if [ "$ARCH" = "arm64" ]; then
    python3 -c "import mlx; import mlx_lm; print('mlx OK, mlx_lm OK')" \
        || error "mlx/mlx_lm import verification failed. Check installation logs above."
fi

# ────────────────────────────────────────────────────
# 3. PyInstaller 打包 localserver
# ────────────────────────────────────────────────────
info "building localserver binary with PyInstaller..."

# 清理旧的构建产物
rm -rf "$TAURI_DIR/build" "$TAURI_DIR/dist"

pyinstaller \
    --noconfirm \
    --clean \
    --distpath "$TAURI_DIR/dist" \
    --workpath "$TAURI_DIR/build" \
    "$TAURI_DIR/localserver.spec"

PYINSTALLER_BIN="$TAURI_DIR/dist/localserver"
[ -f "$PYINSTALLER_BIN" ] || error "PyInstaller output not found: $PYINSTALLER_BIN"
info "localserver binary built: $(du -h "$PYINSTALLER_BIN" | cut -f1)"

# ────────────────────────────────────────────────────
# 4. 放置到 Tauri externalBin 约定路径
# ────────────────────────────────────────────────────
# tauri.conf.json 中 externalBin 配置为 "binaries/localserver"，
# Tauri sidecar 约定文件名为 <name>-<target_triple>。
BINARIES_DIR="$TAURI_DIR/binaries"
mkdir -p "$BINARIES_DIR"
SIDECAR_BIN="$BINARIES_DIR/localserver-${TARGET_TRIPLE}"

cp "$PYINSTALLER_BIN" "$SIDECAR_BIN"
chmod +x "$SIDECAR_BIN"
info "sidecar binary placed: $SIDECAR_BIN"

# ────────────────────────────────────────────────────
# 5. 安装前端依赖
# ────────────────────────────────────────────────────
info "installing frontend dependencies..."
(cd "$APP_DIR" && npm install --no-audit --no-fund)

# ────────────────────────────────────────────────────
# 6. Tauri 构建 DMG（会自动执行 beforeBuildCommand 构建前端）
# ────────────────────────────────────────────────────
info "building Tauri app (DMG)..."
(cd "$SCRIPT_DIR" && cargo tauri build)

# ────────────────────────────────────────────────────
# 7. 清理临时文件，定位产物
# ────────────────────────────────────────────────────
rm -rf "$TAURI_DIR/build" "$TAURI_DIR/dist"
# 清理 sidecar 临时文件（已被 cargo tauri build 打包进 .app）
rm -rf "$TAURI_DIR/binaries"

DMG_DIR="$TAURI_DIR/target/release/bundle/dmg"
if [ -d "$DMG_DIR" ]; then
    DMG_FILE=$(find "$DMG_DIR" -name "*.dmg" -type f | head -1)
    if [ -n "$DMG_FILE" ]; then
        info "=============================="
        info "DMG 打包完成!"
        info "产物路径: $DMG_FILE"
        info "文件大小: $(du -h "$DMG_FILE" | cut -f1)"
        info "=============================="
    else
        warn "DMG directory exists but no .dmg file found"
    fi
else
    warn "DMG output directory not found, check cargo tauri build output above"
fi

deactivate 2>/dev/null || true
info "build finished"
