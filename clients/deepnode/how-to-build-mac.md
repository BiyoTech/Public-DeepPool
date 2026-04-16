# DeepNode macOS Standalone Build Guide

## Overview

`build_standalone_mac.sh` packages the DeepNode local server (Python + Vue frontend) into a self-contained macOS artifact that users can run without installing Python, Node.js, or any dependencies.

The script supports **two build modes** designed for different macOS versions:

| Mode | Flag | macOS Target | Output |
|------|------|-------------|--------|
| **Standard** | _(default)_ | 13 / 14 / 15 | `deepnode-server-bin` + `_internal/` + `mlx-packages/` |
| **Binary-only** | `--binary-only` | 26+ | Single `deepnode-server-bin` (all deps bundled) |

---

## Prerequisites

- **Python 3.10+** (recommended 3.13)
- **Node.js 18+** / npm
- **Xcode Command Line Tools** (for `codesign`, `install_name_tool`)
- Python venv at `../../env/` (auto-created if missing)

---

## Quick Start

```bash
cd clients/deepnode

# Default prod build (auto-detect macOS version)
bash build_standalone_mac.sh

# Dev build targeting macOS 15
bash build_standalone_mac.sh --profile dev --target-os 15

# Single-binary build for macOS 26+
bash build_standalone_mac.sh --target-os 26 --binary-only

# Full options
bash build_standalone_mac.sh --profile prod --target-os 26 --binary-only
```

### CLI Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--profile` | `dev` / `prod` | `prod` | Build profile: determines which config file is bundled and platform server URLs |
| `--target-os` | `14`, `15`, `26`, ... | auto-detect | Target macOS version (used for pip platform tag and artifact naming) |
| `--binary-only` | _(flag)_ | off | Enable PyInstaller onefile mode — single binary, no external dirs |
| `-h`, `--help` | | | Show help and exit |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_ARCH` | `uname -m` | Target architecture: `arm64` or `x86_64` |
| `DEEPNODE_CODESIGN_IDENTITY` | `-` (ad-hoc) | Code signing identity, set to `"Developer ID Application: ..."` for distribution |

---

## Build Modes Explained

### Standard Mode (macOS 13 / 14 / 15)

```bash
bash build_standalone_mac.sh --target-os 15
```

**Output structure:**
```
deepnode-server/
├── deepnode-server              # Bash launcher script (daemon management)
├── deepnode-server-bin          # PyInstaller onedir frozen binary
├── _internal/                   # Frozen Python runtime + business deps
│   ├── fastapi/
│   ├── grpc/
│   ├── ...
│   └── integrity_manifest.json  # HMAC-signed SHA-256 file hashes
├── mlx-packages/                # MLX family (installed separately via pip)
│   ├── mlx/
│   ├── mlx_lm/
│   ├── mlx_vlm/
│   ├── transformers/
│   └── _stdlib/                 # Python stdlib (pure-Python portion)
├── config.yaml
└── README.md
```

**Why this design?**

On macOS 13–15, the `mlx` library uses **nanobind** for C extension registration. nanobind performs a **process-global, one-time-only** registration of enum keys (`"cpu"`, `"gpu"`, etc.). If mlx is loaded from two different paths (e.g., PyInstaller's `_internal/` and an extracted temp dir), nanobind detects the duplicate registration and **aborts the process** with:

```
refusing to add duplicate key
Abort trap: 6
```

To avoid this, mlx is **excluded from PyInstaller** and installed into a separate `mlx-packages/` directory. A runtime hook injects this directory into `sys.path` at startup and pre-loads `mlx.core` to lock the nanobind init source to a single, stable path.

**Build pipeline (6 steps):**

1. **Install Python deps** — pip install from `requirements.txt` + build tools (PyInstaller)
2. **Build Vue frontend** — `npm run build:standalone` → copied to `web-dist/`
3. **Generate spec + runtime hook** — runtime hook handles:
   - `mlx-packages/` path injection
   - torch import blocker (fake module to prevent 600MB torch from being pulled)
   - SHA-256 integrity verification
   - `mlx.core` pre-loading
   - Proxy env cleanup + profile injection
4. **PyInstaller onedir** — freezes business code + web deps into `_internal/`
5. **Install mlx to mlx-packages/** — platform-specific pip install with:
   - `--platform macosx_{ver}_arm64` for correct wheel selection
   - Security hardening: removes server.py, CLI tools, unused integrations
   - `.py` → `.pyc` compilation (transformers excluded — its `_LazyModule` needs `.py`)
   - Python stdlib copy for pure-Python modules needed by transformers
6. **Security hardening** — code signing + HMAC-signed integrity manifest

### Binary-only Mode (macOS 26+)

```bash
bash build_standalone_mac.sh --target-os 26 --binary-only
```

**Output structure:**
```
deepnode-server/
├── deepnode-server              # Bash launcher script
├── deepnode-server-bin          # Single self-contained binary (ALL deps inside)
├── config.yaml
└── README.md
```

**Why this is possible on macOS 26?**

macOS 26 ships with updated nanobind / mlx versions where the "duplicate key" registration issue has been resolved. This means mlx can be safely bundled inside a PyInstaller **onefile** binary without path conflicts.

**Benefits over standard mode:**
- **Simpler distribution** — just one binary + config
- **No external source code** — everything compiled into the binary
- **Smaller attack surface** — no `mlx-packages/` dir to tamper with
- **Faster startup** — no `sys.path` manipulation or integrity manifest verification

**Build pipeline (simplified):**

1. **Install Python deps** — same as standard
2. **Build Vue frontend** — same as standard
3. **Generate onefile spec + simplified runtime hook** — runtime hook only does:
   - torch import blocker
   - Proxy env cleanup + profile injection
   - (No mlx-packages injection, no integrity check — binary is self-contained)
4. **PyInstaller onefile** — ALL deps bundled into single executable, including:
   - mlx, mlx_lm, mlx_vlm, transformers, PIL (Pillow)
   - Aggressive exclusions: torch, datasets, pyarrow, pandas, opencv, matplotlib, scipy
5. **Assemble output** — binary + config + launcher
6. **Code signing** — Hardened Runtime with entitlements

---

## Target macOS Version Selection

The `--target-os` flag determines the **pip platform tag** used when installing mlx wheels:

| `--target-os` | Platform Tag | Typical Use |
|---------------|-------------|-------------|
| `14` | `macosx_14_0_arm64` | macOS Sonoma |
| `15` | `macosx_15_0_arm64` | macOS Sequoia |
| `26` | `macosx_26_0_arm64` | macOS 26 (Tahoe) |

**Why does this matter?**

mlx publishes platform-specific wheels (compiled C extensions linked against specific macOS SDK versions). Using the wrong platform tag results in:
- `pip install` failure (no matching wheel)
- Runtime crashes (`dyld` symbol not found)

**Rule of thumb:**
- Build on the **same macOS version** you're targeting
- Or build on an **older** version (forward-compatible, but may miss newer optimizations)

### Auto-detection

If `--target-os` is omitted, the script auto-detects from `sw_vers -productVersion`:

```bash
# On macOS 15.4 → TARGET_MACOS_VER=15_0
# On macOS 26.0 → TARGET_MACOS_VER=26_0
```

---

## Profile: dev vs prod

| | `--profile dev` | `--profile prod` |
|---|---|---|
| Config file | `config.yaml` | `config_prod.yaml` |
| Platform server | Dev server (101.33.255.185) | Prod server (deeppool.tech) |
| `DEEPPOOL_PROFILE` env | `dev` | `prod` |

Both profiles produce identical binaries — only the bundled config file differs.

---

## Launcher Script Behavior

The generated `deepnode-server` bash script provides daemon management:

```bash
./deepnode-server [--standalone] [...]     # Run in foreground (default)
./deepnode-server --start [...]            # Start as background daemon
./deepnode-server --stop                   # Stop the running daemon
./deepnode-server --status                 # Show daemon status
./deepnode-server --log [-f]               # Show log (add -f to follow)
```

**Key behaviors:**
- **Environment isolation** — clears `PYTHONPATH`, `VIRTUAL_ENV`, proxy vars to prevent interference
- **Quarantine clearing** — auto-removes macOS quarantine (`xattr`) on first run
- **Sleep prevention** — uses `caffeinate` to keep the system awake while serving
- **Port readiness check** — polls `http://127.0.0.1:8765/health` before opening the browser (up to 60s)

