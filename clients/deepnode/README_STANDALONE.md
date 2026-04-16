# DeepNode Server — Standalone Edition

## Quick Start

### 1. Register an Account

Visit **[https://deeppool.tech/register](https://deeppool.tech/register)** to create a DeepPool account.

### 2. Extract & Remove Quarantine

```bash
tar xzf deepnode-v*.tar.gz
cd deepnode-server

# Required on macOS: clear quarantine attribute
xattr -rd com.apple.quarantine .
```

### 3. Start the Service

```bash
# Background daemon mode (recommended — auto-opens browser)
./deepnode-server --start

# Or run in foreground (see logs directly, useful for debugging)
./deepnode-server
```

### 4. Log In via Web UI

Open **http://127.0.0.1:8765/** (auto-opened in daemon mode), log in with your DeepPool account. The device will automatically initialize, download a compatible model, and start serving inference.

### 5. Management Commands

```bash
./deepnode-server --status    # Check running status
./deepnode-server --log -f    # View logs (follow mode)
./deepnode-server --stop      # Stop the service
```

---

## macOS Version Requirements

> **⚠️ Strongly recommended: macOS 26 (Tahoe) or later.**
>
> Older macOS versions may cause model loading failures, abnormal inference output, or inability to provide compute. Upgrading resolves these issues automatically.

| macOS Version | Recommendation | Notes |
|--------------|---------------|-------|
| **26.0+ (Tahoe)** | ✅ **Strongly Recommended** | Full model support, best MLX performance |
| 15.0 (Sequoia) | ⚠️ Usable but limited | Some latest models may run in degraded mode |
| 14.0 (Sonoma) and below | ❌ Not recommended | Most new models cannot load |

> **Important**: Use the artifact matching your macOS version. For example,
> `deepnode-v1.0.0-macos26-arm64.tar.gz` is for macOS 26+ on Apple Silicon.

### Metal Compatibility

DeepNode uses Apple Metal for inference acceleration. Different macOS versions ship different Metal versions. Artifacts are built targeting a specific Metal version — **a lower macOS version cannot run artifacts built for a higher version**. Always match the artifact to your macOS version.

---

## macOS Security Guide

Since this binary is not Apple-notarized, macOS Gatekeeper may block execution on first run.

### Method 1: Remove quarantine attribute (recommended)

```bash
# Run inside the deepnode-server directory after extraction
xattr -rd com.apple.quarantine .
```

### Method 2: System Settings

1. Run `./deepnode-server`, click "Cancel" when the "cannot open" dialog appears
2. Open **System Settings → Privacy & Security**
3. Find the blocked program at the bottom and click **Open Anyway**

### Method 3: Command-line one-time allow

```bash
spctl --add --label "DeepNode" ./deepnode-server-bin
```

---

## Directory Structure

```
deepnode-server/
├── deepnode-server          # Launcher script (shell wrapper)
├── deepnode-server-bin      # PyInstaller-packaged main binary
├── config.yaml              # User-configurable settings
├── README.md                # This file
├── _internal/               # PyInstaller runtime dependencies (do not modify)
└── mlx-packages/            # MLX inference engine packages (do not modify)
```

---

## Configuration

Edit `config.yaml` to adjust:

- **server.port** — Local service port (default: 8765)
- **platform.\*_grpc_target** — Platform component gRPC addresses
- **log.level** — Log level (debug / info / warning / error)
- **engine.\*** — Inference engine parameters (KV cache, thread pool, etc.)
- **multi_model.max_loaded_models** — Max models loaded simultaneously

---

## FAQ

### Q: Startup error "Abort trap: 6"

**A**: Usually caused by Metal shader version incompatibility. Verify:
1. The artifact matches your macOS version
2. Files from different artifact versions are not mixed

### Q: "Metal is not available" or "mlx.core pre-load failed"

**A**: Verify:
1. Your Mac has a Metal-capable GPU
2. macOS version meets the minimum requirement
3. GPU is not blocked by remote desktop or similar tools

### Q: How to switch the connected Platform server?

**A**: Edit the `platform` section in `config.yaml`, change the `*_grpc_target` addresses.

### Q: How to view detailed logs?

**A**: Logs are written to `~/.deeppool/logs/localserver.log` by default. Set `log.level` to `debug` in `config.yaml` for verbose output. Use `./deepnode-server --log -f` to follow in real time.

### Q: Can I run multiple instances?

**A**: Yes, but you need to change `server.port` in `config.yaml` to a different port for each instance.

### Q: Where are model files stored?

**A**: Models are downloaded to `~/.cache/huggingface/hub/` by default, managed by Hugging Face Hub.

---

## Support

If you encounter issues, please collect the following and contact us:

1. Artifact filename (includes version and platform info)
2. Output of `sw_vers` (macOS version)
3. Output of `uname -m` (CPU architecture)
4. Log file: `~/.deeppool/logs/localserver.log`

📧 **Email: contact@deeppool.tech**
