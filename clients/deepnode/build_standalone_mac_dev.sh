#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# build_standalone_mac_dev.sh — 构建 Vue 前端 + PyInstaller 打包 deepnode-server（开发环境）
#
# 打包策略:
#   - PyInstaller (onedir) 打包业务代码为 frozen 二进制（代码保护）
#   - mlx/mlx_lm/mlx_vlm 从 PyInstaller 中排除，直接复制 site-packages
#     到产物的 mlx-packages/ 目录
#   - 启动时 runtime hook 将 mlx-packages/ 插入 sys.path 并预加载 mlx.core，
#     锁定 nanobind 首次初始化来源，彻底避免跨机器运行时
#     "refusing to add duplicate key" abort
#   - engine/mlx_import.py 仅做幂等校验，绝不 delete+reimport
#
# 命名规范:
#   {软件名}-{版本}-{平台}{系统主版本}-{架构}.tar.gz
#   例如: deepnode-v1.0.0-macos15-arm64.tar.gz
#
# 产物: deepnode-v{VER}-{PLATFORM}-{ARCH}.tar.gz 包含:
#   - deepnode-server        shell wrapper（启动入口）
#   - deepnode-server-bin    PyInstaller 二进制
#   - config.yaml            用户可修改配置
#   - VERSION                版本号文件
#   - README.md              运行说明、系统要求、Q&A
#   - _internal/             PyInstaller 运行时依赖
#   - mlx-packages/          mlx 系列原生 Python 包
#
# 用法:
#   cd clients/deepnode && bash build_standalone_mac_dev.sh
#
# 运行:
#   tar xzf deepnode-v1.0.0-macos15-arm64.tar.gz && cd deepnode-server
#   ./deepnode-server --standalone --account user --password pass
# ──────────────────────────────────────────────────────────

set -euo pipefail

# ── 帮助信息 ──
show_help() {
    cat << 'EOF'
用法:
  cd clients/deepnode && bash build_standalone_mac_dev.sh [选项]

描述:
  构建 Vue 前端 + PyInstaller 打包 deepnode-server 独立运行制品。
  mlx 系列包从 PyInstaller 中排除，通过 pip install --target 安装到
  mlx-packages/ 目录，运行时由 runtime hook 隔离加载。

选项:
  -h, --help    显示此帮助信息并退出

环境变量:
  TARGET_MACOS_VER    目标 macOS 最低版本号（格式: "主版本_次版本"）。
                      决定 mlx wheel 的 Metal shader 兼容性。
                      默认值: 自动检测当前 macOS 主版本（如当前为 15.x 则用 15_0）。

                      可选值（必须与 PyPI 上 mlx wheel 的平台标签匹配）:
                        13_5   → macOS 13.5 Ventura    (Metal 3.0)
                        14_0   → macOS 14.0 Sonoma     (Metal 3.1)
                        15_0   → macOS 15.0 Sequoia    (Metal 3.2)
                        26_0   → macOS 26.0 Tahoe      (Metal 4.0)

                      注意: 值越低兼容性越广，但 PyPI 上不一定有对应 wheel。
                      建议设置为目标机器的 macOS 主版本号。
                      示例: TARGET_MACOS_VER=15_0 bash build_standalone_mac_dev.sh

  TARGET_ARCH         PyInstaller 目标架构（如 "arm64" / "x86_64"）。
                      默认自动检测当前架构。

命名规范:
  {软件名}-{版本}-{平台}{系统主版本}-{架构}.tar.gz
  示例:
    deepnode-v1.0.0-macos15-arm64.tar.gz    # M系列 + macOS 15 Sequoia
    deepnode-v1.0.0-macos15-x86_64.tar.gz   # Intel + macOS 15
    deepnode-v1.0.0-macos14-arm64.tar.gz    # M系列 + macOS 14 Sonoma
    deepnode-v1.0.0-macos13-arm64.tar.gz    # M系列 + macOS 13 Ventura

产物:
  dist/deepnode-v{VER}-{PLATFORM}-{ARCH}.tar.gz 解压后包含:
    deepnode-server        shell wrapper（启动入口）
    deepnode-server-bin    PyInstaller 二进制
    config.yaml            用户可修改配置
    VERSION                版本号文件
    README.md              运行说明、系统要求、Q&A
    _internal/             PyInstaller 运行时依赖
    mlx-packages/          mlx 系列原生 Python 包 + 标准库

运行:
  tar xzf deepnode-v1.0.0-macos15-arm64.tar.gz && cd deepnode-server
  ./deepnode-server --standalone --account <user> --password <pass>

示例:
  # 默认构建（自动检测当前平台）
  bash build_standalone_mac_dev.sh

  # 指定目标 macOS 15.0+
  TARGET_MACOS_VER=15_0 bash build_standalone_mac_dev.sh

  # 查看帮助
  bash build_standalone_mac_dev.sh --help
EOF
    exit 0
}