---

## Security Architecture

### Standard Mode

1. **Source code protection** — business `.py` files are frozen into `deepnode-server-bin` by PyInstaller (compiled bytecode inside a binary archive)
2. **mlx-packages `.pyc` compilation** — all `.py` sources in `mlx-packages/` compiled to `.pyc` and originals deleted (except `transformers/` which needs `.py` for `_LazyModule`)
3. **Integrity manifest** — SHA-256 hashes of all critical files (`.pyc`, `.so`, `.dylib`), signed with HMAC-SHA256. Verified at startup and periodically every 5 minutes
4. **Code signing** — Hardened Runtime + entitlements (ad-hoc or Developer ID)
5. **Security hardening** — removal of server.py, CLI tools, webhook handlers, and unused modules from mlx-packages

### Binary-only Mode

1. **Everything inside the binary** — no external files to tamper with
2. **Code signing** — Hardened Runtime protects the entire binary
3. **No integrity manifest needed** — the binary itself is the tamper boundary

---

## Artifact Naming

```
deepnode-v{VERSION}-macos{MAJOR}-{ARCH}.tar.gz
```

Examples:
- `deepnode-v1.0.0-macos15-arm64.tar.gz` — standard mode, macOS 15, Apple Silicon
- `deepnode-v1.0.0-macos26-arm64.tar.gz` — binary-only mode, macOS 26, Apple Silicon

---

## Troubleshooting

### `No module named 'tqdm.cli'` / `'tqdm.gui'`

`tqdm/__init__.py` unconditionally imports `cli`, `gui`, and `notebook` at top level. These modules must NOT be deleted during security hardening.

### `ValueError: Target module "wheel" already imported as "ExcludedModule('wheel',)"`

PyInstaller's setuptools hook creates aliases for vendored packages. Do not add `pip`, `setuptools`, or `wheel` to the `excludes` list.

### `No module named 'PIL'`

`mlx_vlm` depends on Pillow for image processing. Do not exclude `PIL` or `pillow` from the build.

### nanobind "refusing to add duplicate key" (macOS 13–15)

Use **standard mode** (without `--binary-only`). The mlx isolation architecture prevents this by:
1. Excluding mlx from PyInstaller
2. Installing mlx to a separate `mlx-packages/` directory
3. Runtime hook pre-loads `mlx.core` from the stable path before any business code runs

### Binary too large

Check for accidentally included packages. Common offenders:
- `torch` (~600MB) — should be excluded and blocked by runtime hook
- `datasets` / `pyarrow` — should be excluded
- `opencv` — should be excluded (mlx_vlm uses PIL, not OpenCV)

Use `du -sh dist/deepnode-server/_internal/*/ | sort -h` to find large directories.

---

## Build Duration Reference

| Step | Approximate Time |
|------|-----------------|
| Python deps install | 10–30s (cached: 1s) |
| Vue frontend build | 5–15s |
| PyInstaller packaging | 30–90s |
| mlx-packages install + hardening | 20–60s |
| Code signing | 10–30s |
| **Total** | **~2–4 minutes** |
