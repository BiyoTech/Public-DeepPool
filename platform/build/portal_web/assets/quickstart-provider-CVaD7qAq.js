const e=`# Provider Quickstart

This guide will help you connect your idle device to the DeepPool computing pool and start earning inference rewards.

## Prerequisites

- Mac (Apple Silicon M1 or later) or Linux (NVIDIA GPU) device
- Stable network connection
- At least 8GB available memory (for running small models)

## Steps

### 1. Register a Platform Account

Visit the DeepPool portal website and click "Sign Up" to create an account.

### 2. Download and Install DeepNode

DeepNode is a desktop client application (built with Tauri):

- **macOS**: Download the \`.dmg\` installer, drag to Applications folder
- **Linux**: Download the \`.AppImage\` or \`.deb\` package

> Standalone mode (no desktop environment): \`./run_standalone.sh\`

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

| Engine | Platform | Acceleration |
|--------|----------|-------------|
| MLX | macOS Apple Silicon | Metal GPU |
| vLLM | Linux + NVIDIA | CUDA |
| llama.cpp | Universal | CPU / Weak GPU |

The system auto-selects the optimal engine based on device hardware — no manual configuration needed.
`;export{e as default};
