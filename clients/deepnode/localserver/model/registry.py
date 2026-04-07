"""模型本地路径解析工具。

所有模型元信息（名称、仓库 ID、下载地址等）均由 platform manager 下发，
本模块仅提供本地路径计算，不再硬编码任何模型列表。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认模型存储根目录（可被后端下发的 model_base_dir 覆盖）
DEFAULT_MODEL_BASE_DIR = "~/.deeppool/models"


def resolve_model_base_dir(base_dir: str | None = None) -> Path:
    """解析并创建模型存储根目录。"""
    target = Path(base_dir or DEFAULT_MODEL_BASE_DIR).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def resolve_model_dir(model_name: str, base_dir: str | None = None) -> Path:
    """解析模型在本地的存储目录。

    Args:
        model_name: 模型短名称，用作子目录名，如 "Qwen2-7B-Instruct"。
        base_dir: 模型存储根目录，默认 ~/.deeppool/models。

    Returns:
        模型本地存储目录路径。
    """
    if not model_name or not model_name.strip():
        raise ValueError("model_name is required")

    root = resolve_model_base_dir(base_dir)
    subdir = model_name.strip()
    model_dir = (root / subdir).resolve()

    # 路径穿越检查
    if root not in model_dir.parents and model_dir != root:
        raise ValueError(f"invalid model directory: {subdir}")

    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info("resolved model dir model=%s path=%s", model_name, model_dir)
    return model_dir
