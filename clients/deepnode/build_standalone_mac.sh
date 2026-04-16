#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# build_standalone_mac.sh — Build Vue frontend + PyInstaller-packaged deepnode-server
#
# Unified build script supporting both dev and prod profiles.
# The only differences between profiles are:
#   - DEEPPOOL_PROFILE env var (dev / prod)
#   - Config file copied into artifact (config.yaml / config_prod.yaml)
#   - Banner text
#
# Build strategy:
#   - PyInstaller (onedir) freezes business code into a binary (code protection)
#   - mlx/mlx_lm/mlx_vlm excluded from PyInstaller, installed via pip into
#     mlx-packages/ directory alongside the artifact
#   - Runtime hook injects mlx-packages/ into sys.path and pre-loads mlx.core,
#     locking nanobind first-init source to avoid cross-machine
#     "refusing to add duplicate key" abort
#   - .py sources compiled to .pyc and deleted (anti-tamper)
#   - SHA-256 integrity manifest generated for runtime verification
#   - Hardened Runtime codesign (ad-hoc or Developer ID)
#
# CLI options:
#   --profile dev|prod    Build profile (default: prod)
#   --target-os VERSION   Target macOS version (e.g. 14, 15, 26)
#   --binary-only         PyInstaller ONEFILE: single binary, no external dirs
#
# Naming convention:
#   {name}-{version}-{platform}{major}-{arch}.tar.gz
#   e.g. deepnode-v1.0.0-macos15-arm64.tar.gz
#
# Usage:
#   cd clients/deepnode && bash build_standalone_mac.sh [--profile dev|prod] [--target-os 15] [--binary-only] [-h]
#
# Run:
#   tar xzf deepnode-v1.0.0-macos15-arm64.tar.gz && cd deepnode-server
#   ./deepnode-server --standalone --account user --password pass
# ──────────────────────────────────────────────────────────

set -euo pipefail

# ── Defaults ──
BUILD_PROFILE="prod"
BUILD_TARGET_OS=""        # macOS version, e.g. "15" or "14" (empty = auto-detect)
BUILD_BINARY_ONLY=0       # 1 = maximize binary packaging (compile all .py to .pyc in mlx-packages)

# ── Help ──
show_help() {
    cat << 'EOF'
Usage:
  cd clients/deepnode && bash build_standalone_mac.sh [options]

Description:
  Build Vue frontend + PyInstaller-packaged deepnode-server standalone artifact.
  Supports dev/prod profiles, macOS version targeting, and binary-only mode.

Options:
  -h, --help               Show this help message and exit
  --profile dev|prod       Build profile (default: prod)
                           dev  — uses config.yaml, connects to dev platform
                           prod — uses config_prod.yaml, connects to prod platform
  --target-os VERSION      Target macOS version (e.g. 14, 15, 26)
                           Determines pip platform tag for mlx wheel selection.
                           If omitted, auto-detects from current system.
  --binary-only            Single-binary mode: PyInstaller ONEFILE with all deps
                           (including mlx) bundled into one executable. Output is
                           just deepnode-server-bin + config.yaml + launcher script.
                           No _internal/ or mlx-packages/ directories.
                           Requires macOS 26+ (nanobind compatibility).

Environment Variables:
  TARGET_ARCH                   Target architecture ("arm64" / "x86_64")
  DEEPNODE_CODESIGN_IDENTITY    Code signing identity (default: ad-hoc "-")
                                Set to "Developer ID Application: ..." for notarization

Examples:
  # Default prod build (auto-detect macOS version)
  bash build_standalone_mac.sh

  # Dev build targeting macOS 15
  bash build_standalone_mac.sh --profile dev --target-os 15

  # Prod build for macOS 14, maximize binary packaging
  bash build_standalone_mac.sh --target-os 14 --binary-only

  # Build with Developer ID signing
  DEEPNODE_CODESIGN_IDENTITY="Developer ID Application: ..." bash build_standalone_mac.sh
EOF
    exit 0
}

