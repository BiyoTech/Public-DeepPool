# DeepNode Security Technical Design

> **Version**: v1.2 &nbsp;|&nbsp; **Updated**: 2026-04-11

## 1. Threat Model

### 1.1 Core Threat

DeepNode nodes process LLM inference requests forwarded by the Platform. A malicious node operator could tamper with the `mlx-packages/` directory (which contains plain-text Python files in unprotected builds) to intercept plaintext prompts, exfiltrate user data, or return poisoned inference results.

### 1.2 Threat Actor Profile

| Attribute | Description |
|-----------|-------------|
| Identity | Node operator (has physical access to the machine) |
| Capability | Root/admin access, can modify files on disk, can run arbitrary tools |
| Motivation | Steal inference request content, game token accounting, credential theft |
| Constraint | Cannot modify Platform server-side code; each attack must be per-machine |

### 1.3 Attack Surface

```
deepnode-server/
├── deepnode-server-bin      # PyInstaller frozen binary (hard to modify)
├── _internal/               # PyInstaller runtime (frozen .pyc + .so/.dylib)
│   └── integrity_manifest.json  # Build-time hash manifest
├── mlx-packages/            # ⚠ PRIMARY ATTACK SURFACE
│   ├── mlx/                 # .pyc compiled (was plain .py)
│   ├── mlx_lm/              # .pyc compiled
│   ├── transformers/        # .pyc compiled
│   └── _stdlib/             # .pyc compiled
└── config.yaml              # User-editable config
```

### 1.4 Attack Scenarios

| # | Scenario | Impact | Pre-mitigation |
|---|----------|--------|----------------|
| A1 | Modify `.py` files in mlx-packages/ to log/exfiltrate prompts | Critical — data theft | No `.py` files exist (compiled to `.pyc`) |
| A2 | Decompile `.pyc`, modify, recompile | High — requires tooling | Integrity manifest detects hash mismatch |
| A3 | Copy credential to another machine, run tampered node | High — lateral movement | Device binding rejects cross-machine credentials |
| A4 | Read credential file to impersonate device | Medium — identity theft | Keychain encryption protects credentials |
| A5 | Inject malicious dylib via DYLD_INSERT_LIBRARIES | High — code injection | Hardened Runtime blocks library injection |
| A6 | Attach debugger to extract runtime secrets | Medium — memory inspection | Hardened Runtime restricts debugging |

---

## 2. Security Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BUILD TIME                                       │
│                                                                          │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────┐               │
│  │ .py → .pyc  │──▸│ Integrity    │──▸│ Hardened       │               │
│  │ + delete    │   │ Manifest     │   │ Runtime Sign   │               │
│  │ sources     │   │ (SHA-256)    │   │ + Entitlements │               │
│  └─────────────┘   └──────────────┘   └────────────────┘               │
│         │                  │                    │                        │
│  ┌──────▼──────────────────▼────────────────────▼──────────────────┐    │
│  │            Signed Artifact (tar.gz)                              │    │
│  │  deepnode-server-bin (frozen + signed)                           │    │
│  │  _internal/integrity_manifest.json (embedded hash DB)           │    │
│  │  mlx-packages/**/*.pyc (compiled, no .py sources)               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         RUNTIME                                          │
│                                                                          │
│  ┌────────────────────────────────────────────────┐                     │
│  │          PyInstaller Runtime Hook               │   EARLIEST STAGE   │
│  │  ① Inject mlx-packages/ into sys.path          │                     │
│  │  ② Install torch import blocker                 │                     │
│  │  ③ INTEGRITY VERIFICATION (SHA-256 check)       │◀── Tamper detect   │
│  │  ④ Pre-load mlx.core (nanobind lock)            │                     │
│  │  ⑤ Set DEEPPOOL_PROFILE                         │                     │
│  └──────────────────────┬─────────────────────────┘                     │
│                          │                                               │
│  ┌──────────────────────▼─────────────────────────┐                     │
│  │          Credential Loading                      │                     │
│  │  ① Load from macOS Keychain (primary)           │                     │
│  │  ② Fallback to ~/.deeppool/credential.json      │                     │
│  │  ③ DEVICE BINDING VERIFICATION                  │◀── Cross-machine   │
│  │     (re-compute hash, compare with stored)       │    detect           │
│  └──────────────────────┬─────────────────────────┘                     │
│                          │                                               │
│  ┌──────────────────────▼─────────────────────────┐                     │
│  │          Platform Registration                   │                     │
│  │  ① Register device with hardware info           │                     │
│  │  ② Report security status in device_config:     │                     │
│  │     • integrity_passed: bool                    │◀── Platform-side    │
│  │     • device_bound: bool                        │    monitoring       │
│  │     • binding_factors: int                      │                     │
│  └──────────────────────┬─────────────────────────┘                     │
│                          │                                               │
│  ┌──────────────────────▼─────────────────────────┐                     │
│  │          Server-Side Enforcement                  │                     │
│  │  ① evaluateDeviceSecurity() on Register/Update  │                     │
│  │     • Missing "security" field → auto-block     │◀── Admission ctrl   │
│  │     • integrity_passed=false → auto-block       │                     │
│  │  ② DeviceStatusChecker (30s cached from DB)     │                     │
│  │  ③ FindByModel() filters blocked/cheating       │◀── Dispatch filter  │
│  │     → zero inference tasks to blocked devices   │                     │
│  └────────────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Defense Layer 1: Source Code Protection

