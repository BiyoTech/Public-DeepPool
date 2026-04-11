# Provider Quickstart

This guide will help you connect your idle device to the DeepPool computing pool and start earning inference rewards.

## Prerequisites

- Mac (Apple Silicon M1 or later) or Linux (NVIDIA GPU) device
- Stable network connection
- At least 8GB available memory (for running small models)

### macOS Version Requirements

> **⚠️ We strongly recommend upgrading to macOS 15 (Sequoia) or later.**
>
> Users on older macOS versions may experience: model loading failures, abnormal inference output (e.g. thinking content leaking into responses), and inability to provide compute reliably. **These issues are resolved automatically after upgrading.**

DeepPool uses the [MLX](https://github.com/ml-explore/mlx) framework for inference acceleration on Mac. **Different macOS versions vary significantly in model support and stability**:

| macOS Version | Recommendation | Model Support | Known Issues |
|--------------|---------------|---------------|-------------|
| **15.0+ (Sequoia)** | ✅ **Strongly Recommended** | Full support for all models (including Gemma 4, Llama 4, etc.) | None |
| 14.0 (Sonoma) | ⚠️ Usable but limited | Most models work, some latest architectures may run in degraded mode | Gemma 4 series may fall back to text-only mode; inference output may contain unexpected content |
| 13.5 (Ventura) | ❌ Not recommended | Only older models supported | Cannot load most new architecture models; device may be unable to provide compute |

#### Why do older macOS versions cause problems?

1. **Model architecture incompatibility**: Newer models like Gemma 4 require the latest `mlx-vlm` / `transformers` libraries. On older macOS versions, these libraries are version-constrained, potentially causing model loading failures or degraded text-only mode
2. **Abnormal inference output**: In degraded mode, the model may mix internal thinking content into responses, causing API output that doesn't match expectations
3. **Security hardening dependencies**: Some security features (e.g. Hardened Runtime) perform better on newer macOS versions

## Steps

### 1. Register a Platform Account

Visit the DeepPool portal website and click "Sign Up" to create an account.

### 2. Download and Install DeepNode

DeepNode is a desktop client application (built with Tauri):

- **macOS**: Download the `.dmg` installer, drag to Applications folder
- **Linux**: Download the `.AppImage` or `.deb` package

> Standalone mode (no desktop environment): `./run_standalone.sh`

### 3. Login and Initialize

1. Launch DeepNode and login with your platform account
2. The client auto-detects local hardware (GPU model, memory size, etc.)
3. Automatically downloads compatible models based on hardware capabilities (from HuggingFace mirror)
4. Once models are loaded, the inference engine starts and connects to the platform

### 4. Start Earning

After connecting, your device will automatically:
- Maintain a persistent gRPC bidirectional stream tunnel with the platform
- Receive and execute inference requests dispatched by the platform
- Earn rewards based on actual Token consumption

## Verification

Log in to the portal website, navigate to the "Data" page to view your device contribution stats.

## Supported Inference Engines

| Engine | Platform | Acceleration | Notes |
|--------|----------|-------------|-------|
| MLX | macOS Apple Silicon (M1+) | Metal GPU | **macOS 15.0+ strongly recommended**; 14.x works but with limited model support; 13.x not recommended |
| vLLM | Linux + NVIDIA | CUDA | High throughput, ideal for server deployments |
| llama.cpp | Universal | CPU / Weak GPU | Fallback engine with broadest compatibility |

The system auto-selects the optimal engine based on device hardware — no manual configuration needed.