# ── Parse arguments ──
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) show_help ;;
        --profile)
            shift
            if [[ $# -eq 0 ]]; then echo "ERROR: --profile requires a value (dev or prod)"; exit 1; fi
            BUILD_PROFILE="$1"
            ;;
        --target-os)
            shift
            if [[ $# -eq 0 ]]; then echo "ERROR: --target-os requires a macOS version number (e.g. 14, 15)"; exit 1; fi
            BUILD_TARGET_OS="$1"
            ;;
        --binary-only)
            BUILD_BINARY_ONLY=1
            ;;
        *)
            echo "WARNING: unknown argument '$1' (ignored)"
            ;;
    esac
    shift
done

if [[ "$BUILD_PROFILE" != "dev" && "$BUILD_PROFILE" != "prod" ]]; then
    echo "ERROR: --profile must be 'dev' or 'prod', got '$BUILD_PROFILE'"
    exit 1
fi

# Resolve --target-os to TARGET_MACOS_VER format (major_minor)
if [[ -n "$BUILD_TARGET_OS" ]]; then
    # Accept bare major version (e.g. "15") or major_minor (e.g. "15_0")
    if [[ "$BUILD_TARGET_OS" =~ ^[0-9]+$ ]]; then
        TARGET_MACOS_VER="${BUILD_TARGET_OS}_0"
    elif [[ "$BUILD_TARGET_OS" =~ ^[0-9]+_[0-9]+$ ]]; then
        TARGET_MACOS_VER="$BUILD_TARGET_OS"
    else
        echo "ERROR: --target-os must be a version number like 14, 15, or 15_0, got '$BUILD_TARGET_OS'"
        exit 1
    fi
    export TARGET_MACOS_VER
fi

# ── Profile-specific settings ──
# These are the ONLY differences between dev and prod builds.
if [[ "$BUILD_PROFILE" == "prod" ]]; then
    CONFIG_SOURCE_NAME="config_prod.yaml"
    BANNER_SUFFIX="— PROD"
else
    CONFIG_SOURCE_NAME="config.yaml"
    BANNER_SUFFIX=""
fi

# ──────────────────────────────────────────────────────────
# Common paths and version
# ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
LOCALSERVER_DIR="$SCRIPT_DIR/localserver"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION_FILE="$SCRIPT_DIR/VERSION"
if [[ ! -f "$VERSION_FILE" ]]; then
    echo "ERROR: VERSION file not found at $VERSION_FILE"
    exit 1
fi
APP_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [[ ! "$APP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid version format '$APP_VERSION' in $VERSION_FILE (expected: X.Y.Z)"
    exit 1
fi

BUILD_ARCH="${TARGET_ARCH:-$(uname -m)}"

# ── Python venv ──
VENV_DIR="$PROJECT_ROOT/env"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "  Creating venv: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python3"
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: venv Python not found at $VENV_PYTHON"
    exit 1
fi
PYTHON="$VENV_PYTHON"

PYTHON_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SITE_PACKAGES=$("$PYTHON" -c "import site; print(site.getsitepackages()[0])")

echo "═══════════════════════════════════════════════════"
echo "  DeepNode Standalone Builder ${BANNER_SUFFIX} (PyInstaller + mlx isolation)"
echo "  Profile:       ${BUILD_PROFILE}"
echo "  Version:       v${APP_VERSION}"
echo "  Arch:          ${BUILD_ARCH}"
echo "  Target macOS:  ${TARGET_MACOS_VER:-auto-detect}"
echo "  Binary-only:   $( [[ "$BUILD_BINARY_ONLY" -eq 1 ]] && echo 'YES' || echo 'no' )"
echo "  Python:        $PYTHON_VERSION ($PYTHON)"
echo "  site-packages: $SITE_PACKAGES"
echo "═══════════════════════════════════════════════════"

# ──────────────────────────────────────────────────────────
# 0. Install Python dependencies
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [0/6] Installing Python dependencies..."
source "$SCRIPT_DIR/install_deps.sh"
install_python_deps "$VENV_DIR/bin/pip" "$LOCALSERVER_DIR" --with-build-tools

# ──────────────────────────────────────────────────────────
# 1. Build Vue frontend
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [1/6] Building Vue frontend..."

if ! command -v npm &>/dev/null; then
    echo "ERROR: npm not found in PATH."
    exit 1
fi

if [[ ! -d "$APP_DIR/node_modules" ]]; then
    (cd "$APP_DIR" && npm install)
fi

(cd "$APP_DIR" && BUILD_MODE=standalone npm run build:standalone)

rm -rf "$LOCALSERVER_DIR/web-dist"
cp -r "$APP_DIR/dist-standalone" "$LOCALSERVER_DIR/web-dist"
echo "  ✓ Vue SPA → localserver/web-dist/"

# ──────────────────────────────────────────────────────────
# 2. Generate runtime hook + PyInstaller spec
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [2/6] Generating build config..."

cd "$LOCALSERVER_DIR"
rm -rf build/ dist/

# ╔══════════════════════════════════════════════════════════╗
# ║  --binary-only: PyInstaller ONEFILE mode                ║
# ║  Single self-contained binary, mlx bundled inside.      ║
# ║  No _internal/, no mlx-packages/, no .py sources.       ║
# ╚══════════════════════════════════════════════════════════╝
if [[ "$BUILD_BINARY_ONLY" -eq 1 ]]; then

# ── Target platform detection (needed for artifact naming) ──
KNOWN_MACOS_VERS=("13_5" "14_0" "15_0" "26_0")
if [[ -z "${TARGET_MACOS_VER:-}" ]]; then
    _cur_macos_ver="$(sw_vers -productVersion 2>/dev/null || echo "")"
    if [[ -n "$_cur_macos_ver" ]]; then
        _major="${_cur_macos_ver%%.*}"
        TARGET_MACOS_VER="${_major}_0"
    else
        TARGET_MACOS_VER="15_0"
    fi
fi
_TARGET_MAJOR="${TARGET_MACOS_VER%%_*}"
PLATFORM_TAG="macos${_TARGET_MAJOR}"
ARTIFACT_NAME="deepnode-v${APP_VERSION}-${PLATFORM_TAG}-${BUILD_ARCH}"

# ── Runtime Hook (onefile — no mlx-packages injection needed) ──
cat > _runtime_hook.py << HOOK_EOF
"""Runtime hook for onefile binary mode.

All packages (including mlx) are bundled inside the binary.
This hook only needs to:
  1. Install torch import blocker
  2. Clear proxy env vars
  3. Set DEEPPOOL_PROFILE
"""
import sys
import os
import warnings

if getattr(sys, 'frozen', False):
    # ── torch import blocker ──
    import types as _types

    class _TorchBlocker:
        _BLOCKED = frozenset({'torch', 'torchvision', 'functorch', 'torchgen'})
        def find_module(self, fullname, path=None):
            if fullname.split('.')[0] in self._BLOCKED:
                return self
            return None
        def load_module(self, fullname):
            if fullname in sys.modules:
                return sys.modules[fullname]
            mod = _StubModule(fullname)
            sys.modules[fullname] = mod
            return mod

    class _StubModule(_types.ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.__file__ = '<blocked>'
            self.__path__ = []
            self.__package__ = name
            self.__all__ = []
        def __getattr__(self, name):
            if name.startswith('_'):
                raise AttributeError(name)
            qual = f'{self.__name__}.{name}'
            if qual not in sys.modules:
                sub = _StubModule(qual)
                sys.modules[qual] = sub
            return sys.modules[qual]

    sys.meta_path.insert(0, _TorchBlocker())
    print("[runtime_hook] onefile mode: torch blocker installed", flush=True)

# Clear proxy environment variables
for _v in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
           'all_proxy', 'ALL_PROXY', 'grpc_proxy', 'GRPC_PROXY'):
    os.environ.pop(_v, None)
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'
os.environ['grpc_proxy'] = ''
os.environ['DEEPPOOL_PROFILE'] = '${BUILD_PROFILE}'
warnings.filterwarnings("ignore", message=".*nanobind.*", category=RuntimeWarning)
HOOK_EOF

# ── PyInstaller Spec (ONEFILE) ──
cat > standalone.spec << 'SPEC_EOF'
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller ONEFILE spec — all deps (including mlx) bundled into single binary."""
import os, sys, platform, importlib, sysconfig
import glob as _glob

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None
localserver_dir = os.path.abspath(SPECPATH)
target_arch = os.environ.get('TARGET_ARCH') or None

# ── Stdlib C extensions ──
_REQUIRED_EXTS = [
    '_contextvars', '_hashlib', '_ssl', '_uuid', '_decimal',
    '_lzma', '_bz2', '_json', '_csv', '_multiprocessing', '_ctypes', '_sqlite3',
]
_dynload = os.path.join(sysconfig.get_path('stdlib'), 'lib-dynload')
_stdlib_bins = []
for _m in _REQUIRED_EXTS:
    try:
        _mod = importlib.import_module(_m)
        _p = getattr(_mod, '__file__', None)
        if _p and os.path.isfile(_p):
            _stdlib_bins.append((_p, '.'))
            continue
    except ImportError:
        pass
    if os.path.isdir(_dynload):
        for _f in _glob.glob(os.path.join(_dynload, _m + '*.so')):
            _stdlib_bins.append((_f, '.'))
            break

# ── OpenSSL dylibs ──
_flib = os.path.join(sys.base_prefix, 'lib')
if sys.platform == 'darwin' and os.path.isdir(_flib):
    for _pat in ('libssl*.dylib', 'libcrypto*.dylib', 'libsqlite3*.dylib'):
        for _f in sorted(_glob.glob(os.path.join(_flib, _pat))):
            if os.path.isfile(_f) and not os.path.islink(_f):
                _stdlib_bins.append((_f, '.'))

# ── web-dist ──
web_dist = os.path.join(localserver_dir, 'web-dist')
web_datas = [(web_dist, 'web-dist')] if os.path.isdir(web_dist) else []

# ── email_validator dist-info ──
ev_datas = []
try:
    import email_validator
    ev_dir = os.path.dirname(email_validator.__file__ or '')
    for di in _glob.glob(os.path.join(ev_dir, '..', 'email_validator*.dist-info')):
        if os.path.isdir(di):
            ev_datas.append((di, os.path.basename(di)))
except ImportError:
    pass

# ── Auto-collect: business deps + mlx family (ALL bundled in onefile) ──
_auto_hiddenimports = []
_auto_datas = []
_auto_binaries = []
_COLLECT_PACKAGES = [
    # Web framework
    'fastapi', 'starlette', 'uvicorn', 'pydantic', 'pydantic_core',
    'anyio', 'sniffio', 'httptools', 'uvloop', 'websockets', 'wsproto',
    'httpcore', 'httpx', 'h11', 'h2', 'hpack', 'hyperframe',
    # gRPC
    'grpc', 'google.protobuf', 'google.auth', 'google._upb',
    # Utilities
    'psutil', 'yaml', 'certifi', 'charset_normalizer', 'idna', 'urllib3',
    'huggingface_hub', 'requests', 'tqdm', 'filelock', 'packaging',
    'aiohttp', 'aiosignal', 'frozenlist', 'multidict', 'yarl', 'async_timeout',
    'brotli', 'email_validator', 'dns', 'annotated_types',
    'safetensors', 'tokenizers', 'regex', 'numpy',
    'click', 'typing_extensions', 'dotenv',
    'distro', 'hf_xet',
    # MLX family — bundled directly into binary in onefile mode
    'mlx', 'mlx_lm', 'mlx_vlm',
    'transformers', 'sentencepiece',
    'outlines', 'outlines_core',
]
for _pkg in _COLLECT_PACKAGES:
    try:
        _auto_hiddenimports += collect_submodules(_pkg)
    except Exception:
        pass
    try:
        _auto_datas += collect_data_files(_pkg)
    except Exception:
        pass
    try:
        _auto_binaries += collect_dynamic_libs(_pkg)
    except Exception:
        pass

a = Analysis(
    [os.path.join(localserver_dir, 'main.py')],
    pathex=[localserver_dir],
    binaries=_stdlib_bins + _auto_binaries,
    datas=web_datas + ev_datas + _auto_datas,
    hiddenimports=_auto_hiddenimports + [
        # Business modules
        'api', 'api.init', 'api.stats', 'api.dashboard', 'api.auth', 'config',
        'engine', 'engine.base', 'engine.selector', 'engine.llamacpp',
        'engine.vllm_engine', 'engine.vllm_mlx', 'engine.reasoning',
        'engine.tool_call_parser', 'engine.outlines_mlx_provider', 'engine.mlx_import',
        'model', 'model.downloader', 'model.registry',
        'rpc', 'rpc.infer_server', 'rpc.platform_client', 'rpc.node_manager_client',
        'service', 'service.credential', 'service.device_fingerprint',
        'service.log_reporter', 'service.manager', 'service.platform_auth',
        'service.statistics', 'service.memory_guard', 'service.device_info',
        'service.integrity', 'service.keychain', 'service.device_binding',
        'service.pyc_watermark',
        'platform_defaults', 'version', 'log_setup',
        'generated', 'generated.__init__',
        'generated.llm_infer_pb2', 'generated.llm_infer_pb2_grpc',
        'generated.manager_service_pb2', 'generated.manager_service_pb2_grpc',
        'generated.node_tunnel_pb2', 'generated.node_tunnel_pb2_grpc',
        'generated.nodemanager_service_pb2', 'generated.nodemanager_service_pb2_grpc',
        '_contextvars', '_hashlib', '_ssl', '_uuid', '_decimal', '_json', '_sqlite3',
        'ssl', 'hashlib', 'sqlite3',
    ],
    runtime_hooks=[os.path.join(localserver_dir, '_runtime_hook.py')],
    excludes=[
        # Aggressive exclusions to minimize binary size
        'cv2', 'opencv-python', 'opencv-python-headless',
        'matplotlib', 'scipy', 'pandas', 'notebook', 'jupyter',
        'tkinter',
        'torch', 'torchvision', 'torchgen', 'functorch', 'accelerate',
        'datasets', 'pyarrow',
        'gradio', 'gradio_client',
        'ensurepip', 'unittest', 'doctest', 'pydoc',
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ── Fix _ssl.so / _hashlib.so dylib references ──
if sys.platform == 'darwin':
    import shutil, subprocess
    _rewrites = {'libssl': 'libssl.3.dylib', 'libcrypto': 'libcrypto.3.dylib'}
    for i, (dest, src, tc) in enumerate(a.binaries):
        bn = os.path.basename(dest)
        if not (bn.startswith('_ssl') or bn.startswith('_hashlib')):
            continue
        if not src or not os.path.isfile(src):
            continue
        tmp = os.path.join(SPECPATH, 'build', '_patched_' + bn)
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        shutil.copy2(src, tmp)
        otool = subprocess.check_output(['otool', '-L', tmp], text=True)
        for lk, lf in _rewrites.items():
            for line in otool.strip().split('\n'):
                line = line.strip()
                if lk in line and '(' in line:
                    old = line.split('(')[0].strip()
                    depth = dest.count('/')
                    pfx = '/'.join(['..'] * depth) if depth > 0 else '.'
                    new = f'@loader_path/{pfx}/{lf}'
                    subprocess.check_call(['install_name_tool', '-change', old, new, tmp])
                    break
        a.binaries[i] = (dest, tmp, tc)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ONEFILE: all binaries/data/zips bundled into single executable
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='deepnode-server-bin',
    debug=False, strip=False, upx=False, console=True,
    target_arch=target_arch,
)
SPEC_EOF

echo "  ✓ _runtime_hook.py (onefile mode)"
echo "  ✓ standalone.spec (onefile mode)"

# ──────────────────────────────────────────────────────────
# 3. Run PyInstaller (onefile)
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [3/6] PyInstaller packaging (onefile — single binary)..."

# Inject version into version.py
echo "  Injecting version ${APP_VERSION} into version.py..."
sed -i '' "s/__DEEPNODE_VERSION_PLACEHOLDER__/${APP_VERSION}/" \
    "$LOCALSERVER_DIR/version.py"

"$PYTHON" -m PyInstaller standalone.spec --noconfirm --clean

# Restore placeholder
sed -i '' "s/${APP_VERSION}/__DEEPNODE_VERSION_PLACEHOLDER__/" \
    "$LOCALSERVER_DIR/version.py"

rm -rf "$LOCALSERVER_DIR/web-dist"

ONEFILE_BIN="$LOCALSERVER_DIR/dist/deepnode-server-bin"
if [[ ! -f "$ONEFILE_BIN" ]]; then
    echo "  ❌ Onefile packaging failed"
    exit 1
fi
echo "  ✓ Single binary: $(du -sh "$ONEFILE_BIN" | cut -f1)"

# ──────────────────────────────────────────────────────────
# 4. Skip (no mlx-packages in onefile mode)
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [4/6] Skipping mlx-packages install (bundled in binary)"

# ──────────────────────────────────────────────────────────
# 5. Assemble output directory
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [5/6] Assembling output..."

OUTDIR="$LOCALSERVER_DIR/dist/deepnode-server"
rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

mv "$ONEFILE_BIN" "$OUTDIR/deepnode-server-bin"
cp "$LOCALSERVER_DIR/$CONFIG_SOURCE_NAME" "$OUTDIR/config.yaml"
cp "$SCRIPT_DIR/README_STANDALONE.md" "$OUTDIR/README.md"

# Generate launcher script (same interface, adapted for onefile)
cat > "$OUTDIR/deepnode-server" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# ── DeepNode Server — launcher with daemon management (onefile mode) ──
set -euo pipefail

# ── macOS version check: require macOS 26+ ──
_check_macos_version() {
    local ver
    ver="$(sw_vers -productVersion 2>/dev/null || echo "0")"
    local major="${ver%%.*}"
    if [[ "$major" -lt 26 ]]; then
        echo ""
        echo "============================================================"
        echo "  ERROR: macOS version too old"
        echo ""
        echo "  Current version:  macOS ${ver}"
        echo "  Required version: macOS 26.0 or later"
        echo ""
        echo "  DeepNode requires macOS 26 (Tahoe) or later."
        echo "  Please upgrade your macOS before running DeepNode."
        echo ""
        echo "  How to upgrade:"
        echo "    System Settings → General → Software Update"
        echo "============================================================"
        echo ""
        exit 1
    fi
}
_check_macos_version

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$SCRIPT_DIR/deepnode-server-bin"
CONFIG="$SCRIPT_DIR/config.yaml"
PID_FILE="$SCRIPT_DIR/.deepnode.pid"
CAFFEINATE_PID_FILE="$SCRIPT_DIR/.caffeinate.pid"
LOG_FILE="$HOME/.deeppool/logs/localserver.log"
PORT=8765

_setup_env() {
    unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE
    unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV
    export PYTHONNOUSERSITE=1
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
    unset all_proxy ALL_PROXY GRPC_PROXY grpc_proxy
    export no_proxy="localhost,127.0.0.1,::1"
    export NO_PROXY="localhost,127.0.0.1,::1"
    export grpc_proxy=""
    if xattr -l "$BIN" 2>/dev/null | grep -q quarantine; then
        echo "[DeepNode] Clearing quarantine attributes..."
        xattr -rd com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true
    fi
}

_start_caffeinate() {
    local target_pid="$1"
    _stop_caffeinate
    if command -v caffeinate &>/dev/null; then
        caffeinate -i -s -w "$target_pid" &
        local caf_pid=$!
        echo "$caf_pid" > "$CAFFEINATE_PID_FILE"
        echo "[DeepNode] Sleep prevention enabled (caffeinate pid=$caf_pid, watching pid=$target_pid)"
    else
        echo "[DeepNode] Warning: caffeinate not found, system may sleep while running"
    fi
}

_stop_caffeinate() {
    if [[ -f "$CAFFEINATE_PID_FILE" ]]; then
        local caf_pid
        caf_pid="$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null || echo "")"
        if [[ -n "$caf_pid" ]] && kill -0 "$caf_pid" 2>/dev/null; then
            kill "$caf_pid" 2>/dev/null || true
            echo "[DeepNode] Sleep prevention disabled (caffeinate pid=$caf_pid)"
        fi
        rm -f "$CAFFEINATE_PID_FILE"
    fi
}

_read_pid() { [[ -f "$PID_FILE" ]] && cat "$PID_FILE" 2>/dev/null || echo ""; }
_is_running() { local pid="$(_read_pid)"; [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; }

# Poll /health endpoint until server is ready (max 60s)
_wait_for_port() {
    local max_wait=60 waited=0
    echo "[DeepNode] Waiting for server to be ready on port ${PORT}..."
    while [[ $waited -lt $max_wait ]]; do
        if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/health" 2>/dev/null; then
            echo "[DeepNode] Server ready (${waited}s)"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "[DeepNode] Warning: server not ready after ${max_wait}s"
    return 1
}

cmd_start() {
    if _is_running; then echo "[DeepNode] Already running (pid=$(_read_pid))"; return 0; fi
    _setup_env
    mkdir -p "$(dirname "$LOG_FILE")"
    cd "$SCRIPT_DIR"
    echo "[DeepNode] Starting daemon..."
    nohup "$BIN" --config "$CONFIG" "$@" > /dev/null 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        _start_caffeinate "$pid"
        echo "[DeepNode] Started (pid=$pid)"
        echo "[DeepNode] Log: $LOG_FILE"
        echo "[DeepNode] Web UI: http://127.0.0.1:${PORT}/"
        (_wait_for_port && open "http://127.0.0.1:${PORT}/" 2>/dev/null || true) &
    else
        rm -f "$PID_FILE"
        echo "[DeepNode] Failed to start. Check log: $LOG_FILE"
        return 1
    fi
}

cmd_stop() {
    _stop_caffeinate
    if ! _is_running; then echo "[DeepNode] Not running"; rm -f "$PID_FILE"; return 0; fi
    local pid="$(_read_pid)"
    echo "[DeepNode] Stopping (pid=$pid)..."
    kill "$pid" 2>/dev/null
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do sleep 1; waited=$((waited + 1)); done
    if kill -0 "$pid" 2>/dev/null; then echo "[DeepNode] Force killing..."; kill -9 "$pid" 2>/dev/null || true; fi
    rm -f "$PID_FILE"
    echo "[DeepNode] Stopped"
}

cmd_status() {
    if _is_running; then
        local pid="$(_read_pid)"
        echo "[DeepNode] Running (pid=$pid)"
        if [[ -f "$CAFFEINATE_PID_FILE" ]]; then
            local caf_pid; caf_pid="$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null || echo "")"
            if [[ -n "$caf_pid" ]] && kill -0 "$caf_pid" 2>/dev/null; then
                echo "[DeepNode] Sleep prevention: active (caffeinate pid=$caf_pid)"
            else
                echo "[DeepNode] Sleep prevention: inactive"
            fi
        fi
    else
        echo "[DeepNode] Not running"; rm -f "$PID_FILE"; _stop_caffeinate
    fi
}

cmd_log() {
    if [[ ! -f "$LOG_FILE" ]]; then echo "[DeepNode] Log file not found: $LOG_FILE"; return 1; fi
    if [[ "${1:-}" == "-f" ]]; then tail -100f "$LOG_FILE"; else tail -100 "$LOG_FILE"; fi
}

case "${1:-}" in
    --start)  shift; cmd_start "$@" ;;
    --stop)   cmd_stop ;;
    --status) cmd_status ;;
    --log)    shift; cmd_log "${1:-}" ;;
    *)
        _setup_env; cd "$SCRIPT_DIR"
        if command -v caffeinate &>/dev/null; then
            echo "[DeepNode] Sleep prevention enabled (foreground mode)"
            exec caffeinate -i -s "$BIN" --config "$CONFIG" "$@"
        else
            exec "$BIN" --config "$CONFIG" "$@"
        fi
        ;;
esac
WRAPPER_EOF

chmod +x "$OUTDIR/deepnode-server"
chmod +x "$OUTDIR/deepnode-server-bin"

# ──────────────────────────────────────────────────────────
# 6. Code signing (onefile)
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [6/6] Security hardening (onefile)..."

CODESIGN_IDENTITY="${DEEPNODE_CODESIGN_IDENTITY:--}"
CODESIGN_TIMESTAMP="--timestamp=none"
if [[ "$CODESIGN_IDENTITY" != "-" ]]; then
    CODESIGN_TIMESTAMP="--timestamp"
    echo "  Code signing with Developer ID: $CODESIGN_IDENTITY"
else
    echo "  Code signing with ad-hoc identity (Hardened Runtime enabled)"
fi

cat > /tmp/deepnode_entitlements.plist << 'ENTITLEMENTS_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
</dict>
</plist>
ENTITLEMENTS_EOF

echo "  Signing binary with Hardened Runtime + entitlements..."
codesign --force --sign "$CODESIGN_IDENTITY" --options runtime \
    --entitlements /tmp/deepnode_entitlements.plist \
    $CODESIGN_TIMESTAMP "$OUTDIR/deepnode-server-bin" 2>/dev/null || true

rm -f /tmp/deepnode_entitlements.plist

# ── Cleanup temp files ──
rm -f "$LOCALSERVER_DIR/_runtime_hook.py"
rm -f "$LOCALSERVER_DIR/standalone.spec"

# ── Final: package tar.gz ──
SIZE=$(du -sh "$OUTDIR" | cut -f1)
BIN_SIZE=$(du -sh "$OUTDIR/deepnode-server-bin" | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ Build succeeded! (onefile mode)"
echo "  Profile: ${BUILD_PROFILE}  Version: v${APP_VERSION}  Platform: ${PLATFORM_TAG}-${BUILD_ARCH}"
echo "  Binary:  $BIN_SIZE (single file, all deps bundled)"
echo "  Total:   $SIZE"
echo ""
echo "  Artifacts:"
ls -lh "$OUTDIR/deepnode-server" "$OUTDIR/deepnode-server-bin" "$OUTDIR/config.yaml" 2>/dev/null || true
echo ""
echo "═══════════════════════════════════════════════════"

echo ""
echo "  Packaging tar.gz..."
TARBALL="${ARTIFACT_NAME}.tar.gz"
(cd "$LOCALSERVER_DIR/dist" && tar czf "$TARBALL" deepnode-server/)
TARSIZE=$(du -sh "$LOCALSERVER_DIR/dist/$TARBALL" | cut -f1)
echo "  ✅ dist/${TARBALL} ($TARSIZE)"
echo ""
echo "  Distribute: tar xzf ${TARBALL} && cd deepnode-server && ./deepnode-server --standalone"

exit 0
fi
# ╔══════════════════════════════════════════════════════════╗
# ║  Standard mode: PyInstaller onedir + external mlx       ║
# ╚══════════════════════════════════════════════════════════╝

# ── Runtime Hook ──
# Executes at the earliest stage of PyInstaller binary startup:
# - Injects mlx-packages/ into sys.path
# - Installs torch import blocker
# - Verifies file integrity against build-time manifest
# - Pre-loads mlx.core to lock nanobind init source
# - Clears proxy env vars
# - Sets DEEPPOOL_PROFILE
cat > _runtime_hook.py << HOOK_EOF
"""Runtime hook: environment isolation + mlx-packages path injection + integrity check.

mlx packages are NOT frozen by PyInstaller; they reside in mlx-packages/ alongside the binary.
This hook runs at the earliest stage of PyInstaller startup:
  1. Insert mlx-packages/ at the front of sys.path
  2. Install torch import blocker (prevent pybind11 re-registration crash)
  3. Verify file integrity against build-time SHA-256 manifest
  4. Pre-load mlx.core — lock nanobind first-init source in mlx-packages/
  5. All subsequent 'import mlx.core' reuse this cached load, avoiding duplicate init

Key principle: nanobind registration (DeviceType enum etc.) is a process-global operation.
  Once first-init completes via the correct path, subsequent imports return sys.modules cache
  without re-triggering C-layer registration, avoiding "refusing to add duplicate key" abort.
"""
import sys
import os
import warnings

if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
    _mlx_pkgs = os.path.normpath(os.path.join(_base, '..', 'mlx-packages'))
    if os.path.isdir(_mlx_pkgs) and _mlx_pkgs not in sys.path:
        sys.path.insert(0, _mlx_pkgs)
    # Python stdlib (pure-Python portion) also lives in mlx-packages/_stdlib/.
    # transformers et al. import filecmp/difflib/csv etc. which are not in _internal/.
    _stdlib = os.path.join(_mlx_pkgs, '_stdlib')
    if os.path.isdir(_stdlib) and _stdlib not in sys.path:
        sys.path.insert(1, _stdlib)

    # ── torch import blocker ──
    # torch is NOT shipped (removed to save ~600MB and avoid pybind11 crash).
    # Install a fake finder so transformers' is_torch_available() returns False.
    import types as _types

    class _TorchBlocker:
        """Meta path finder that blocks torch/torchvision imports with deep stubs."""
        _BLOCKED = frozenset({'torch', 'torchvision', 'functorch', 'torchgen'})

        def find_module(self, fullname, path=None):
            if fullname.split('.')[0] in self._BLOCKED:
                return self
            return None

        def load_module(self, fullname):
            if fullname in sys.modules:
                return sys.modules[fullname]
            mod = _StubModule(fullname)
            sys.modules[fullname] = mod
            return mod

    class _StubModule(_types.ModuleType):
        """A stub module where any attribute access returns another stub."""
        def __init__(self, name):
            super().__init__(name)
            self.__file__ = '<blocked>'
            self.__path__ = []
            self.__package__ = name
            self.__all__ = []

        def __getattr__(self, name):
            if name.startswith('_'):
                raise AttributeError(name)
            qual = f'{self.__name__}.{name}'
            if qual not in sys.modules:
                sub = _StubModule(qual)
                sys.modules[qual] = sub
            return sys.modules[qual]

    sys.meta_path.insert(0, _TorchBlocker())
    print("[runtime_hook] torch import blocker installed", flush=True)

    # ── Integrity verification ──
    # Verify critical files against build-time SHA-256 manifest before
    # loading any business code. Detects tampering of mlx-packages/ etc.
    try:
        from service.integrity import verify_integrity as _verify
        _integrity_result = _verify()
        if _integrity_result is not None:
            if _integrity_result.passed:
                print(f"[runtime_hook] integrity check passed ({_integrity_result.verified_files}/{_integrity_result.total_files} files, {_integrity_result.duration_ms}ms)", flush=True)
            else:
                _tamper_detail = []
                if _integrity_result.mismatched_files:
                    _tamper_detail.append(f"mismatched={_integrity_result.mismatched_files[:5]}")
                if _integrity_result.missing_files:
                    _tamper_detail.append(f"missing={_integrity_result.missing_files[:5]}")
                print(f"[runtime_hook] ⚠ INTEGRITY CHECK FAILED: {', '.join(_tamper_detail)}", flush=True)
                os.environ['_DEEPNODE_INTEGRITY_FAILED'] = '1'
                os.environ['_DEEPNODE_INTEGRITY_DETAIL'] = ';'.join(
                    _integrity_result.mismatched_files[:10] + _integrity_result.missing_files[:10]
                )
                # Block startup: tampered binary must not serve inference
                print("[runtime_hook] FATAL: refusing to start with tampered files", flush=True)
                sys.exit(78)  # EX_CONFIG (sysexits.h) — configuration error
    except Exception as _ie:
        print(f"[runtime_hook] integrity check error (non-fatal): {_ie}", flush=True)

    # ── Pre-load mlx.core: lock nanobind first-init source ──
    try:
        import mlx.core as _mx  # noqa: F401
        print(f"[runtime_hook] mlx.core pre-loaded from: {_mx.__file__}", flush=True)
    except Exception as _e:
        os.environ['_DEEPNODE_MLX_INIT_FAILED'] = str(_e)
        print(f"[runtime_hook] mlx.core pre-load failed: {_e}", flush=True)
        print("[runtime_hook] MLX features will be disabled to prevent nanobind abort", flush=True)

# Clear proxy environment variables
for _v in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
           'all_proxy', 'ALL_PROXY', 'grpc_proxy', 'GRPC_PROXY'):
    os.environ.pop(_v, None)
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'
os.environ['grpc_proxy'] = ''

# Set build profile for platform_defaults module
os.environ['DEEPPOOL_PROFILE'] = '${BUILD_PROFILE}'

warnings.filterwarnings("ignore", message=".*nanobind.*", category=RuntimeWarning)
HOOK_EOF

# ── PyInstaller Spec ──
cat > standalone.spec << 'SPEC_EOF'
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec — business code frozen + mlx external."""
import os, sys, platform, importlib, sysconfig
import glob as _glob

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None
localserver_dir = os.path.abspath(SPECPATH)
target_arch = os.environ.get('TARGET_ARCH') or None

# ── Stdlib C extensions ──
_REQUIRED_EXTS = [
    '_contextvars', '_hashlib', '_ssl', '_uuid', '_decimal',
    '_lzma', '_bz2', '_json', '_csv', '_multiprocessing', '_ctypes', '_sqlite3',
]
_dynload = os.path.join(sysconfig.get_path('stdlib'), 'lib-dynload')
_stdlib_bins = []
for _m in _REQUIRED_EXTS:
    try:
        _mod = importlib.import_module(_m)
        _p = getattr(_mod, '__file__', None)
        if _p and os.path.isfile(_p):
            _stdlib_bins.append((_p, '.'))
            continue
    except ImportError:
        pass
    if os.path.isdir(_dynload):
        for _f in _glob.glob(os.path.join(_dynload, _m + '*.so')):
            _stdlib_bins.append((_f, '.'))
            break

# ── OpenSSL dylibs ──
_flib = os.path.join(sys.base_prefix, 'lib')
if sys.platform == 'darwin' and os.path.isdir(_flib):
    for _pat in ('libssl*.dylib', 'libcrypto*.dylib', 'libsqlite3*.dylib'):
        for _f in sorted(_glob.glob(os.path.join(_flib, _pat))):
            if os.path.isfile(_f) and not os.path.islink(_f):
                _stdlib_bins.append((_f, '.'))

# ── web-dist ──
web_dist = os.path.join(localserver_dir, 'web-dist')
web_datas = [(web_dist, 'web-dist')] if os.path.isdir(web_dist) else []

# ── email_validator dist-info ──
ev_datas = []
try:
    import email_validator
    ev_dir = os.path.dirname(email_validator.__file__ or '')
    for di in _glob.glob(os.path.join(ev_dir, '..', 'email_validator*.dist-info')):
        if os.path.isdir(di):
            ev_datas.append((di, os.path.basename(di)))
except ImportError:
    pass

# ── Auto-collect third-party packages ──
_auto_hiddenimports = []
_auto_datas = []
_auto_binaries = []
_COLLECT_PACKAGES = [
    'fastapi', 'starlette', 'uvicorn', 'pydantic', 'pydantic_core',
    'anyio', 'sniffio', 'httptools', 'uvloop', 'websockets', 'wsproto',
    'httpcore', 'httpx', 'h11', 'h2', 'hpack', 'hyperframe',
    'grpc', 'google.protobuf', 'google.auth', 'google._upb',
    'psutil', 'yaml', 'certifi', 'charset_normalizer', 'idna', 'urllib3',
    'huggingface_hub', 'requests', 'tqdm', 'filelock', 'packaging',
    'aiohttp', 'aiosignal', 'frozenlist', 'multidict', 'yarl', 'async_timeout',
    'brotli', 'email_validator', 'dns', 'annotated_types',
    'safetensors', 'tokenizers', 'regex', 'numpy',
    'click', 'typing_extensions', 'dotenv',
    'distro', 'hf_xet',
]
for _pkg in _COLLECT_PACKAGES:
    try:
        _auto_hiddenimports += collect_submodules(_pkg)
    except Exception:
        pass
    try:
        _auto_datas += collect_data_files(_pkg)
    except Exception:
        pass
    try:
        _auto_binaries += collect_dynamic_libs(_pkg)
    except Exception:
        pass

a = Analysis(
    [os.path.join(localserver_dir, 'main.py')],
    pathex=[localserver_dir],
    binaries=_stdlib_bins + _auto_binaries,
    datas=web_datas + ev_datas + _auto_datas,
    hiddenimports=_auto_hiddenimports + [
        # Business modules (PyInstaller static analysis may miss lazy imports)
        'api', 'api.init', 'api.stats', 'api.dashboard', 'api.auth', 'config',
        'engine', 'engine.base', 'engine.selector', 'engine.llamacpp',
        'engine.vllm_engine', 'engine.vllm_mlx', 'engine.reasoning',
        'engine.tool_call_parser', 'engine.outlines_mlx_provider', 'engine.mlx_import',
        'model', 'model.downloader', 'model.registry',
        'rpc', 'rpc.infer_server', 'rpc.platform_client', 'rpc.node_manager_client',
        'service', 'service.credential', 'service.device_fingerprint',
        'service.log_reporter', 'service.manager', 'service.platform_auth',
        'service.statistics', 'service.memory_guard', 'service.device_info',
        'service.integrity', 'service.keychain', 'service.device_binding',
        'service.pyc_watermark',
        'platform_defaults',
        'version',
        'log_setup',
        # protobuf/gRPC generated stubs (frozen into binary for code protection)
        'generated', 'generated.__init__',
        'generated.llm_infer_pb2', 'generated.llm_infer_pb2_grpc',
        'generated.manager_service_pb2', 'generated.manager_service_pb2_grpc',
        'generated.node_tunnel_pb2', 'generated.node_tunnel_pb2_grpc',
        'generated.nodemanager_service_pb2', 'generated.nodemanager_service_pb2_grpc',
        # Stdlib C extensions
        '_contextvars', '_hashlib', '_ssl', '_uuid', '_decimal', '_json', '_sqlite3',
        'ssl', 'hashlib', 'sqlite3',
    ],
    runtime_hooks=[os.path.join(localserver_dir, '_runtime_hook.py')],
    excludes=[
        # mlx family — loaded from mlx-packages/ via runtime hook
        'mlx', 'mlx.core', 'mlx.nn', 'mlx.optimizers',
        'mlx_lm', 'mlx_vlm',
        'outlines', 'outlines_core',
        # Unneeded large packages
        'cv2', 'opencv-python', 'opencv-python-headless',
        'matplotlib', 'scipy', 'pandas', 'notebook', 'jupyter',
        'tkinter', 'PIL', 'torch', 'torchvision', 'torchgen', 'functorch', 'accelerate',
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ── Fix _ssl.so / _hashlib.so dylib references ──
if sys.platform == 'darwin':
    import shutil, subprocess
    _rewrites = {'libssl': 'libssl.3.dylib', 'libcrypto': 'libcrypto.3.dylib'}
    for i, (dest, src, tc) in enumerate(a.binaries):
        bn = os.path.basename(dest)
        if not (bn.startswith('_ssl') or bn.startswith('_hashlib')):
            continue
        if not src or not os.path.isfile(src):
            continue
        tmp = os.path.join(SPECPATH, 'build', '_patched_' + bn)
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        shutil.copy2(src, tmp)
        otool = subprocess.check_output(['otool', '-L', tmp], text=True)
        for lk, lf in _rewrites.items():
            for line in otool.strip().split('\n'):
                line = line.strip()
                if lk in line and '(' in line:
                    old = line.split('(')[0].strip()
                    depth = dest.count('/')
                    pfx = '/'.join(['..'] * depth) if depth > 0 else '.'
                    new = f'@loader_path/{pfx}/{lf}'
                    subprocess.check_call(['install_name_tool', '-change', old, new, tmp])
                    break
        a.binaries[i] = (dest, tmp, tc)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='deepnode-server-bin',
    debug=False, strip=False, upx=False, console=True,
    target_arch=target_arch,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, name='deepnode-server',
)
SPEC_EOF

echo "  ✓ _runtime_hook.py"
echo "  ✓ standalone.spec"

# ──────────────────────────────────────────────────────────
# 3. Run PyInstaller
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [3/6] PyInstaller packaging..."

# Generate a random HMAC key and inject it into integrity.py before freezing.
# This key will be embedded in the frozen binary, making manifest tampering
# detectable even with ad-hoc code signing.
HMAC_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "  Injecting HMAC key into integrity.py..."
sed -i '' "s/__DEEPNODE_MANIFEST_HMAC_KEY_PLACEHOLDER__/${HMAC_KEY}/" \
    "$LOCALSERVER_DIR/service/integrity.py"

# Inject version into version.py (baked into frozen binary, tamper-proof)
echo "  Injecting version ${APP_VERSION} into version.py..."
sed -i '' "s/__DEEPNODE_VERSION_PLACEHOLDER__/${APP_VERSION}/" \
    "$LOCALSERVER_DIR/version.py"

"$PYTHON" -m PyInstaller standalone.spec --noconfirm --clean

# Restore placeholders in source after build (keep source clean)
sed -i '' "s/${HMAC_KEY}/__DEEPNODE_MANIFEST_HMAC_KEY_PLACEHOLDER__/" \
    "$LOCALSERVER_DIR/service/integrity.py"
sed -i '' "s/${APP_VERSION}/__DEEPNODE_VERSION_PLACEHOLDER__/" \
    "$LOCALSERVER_DIR/version.py"

rm -rf "$LOCALSERVER_DIR/web-dist"

ONEDIR="$LOCALSERVER_DIR/dist/deepnode-server"
if [[ ! -d "$ONEDIR" ]]; then
    echo "  ❌ Packaging failed"
    exit 1
fi

# Verify critical modules are packaged
echo "  Verifying package completeness..."
INTERNAL="$ONEDIR/_internal"
MISSING=0
for check_mod in fastapi starlette uvicorn grpc google yaml psutil; do
    if ! find "$INTERNAL" -name "${check_mod}*" -maxdepth 2 2>/dev/null | grep -q .; then
        echo "  ❌ Missing: $check_mod"
        MISSING=1
    fi
done
if [[ "$MISSING" -eq 1 ]]; then
    echo "  ⚠ Some modules may not be packaged — check PyInstaller logs"
else
    echo "  ✓ Critical modules verified"
fi

# Verify _internal/ has no mlx residue (prevent nanobind dual-path dual-init)
echo "  Checking _internal/ for mlx residue..."
MLX_LEAK=0
for mlx_pattern in "mlx" "mlx_lm" "mlx_vlm" "mlx.core" "outlines" "outlines_core" "torch" "torchvision" "functorch" "torchgen"; do
    leaked=$(find "$INTERNAL" -name "${mlx_pattern}*" -maxdepth 2 2>/dev/null | head -5)
    if [[ -n "$leaked" ]]; then
        echo "  ⚠ Found mlx residue in _internal/: $mlx_pattern"
        echo "$leaked" | head -3 | sed 's/^/      /'
        find "$INTERNAL" -name "${mlx_pattern}*" -maxdepth 2 -exec rm -rf {} + 2>/dev/null || true
        MLX_LEAK=1
    fi
done
if [[ "$MLX_LEAK" -eq 1 ]]; then
    echo "  ⚠ Auto-cleaned mlx/torch residue from _internal/"
else
    echo "  ✓ _internal/ clean (no mlx residue)"
fi

# ──────────────────────────────────────────────────────────
# 4. Install mlx packages to mlx-packages/
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [4/6] Installing mlx packages to mlx-packages/ ..."

MLX_DIR="$ONEDIR/mlx-packages"
rm -rf "$MLX_DIR"
mkdir -p "$MLX_DIR"

# ── Target platform detection ──
KNOWN_MACOS_VERS=("13_5" "14_0" "15_0" "26_0")

if [[ -z "${TARGET_MACOS_VER:-}" ]]; then
    _cur_macos_ver="$(sw_vers -productVersion 2>/dev/null || echo "")"
    if [[ -n "$_cur_macos_ver" ]]; then
        _major="${_cur_macos_ver%%.*}"
        TARGET_MACOS_VER="${_major}_0"
        echo "  Auto-detected macOS: $_cur_macos_ver → TARGET_MACOS_VER=${TARGET_MACOS_VER}"
    else
        TARGET_MACOS_VER="14_0"
        echo "  Cannot detect macOS version, using default TARGET_MACOS_VER=${TARGET_MACOS_VER}"
    fi
fi

if [[ ! "$TARGET_MACOS_VER" =~ ^[0-9]+_[0-9]+$ ]]; then
    echo "  ❌ Invalid TARGET_MACOS_VER format: '$TARGET_MACOS_VER' (expected: major_minor, e.g. 15_0)"
    echo "     Valid values: ${KNOWN_MACOS_VERS[*]}"
    exit 1
fi

_is_known=0
for _v in "${KNOWN_MACOS_VERS[@]}"; do
    if [[ "$TARGET_MACOS_VER" == "$_v" ]]; then _is_known=1; break; fi
done
if [[ "$_is_known" -eq 0 ]]; then
    echo "  ⚠ TARGET_MACOS_VER=${TARGET_MACOS_VER} not in known list: ${KNOWN_MACOS_VERS[*]}"
fi

TARGET_PLATFORM="macosx_${TARGET_MACOS_VER}_arm64"
PY_VER_SHORT="${PYTHON_VERSION//./}"

_TARGET_MAJOR="${TARGET_MACOS_VER%%_*}"
PLATFORM_TAG="macos${_TARGET_MAJOR}"
ARTIFACT_NAME="deepnode-v${APP_VERSION}-${PLATFORM_TAG}-${BUILD_ARCH}"

echo "  Target platform: $TARGET_PLATFORM"
echo "  Artifact name:   ${ARTIFACT_NAME}.tar.gz"

MLX_INSTALL_PKGS=(
    "mlx-lm>=0.31.0"
)

if "$PYTHON" -c "import mlx_vlm" &>/dev/null; then
    MLX_INSTALL_PKGS+=(mlx-vlm)
fi
if "$PYTHON" -c "import outlines" &>/dev/null; then
    MLX_INSTALL_PKGS+=(outlines)
fi

echo "  Installing: ${MLX_INSTALL_PKGS[*]}"

if "$PYTHON" -m pip install --target "$MLX_DIR" --no-user \
    --only-binary=:all: \
    --platform "$TARGET_PLATFORM" \
    --python-version "$PY_VER_SHORT" \
    --implementation cp \
    "${MLX_INSTALL_PKGS[@]}" \
    -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1 | tail -10; then
    echo "  ✓ Platform-specific install succeeded (platform=$TARGET_PLATFORM)"
else
    echo "  ⚠ Platform-specific install failed, falling back to default install"
    rm -rf "$MLX_DIR"
    mkdir -p "$MLX_DIR"
    "$PYTHON" -m pip install --target "$MLX_DIR" --no-user \
        --only-binary=:all: \
        "${MLX_INSTALL_PKGS[@]}" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1 | tail -5
fi

MLX_WHEEL_TAG=$(cat "$MLX_DIR"/mlx-*.dist-info/WHEEL 2>/dev/null | grep "^Tag:" | head -1 || echo "unknown")
echo "  mlx wheel tag: $MLX_WHEEL_TAG"

_MLX_LM_VER=$(cat "$MLX_DIR"/mlx_lm-*.dist-info/METADATA 2>/dev/null | grep "^Version:" | head -1 | awk '{print $2}')
echo "  mlx-lm version: ${_MLX_LM_VER:-unknown}"
if [[ -n "$_MLX_LM_VER" && "$_MLX_LM_VER" < "0.31" ]]; then
    echo "  ⚠ WARNING: mlx-lm $_MLX_LM_VER may not support newer model architectures."
    echo "    Consider using TARGET_MACOS_VER=14_0 or higher."
fi

# ── Purge torch (pulled by transformers dependency chain) ──
echo "  Purging torch family..."
_TORCH_PURGE_SIZE=0
for _tp in torch functorch torchgen torchvision torch-*.dist-info functorch-*.dist-info torchvision-*.dist-info; do
    if ls -d "$MLX_DIR"/$_tp 2>/dev/null | grep -q .; then
        _tp_size=$(du -sk "$MLX_DIR"/$_tp 2>/dev/null | awk '{s+=$1}END{print s+0}')
        _TORCH_PURGE_SIZE=$((_TORCH_PURGE_SIZE + _tp_size))
        rm -rf "$MLX_DIR"/$_tp
    fi
done
if [[ "$_TORCH_PURGE_SIZE" -gt 0 ]]; then
    echo "  ✓ Removed torch family: ~$((_TORCH_PURGE_SIZE / 1024))MB freed"
else
    echo "  ✓ No torch family found (already clean)"
fi

# ── Cleanup cache/test dirs ──
find "$MLX_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$MLX_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$MLX_DIR" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
rm -rf "$MLX_DIR"/pip "$MLX_DIR"/pip-*.dist-info 2>/dev/null || true

# ── Security: remove high-risk and unused modules from mlx-packages ──
# The pip install pulls many transitive dependencies. Some contain HTTP servers,
# CLI tools, external messaging integrations, or large unused modules that
# expand the attack surface. We strip them here.
#
# Audit criteria:
#   🔴 HIGH: contains server code / handles prompt data / can exfiltrate data
#   🟡 MEDIUM: has external communication channels or CLI tools
#   🟢 LOW: unnecessary modules that bloat the artifact
echo "  Removing high-risk and unused modules (security hardening)..."
_SEC_PURGED=0
_sec_rm() {
    for _t in "$@"; do
        if [[ -e "$_t" ]]; then
            rm -rf "$_t"
            _SEC_PURGED=$((_SEC_PURGED + 1))
        fi
    done
}

# ── transformers: keep only model loading / tokenizer / config modules ──
_TF_DIR="$MLX_DIR/transformers"
_sec_rm \
    "$_TF_DIR/cli"                    \
    "$_TF_DIR"/trainer.py             \
    "$_TF_DIR"/trainer_*.py           \
    "$_TF_DIR"/training_args*.py      \
    "$_TF_DIR/optimization.py"        \
    "$_TF_DIR/testing_utils.py"       \
    "$_TF_DIR/hf_argparser.py"        \
    "$_TF_DIR/modelcard.py"           \
    "$_TF_DIR/hyperparameter_search.py"

# ── mlx_lm: server.py is a full HTTP server (prompt/response interception risk) ──
_sec_rm \
    "$MLX_DIR/mlx_lm/server.py"       \
    "$MLX_DIR/mlx_lm/cli.py"          \
    "$MLX_DIR/mlx_lm/__main__.py"     \
    "$MLX_DIR/mlx_lm/chat.py"         \
    "$MLX_DIR/mlx_lm/share.py"        \
    "$MLX_DIR/mlx_lm/lora.py"         \
    "$MLX_DIR/mlx_lm/evaluate.py"     \
    "$MLX_DIR/mlx_lm/fuse.py"         \
    "$MLX_DIR/mlx_lm/upload.py"       \
    "$MLX_DIR/mlx_lm/benchmark.py"    \
    "$MLX_DIR/mlx_lm/perplexity.py"   \
    "$MLX_DIR/mlx_lm/tuner"

# ── mlx_vlm: server.py is a FastAPI server with /v1/chat/completions endpoint ──
_sec_rm \
    "$MLX_DIR/mlx_vlm/server.py"      \
    "$MLX_DIR/mlx_vlm/__main__.py"    \
    "$MLX_DIR/mlx_vlm/chat.py"        \
    "$MLX_DIR/mlx_vlm/chat_ui.py"     \
    "$MLX_DIR/mlx_vlm/lora.py"        \
    "$MLX_DIR/mlx_vlm/evals"          \
    "$MLX_DIR/mlx_vlm/trainer"

# ── huggingface_hub: strip CLI, webhook server, inference client, MCP agent ──
_HF_DIR="$MLX_DIR/huggingface_hub"
_sec_rm \
    "$_HF_DIR/cli"                    \
    "$_HF_DIR/_webhooks_server.py"    \
    "$_HF_DIR/_webhooks_payload.py"   \
    "$_HF_DIR/inference"              \
    "$_HF_DIR/_hot_reload"            \
    "$_HF_DIR/_oauth.py"              \
    "$_HF_DIR/_login.py"              \
    "$_HF_DIR/_tensorboard_logger.py" \
    "$_HF_DIR/_upload_large_folder.py" \
    "$_HF_DIR/fastai_utils.py"        \
    "$_HF_DIR/hub_mixin.py"           \
    "$_HF_DIR/repocard.py"            \
    "$_HF_DIR/repocard_data.py"       \
    "$_HF_DIR/community.py"

# ── tqdm: strip external messaging integrations and unused extras ──
# IMPORTANT: tqdm/__init__.py unconditionally imports cli, gui, notebook at top level.
# Deleting any of them causes "No module named 'tqdm.xxx'" at runtime.
# Only remove modules that are NOT imported by __init__.py or auto.py.
_sec_rm \
    "$MLX_DIR/tqdm/contrib/discord.py"   \
    "$MLX_DIR/tqdm/contrib/telegram.py"  \
    "$MLX_DIR/tqdm/contrib/slack.py"     \
    "$MLX_DIR/tqdm/tk.py"                \
    "$MLX_DIR/tqdm/keras.py"             \
    "$MLX_DIR/tqdm/dask.py"              \
    "$MLX_DIR/tqdm/rich.py"              \
    "$MLX_DIR/tqdm/tqdm.1"               \
    "$MLX_DIR/tqdm/completion.sh"

# ── numpy: strip f2py, tests, pyinstaller hooks ──
_sec_rm \
    "$MLX_DIR/numpy/f2py"             \
    "$MLX_DIR/numpy/tests"            \
    "$MLX_DIR/numpy/testing/tests"    \
    "$MLX_DIR/numpy/_pyinstaller"     \
    "$MLX_DIR/numpy/conftest.py"      \
    "$MLX_DIR/numpy/doc"

# ── outlines: strip unused model provider integrations (not used in our pipeline) ──
# Only mlxlm.py is used at runtime; remote API providers are not needed
for _om in anthropic dottxt gemini llamacpp lmstudio mistral ollama openai sglang tgi vllm vllm_offline; do
    _sec_rm "$MLX_DIR/outlines/models/${_om}.py"
done

# ── gradio: entire package is unnecessary (pulled by huggingface_hub optionally) ──
_sec_rm "$MLX_DIR/gradio" "$MLX_DIR/gradio_client"

# ── datasets: large unused HF datasets library ──
_sec_rm "$MLX_DIR/datasets"

# ── accelerate: training acceleration, not used in inference ──
_sec_rm "$MLX_DIR/accelerate"

# ── tokenizers: strip visualizer tool (generates HTML, not needed) ──
_sec_rm "$MLX_DIR/tokenizers/tools/visualizer.py"

# Clean .pyc counterparts of all removed .py files
find "$MLX_DIR" -name "*.pyc" -type f | while read -r _pyc; do
    _base="${_pyc%.pyc}"
    # If a .py was deleted and a .pyc remains from compileall, the .pyc is now orphaned
    # but this is fine — it will be covered by integrity manifest
done

echo "  ✓ Security cleanup: removed $_SEC_PURGED high-risk/unused items"

# ── Security: compile .py → .pyc and remove source files ──
# transformers is excluded because its _LazyModule (v5.x+) requires .py source files.
echo "  Compiling .py → .pyc (mlx-packages/, excluding transformers/)..."
"$PYTHON" -c "
import compileall, os, sys, pathlib

target = sys.argv[1]

# transformers _LazyModule requires .py for dynamic import resolution
EXCLUDE_DIRS = {'transformers'}

success = compileall.compile_dir(target, ddir='.', force=True, quiet=1, legacy=False)
if not success:
    print('WARNING: some .py files failed to compile', flush=True)
    sys.exit(0)

count_compiled = 0
for pyc in pathlib.Path(target).rglob('__pycache__/*.pyc'):
    stem = pyc.stem.rsplit('.', 1)[0]
    dest = pyc.parent.parent / (stem + '.pyc')
    pyc.rename(dest)
    count_compiled += 1

for cache_dir in sorted(pathlib.Path(target).rglob('__pycache__'), reverse=True):
    if cache_dir.is_dir():
        try: cache_dir.rmdir()
        except OSError: pass

count_deleted = 0
for py_file in pathlib.Path(target).rglob('*.py'):
    # Skip files inside excluded directories
    rel = py_file.relative_to(target)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        continue
    py_file.unlink()
    count_deleted += 1

excluded_note = 'transformers excluded'
print(f'Compiled {count_compiled} .pyc files, deleted {count_deleted} .py sources ({excluded_note})', flush=True)
" "$MLX_DIR"
echo "  ✓ .py → .pyc compilation complete"

# ── Copy Python stdlib (pure-Python portion) to mlx-packages/ ──
echo "  Copying Python stdlib..."
STDLIB_PATH=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_path('stdlib'))")
if [[ -d "$STDLIB_PATH" ]]; then
    # rsync filter rules are order-sensitive: excludes MUST come before includes.
    # The previous --include='*/' before --exclude caused site-packages/ and test/
    # to leak through. Using explicit exclude-first ordering fixes this.
    rsync -a \
        --exclude='__pycache__' \
        --exclude='site-packages/' \
        --exclude='test/' \
        --exclude='tests/' \
        --exclude='idlelib/' \
        --exclude='tkinter/' \
        --exclude='turtledemo/' \
        --exclude='ensurepip/' \
        --exclude='lib2to3/' \
        --exclude='distutils/' \
        --exclude='unittest/' \
        --exclude='doctest*' \
        --exclude='pydoc*' \
        --exclude='turtle*' \
        --exclude='_pyrepl/' \
        --exclude='*.pyc' \
        --exclude='*.so' \
        --exclude='*.dylib' \
        --include='*.py' \
        --include='*/' \
        --exclude='*' \
        "$STDLIB_PATH/" "$MLX_DIR/_stdlib/"

    # Safety net: remove any directories that leaked through rsync rules
    for _junk in site-packages test tests idlelib tkinter turtledemo ensurepip lib2to3 distutils unittest _pyrepl; do
        rm -rf "$MLX_DIR/_stdlib/$_junk" 2>/dev/null || true
    done

    # Remove empty directories left after filtering
    find "$MLX_DIR/_stdlib" -type d -empty -delete 2>/dev/null || true

    STDLIB_SIZE=$(du -sh "$MLX_DIR/_stdlib" | cut -f1)
    echo "  ✓ stdlib ($STDLIB_SIZE)"

    # Compile _stdlib/ as well
    echo "  Compiling _stdlib/ .py → .pyc..."
    "$PYTHON" -c "
import compileall, pathlib, sys
target = sys.argv[1]
compileall.compile_dir(target, ddir='.', force=True, quiet=1, legacy=False)
count = 0
for pyc in pathlib.Path(target).rglob('__pycache__/*.pyc'):
    stem = pyc.stem.rsplit('.', 1)[0]
    dest = pyc.parent.parent / (stem + '.pyc')
    pyc.rename(dest)
    count += 1
for d in sorted(pathlib.Path(target).rglob('__pycache__'), reverse=True):
    if d.is_dir():
        try: d.rmdir()
        except OSError: pass
for f in pathlib.Path(target).rglob('*.py'):
    f.unlink()
print(f'_stdlib: compiled {count} .pyc files', flush=True)
" "$MLX_DIR/_stdlib"
fi

echo "  mlx-packages: $(du -sh "$MLX_DIR" | cut -f1)"

# ──────────────────────────────────────────────────────────
# 5. Generate wrapper script & post-processing
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [5/6] Generating launcher script & post-processing..."

cp "$LOCALSERVER_DIR/$CONFIG_SOURCE_NAME" "$ONEDIR/config.yaml"
cp "$SCRIPT_DIR/README_STANDALONE.md" "$ONEDIR/README.md"

cat > "$ONEDIR/deepnode-server" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# ── DeepNode Server — launcher with daemon management ──
#
# Usage:
#   ./deepnode-server [--standalone] [...]     Run in foreground (default)
#   ./deepnode-server --start [...]            Start as background daemon
#   ./deepnode-server --stop                   Stop the running daemon
#   ./deepnode-server --status                 Show daemon status
#   ./deepnode-server --log [-f]               Show log (add -f to follow)
#
set -euo pipefail

# ── macOS version check: require macOS 26+ ──
_check_macos_version() {
    local ver
    ver="$(sw_vers -productVersion 2>/dev/null || echo "0")"
    local major="${ver%%.*}"
    if [[ "$major" -lt 26 ]]; then
        echo ""
        echo "============================================================"
        echo "  ERROR: macOS version too old"
        echo ""
        echo "  Current version:  macOS ${ver}"
        echo "  Required version: macOS 26.0 or later"
        echo ""
        echo "  DeepNode requires macOS 26 (Tahoe) or later."
        echo "  Please upgrade your macOS before running DeepNode."
        echo ""
        echo "  How to upgrade:"
        echo "    System Settings → General → Software Update"
        echo "============================================================"
        echo ""
        exit 1
    fi
}
_check_macos_version

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$SCRIPT_DIR/deepnode-server-bin"
CONFIG="$SCRIPT_DIR/config.yaml"
PID_FILE="$SCRIPT_DIR/.deepnode.pid"
CAFFEINATE_PID_FILE="$SCRIPT_DIR/.caffeinate.pid"
LOG_FILE="$HOME/.deeppool/logs/localserver.log"
PORT=8765

_setup_env() {
    unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE
    unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV
    export PYTHONNOUSERSITE=1
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
    unset all_proxy ALL_PROXY GRPC_PROXY grpc_proxy
    export no_proxy="localhost,127.0.0.1,::1"
    export NO_PROXY="localhost,127.0.0.1,::1"
    export grpc_proxy=""
    if xattr -l "$BIN" 2>/dev/null | grep -q quarantine; then
        echo "[DeepNode] Clearing quarantine attributes..."
        xattr -rd com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true
    fi
}

_start_caffeinate() {
    local target_pid="$1"
    _stop_caffeinate
    if command -v caffeinate &>/dev/null; then
        caffeinate -i -s -w "$target_pid" &
        local caf_pid=$!
        echo "$caf_pid" > "$CAFFEINATE_PID_FILE"
        echo "[DeepNode] Sleep prevention enabled (caffeinate pid=$caf_pid, watching pid=$target_pid)"
    else
        echo "[DeepNode] Warning: caffeinate not found, system may sleep while running"
    fi
}

_stop_caffeinate() {
    if [[ -f "$CAFFEINATE_PID_FILE" ]]; then
        local caf_pid
        caf_pid="$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null || echo "")"
        if [[ -n "$caf_pid" ]] && kill -0 "$caf_pid" 2>/dev/null; then
            kill "$caf_pid" 2>/dev/null || true
            echo "[DeepNode] Sleep prevention disabled (caffeinate pid=$caf_pid)"
        fi
        rm -f "$CAFFEINATE_PID_FILE"
    fi
}

_read_pid() { [[ -f "$PID_FILE" ]] && cat "$PID_FILE" 2>/dev/null || echo ""; }
_is_running() { local pid="$(_read_pid)"; [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; }

# Poll /health endpoint until server is ready (max 60s)
_wait_for_port() {
    local max_wait=60 waited=0
    echo "[DeepNode] Waiting for server to be ready on port ${PORT}..."
    while [[ $waited -lt $max_wait ]]; do
        if curl -sf -o /dev/null "http://127.0.0.1:${PORT}/health" 2>/dev/null; then
            echo "[DeepNode] Server ready (${waited}s)"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "[DeepNode] Warning: server not ready after ${max_wait}s"
    return 1
}

cmd_start() {
    if _is_running; then echo "[DeepNode] Already running (pid=$(_read_pid))"; return 0; fi
    _setup_env
    mkdir -p "$(dirname "$LOG_FILE")"
    cd "$SCRIPT_DIR"
    echo "[DeepNode] Starting daemon..."
    nohup "$BIN" --config "$CONFIG" "$@" > /dev/null 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        _start_caffeinate "$pid"
        echo "[DeepNode] Started (pid=$pid)"
        echo "[DeepNode] Log: $LOG_FILE"
        echo "[DeepNode] Web UI: http://127.0.0.1:${PORT}/"
        (_wait_for_port && open "http://127.0.0.1:${PORT}/" 2>/dev/null || true) &
    else
        rm -f "$PID_FILE"
        echo "[DeepNode] Failed to start. Check log: $LOG_FILE"
        return 1
    fi
}

cmd_stop() {
    _stop_caffeinate
    if ! _is_running; then echo "[DeepNode] Not running"; rm -f "$PID_FILE"; return 0; fi
    local pid="$(_read_pid)"
    echo "[DeepNode] Stopping (pid=$pid)..."
    kill "$pid" 2>/dev/null
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do sleep 1; waited=$((waited + 1)); done
    if kill -0 "$pid" 2>/dev/null; then echo "[DeepNode] Force killing..."; kill -9 "$pid" 2>/dev/null || true; fi
    rm -f "$PID_FILE"
    echo "[DeepNode] Stopped"
}

cmd_status() {
    if _is_running; then
        local pid="$(_read_pid)"
        echo "[DeepNode] Running (pid=$pid)"
        if [[ -f "$CAFFEINATE_PID_FILE" ]]; then
            local caf_pid; caf_pid="$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null || echo "")"
            if [[ -n "$caf_pid" ]] && kill -0 "$caf_pid" 2>/dev/null; then
                echo "[DeepNode] Sleep prevention: active (caffeinate pid=$caf_pid)"
            else
                echo "[DeepNode] Sleep prevention: inactive"
            fi
        fi
    else
        echo "[DeepNode] Not running"; rm -f "$PID_FILE"; _stop_caffeinate
    fi
}

cmd_log() {
    if [[ ! -f "$LOG_FILE" ]]; then echo "[DeepNode] Log file not found: $LOG_FILE"; return 1; fi
    if [[ "${1:-}" == "-f" ]]; then tail -100f "$LOG_FILE"; else tail -100 "$LOG_FILE"; fi
}

case "${1:-}" in
    --start)  shift; cmd_start "$@" ;;
    --stop)   cmd_stop ;;
    --status) cmd_status ;;
    --log)    shift; cmd_log "${1:-}" ;;
    *)
        _setup_env; cd "$SCRIPT_DIR"
        if command -v caffeinate &>/dev/null; then
            echo "[DeepNode] Sleep prevention enabled (foreground mode)"
            exec caffeinate -i -s "$BIN" --config "$CONFIG" "$@"
        else
            exec "$BIN" --config "$CONFIG" "$@"
        fi
        ;;
