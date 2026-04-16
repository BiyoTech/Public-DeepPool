# 算力提供者快速开始

本指南将帮助你将闲置设备接入 DeepPool 算力池，开始赚取推理收益。

## 前置条件

- Mac（Apple Silicon M1 及以上）或 Linux（NVIDIA GPU）设备
- 稳定的网络连接
- 至少 8GB 可用内存（运行小型模型）

### macOS 版本要求

> **⚠️ 强烈建议升级到 macOS 26 (Tahoe) 或更高版本。**
>
> 低版本 macOS 用户可能遇到：模型无法加载、推理结果异常（如 thinking 内容泄露到回复中）、无法正常提供算力等问题。**这些问题在升级系统后可自动解决。**

DeepPool 在 Mac 上使用 [MLX](https://github.com/ml-explore/mlx) 框架进行推理加速。**不同 macOS 版本对模型的支持范围和稳定性差异显著**：

| macOS 版本 | 推荐级别 | 模型支持 | 已知问题 |
|-----------|---------|---------|---------|
| **26.0+ (Tahoe)** | ✅ **强烈推荐** | 全部模型完整支持（含 Gemma 4、Llama 4 等最新架构） | 无 |
| 15.0 (Sequoia) | ⚠️ 可用但有限 | 大部分模型可用，部分最新架构可能降级运行 | Gemma 4 系列可能降级为纯文本模式，推理输出可能包含异常内容 |
| 14.0 (Sonoma) 及更低 | ❌ 不推荐 | 仅支持较旧模型 | 无法加载多数新架构模型，可能导致设备无法正常提供算力 |

#### 为什么低版本 macOS 会出现问题？

1. **模型架构不兼容**：Gemma 4 等新模型需要最新版本的 `mlx-vlm` / `transformers` 库支持。低版本 macOS 上这些库的版本受限，可能导致模型加载失败或降级到纯文本模式
2. **推理输出异常**：降级模式下，模型可能在回复中混入内部思考过程（thinking content），导致 API 返回内容不符合预期
3. **安全加固依赖**：部分安全特性（如 Hardened Runtime）在新版 macOS 上表现更佳
4. **MLX 框架优化**：macOS 26 对 Metal GPU 的底层调度做了大幅优化，MLX 推理吞吐量和稳定性显著提升

## 步骤

### 1. 注册平台账号

访问 **[https://deeppool.tech/register](https://deeppool.tech/register)** 注册 DeepPool 账号。启动 DeepNode 后需要使用该账号登录完成设备初始化。

### 2. 下载 DeepNode

前往 GitHub Releases 页面下载适合你系统的安装包：

👉 **[下载 DeepNode 最新版](https://github.com/BiyoTech/deepnode/releases/latest)**

下载文件为 `deepnode-vX.Y.Z-macosXX-arm64.tar.gz` 格式的压缩包。请根据你的 macOS 版本选择对应的包（如 `macos26`、`macos15` 等）。

> 也可以通过命令行一键安装：
> ```bash
> curl -fsSL https://raw.githubusercontent.com/BiyoTech/deepnode/main/install.sh | bash
> ```

### 3. 解压与运行

```bash
# 解压
tar xzf deepnode-v*.tar.gz
cd deepnode-server

# 清除 macOS 隔离属性（首次运行必须）
xattr -rd com.apple.quarantine .

# 启动服务（后台守护进程模式，推荐）
./deepnode-server --start
```

启动后会自动打开浏览器访问 Web UI：**http://127.0.0.1:8765/**

在 Web UI 中使用步骤 1 注册的账号登录，即可完成设备初始化。

#### 其他运行方式

```bash
# 前台运行（可直接看到日志输出，适合调试）
./deepnode-server

# 查看运行状态
./deepnode-server --status

# 查看日志（实时跟踪）
./deepnode-server --log -f

# 停止服务
./deepnode-server --stop
```

### 4. 自动初始化

登录后，DeepNode 将自动完成以下步骤：

1. 检测本机硬件（GPU 型号、内存大小等）
2. 根据硬件能力自动下载适配的模型（从 HuggingFace 镜像加速）
3. 模型加载完成后，自动启动推理引擎并连接平台

### 5. 开始赚取收益

设备接入后将自动：
- 通过 gRPC 双向流隧道与平台保持长连接
- 接收并执行平台分发的推理请求
- 按实际消耗的 Token 数获得收益

## 验证

登录门户网站，进入「数据」页面可以看到设备的贡献统计。

## 支持的推理引擎

| 引擎 | 适用平台 | 加速方式 | 备注 |
|------|---------|---------|------|
| MLX | macOS Apple Silicon (M1+) | Metal GPU | **强烈推荐 macOS 26.0+**；15.x 可用但部分模型受限；14.x 及更低不推荐 |
| vLLM | Linux + NVIDIA | CUDA | 高吞吐，适合服务器部署 |
| llama.cpp | 通用 | CPU / 弱 GPU | 兜底引擎，兼容性最广 |

系统根据设备硬件自动选择最优引擎，无需手动配置。
