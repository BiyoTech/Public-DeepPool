const n=`# 算力提供者快速开始

本指南将帮助你将闲置设备接入 DeepPool 算力池，开始赚取推理收益。

## 前置条件

- Mac（Apple Silicon M1 及以上）或 Linux（NVIDIA GPU）设备
- 稳定的网络连接
- 至少 8GB 可用内存（运行小型模型）

## 步骤

### 1. 注册平台账号

访问 DeepPool 门户网站，点击「注册」创建账号。

### 2. 下载并安装 DeepNode

DeepNode 是一个桌面客户端应用（基于 Tauri 构建）：

- **macOS**：下载 \`.dmg\` 安装包，拖拽到 Applications 文件夹
- **Linux**：下载 \`.AppImage\` 或 \`.deb\` 包

> 独立运行模式（无需桌面环境）：\`./run_standalone.sh\`

### 3. 登录并初始化

1. 启动 DeepNode，使用平台账号登录
2. 客户端自动检测本机硬件（GPU 型号、内存大小等）
3. 根据硬件能力自动下载适配的模型（从 HuggingFace 镜像加速）
4. 模型加载完成后，自动启动推理引擎并连接平台

### 4. 开始赚取收益

设备接入后将自动：
- 通过 gRPC 双向流隧道与平台保持长连接
- 接收并执行平台分发的推理请求
- 按实际消耗的 Token 数获得收益

## 验证

登录门户网站，进入「数据」页面可以看到设备的贡献统计。

## 支持的推理引擎

| 引擎 | 适用平台 | 加速方式 |
|------|---------|---------|
| MLX | macOS Apple Silicon | Metal GPU |
| vLLM | Linux + NVIDIA | CUDA |
| llama.cpp | 通用 | CPU / 弱 GPU |

系统根据设备硬件自动选择最优引擎，无需手动配置。
`;export{n as default};