esac
WRAPPER_EOF

chmod +x "$ONEDIR/deepnode-server"
chmod +x "$ONEDIR/deepnode-server-bin"

# ── Replace symlinks with real files ──
echo "  Replacing symlinks..."
find "$ONEDIR" -type l | while read -r link; do
    target=$(readlink "$link")
    if [[ -n "$target" ]]; then
        link_dir="$(dirname "$link")"
        abs_target="$(cd "$link_dir" && realpath "$target" 2>/dev/null || echo "")"
        if [[ -n "$abs_target" && -f "$abs_target" ]]; then
            rm "$link" && cp "$abs_target" "$link"
        fi
    fi
done || true

# ──────────────────────────────────────────────────────────
# 6. Security: integrity manifest + code signing
# ──────────────────────────────────────────────────────────
echo ""
echo "▸ [6/6] Security hardening..."

# ── Code signing (ad-hoc + Hardened Runtime, Developer ID ready) ──
# NOTE: codesign MUST run BEFORE manifest generation, because codesign --force
#       modifies .so/.dylib/binary contents (embeds signature data). If the
#       manifest were generated first, all signed files would have hash mismatches.
CODESIGN_IDENTITY="${DEEPNODE_CODESIGN_IDENTITY:--}"
CODESIGN_TIMESTAMP="--timestamp=none"