# 解析参数
for arg in "$@"; do
    case "$arg" in
        -h|--help) show_help ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
LOCALSERVER_DIR="$SCRIPT_DIR/localserver"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── 版本号（从 VERSION 文件读取）──
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

# ── 架构检测 ──
# 优先使用环境变量 TARGET_ARCH，否则自动检测
BUILD_ARCH="${TARGET_ARCH:-$(uname -m)}"

# 注意：PLATFORM_TAG 和 ARTIFACT_NAME 在 TARGET_MACOS_VER 确定后生成（见步骤 5）

# ── 定位 / 创建 Python venv ──
VENV_DIR="$PROJECT_ROOT/env"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "  创建 venv: $VENV_DIR"
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
echo "  DeepNode Standalone Builder (PyInstaller + mlx 隔离)"
echo "  Version:       v${APP_VERSION}"
echo "  Arch:          ${BUILD_ARCH}"
echo "  Python:        $PYTHON_VERSION ($PYTHON)"
echo "  site-packages: $SITE_PACKAGES"
echo "═══════════════════════════════════════════════════"

# ──────────────────────────────────────────────────
# 0. 自动安装所有 Python 依赖（核心 + 平台推理引擎 + 构建工具）
# ──────────────────────────────────────────────────
echo ""
echo "▸ [0/6] 安装 Python 依赖（自动检测平台）..."
source "$SCRIPT_DIR/install_deps.sh"
install_python_deps "$VENV_DIR/bin/pip" "$LOCALSERVER_DIR" --with-build-tools

# ──────────────────────────────────────────────────
# 1. 构建 Vue 前端
# ──────────────────────────────────────────────────
echo ""
echo "▸ [1/6] 构建 Vue 前端..."

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

# ──────────────────────────────────────────────────
# 2. 生成 runtime hook + PyInstaller spec
# ──────────────────────────────────────────────────
echo ""
echo "▸ [3/6] 生成打包配置..."

cd "$LOCALSERVER_DIR"
rm -rf build/ dist/

# ── Runtime Hook ──
# 在 PyInstaller 二进制启动最早期执行：
# - 插入 mlx-packages 路径到 sys.path
# - 清除代理
# - 抑制 nanobind 警告
cat > _runtime_hook.py << 'HOOK_EOF'
"""Runtime hook: 环境隔离 + mlx-packages 路径注入 + mlx.core 预加载。

mlx 系列包不经过 PyInstaller frozen importer，而是放在产物目录的 mlx-packages/ 中。
此 hook 在 PyInstaller 启动最早期执行：
  1. 将 mlx-packages/ 插入 sys.path 最前
  2. 安装 torch import blocker（防止 pybind11 重复注册 crash）
  3. 预加载 mlx.core — 锁定 nanobind 首次初始化来源在 mlx-packages/
  4. 后续所有代码 import mlx.core 都直接复用此次加载，不会二次初始化

关键原理：nanobind 注册（DeviceType 枚举等）是进程级全局操作，
  一旦通过正确路径完成首次初始化，后续 import 只返回 sys.modules 缓存，
  不会再触发 C 层注册，从而避免 "refusing to add duplicate key" abort。
"""
import sys
import os
import warnings

