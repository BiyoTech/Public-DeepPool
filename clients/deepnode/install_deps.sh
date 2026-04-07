#!/bin/bash
# ──────────────────────────────────────────────────────────
# install_deps.sh — 自动检测平台并安装所有 Python 依赖
#
# 被 run_standalone.sh 和 build_standalone.sh 共同调用。
# 逻辑:
#   1. 安装 requirements.txt 中的核心依赖
#   2. 检测当前机型，自动安装对应的推理引擎依赖:
#      - macOS Apple Silicon (M系列) → mlx-lm, mlx-vlm, outlines
#      - macOS Intel                 → llama-cpp-python
#      - Linux                       → vllm
#   3. 安装构建工具（如需要）
#
# 用法:
#   source install_deps.sh <venv_python> <localserver_dir> [--with-build-tools]
# ──────────────────────────────────────────────────────────

install_python_deps() {
    local VENV_PIP="$1"
    local LOCALSERVER_DIR="$2"
    local WITH_BUILD_TOOLS="${3:-}"

    if [[ ! -x "$VENV_PIP" ]]; then
        echo "ERROR: pip not found at $VENV_PIP"
        return 1
    fi

    # ── 1. 核心依赖 ──
    echo "  📦 安装核心依赖 (requirements.txt)..."
    "$VENV_PIP" install -q -r "$LOCALSERVER_DIR/requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

    # ── 2. 检测平台，安装推理引擎依赖 ──
    local SYSTEM
    SYSTEM="$(uname -s)"
    local ARCH
    ARCH="$(uname -m)"

    if [[ "$SYSTEM" == "Darwin" ]]; then
        if [[ "$ARCH" == "arm64" ]]; then
            # macOS Apple Silicon (M系列)
            echo "  🍎 检测到 macOS Apple Silicon ($ARCH)"
            echo "  📦 安装 MLX 推理引擎依赖..."
            "$VENV_PIP" install -q \
                "mlx-lm>=0.31.0" \
                "mlx-vlm>=0.1.0" \
                "outlines" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
            echo "  ✓ mlx-lm, mlx-vlm, outlines 已安装"
        else
            # macOS Intel
            echo "  🖥️  检测到 macOS Intel ($ARCH)"
            echo "  📦 安装 llama.cpp 推理引擎依赖..."
            "$VENV_PIP" install -q "llama-cpp-python>=0.3.0" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
            echo "  ✓ llama-cpp-python 已安装"
        fi
    elif [[ "$SYSTEM" == "Linux" ]]; then
        echo "  🐧 检测到 Linux ($ARCH)"
        echo "  📦 安装 vLLM 推理引擎依赖..."
        "$VENV_PIP" install -q "vllm>=0.17.1" "distro" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
        echo "  ✓ vllm, distro 已安装"
    else
        echo "  ⚠️  未知平台 $SYSTEM，跳过推理引擎依赖安装"
    fi

    # ── 3. 构建工具（可选）──
    if [[ "$WITH_BUILD_TOOLS" == "--with-build-tools" ]]; then
        echo "  📦 安装构建工具 (PyInstaller, grpcio-tools)..."
        "$VENV_PIP" install -q pyinstaller "grpcio-tools>=1.68.0" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
        echo "  ✓ 构建工具已安装"
    fi

    echo "  ✅ 所有 Python 依赖安装完成"
}