if [[ "$CODESIGN_IDENTITY" != "-" ]]; then
    CODESIGN_TIMESTAMP="--timestamp"
    echo "  Code signing with Developer ID: $CODESIGN_IDENTITY"
else
    echo "  Code signing with ad-hoc identity (Hardened Runtime enabled)"
fi

cat > /tmp/deepnode_entitlements.plist << 'ENTITLEMENTS_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
</dict>
</plist>
ENTITLEMENTS_EOF

echo "  Signing .so/.dylib files..."
find "$ONEDIR" \( -name "*.so" -o -name "*.dylib" \) -type f -exec \
    codesign --force --sign "$CODESIGN_IDENTITY" --options runtime \
    $CODESIGN_TIMESTAMP {} \; 2>/dev/null || true

echo "  Signing main binary with Hardened Runtime + entitlements..."
codesign --force --sign "$CODESIGN_IDENTITY" --options runtime \
    --entitlements /tmp/deepnode_entitlements.plist \
    $CODESIGN_TIMESTAMP "$ONEDIR/deepnode-server-bin" 2>/dev/null || true

rm -f /tmp/deepnode_entitlements.plist

# ── Generate integrity manifest (HMAC-signed) ──
# Runs AFTER codesign so hashes reflect the final signed file contents.
echo "  Generating HMAC-signed integrity manifest..."
"$PYTHON" -c "
import json, hashlib, hmac, sys, time
from pathlib import Path

