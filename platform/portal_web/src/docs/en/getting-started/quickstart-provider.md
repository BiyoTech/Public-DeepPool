# Provider Quickstart

This guide will help you connect your idle device to the DeepPool computing pool and start earning inference rewards.

## Prerequisites

- Mac (Apple Silicon M1 or later) or Linux (NVIDIA GPU) device
- Stable network connection
- At least 8GB available memory (for running small models)

### macOS Version Requirements

> **⚠️ We strongly recommend upgrading to macOS 26 (Tahoe) or later.**
>
> Users on older macOS versions may experience: model loading failures, abnormal inference output (e.g. thinking content leaking into responses), and inability to provide compute reliably. **These issues are resolved automatically after upgrading.**

DeepPool uses the [MLX](https://github.com/ml-explore/mlx) framework for inference acceleration on Mac. **Different macOS versions vary significantly in model support and stability**:

| macOS Version | Recommendation | Model Support | Known Issues |
|--------------|---------------|---------------|-------------|
| **26.0+ (Tahoe)** | ✅ **Strongly Recommended** | Full support for all models (including Gemma 4, Llama 4, and latest architectures) | None |
| 15.0 (Sequoia) | ⚠️ Usable but limited | Most models work, some latest architectures may run in degraded mode | Gemma 4 series may fall back to text-only mode; inference output may contain unexpected content |
| 14.0 (Sonoma) and below | ❌ Not recommended | Only older models supported | Cannot load most new architecture models; device may be unable to provide compute |

#### Why do older macOS versions cause problems?

1. **Model architecture incompatibility**: Newer models like Gemma 4 require the latest `mlx-vlm` / `transformers` libraries. On older macOS versions, these libraries are version-constrained, potentially causing model loading failures or degraded text-only mode
2. **Abnormal inference output**: In degraded mode, the model may mix internal thinking content into responses, causing API output that doesn't match expectations
3. **Security hardening dependencies**: Some security features (e.g. Hardened Runtime) perform better on newer macOS versions
4. **MLX framework optimization**: macOS 26 significantly improves Metal GPU scheduling, resulting in notably better MLX inference throughput and stability

## Steps

### 1. Register a Platform Account

Visit **[https://deeppool.tech/register](https://deeppool.tech/register)** to create a DeepPool account. You will need this account to log in and complete device setup after starting DeepNode.

### 2. Download DeepNode

Go to the GitHub Releases page to download the package for your system:

👉 **[Download DeepNode Latest Release](https://github.com/BiyoTech/deepnode/releases/latest)**

The download is a `deepnode-vX.Y.Z-macosXX-arm64.tar.gz` archive. Choose the package matching your macOS version (e.g. `macos26`, `macos15`, etc.).

> You can also install via one-liner:
> ```bash
> curl -fsSL https://raw.githubusercontent.com/BiyoTech/deepnode/main/install.sh | bash
> ```

### 3. Extract and Run

```bash
# Extract
tar xzf deepnode-v*.tar.gz
cd deepnode-server

# Clear macOS quarantine attribute (required on first run)
xattr -rd com.apple.quarantine .

# Start the service (background daemon mode, recommended)
./deepnode-server --start
```

After starting, the browser will automatically open the Web UI at: **http://127.0.0.1:8765/**

Log in with the account you created in Step 1 to complete device initialization.

#### Other Run Modes

```bash
# Run in foreground (see logs directly, useful for debugging)
./deepnode-server

# Check running status
./deepnode-server --status

# View logs (follow mode)
./deepnode-server --log -f

# Stop the service
./deepnode-server --stop
```

### 4. Automatic Initialization

After logging in, DeepNode will automatically:

1. Detect local hardware (GPU model, memory size, etc.)
2. Download compatible models based on hardware capabilities (from HuggingFace mirror)
3. Start the inference engine and connect to the platform once models are loaded

### 5. Start Earning

After connecting, your device will automatically:
- Maintain a persistent gRPC bidirectional stream tunnel with the platform
- Receive and execute inference requests dispatched by the platform
- Earn rewards based on actual Token consumption

## Verification

Log in to the portal website, navigate to the "Data" page to view your device contribution stats.

## Supported Inference Engines

| Engine | Platform | Acceleration | Notes |
|--------|----------|-------------|-------|
| MLX | macOS Apple Silicon (M1+) | Metal GPU | **macOS 26.0+ strongly recommended**; 15.x works but with limited model support; 14.x and below not recommended |
| vLLM | Linux + NVIDIA | CUDA | High throughput, ideal for server deployments |
| llama.cpp | Universal | CPU / Weak GPU | Fallback engine with broadest compatibility |

The system auto-selects the optimal engine based on device hardware — no manual configuration needed.