### 3.1 .py → .pyc Compilation

**Goal**: Eliminate plain-text Python source files from the artifact, forcing attackers to use non-trivial decompilation tools.

**Build-time process** (in `build_standalone_mac.sh`):

```
mlx-packages/**/*.py  ──compileall──▸  __pycache__/*.cpython-3xx.pyc
                                              │
                                     flatten to parent dir
                                              │
                                        module.pyc
                                              │
                                     delete all *.py
```

**Implementation details**:
- Python `compileall.compile_dir()` with `force=True`, `quiet=1`
- `.pyc` files moved from `__pycache__/` to parent directories (flat layout)
- All `__pycache__/` directories removed
- All `.py` source files deleted
- Applied to both `mlx-packages/` and `mlx-packages/_stdlib/`

**Effectiveness**:
- Prevents trivial `vim`/`sed` modification of source files
- Decompilation tools (uncompyle6, decompyle3) can reverse `.pyc` but require effort and expertise
- Combined with integrity verification, even decompiled+recompiled files will have different hashes

### 3.2 Generated Code Freezing

**Goal**: Protect protobuf/gRPC stub files from modification.

The `generated/` directory (containing `*_pb2.py` and `*_pb2_grpc.py`) is no longer shipped as plain-text data files. Instead, all generated modules are registered as PyInstaller `hiddenimports`, causing them to be frozen into the main binary:

```python
# In standalone.spec — hiddenimports list
'generated', 'generated.__init__',
'generated.llm_infer_pb2', 'generated.llm_infer_pb2_grpc',
'generated.manager_service_pb2', 'generated.manager_service_pb2_grpc',
'generated.node_tunnel_pb2', 'generated.node_tunnel_pb2_grpc',
'generated.nodemanager_service_pb2', 'generated.nodemanager_service_pb2_grpc',
```

This means the gRPC communication protocol definitions are embedded inside the signed binary — modifying them requires reverse-engineering the PyInstaller archive.

---

## 4. Defense Layer 2: Runtime Integrity Verification

### 4.1 Architecture