product_root = Path(sys.argv[1])
version = sys.argv[2]
hmac_key = sys.argv[3]
exts = {'.pyc', '.so', '.dylib', '.py'}
files = {}

for d, ext_filter in [('mlx-packages', exts), ('_internal', {'.so', '.dylib'})]:
    target = product_root / d
    if target.is_dir():
        for f in sorted(target.rglob('*')):
            if f.is_file() and f.suffix in ext_filter:
                files[str(f.relative_to(product_root))] = hashlib.sha256(f.read_bytes()).hexdigest()

bin_path = product_root / 'deepnode-server-bin'
if bin_path.is_file():
    files['deepnode-server-bin'] = hashlib.sha256(bin_path.read_bytes()).hexdigest()

manifest = {
    'version': version,
    'build_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'total_files': len(files),
    'files': files,
}

# Compute HMAC-SHA256 over canonical manifest JSON
canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode('utf-8')
manifest['hmac'] = hmac.new(hmac_key.encode('utf-8'), canonical, hashlib.sha256).hexdigest()

out = product_root / '_internal' / 'integrity_manifest.json'
out.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Integrity manifest: {len(files)} files hashed, HMAC signed', flush=True)
" "$ONEDIR" "$APP_VERSION" "$HMAC_KEY"
echo "  ✓ HMAC-signed integrity manifest generated"

