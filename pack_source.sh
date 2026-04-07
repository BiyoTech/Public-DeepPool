#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# pack_source.sh — 打包 DeepPool 工程源代码
#
# 排除 .gitignore 中指定的目录/文件以及其他非源码产物。
# 产物: DeepPool-source-<日期>.tar.gz
# ──────────────────────────────────────────────────

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"
DATE_TAG="$(date +%Y%m%d)"
OUTPUT="$PROJECT_ROOT/${PROJECT_NAME}-source-${DATE_TAG}.tar.gz"

echo "打包 $PROJECT_NAME 源代码..."
echo "  项目目录: $PROJECT_ROOT"

tar czf "$OUTPUT" \
    -C "$(dirname "$PROJECT_ROOT")" \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='dist' \
    --exclude='bin' \
    --exclude='*.test' \
    --exclude='*.out' \
    --exclude='venv' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='src-tauri/target' \
    --exclude='src-tauri/binaries' \
    --exclude='src-tauri/build' \
    --exclude='src-tauri/dist' \
    --exclude='.build_venv' \
    --exclude='.DS_Store' \
    --exclude='env' \
    --exclude='*.tar.gz' \
    "$PROJECT_NAME"

SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo "  ✅ $OUTPUT ($SIZE)"
