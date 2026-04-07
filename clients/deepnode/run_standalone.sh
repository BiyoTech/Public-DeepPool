#!/bin/bash
#
# run_standalone.sh — DeepNode Standalone 本地开发启动脚本
#
# 自动完成: 创建 venv → 安装核心+平台推理引擎依赖 → 构建前端 → 启动服务
#
# 用法:
#   bash run_standalone.sh                         # 默认启动，浏览器登录
#   bash run_standalone.sh --skip-build            # 跳过前端构建（已构建过）
#   bash run_standalone.sh -a <account> -p <pass>  # 自动登录模式
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VENV_PATH="$PROJECT_ROOT/env"
APP_DIR="$SCRIPT_DIR/app"
LOCALSERVER_DIR="$SCRIPT_DIR/localserver"
PORT=8765

# ── 解析脚本参数 ──
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

# ── 前置检查 ──
# 查找可用的 Python 3.13（支持多种命令名）
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
    echo "❌ 未找到 Python 3.13，请先安装"
    exit 1
fi
command -v node >/dev/null || { echo "❌ 未找到 node，请先安装 Node.js"; exit 1; }

# ── 步骤 1: Python 虚拟环境 + 依赖安装 ──
echo "📦 检查 Python 虚拟环境..."
if [ ! -d "$VENV_PATH" ]; then
    echo "   创建 venv: $VENV_PATH"
    "$PYTHON_CMD" -m venv "$VENV_PATH"
fi

# 加载共享依赖安装函数并执行
echo "📦 检查并安装 Python 依赖（自动检测平台）..."
source "$SCRIPT_DIR/install_deps.sh"
install_python_deps "$VENV_PATH/bin/pip" "$LOCALSERVER_DIR"

# ── 步骤 2: 构建 Vue 前端（standalone 模式） ──
if [ "$SKIP_BUILD" = false ]; then
    echo "🔨 构建 Vue 前端（standalone 模式）..."
    cd "$APP_DIR"
    npm install --silent
    npm run build:standalone
    echo "   构建完成: $APP_DIR/dist-standalone/"
else
    echo "⏭️  跳过前端构建（--skip-build）"
    if [ ! -f "$APP_DIR/dist-standalone/index.html" ]; then
        echo "⚠️  警告: dist-standalone/index.html 不存在，页面可能无法加载"
        echo "   请先运行一次不带 --skip-build 的命令"
    fi
fi

# ── 步骤 3: 启动 localserver ──
cd "$LOCALSERVER_DIR"
echo ""
echo "🚀 启动 DeepNode Standalone Server..."
echo "   地址: http://127.0.0.1:$PORT/"
echo "   按 Ctrl+C 停止"
echo ""

# 延迟 1 秒后在后台打开浏览器（等 uvicorn 启动）
(sleep 1 && open "http://127.0.0.1:$PORT/" 2>/dev/null || true) &

# 前台运行 localserver，--standalone 模式
exec "$VENV_PATH/bin/python" main.py --standalone "${EXTRA_ARGS[@]}"
