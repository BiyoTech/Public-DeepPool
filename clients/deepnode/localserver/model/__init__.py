"""Model management — download and local path resolution."""

from .downloader import download_model, download_model_hf
from .registry import resolve_model_dir

__all__ = ["download_model", "download_model_hf", "resolve_model_dir"]