```
BUILD TIME                              RUNTIME
──────────                              ───────
                                        
  Hash all critical files               Load manifest from
  (.pyc, .so, .dylib, binary)           _internal/integrity_manifest.json
         │                                       │
         ▼                                       ▼
  Generate JSON manifest ──────────▸    For each file in manifest:
  {                                       actual_hash = SHA256(file)
    "version": "1.0.0",                   if actual_hash != expected_hash:
    "build_timestamp": "...",               → INTEGRITY FAILED
    "files": {                            
      "mlx-packages/mlx/core.pyc":      Report result via env var:
        "a1b2c3...",                       _DEEPNODE_INTEGRITY_FAILED=1
      "deepnode-server-bin":               _DEEPNODE_INTEGRITY_DETAIL=...
        "d4e5f6...",                     
      ...                               Report to Platform in device_config:
    }                                      security.integrity_passed
  }                                     
         │                              
         ▼                              
  Place in _internal/ (frozen path)     
```

### 4.2 Module: `service/integrity.py`

| Component | Description |
|-----------|-------------|
| `IntegrityResult` | Dataclass holding verification outcome (passed, mismatched files, timing) |
| `verify_integrity()` | Main entry: loads manifest, hashes files, compares, returns result |
| `_sha256_file()` | Streaming SHA-256 computation (64KB buffer) |
| `_find_manifest()` | Locates manifest in `sys._MEIPASS` (frozen mode only) |
| `generate_manifest()` | Build-time utility to create the hash database |

### 4.3 Verification Timing

The integrity check runs in the **runtime hook** — the earliest possible execution point in the PyInstaller lifecycle, before any business code loads:

```python
# In _runtime_hook.py (generated by build script)
from service.integrity import verify_integrity as _verify
_integrity_result = _verify()
if _integrity_result is not None and not _integrity_result.passed:
    os.environ['_DEEPNODE_INTEGRITY_FAILED'] = '1'
    os.environ['_DEEPNODE_INTEGRITY_DETAIL'] = ';'.join(...)
```

### 4.4 Files Covered

| Directory | Extensions Hashed | Rationale |
|-----------|-------------------|-----------|
| `mlx-packages/` | `.pyc`, `.so`, `.dylib` | Primary attack surface — inference code |
| `_internal/` | `.so`, `.dylib` | Runtime native libraries |
| Root | `deepnode-server-bin` | Main frozen binary |

### 4.5 Limitations (Ad-hoc Signing)

With ad-hoc code signing, an attacker can theoretically:
1. Modify files in `mlx-packages/`
2. Update `integrity_manifest.json` with new hashes
3. Re-sign with `codesign --force --sign -`

This is mitigated by:
- The manifest is inside `_internal/` (PyInstaller frozen path) — modifying it requires unpacking and repacking the binary
- Combined with device binding, the attacker must repeat this on every machine

**With Developer ID signing** (future upgrade): the binary signature protects the manifest, making step 2 impossible without the private key.

---

## 5. Defense Layer 3: macOS Hardened Runtime

### 5.1 Codesign Configuration

```bash
# Environment variable for Developer ID upgrade path
CODESIGN_IDENTITY="${DEEPNODE_CODESIGN_IDENTITY:--}"  # default: ad-hoc

# All .so/.dylib files signed with Hardened Runtime
codesign --force --sign "$CODESIGN_IDENTITY" --options runtime \
    $CODESIGN_TIMESTAMP <file>

# Main binary signed with Hardened Runtime + entitlements
codesign --force --sign "$CODESIGN_IDENTITY" --options runtime \
    --entitlements deepnode_entitlements.plist \
    $CODESIGN_TIMESTAMP deepnode-server-bin
```

### 5.2 Entitlements

```xml
<dict>
    <!-- Allow loading mlx Metal shader plugins (unsigned in-process) -->
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <!-- Allow JIT for mlx Metal compute pipeline compilation -->
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
    <!-- Allow unsigned executable memory (numpy/scipy BLAS) -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
</dict>
```

### 5.3 Hardened Runtime Protections

| Protection | Effect |
|-----------|--------|
| Library validation | Blocks `DYLD_INSERT_LIBRARIES` code injection |
| Debugging restriction | Prevents `lldb`/`dtrace` attachment |
| Code signing enforcement | OS rejects execution if signature is broken |
| Runtime exceptions | Only the 3 entitlements above are granted (minimal privilege) |