if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
    _mlx_pkgs = os.path.normpath(os.path.join(_base, '..', 'mlx-packages'))
    if os.path.isdir(_mlx_pkgs) and _mlx_pkgs not in sys.path:
        sys.path.insert(0, _mlx_pkgs)
    # Python 标准库（纯 Python 部分）也在 mlx-packages/_stdlib/ 中，
    # transformers 等包会 import filecmp/difflib/csv 等标准库模块，
    # 这些不在 PyInstaller _internal/ 中，需要从此处加载。
    _stdlib = os.path.join(_mlx_pkgs, '_stdlib')
    if os.path.isdir(_stdlib) and _stdlib not in sys.path:
        sys.path.insert(1, _stdlib)

    # ── torch import blocker ──
    # torch is NOT shipped in the standalone build (removed from mlx-packages
    # during build to save ~600MB and avoid pybind11 RpcBackendOptions crash).
    # However, transformers lazily tries `import torch` in many places.
    # We install a fake "torch" finder that makes `import torch` return a stub,
    # so transformers' `is_torch_available()` returns False.
    import types as _types

    class _TorchBlocker:
        """Meta path finder that blocks torch/torchvision imports with deep stubs.

        transformers' image_utils.py does 'from torchvision.transforms import InterpolationMode'
        at module level. The stub must support arbitrary sub-attribute access so these
        imports silently resolve to dummy objects instead of crashing.
        """
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
            # Return a nested stub so 'from torchvision.transforms import X' works.
            qual = f'{self.__name__}.{name}'
            if qual not in sys.modules:
                sub = _StubModule(qual)
                sys.modules[qual] = sub
            return sys.modules[qual]

    sys.meta_path.insert(0, _TorchBlocker())
    print("[runtime_hook] torch import blocker installed", flush=True)

    # ── 预加载 mlx.core：锁定 nanobind 首次初始化来源 ──
    # 必须在任何业务代码运行前完成，确保 mlx.core 从 mlx-packages/ 加载。
    # 这是防止跨机器运行 nanobind duplicate key abort 的核心防线。
    #
    # 关键：即使加载失败（如 Metal 版本不兼容），nanobind C 层可能已完成
    # 部分注册（枚举键 "cpu" 已写入全局注册表）。此时如果后续代码再次
    # import mlx.core，nanobind 会检测到重复键 → Abort trap: 6。
    # 因此失败时必须通过环境变量标记，阻止后续任何重试。
    try:
        import mlx.core as _mx  # noqa: F401
        print(f"[runtime_hook] mlx.core pre-loaded from: {_mx.__file__}", flush=True)
    except Exception as _e:
        # 标记 nanobind 已被污染（C 层可能已部分注册），后续禁止重试 import
        os.environ['_DEEPNODE_MLX_INIT_FAILED'] = str(_e)
        print(f"[runtime_hook] mlx.core pre-load failed: {_e}", flush=True)
        print("[runtime_hook] MLX features will be disabled to prevent nanobind abort", flush=True)

# 清除代理环境变量
for _v in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
           'all_proxy', 'ALL_PROXY', 'grpc_proxy', 'GRPC_PROXY'):
    os.environ.pop(_v, None)
os.environ['no_proxy'] = 'localhost,127.0.0.1,::1'
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'
os.environ['grpc_proxy'] = ''

# Set build profile for platform_defaults module
os.environ['DEEPPOOL_PROFILE'] = 'dev'

warnings.filterwarnings("ignore", message=".*nanobind.*", category=RuntimeWarning)
HOOK_EOF

