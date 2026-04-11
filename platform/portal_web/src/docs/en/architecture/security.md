# DeepNode Security

## Overview

DeepPool considers Prompt data security as one of the platform's core capabilities. When your inference requests are processed through DeepNode nodes, we employ a **multi-layer defense-in-depth system** to ensure your Prompts and business data cannot be inspected, tampered with, or leaked on edge devices.

This document is intended for API consumers, explaining DeepNode's security capabilities and the associated usage guidelines.

---

## Data Security Capabilities

### 🔒 Inference Code Anti-Tampering

DeepNode's inference engine code is **compiled and protected** during the build process. Node operators cannot directly view or modify the source code involved in inference. Even with administrator privileges on the device, an attacker cannot simply edit files to inject data-stealing logic.

### 🔒 Runtime Integrity Verification

Each DeepNode installation package generates a unique **integrity fingerprint** at build time. During startup and continuously at runtime, DeepNode verifies that all critical components remain unmodified. If any tampering is detected, the node will **automatically refuse to start or immediately terminate**, ensuring that compromised nodes cannot process any inference requests.

### 🔒 Hardware-Level Device Binding

Each DeepNode instance is bound to the unique hardware identity of its host device upon first activation. Credentials are encrypted and stored using **OS-level secure storage** (such as macOS Keychain). This means:

- Credentials cannot be copied and used on other devices
- Even copying the entire application directory will fail verification on a different device
- Each device's runtime environment is independently isolated

### 🔒 Cross-Device Tampering Detection

DeepNode uses a **device-specific tagging mechanism** that applies unforgeable, device-unique marks to runtime components. If someone attempts to copy modified files from one device to another, the system will immediately detect and reject the operation. Even carefully crafted "patch packages" cannot be propagated across devices.

### 🔒 OS-Level Runtime Protection

DeepNode leverages the operating system's **native security mechanisms** (such as macOS Hardened Runtime) to effectively defend against advanced attack vectors:

- Code injection attacks
- Debugger attachment attacks
- Memory inspection attacks

### 🔒 Platform-Level Security Monitoring

The DeepPool platform continuously monitors the security status of every node. When anomalies are detected, the platform will **automatically ban the node** and stop dispatching inference tasks to it:

- Integrity verification failures
- Device binding anomalies
- Other suspicious security events

Banned nodes can no longer receive any inference requests, providing maximum protection for API consumers' data security.

### 🔒 Server-Side Version Admission Control

The DeepPool platform enforces **security version admission checks** on all connecting DeepNode instances. Legacy installation packages without security hardening are **automatically identified and rejected** during registration, preventing them from entering the available device pool. This ensures:

- Only security-hardened DeepNode builds can connect to the platform
- Legacy versions cannot bypass security mechanisms to serve inference requests
- Platform operators need not manually audit — the system enforces admission automatically

### 🔒 Dispatch-Layer Security Isolation

Even if a device's network connection remains alive, once the platform flags it as anomalous (blocked or cheating), the inference task scheduling system will **skip that device in real time**, ensuring zero inference traffic is dispatched to anomalous nodes. The ban status is linked to the dispatch system in real time — no need to wait for the device to disconnect.

---

## Security Summary

| Layer | Capability | Effect |
|-------|-----------|--------|
| Code Protection | Compiled protection + embedded protocols | Cannot read or modify inference code |
| Integrity Verification | Startup check + continuous runtime check | Immediate termination upon tampering |
| Device Binding | Hardware identity + encrypted storage | Credentials cannot be used cross-device |
| Cross-Device Protection | Device-specific tags + file-level detection | Patches cannot propagate across devices |
| OS Protection | Native OS security mechanisms | Anti-injection / anti-debug / anti-memory-read |
| Platform Monitoring | Real-time security reporting + auto-ban | Anomalous nodes automatically isolated |
| Version Admission | Server-side security version check | Unprotected builds cannot connect |
| Dispatch Isolation | Ban status linked to dispatch in real time | Zero inference traffic to anomalous devices |

---

## Provider Usage Guidelines

Due to the above security mechanisms, DeepNode has the following usage constraints. Please take note if you are a compute provider:

### ⚠️ No Cross-Device Copying

**A DeepNode that has been activated on one Mac cannot be copied to another Mac.** Due to device binding and device-specific tagging, a copied DeepNode will fail security verification and will not start.

**Correct approach**: Download a fresh installation package on the new device and complete the activation process. Each device must independently complete its first activation.

### ⚠️ Do Not Modify Application Files

Do not modify any files within the DeepNode installation directory. The integrity verification mechanism will detect changes and refuse to start. If you encounter issues, please re-download the installation package.

### ⚠️ Credentials Are Device-Bound

Device credentials are bound to hardware. After hardware replacement or reinstallation, re-activation may be required. Credentials are stored in the system's secure storage — there is no need to manually handle credential files during system backup or migration.

---

## FAQ

**Q: Is my Prompt data safe on DeepNode?**

A: Yes. DeepNode protects the inference process through multiple security layers. Node operators cannot tamper with inference code to steal Prompt data. Even if a node is physically compromised, tampering will be detected and blocked.

**Q: What happens if a node operator tries to steal data?**

A: Any modification to inference components will be detected by integrity verification. A tampered node will fail to start. Even if local checks are somehow bypassed, the platform will automatically ban the node and stop dispatching tasks to it.

**Q: How do I migrate DeepNode to a new Mac?**

A: Please download a fresh DeepNode installation package on the new device. An activated DeepNode cannot be migrated by copying.

**Q: Do I need to re-activate after a DeepNode update?**

A: Usually not. Regular updates preserve device binding information. Re-activation is only needed for fresh installations or hardware replacements.