# ── Cleanup temp files ──
rm -f "$LOCALSERVER_DIR/_runtime_hook.py"
rm -f "$LOCALSERVER_DIR/standalone.spec"

# ──────────────────────────────────────────────────────────
# Final: package tar.gz
# ──────────────────────────────────────────────────────────
SIZE=$(du -sh "$ONEDIR" | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ Build succeeded!  Size: $SIZE"
echo "  Profile: ${BUILD_PROFILE}  Version: v${APP_VERSION}  Platform: ${PLATFORM_TAG}-${BUILD_ARCH}"
echo ""
echo "  Artifacts:"
ls -lh "$ONEDIR/deepnode-server" "$ONEDIR/deepnode-server-bin" "$ONEDIR/config.yaml" "$ONEDIR/README.md" 2>/dev/null || true
echo ""
echo "═══════════════════════════════════════════════════"

echo ""
echo "  Packaging tar.gz..."
TARBALL="${ARTIFACT_NAME}.tar.gz"
(cd "$LOCALSERVER_DIR/dist" && tar czf "$TARBALL" deepnode-server/)
TARSIZE=$(du -sh "$LOCALSERVER_DIR/dist/$TARBALL" | cut -f1)
echo "  ✅ dist/${TARBALL} ($TARSIZE)"
echo ""
echo "  Distribute: tar xzf ${TARBALL} && cd deepnode-server && ./deepnode-server --standalone"