### 5.4 Developer ID Upgrade Path

To upgrade from ad-hoc to Developer ID signing:

```bash
# Set environment variable before build
DEEPNODE_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
    bash build_standalone_mac.sh
```

This automatically enables:
- `--timestamp` (instead of `--timestamp=none`) — Apple timestamp server
- Apple Notarization readiness
- Signature identity verification — attackers cannot re-sign

---

## 6. Defense Layer 4: Device Binding

### 6.1 Design Goal

Ensure that a credential obtained on machine A cannot be used on machine B. This forces an attacker to independently compromise **every** machine, raising attack cost from O(1) to O(N).

### 6.2 Hardware Binding Factors

| Factor | Source | Forgery Difficulty |
|--------|--------|-------------------|
| `platform_uuid` | `IOPlatformUUID` via `ioreg` (Secure Enclave) | Extremely hard |
| `serial_number` | `system_profiler SPHardwareDataType` | Hardware-level |
| `hardware_uuid` | `system_profiler SPHardwareDataType` | Hardware-level |
| `model_id` | `system_profiler SPHardwareDataType` | Trivial (same model) |

### 6.3 Binding Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ FIRST ACTIVATION (save_credential)                               │
│                                                                  │
│  simei ──┐                                                       │
│          ├──▸ SHA256(simei;hardware_uuid=X;model_id=Y;           │
│  HW IDs ─┘          platform_uuid=Z;serial_number=W)            │
│                              │                                   │
│                              ▼                                   │
│                      binding_hash = "a1b2c3..."                  │
│                              │                                   │
│                    ┌─────────┴─────────┐                         │
│                    ▼                   ▼                          │
│              Keychain store      JSON file store                 │
│              (encrypted)         (fallback)                      │
│              {simei, token,      {simei, token,                  │
│               binding_hash}       binding_hash}                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ EVERY STARTUP (load_credential)                                  │
│                                                                  │
│  Load stored credential (Keychain or file)                       │
│         │                                                        │
│         ▼                                                        │
│  stored.binding_hash exists?                                     │
│    │ No → skip check (legacy credential)                         │
│    │ Yes ↓                                                       │
│  Re-compute binding_hash from current hardware                   │
│         │                                                        │
│         ▼                                                        │
│  current_hash == stored_hash?                                    │
│    │ Yes → credential valid, proceed                             │
│    │ No  → REJECT — "credential copied from another machine"    │
│           → load_credential() returns None                       │
│           → device must re-register                              │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 Module: `service/device_binding.py`

| Function | Description |
|----------|-------------|
| `get_hardware_binding_factors()` | Collects IOPlatformUUID, serial, HW UUID, model ID |
| `compute_binding_hash(simei)` | `SHA256(simei;factor1=val1;factor2=val2;...)` |
| `verify_binding(simei, stored_hash)` | Re-computes and compares, returns bool |

---

## 7. Defense Layer 5: Credential Security

### 7.1 Storage Strategy

