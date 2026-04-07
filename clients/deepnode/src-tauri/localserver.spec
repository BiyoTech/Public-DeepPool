# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 — 将 localserver 打包为单文件可执行程序。

用法: pyinstaller localserver.spec
输出: dist/localserver (macOS 单文件二进制)
"""

import os
import platform
import sys

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

block_cipher = None

# localserver 源码根目录
localserver_dir = os.path.abspath(os.path.join(SPECPATH, '..', 'localserver'))

# ── 按平台自动收集推理引擎的子模块、数据文件和动态库 ──
# MLX 包含 C 扩展（libmlx.dylib）和 Metal 着色器（mlx.metallib），必须显式收集
platform_hiddenimports = []
platform_datas = []
platform_binaries = []

is_apple_silicon = (sys.platform == 'darwin' and platform.machine() == 'arm64')

if is_apple_silicon:
    # Apple Silicon: 收集 mlx / mlx_lm / mlx_vlm 的全部子模块、数据文件和动态库
    for pkg in ('mlx', 'mlx_lm', 'mlx_vlm'):
        try:
            subs = collect_submodules(pkg)
            datas = collect_data_files(pkg)
            dylibs = collect_dynamic_libs(pkg)
            platform_hiddenimports += subs
            platform_datas += datas
            platform_binaries += dylibs
            print(f'[spec] {pkg}: {len(subs)} submodules, {len(datas)} data files, {len(dylibs)} dynamic libs')
        except ImportError:
            print(f'[spec] WARNING: {pkg} not installed, skipping')

    # mlx_lm 依赖 transformers（AutoTokenizer / PreTrainedTokenizer / chat_template 等），
    # 必须收集其子模块和数据文件，否则运行时 import 失败
    try:
        tf_subs = collect_submodules('transformers')
        tf_datas = collect_data_files('transformers')
        platform_hiddenimports += tf_subs
        platform_datas += tf_datas
        print(f'[spec] transformers: {len(tf_subs)} submodules, {len(tf_datas)} data files')
    except ImportError:
        print('[spec] WARNING: transformers not installed, skipping')
elif sys.platform == 'darwin':
    # Intel Mac: 收集 llama_cpp
    try:
        platform_hiddenimports += collect_submodules('llama_cpp')
        platform_datas += collect_data_files('llama_cpp')
        platform_binaries += collect_dynamic_libs('llama_cpp')
    except ImportError:
        print('[spec] WARNING: llama_cpp not installed, skipping')

a = Analysis(
    [os.path.join(localserver_dir, 'main.py')],
    pathex=[localserver_dir],
    binaries=[] + platform_binaries,  # 合并平台特定的动态库（如 libmlx.dylib）
    datas=[
        # 打包 gRPC 生成代码
        (os.path.join(localserver_dir, 'generated'), 'generated'),
        # 打包默认配置文件
        (os.path.join(localserver_dir, 'config.yaml'), '.'),
    ] + platform_datas,  # 合并平台特定的推理引擎数据文件
    hiddenimports=[
        # FastAPI + uvicorn 依赖
        'uvicorn.logging',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.protocols.websockets.websockets_impl',
        'fastapi',
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware.cors',
        # gRPC + protobuf
        'grpc',
        'grpc._cython',
        'grpc._cython.cygrpc',
        'google.protobuf',
        'google.protobuf.descriptor',
        'google.protobuf.descriptor_pool',
        'google.protobuf.runtime_version',
        'google.protobuf.symbol_database',
        'google.protobuf.internal.builder',
        # localserver 子模块
        'api',
        'api.init',
        'api.stats',
        'api.dashboard',
        'config',
        'engine',
        'engine.base',
        'engine.selector',
        'engine.llamacpp',
        'engine.vllm_engine',
        'engine.vllm_mlx',
        'engine.reasoning',
        'model',
        'model.downloader',
        'model.registry',
        'rpc',
        'rpc.infer_server',
        'rpc.platform_client',
        'rpc.node_manager_client',
        'service',
        'service.credential',
        'service.device_fingerprint',
        'service.log_reporter',
        'service.manager',
        'service.platform_auth',
        'service.statistics',
        # 核心工具库
        'psutil',
        'yaml',
        'huggingface_hub',
        # HTTP 编解码器：urllib3 检测到 brotli 后会在 Accept-Encoding 中发送 br，
        # 若 _brotli C 扩展未打包，服务端返回 Brotli 压缩数据时 zlib 无法解码
        'brotli',
        '_brotli',
    ] + platform_hiddenimports,  # 合并平台特定的推理引擎子模块
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库以减小体积
        'matplotlib',
        'scipy',
        'pandas',
        'notebook',
        'jupyter',
        'tkinter',
        'PIL',
        # 排除大型可选依赖（mlx_lm 不直接使用 torch/accelerate）
        'torch',
        'accelerate',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='localserver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,          # localserver 是后台服务，需要 stdout/stderr
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,      # 自动检测 (arm64 / x86_64)
    codesign_identity=None,
    entitlements_file=None,
)