# ── PyInstaller Spec ──
cat > standalone.spec << 'SPEC_EOF'
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — 业务代码 frozen + mlx 外置。"""
import os, sys, platform, importlib, sysconfig
import glob as _glob

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None
localserver_dir = os.path.abspath(SPECPATH)
target_arch = os.environ.get('TARGET_ARCH') or None

# ── 标准库 C 扩展 ──
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

# ── Analysis ──
# 用 collect_submodules 自动递归收集关键第三方包的所有子模块，
# 确保在目标机器（无 Python 环境）上不缺任何依赖。
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
    datas=[
        (os.path.join(localserver_dir, 'generated'), 'generated'),
    ] + web_datas + ev_datas + _auto_datas,
    hiddenimports=_auto_hiddenimports + [
        # 业务模块（PyInstaller 静态分析可能遗漏延迟导入）
        'api', 'api.init', 'api.stats', 'api.dashboard', 'api.auth', 'config',
        'engine', 'engine.base', 'engine.selector', 'engine.llamacpp',
        'engine.vllm_engine', 'engine.vllm_mlx', 'engine.reasoning',
        'engine.tool_call_parser', 'engine.outlines_mlx_provider', 'engine.mlx_import',
        'model', 'model.downloader', 'model.registry',
        'rpc', 'rpc.infer_server', 'rpc.platform_client', 'rpc.node_manager_client',
        'service', 'service.credential', 'service.device_fingerprint',
        'service.log_reporter', 'service.manager', 'service.platform_auth',
        'service.statistics', 'service.memory_guard', 'service.device_info',
        'platform_defaults',
        'log_setup',
        # 标准库 C 扩展
        '_contextvars', '_hashlib', '_ssl', '_uuid', '_decimal', '_json', '_sqlite3',
        'ssl', 'hashlib', 'sqlite3',
    ],
    runtime_hooks=[os.path.join(localserver_dir, '_runtime_hook.py')],
    excludes=[
        # mlx 全家族 — 不经过 frozen importer，由 mlx_import.py 隔离导入
        'mlx', 'mlx.core', 'mlx.nn', 'mlx.optimizers',
        'mlx_lm', 'mlx_vlm',
        'outlines', 'outlines_core',
        # 不需要的大包
        'cv2', 'opencv-python', 'opencv-python-headless',
        'matplotlib', 'scipy', 'pandas', 'notebook', 'jupyter',
        'tkinter', 'PIL', 'torch', 'torchvision', 'torchgen', 'functorch', 'accelerate',
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ── 修正 _ssl.so / _hashlib.so 的 dylib 引用 ──
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

# ──────────────────────────────────────────────────
# 4. 运行 PyInstaller
# ──────────────────────────────────────────────────
echo ""
echo "▸ [4/6] PyInstaller 打包..."

"$PYTHON" -m PyInstaller standalone.spec --noconfirm --clean

rm -rf "$LOCALSERVER_DIR/web-dist"

ONEDIR="$LOCALSERVER_DIR/dist/deepnode-server"
if [[ ! -d "$ONEDIR" ]]; then
    echo "  ❌ 打包失败"
    exit 1
fi

# 验证关键模块已被打包（在 _internal/ 中检查）
echo "  验证打包完整性..."
INTERNAL="$ONEDIR/_internal"
MISSING=0
for check_mod in fastapi starlette uvicorn grpc google yaml psutil; do
    if ! find "$INTERNAL" -name "${check_mod}*" -maxdepth 2 2>/dev/null | grep -q .; then
        echo "  ❌ 缺少: $check_mod"
        MISSING=1
    fi
done
if [[ "$MISSING" -eq 1 ]]; then
    echo "  ⚠ 部分模块可能未被打包，请检查 PyInstaller 日志"
else
    echo "  ✓ 关键模块验证通过"
fi

# 验证 _internal/ 中不包含 mlx 残留（防止 nanobind 双路径双初始化）
echo "  检查 _internal/ 中 mlx 残留..."
MLX_LEAK=0
for mlx_pattern in "mlx" "mlx_lm" "mlx_vlm" "mlx.core" "outlines" "outlines_core" "torch" "torchvision" "functorch" "torchgen"; do
    leaked=$(find "$INTERNAL" -name "${mlx_pattern}*" -maxdepth 2 2>/dev/null | head -5)
    if [[ -n "$leaked" ]]; then
        echo "  ⚠ _internal/ 中发现 mlx 残留: $mlx_pattern"
        echo "$leaked" | head -3 | sed 's/^/      /'
        # 主动清理残留，防止跨机器运行时 nanobind duplicate key abort
        find "$INTERNAL" -name "${mlx_pattern}*" -maxdepth 2 -exec rm -rf {} + 2>/dev/null || true
        MLX_LEAK=1
    fi
done
if [[ "$MLX_LEAK" -eq 1 ]]; then
    echo "  ⚠ 已自动清理 _internal/ 中的 mlx/torch 残留（mlx 应仅存在于 mlx-packages/，torch 不应存在）"
else
    echo "  ✓ _internal/ 无 mlx 残留"
fi

# ──────────────────────────────────────────────────
# 5. 用 pip install --target 安装 mlx 全家族到 mlx-packages/
# ──────────────────────────────────────────────────
echo ""
echo "▸ [5/6] 安装 mlx 系列包到 mlx-packages/ (pip install --target)..."

MLX_DIR="$ONEDIR/mlx-packages"
rm -rf "$MLX_DIR"
mkdir -p "$MLX_DIR"

# ── 目标平台检测 ──
# mlx 的 Metal shader library 编译时绑定了 Metal language version，
# 高版本 macOS (如 26.x) 编译的 wheel 使用 Metal language version 4.0，
# 在低版本 macOS (如 15.x) 上会报 "language version not supported" 并 abort。
#
# 解决方案：通过 --platform 参数强制安装兼容目标平台的 wheel。
# 可通过环境变量 TARGET_MACOS_VER 覆盖（如 "15_0" 或 "14_0"）。
# 默认自动检测当前 macOS 主版本号。

# PyPI 上 mlx wheel 已知可用的平台标签（主版本_次版本）
# NOTE: mlx>=0.30 only has wheels for macOS 14.0+. Using 13_x will result in
#       mlx 0.29.x + mlx-lm 0.30.x which lacks support for newer model architectures.
KNOWN_MACOS_VERS=("13_5" "14_0" "15_0" "26_0")

# 自动检测当前 macOS 主版本作为默认值
if [[ -z "${TARGET_MACOS_VER:-}" ]]; then
    _cur_macos_ver="$(sw_vers -productVersion 2>/dev/null || echo "")"
    if [[ -n "$_cur_macos_ver" ]]; then
        _major="${_cur_macos_ver%%.*}"
        TARGET_MACOS_VER="${_major}_0"
        echo "  自动检测 macOS 版本: $_cur_macos_ver → TARGET_MACOS_VER=${TARGET_MACOS_VER}"
    else
        TARGET_MACOS_VER="14_0"
        echo "  无法检测 macOS 版本，使用默认 TARGET_MACOS_VER=${TARGET_MACOS_VER}"
    fi
fi

# 校验 TARGET_MACOS_VER 格式（必须为 数字_数字）
if [[ ! "$TARGET_MACOS_VER" =~ ^[0-9]+_[0-9]+$ ]]; then
    echo "  ❌ TARGET_MACOS_VER 格式错误: '$TARGET_MACOS_VER' (期望格式: 主版本_次版本，如 15_0)"
    echo "     可选值: ${KNOWN_MACOS_VERS[*]}"
    exit 1
fi

# 提示是否为已知版本
_is_known=0
for _v in "${KNOWN_MACOS_VERS[@]}"; do
    if [[ "$TARGET_MACOS_VER" == "$_v" ]]; then _is_known=1; break; fi
done
if [[ "$_is_known" -eq 0 ]]; then
    echo "  ⚠ TARGET_MACOS_VER=${TARGET_MACOS_VER} 不在已知列表中: ${KNOWN_MACOS_VERS[*]}"
    echo "    PyPI 上可能没有对应 wheel，安装可能失败后回退到默认安装"
fi

TARGET_PLATFORM="macosx_${TARGET_MACOS_VER}_arm64"
PY_VER_SHORT="${PYTHON_VERSION//./}"  # "3.13" → "313"

# ── 生成产物文件名（基于目标平台版本，而非编译机器版本）──
_TARGET_MAJOR="${TARGET_MACOS_VER%%_*}"  # "15_0" → "15"
PLATFORM_TAG="macos${_TARGET_MAJOR}"
ARTIFACT_NAME="deepnode-v${APP_VERSION}-${PLATFORM_TAG}-${BUILD_ARCH}"

echo "  目标平台: $TARGET_PLATFORM (可通过 TARGET_MACOS_VER 环境变量覆盖)"
echo "  产物名称: ${ARTIFACT_NAME}.tar.gz"

# 用 pip install --target 一次性安装 mlx-lm 及其全部传递依赖。
# --platform 强制选择兼容目标 macOS 的 wheel（避免 Metal shader 版本不兼容）。
# --python-version + --implementation 是 --platform 的必需搭配参数。
MLX_INSTALL_PKGS=(
    "mlx-lm>=0.31.0"  # auto-pulls mlx, transformers, jinja2, safetensors, tokenizers, sentencepiece, etc.
)

# 可选：mlx-vlm（如果当前 venv 中已安装）
if "$PYTHON" -c "import mlx_vlm" &>/dev/null; then
    MLX_INSTALL_PKGS+=(mlx-vlm)
fi

# 可选：outlines（如果当前 venv 中已安装）
if "$PYTHON" -c "import outlines" &>/dev/null; then
    MLX_INSTALL_PKGS+=(outlines)
fi

echo "  安装: ${MLX_INSTALL_PKGS[*]}"

# 第一步：尝试使用 --platform 安装指定目标平台的 wheel
# 这确保 mlx 的 Metal shader 兼容目标 macOS 版本
if "$PYTHON" -m pip install --target "$MLX_DIR" --no-user \
    --only-binary=:all: \
    --platform "$TARGET_PLATFORM" \
    --python-version "$PY_VER_SHORT" \
    --implementation cp \
    "${MLX_INSTALL_PKGS[@]}" \
    -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1 | tail -10; then
    echo "  ✓ 使用平台指定安装成功 (platform=$TARGET_PLATFORM)"
else
    echo "  ⚠ 平台指定安装失败，回退到默认安装（产物可能仅兼容当前 macOS 版本）"
    rm -rf "$MLX_DIR"
    mkdir -p "$MLX_DIR"
    "$PYTHON" -m pip install --target "$MLX_DIR" --no-user \
        --only-binary=:all: \
        "${MLX_INSTALL_PKGS[@]}" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com 2>&1 | tail -5
fi

# 验证 mlx wheel 的平台标签
MLX_WHEEL_TAG=$(cat "$MLX_DIR"/mlx-*.dist-info/WHEEL 2>/dev/null | grep "^Tag:" | head -1 || echo "unknown")
echo "  mlx wheel tag: $MLX_WHEEL_TAG"

# 验证 mlx-lm 版本（macOS 13.x 平台可能导致旧版本，缺少新模型架构支持）
_MLX_LM_VER=$(cat "$MLX_DIR"/mlx_lm-*.dist-info/METADATA 2>/dev/null | grep "^Version:" | head -1 | awk '{print $2}')
echo "  mlx-lm version: ${_MLX_LM_VER:-unknown}"
if [[ -n "$_MLX_LM_VER" && "$_MLX_LM_VER" < "0.31" ]]; then
    echo "  ⚠ WARNING: mlx-lm $_MLX_LM_VER is outdated and may not support newer model architectures (e.g. gemma4)."
    echo "    This is likely because TARGET_MACOS_VER=$TARGET_MACOS_VER is too low for mlx>=0.30 wheels."
    echo "    Consider using TARGET_MACOS_VER=14_0 or higher for full model support."
fi

# ── 清除 torch 系列（mlx-lm 不使用 torch，但 transformers 依赖链会拉入） ──
# torch 在 PyInstaller frozen 环境下会触发 pybind11 RpcBackendOptions 重复注册：
#   torch.__init__ → torch._jit_internal → import torch.distributed.rpc
#   → torch._C._rpc_init() → generic_type: "RpcBackendOptions" already defined
# 同时删除 torch 可大幅减小产物体积（~600MB → 清理后约 100MB）。
echo "  清除 torch 系列包（避免 pybind11 重复注册 + 减小体积）..."
_TORCH_PURGE_SIZE=0
for _tp in torch functorch torchgen torchvision torch-*.dist-info functorch-*.dist-info torchvision-*.dist-info; do
    if ls -d "$MLX_DIR"/$_tp 2>/dev/null | grep -q .; then
        _tp_size=$(du -sk "$MLX_DIR"/$_tp 2>/dev/null | awk '{s+=$1}END{print s+0}')
        _TORCH_PURGE_SIZE=$((_TORCH_PURGE_SIZE + _tp_size))
        rm -rf "$MLX_DIR"/$_tp
    fi
done
if [[ "$_TORCH_PURGE_SIZE" -gt 0 ]]; then
    echo "  ✓ removed torch family: ~$((_TORCH_PURGE_SIZE / 1024))MB freed"
else
    echo "  ✓ no torch family found (already clean)"
fi

# 清理 pip 缓存/编译文件以减小体积
find "$MLX_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$MLX_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$MLX_DIR" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
rm -rf "$MLX_DIR"/pip "$MLX_DIR"/pip-*.dist-info 2>/dev/null || true

# ── 复制 Python 标准库（纯 Python 部分）到 mlx-packages/ ──
# PyInstaller frozen 环境只包含它分析到的标准库模块。
# 但 mlx-packages/ 中的 transformers 等包会 import 大量标准库模块
# （filecmp, difflib, csv, ast, textwrap 等 71 个），这些不在 _internal/ 中。
# 将标准库复制到 mlx-packages/ 确保所有 import 都能成功。
echo "  复制 Python 标准库..."
STDLIB_PATH=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_path('stdlib'))")
if [[ -d "$STDLIB_PATH" ]]; then
    # 复制纯 Python 标准库文件和包目录（排除不需要的大目录）
    rsync -a \
        --include='*.py' \
        --include='*/' \
        --exclude='__pycache__' \
        --exclude='test/' \
        --exclude='tests/' \
        --exclude='idlelib/' \
        --exclude='tkinter/' \
        --exclude='turtledemo/' \
        --exclude='ensurepip/' \
        --exclude='lib2to3/' \
        --exclude='site-packages/' \
        --exclude='*.pyc' \
        --exclude='*.so' \
        --exclude='*.dylib' \
        "$STDLIB_PATH/" "$MLX_DIR/_stdlib/"
    STDLIB_SIZE=$(du -sh "$MLX_DIR/_stdlib" | cut -f1)
    echo "  ✓ stdlib ($STDLIB_SIZE)"
fi

echo "  mlx-packages: $(du -sh "$MLX_DIR" | cut -f1)"

# ── 生成 wrapper 脚本 ──
echo ""
echo "▸ [6/6] 生成启动脚本 & 后处理..."

cp "$LOCALSERVER_DIR/config.yaml" "$ONEDIR/config.yaml"

# ── 复制版本文件和 README ──
cp "$VERSION_FILE" "$ONEDIR/VERSION"
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
# Sleep prevention:
#   Uses macOS caffeinate to prevent system sleep while deepnode is running.
#   This ensures the inference service stays available even when the screen
#   is off or the lid is closed (on desktop Macs / clamshell mode).
#   Caffeinate is automatically managed — it starts with deepnode and stops
#   when deepnode exits.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$SCRIPT_DIR/deepnode-server-bin"
CONFIG="$SCRIPT_DIR/config.yaml"
PID_FILE="$SCRIPT_DIR/.deepnode.pid"
CAFFEINATE_PID_FILE="$SCRIPT_DIR/.caffeinate.pid"
LOG_FILE="$HOME/.deeppool/logs/localserver.log"
PORT=8765

# ── Environment isolation ──
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

# ── Caffeinate helpers ──
# caffeinate prevents macOS from sleeping while deepnode is running.
# Flags: -i (prevent idle sleep) -s (prevent system sleep, keeps running
#        even with lid closed on desktops / clamshell mode)
# -w PID: automatically exit when the watched process terminates.

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

# ── PID helpers ──
_read_pid() {
    [[ -f "$PID_FILE" ]] && cat "$PID_FILE" 2>/dev/null || echo ""
}

_is_running() {
    local pid="$(_read_pid)"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# ── Commands ──

cmd_start() {
    if _is_running; then
        echo "[DeepNode] Already running (pid=$(_read_pid))"
        return 0
    fi
    _setup_env
    mkdir -p "$(dirname "$LOG_FILE")"
    cd "$SCRIPT_DIR"
    echo "[DeepNode] Starting daemon..."
    # Redirect stdout/stderr to /dev/null — Python's internal file handler
    # already writes to LOG_FILE. Redirecting nohup output to the same file
    # would cause every log line to appear twice.
    nohup "$BIN" --config "$CONFIG" "$@" > /dev/null 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        _start_caffeinate "$pid"
        echo "[DeepNode] Started (pid=$pid)"
        echo "[DeepNode] Log: $LOG_FILE"
        echo "[DeepNode] Web UI: http://127.0.0.1:${PORT}/"
        (sleep 2 && open "http://127.0.0.1:${PORT}/" 2>/dev/null || true) &
    else
        rm -f "$PID_FILE"
        echo "[DeepNode] Failed to start. Check log: $LOG_FILE"
        return 1
    fi
}

cmd_stop() {
    _stop_caffeinate
    if ! _is_running; then
        echo "[DeepNode] Not running"
        rm -f "$PID_FILE"
        return 0
    fi
    local pid="$(_read_pid)"
    echo "[DeepNode] Stopping (pid=$pid)..."
    kill "$pid" 2>/dev/null
    local waited=0
    while kill -0 "$pid" 2>/dev/null && [[ $waited -lt 10 ]]; do
        sleep 1
        waited=$((waited + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "[DeepNode] Force killing..."
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "[DeepNode] Stopped"
}

cmd_status() {
    if _is_running; then
        local pid="$(_read_pid)"
        echo "[DeepNode] Running (pid=$pid)"
        if [[ -f "$CAFFEINATE_PID_FILE" ]]; then
            local caf_pid
            caf_pid="$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null || echo "")"
            if [[ -n "$caf_pid" ]] && kill -0 "$caf_pid" 2>/dev/null; then
                echo "[DeepNode] Sleep prevention: active (caffeinate pid=$caf_pid)"
            else
                echo "[DeepNode] Sleep prevention: inactive"
            fi
        fi
    else
        echo "[DeepNode] Not running"
        rm -f "$PID_FILE"
        _stop_caffeinate
    fi
}

cmd_log() {
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "[DeepNode] Log file not found: $LOG_FILE"
        return 1
    fi
    if [[ "${1:-}" == "-f" ]]; then
        tail -100f "$LOG_FILE"
    else
        tail -100 "$LOG_FILE"
    fi
}

# ── Main dispatcher ──
case "${1:-}" in
    --start)
        shift
        cmd_start "$@"
        ;;
    --stop)
        cmd_stop
        ;;
    --status)
        cmd_status
        ;;
    --log)
        shift
        cmd_log "${1:-}"
        ;;
    *)
        # Foreground mode: wrap the server process with caffeinate
        _setup_env
        cd "$SCRIPT_DIR"
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

# ── symlink 替换 ──
echo "  替换 symlink..."
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

# ── 代码签名 ──
echo "  代码签名..."
find "$ONEDIR" \( -name "*.so" -o -name "*.dylib" \) -type f -exec \
    codesign --force --sign - --timestamp=none {} \; 2>/dev/null || true
codesign --force --sign - --timestamp=none "$ONEDIR/deepnode-server-bin" 2>/dev/null || true

# ── 清理临时文件 ──
rm -f "$LOCALSERVER_DIR/_runtime_hook.py"
rm -f "$LOCALSERVER_DIR/standalone.spec"

# ── 打包 tar.gz ──
SIZE=$(du -sh "$ONEDIR" | cut -f1)
echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ 打包成功!  总大小: $SIZE"
echo "  版本: v${APP_VERSION}  平台: ${PLATFORM_TAG}-${BUILD_ARCH}"
echo ""
echo "  产物:"
ls -lh "$ONEDIR/deepnode-server" "$ONEDIR/deepnode-server-bin" "$ONEDIR/config.yaml" "$ONEDIR/VERSION" "$ONEDIR/README.md" 2>/dev/null || true
echo ""
echo "═══════════════════════════════════════════════════"

echo ""
echo "  打包为 tar.gz..."
TARBALL="${ARTIFACT_NAME}.tar.gz"
(cd "$LOCALSERVER_DIR/dist" && tar czf "$TARBALL" deepnode-server/)
TARSIZE=$(du -sh "$LOCALSERVER_DIR/dist/$TARBALL" | cut -f1)
echo "  ✅ dist/${TARBALL} ($TARSIZE)"
echo ""
echo "  分发: tar xzf ${TARBALL} && cd deepnode-server && ./deepnode-server --standalone"