```
┌─────────────────────────────────────────────────────┐
│                save_credential()                      │
│                                                       │
│  ┌────────────────────┐   ┌─────────────────────┐   │
│  │ PRIMARY:           │   │ FALLBACK:            │   │
│  │ macOS Keychain     │   │ JSON file            │   │
│  │                    │   │ ~/.deeppool/          │   │
│  │ Service:           │   │   device_credential   │   │
│  │   com.deeppool.    │   │   .json               │   │
│  │   deepnode         │   │                       │   │
│  │                    │   │ Contains:             │   │
│  │ Encryption:        │   │   simei, token,       │   │
│  │   AES-256-GCM      │   │   binding_hash        │   │
│  │   (Secure Enclave) │   │                       │   │
│  │                    │   │ Permissions:           │   │
│  │ Access control:    │   │   0600 (user-only)    │   │
│  │   Login keychain   │   │                       │   │
│  │   + Touch ID       │   │                       │   │
│  └────────────────────┘   └─────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 7.2 Module: `service/keychain.py`

Uses macOS `security` CLI to interact with the system Keychain:

| Function | Description |
|----------|-------------|
| `save_to_keychain(simei, token, binding_hash)` | `security add-generic-password -U` |
| `load_from_keychain()` | `security find-generic-password -w` |
| `delete_from_keychain()` | `security delete-generic-password` |

**Keychain entry identifiers**:
- Service: `com.deeppool.deepnode`
- Account: `device_credential`
- Password: JSON payload `{"simei": "...", "token": "...", "binding_hash": "..."}`

### 7.3 Module: `service/credential.py`

Orchestrates the dual-storage strategy with device binding integration:

| Function | Flow |
|----------|------|
| `save_credential(cred)` | Compute binding hash → Save to Keychain → Save to file |
| `load_credential()` | Load raw → Verify binding hash → Return or reject |
| `_load_credential_raw()` | Keychain first → File fallback |

---

## 8. Defense Layer 6: Platform-Side Monitoring

### 8.1 Security Status Reporting

When a device registers or reports "ready" status, the `device_config` JSON includes a `security` object:

```json
{
  "init_stage": "ready",
  "simei": "a1b2c3...",
  "security": {
    "integrity_passed": true,
    "device_bound": true,
    "binding_factors": 4
  },
  "hardware": { ... }
}
```

### 8.2 Platform Detection Signals

| Signal | Source | Meaning |
|--------|--------|---------|
| `security` field missing | Legacy build without hardening | Unprotected node |
| `integrity_passed = false` | Runtime hook env var | Files tampered after build |
| `device_bound = false` | `get_hardware_binding_factors()` | Non-macOS or hardware info unavailable |
| `binding_factors < 3` | Binding module | Some hardware IDs missing (VM?) |
| Credential load failure | `load_credential()` returns None | Binding mismatch (credential copied) |
| Missing heartbeat | NodeManager tunnel timeout | Node offline or killed |

### 8.3 Response Actions (Platform-side)

**Manager-side enforcement** (`evaluateDeviceSecurity` in `user_service.go`):

| Condition | Action | Status |
|-----------|--------|--------|
| `security` field missing (unprotected build) | Auto-block device | ✅ Implemented |
| `integrity_passed = false` | Auto-block device | ✅ Implemented |
| `device_bound = false` | Log warning (non-macOS compat) | ✅ Implemented |

**NodeManager-side enforcement** (`DeviceStatusChecker` + `FindByModel` filter):

| Condition | Action | Status |
|-----------|--------|--------|
| `user_devices.status = blocked` | Exclude from inference dispatch | ✅ Implemented |
| `user_devices.status = cheating` | Exclude from inference dispatch | ✅ Implemented |

The `DeviceStatusChecker` maintains an in-memory cache of blocked/cheating SIMEIs
(refreshed every 30s from DB), providing O(1) lookup on the dispatch hot path.
Blocked devices remain connected via gRPC tunnel but receive zero inference tasks.

---

## 9. Build Security Pipeline

### 9.1 Full Build Flow

```
build_standalone_mac.sh [--profile dev|prod]
  │
  ▼
[0/6] Install Python deps
  │
  ▼
[1/6] Build Vue frontend → web-dist/
  │
  ▼
[2/6] Generate _runtime_hook.py + standalone.spec
  │    └── Hook includes: integrity check, torch blocker, mlx preload
  │    └── Spec: generated/ as hiddenimports (frozen, not datas)
  │
  ▼
[3/6] PyInstaller packaging → dist/deepnode-server/
  │    └── Verify critical modules present
  │    └── Clean mlx/torch residue from _internal/
  │
  ▼
[4/6] Install mlx to mlx-packages/
  │    └── Platform-targeted wheel install
  │    └── Purge torch family (~600MB)
  │    └── ★ COMPILE .py → .pyc + DELETE .py SOURCES ★
  │    └── Copy + compile stdlib
  │
  ▼
