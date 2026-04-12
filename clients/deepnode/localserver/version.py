"""DeepNode version — baked into the frozen binary at build time.

The placeholder below is replaced by build_standalone_mac.sh with the actual
version from the VERSION file. In development mode the placeholder is used as-is.

Security: this module is frozen into the PyInstaller binary, so the version
string cannot be tampered with by modifying external files (unlike VERSION).
"""

__version__ = "__DEEPNODE_VERSION_PLACEHOLDER__"


def get_version() -> str:
    """Return the DeepNode version string.

    In frozen builds this returns the build-time injected version (e.g. "__DEEPNODE_VERSION_PLACEHOLDER__").
    In development mode this falls back to reading the VERSION file.
    """
    if "PLACEHOLDER" not in __version__:
        return __version__

    # Development fallback: read from VERSION file
    from pathlib import Path
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.is_file():
        return version_file.read_text().strip()
    return "dev"