[5/6] Generate launcher + post-processing
  │    └── Copy config (profile-dependent)
  │    └── Replace symlinks with real files
  │
  ▼
[6/6] SECURITY HARDENING
       └── ★ Generate integrity manifest (SHA-256 all critical files) ★
       └── ★ Codesign with Hardened Runtime + entitlements ★
       └── Package tar.gz
```

### 9.2 Signing Identity Configuration

| Mode | `DEEPNODE_CODESIGN_IDENTITY` | Timestamp | Notarizable |
|------|------|-----------|-------------|
| Ad-hoc (current) | `-` (default) | `--timestamp=none` | No |
| Developer ID (future) | `Developer ID Application: ...` | `--timestamp` | Yes |

---

## 10. Security Effectiveness Matrix

| Attack Vector | L1: .pyc | L2: Integrity | L3: Hardened RT | L4: Binding | L5: Keychain | L6: Platform | Combined |
|---------------|----------|---------------|-----------------|-------------|--------------|--------------|----------|
| Edit `.py` in mlx-packages/ | ✅ No `.py` exists | — | — | — | — | — | **Blocked** |
| Edit `.pyc` in mlx-packages/ | — | ✅ Hash mismatch | — | — | — | ✅ Auto-block | **Blocked** |
| Modify `.so`/`.dylib` | — | ✅ Hash mismatch | ✅ Signature broken | — | — | ✅ Auto-block | **Blocked** |
| Modify manifest + files | — | ✅ HMAC rejects | — | — | — | — | **Blocked** |
| Read generated/ proto stubs | ✅ Frozen in binary | — | — | — | — | — | **Protected** |
| Copy credential to new machine | — | — | — | ✅ Binding rejects | — | — | **Blocked** |
| Copy .pyc patches cross-device | — | ✅ Hash mismatch | — | — | ✅ Watermark mismatch | — | **Blocked** |
| Read credential from disk | — | — | — | — | ✅ Keychain + 0600 | — | **Protected** |
| DYLD_INSERT_LIBRARIES injection | — | — | ✅ Blocked by HR | — | — | — | **Blocked** |
| Debugger attachment | — | — | ✅ Restricted by HR | — | — | — | **Blocked** |
| Runtime file replacement | — | ✅ Periodic check | — | — | — | ✅ Auto-block | **Detected+Kill** |
| Tamper + re-sign (ad-hoc) | — | ✅ HMAC rejects | ⚠ Re-signable | ✅ Per-machine | — | ✅ Auto-block | **Blocked** |
| Tamper + re-sign (Dev ID) | — | ✅ Binary protected | ✅ Identity verified | ✅ Per-machine | — | ✅ Auto-block | **Blocked** |
| Use unprotected legacy build | — | — | — | — | — | ✅ Admission reject | **Blocked** |
| Blocked device still online | — | — | — | — | — | ✅ Dispatch filter | **Zero tasks** |

---

## 11. File Inventory

### 11.1 Security Modules (Client-side)

| File | Lines | Purpose |
|------|-------|---------|
| `service/integrity.py` | ~235 | SHA-256 integrity verification (build + runtime) |
| `service/keychain.py` | ~152 | macOS Keychain credential storage |
| `service/device_binding.py` | ~168 | Hardware-bound credential verification |
| `service/credential.py` | ~136 | Dual-storage credential management with binding |
| `service/pyc_watermark.py` | ~175 | Device-specific .pyc watermarking (cross-machine detection) |
| `service/device_fingerprint.py` | ~393 | Hardware fingerprint (SIMEI) generation |

### 11.1b Security Modules (Server-side)

| File | Lines | Purpose |
|------|-------|---------|
| `user_service.go` (`evaluateDeviceSecurity`) | ~50 | Server-side admission control: blocks unprotected/tampered devices |
| `device_status_checker.go` | ~95 | Cached blocked-SIMEI lookup for dispatch-time filtering (30s refresh) |
| `connection_hub.go` (`FindByModel`) | ~15 | Dispatch filter: skips blocked/cheating devices in inference routing |

### 11.2 Build Infrastructure

| File | Purpose |
|------|---------|
| `build_standalone_mac.sh` | Unified build script (dev/prod via `--profile`) |
| `release.sh` | GitHub Release automation |

### 11.3 Artifact Structure

```
deepnode-server/                         # Final distributed artifact
├── deepnode-server                      # Shell launcher (daemon mgmt, caffeinate)
├── deepnode-server-bin                  # PyInstaller frozen binary (signed, HR)
├── config.yaml                          # Runtime config (profile-dependent)
├── VERSION                              # Semver version file
├── README.md                            # User documentation
├── _internal/                           # PyInstaller runtime
│   ├── integrity_manifest.json          # ★ Build-time SHA-256 hash database
│   ├── *.so / *.dylib                   # Native libraries (signed)
│   └── (frozen .pyc modules)            # Business code + generated/ stubs
└── mlx-packages/                        # External Python packages
    ├── mlx/**/*.pyc                     # ★ Compiled, no .py sources
    ├── mlx_lm/**/*.pyc                  # ★ Compiled
    ├── transformers/**/*.pyc            # ★ Compiled
    └── _stdlib/**/*.pyc                 # ★ Compiled stdlib
```

---

## 12. Recent Security Enhancements (v1.1)

The following items were implemented in the security hardening pass:

| # | Enhancement | Status | Details |
|---|-------------|--------|---------|
| P0-1 | Fix Keychain `load_from_keychain()` missing `binding_hash` | ✅ Done | `keychain.py` now returns `binding_hash` field, fixing L4 device binding bypass |
| P0-2 | Integrity check failure blocks startup | ✅ Done | Runtime hook calls `sys.exit(78)` on integrity failure instead of just setting env var |
| P0-3 | Platform consumes security status | ✅ Done | `user_service.go` parses `security` object from `device_config` and auto-blocks devices with `integrity_passed=false` |
| P1-7 | Manifest HMAC signing | ✅ Done | Build generates random HMAC key → injects into `integrity.py` → frozen into binary. Manifest verified at runtime with HMAC-SHA256. Attacker cannot modify manifest without binary RE |
| P2-8 | Periodic integrity re-verification | ✅ Done | Background thread checks integrity every 5 minutes. On failure, process terminates (`os._exit(78)`) |
| P2-9 | Platform auto-ban mechanism | ✅ Done | `evaluateDeviceSecurity()` in `user_service.go` auto-blocks devices on both `RegisterDevice` and `UpdateDevice` |
| P2-10 | Credential file permission hardening | ✅ Done | `~/.deeppool/` dir set to `0700`, `device_credential.json` set to `0600` |
| P2-11 | Device-specific `.pyc` watermarking | ✅ Done | First activation: HMAC(binding_hash, file) tag appended to each .pyc → manifest regenerated. Startup: watermark verified against current device. Cross-machine .pyc copies cause hash mismatch |
| P0-12 | Reject unprotected builds server-side | ✅ Done | `evaluateDeviceSecurity()` auto-blocks devices missing `security` field in device_config (legacy builds without hardening) |
| P0-13 | Dispatch-layer blocked device filtering | ✅ Done | `DeviceStatusChecker` caches blocked/cheating SIMEIs from DB; `FindByModel()` skips them during inference routing. Blocked devices get zero tasks even with live gRPC tunnel |

---

## 13. Remaining Future Enhancements

| Priority | Enhancement | Benefit |
|----------|-------------|---------|
| **P0** | Developer ID certificate + Apple Notarization | Prevents re-signing; Gatekeeper trust |
| P3 | Secure Enclave key storage (replace Keychain CLI) | Hardware-backed key protection |
| P3 | Remote attestation protocol | Cryptographic proof of node integrity |
