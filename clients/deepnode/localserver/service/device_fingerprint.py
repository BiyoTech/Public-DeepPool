"""设备指纹（simei）生成模块。

完整移植自 Rust `device_fingerprint.rs`，通过采集本机硬件信息
（系统标识、磁盘序列号、GPU 信息、网卡 MAC 地址等），
拼接后经 SHA-256 哈希，生成 64 位十六进制字符串作为设备唯一 ID。

当前支持 macOS、Windows、Linux 三个平台。
算法与 Rust 版本完全一致，相同硬件产生相同的 simei。
"""

from __future__ import annotations

import hashlib
import logging
import platform
import re
import subprocess
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# 无效硬件值黑名单：匹配时丢弃该值，避免不同设备产生相同指纹
_INVALID_VALUES = frozenset({
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "to be filled by o.e.m.",
    "default string",
    "system serial number",
})

# 用于合并连续空白字符
_WHITESPACE_RE = re.compile(r"\s+")

# ─────────────────────────────────────────────────
# 基础工具函数（与 Rust 版本逻辑完全对齐）
# ─────────────────────────────────────────────────


def _run_command(cmd: str, args: list[str], timeout: int = 10) -> str:
    """执行系统命令并返回 stdout 输出（去除首尾空白）。

    命令执行失败或返回非零状态码时返回空字符串。
    """
    try:
        result = subprocess.run(
            [cmd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except Exception as exc:
        logger.debug("command '%s %s' failed: %s", cmd, " ".join(args), exc)
        return ""


def _normalize(value: str) -> str:
    """标准化硬件值：合并连续空白为单个空格 → 转小写 → 黑名单过滤。

    与 Rust 版本 normalize() 函数行为完全一致。
    """
    compact = _WHITESPACE_RE.sub(" ", value).strip().lower()
    if compact in _INVALID_VALUES:
        return ""
    return compact


def _push_value(values: set[str], raw: str) -> None:
    """将一个硬件值标准化后加入集合（空值丢弃）。

    使用 Python set 收集，最终排序时用 sorted() 模拟 Rust BTreeSet。
    """
    v = _normalize(raw)
    if v:
        values.add(v)


def _push_lines(values: set[str], text: str) -> None:
    """按行拆分文本，将每一行作为独立硬件值加入集合。"""
    for line in text.splitlines():
        _push_value(values, line)


def _extract_after_colon(output: str, keys: list[str], values: set[str]) -> None:
    """从 'key: value' 格式的输出中提取指定 key 对应的 value。

    与 Rust 版本 extract_after_colon() 行为一致：
    只有冒号左侧 key（忽略大小写）匹配 keys 列表中的某一项时，
    才将冒号右侧 value 加入集合。
    """
    for line in output.splitlines():
        raw = line.strip()
        if ":" not in raw:
            continue
        left, right = raw.split(":", 1)
        key = left.strip().lower()
        if key in keys:
            _push_value(values, right)


# ─────────────────────────────────────────────────
# Windows 平台硬件采集
# ─────────────────────────────────────────────────


def _collect_ps(script: str) -> str:
    """执行 PowerShell 脚本并返回输出（仅 Windows 使用）。"""
    return _run_command("powershell", ["-NoProfile", "-Command", script])


def _collect_windows_material() -> tuple[set[str], set[str], set[str], set[str]]:
    """采集 Windows 平台的硬件指纹素材。

    返回四个集合：(system, disk, gpu, network)
    """
    system: set[str] = set()
    disk: set[str] = set()
    gpu: set[str] = set()
    network: set[str] = set()

    # ---- 系统级标识 ----
    _push_value(system, _collect_ps("(Get-CimInstance Win32_ComputerSystemProduct).UUID"))
    _push_value(system, _collect_ps("(Get-CimInstance Win32_BIOS).SerialNumber"))
    _push_value(system, _collect_ps("(Get-CimInstance Win32_BaseBoard).SerialNumber"))
    _push_value(system, _collect_ps(
        "(Get-CimInstance Win32_Processor | Select-Object -First 1).ProcessorId"
    ))

    # ---- 磁盘序列号：优先 PhysicalMedia，退而求其次用 DiskDrive ----
    disk_serials = _collect_ps(
        "Get-CimInstance Win32_PhysicalMedia | Select-Object -ExpandProperty SerialNumber"
    )
    if not disk_serials:
        _push_lines(disk, _collect_ps(
            "Get-CimInstance Win32_DiskDrive | Select-Object -ExpandProperty SerialNumber"
        ))
    else:
        _push_lines(disk, disk_serials)

    # ---- GPU PNP 设备 ID ----
    _push_lines(gpu, _collect_ps(
        "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty PNPDeviceID"
    ))

    # ---- 物理网卡 MAC 地址（排除虚拟/VPN 适配器）----
    _push_lines(network, _collect_ps(
        "Get-CimInstance Win32_NetworkAdapter | Where-Object { "
        "$_.PhysicalAdapter -eq $true -and $_.MACAddress -and "
        "$_.PNPDeviceID -match '^PCI' } | Select-Object -ExpandProperty MACAddress"
    ))

    return system, disk, gpu, network


# ─────────────────────────────────────────────────
# macOS 平台硬件采集
# ─────────────────────────────────────────────────


def _collect_macos_material() -> tuple[set[str], set[str], set[str], set[str]]:
    """采集 macOS 平台的硬件指纹素材。

    返回四个集合：(system, disk, gpu, network)
    与 Rust 版本 collect_macos_material() 完全一致。
    """
    system: set[str] = set()
    disk: set[str] = set()
    gpu: set[str] = set()
    network: set[str] = set()

    # ---- 通过 ioreg 获取平台 UUID 和序列号 ----
    ioreg = _run_command("ioreg", ["-rd1", "-c", "IOPlatformExpertDevice"])
    for line in ioreg.splitlines():
        row = line.strip()
        if '"IOPlatformUUID"' in row:
            if "=" in row:
                _, right = row.split("=", 1)
                _push_value(system, right.strip().strip('"'))
        if '"IOPlatformSerialNumber"' in row:
            if "=" in row:
                _, right = row.split("=", 1)
                _push_value(system, right.strip().strip('"'))

    # ---- 通过 system_profiler 获取硬件概要信息 ----
    hardware = _run_command("system_profiler", ["SPHardwareDataType"])
    _extract_after_colon(
        hardware,
        ["hardware uuid", "serial number (system)", "serial number", "model identifier"],
        system,
    )

    # ---- CPU 品牌字符串 ----
    cpu_brand = _run_command("sysctl", ["-n", "machdep.cpu.brand_string"])
    _push_value(system, cpu_brand)

    # ---- 磁盘信息：合并 NVMe 与 SATA 数据 ----
    nvme = _run_command("system_profiler", ["SPNVMeDataType"])
    sata = _run_command("system_profiler", ["SPSerialATADataType"])
    disk_joined = f"{nvme}\n{sata}"
    _extract_after_colon(
        disk_joined,
        ["serial number", "device / media name", "model"],
        disk,
    )

    # ---- GPU / 显示器信息 ----
    displays = _run_command("system_profiler", ["SPDisplaysDataType"])
    _extract_after_colon(displays, ["chipset model", "device id", "vendor"], gpu)

    # ---- 网卡 MAC 地址（仅采集真实硬件端口）----
    hw_ports = _run_command("networksetup", ["-listallhardwareports"])
    for line in hw_ports.splitlines():
        row = line.strip()
        if row.startswith("Ethernet Address:"):
            mac = row[len("Ethernet Address:"):].strip()
            if mac and mac != "N/A":
                _push_value(network, mac)

    return system, disk, gpu, network


# ─────────────────────────────────────────────────
# Linux 平台硬件采集
# ─────────────────────────────────────────────────


def _collect_linux_material() -> tuple[set[str], set[str], set[str], set[str]]:
    """采集 Linux 平台的硬件指纹素材。

    返回四个集合：(system, disk, gpu, network)
    Rust 版本未实现 Linux，此处为 Python 扩展实现。
    """
    system: set[str] = set()
    disk: set[str] = set()
    gpu: set[str] = set()
    network: set[str] = set()

    # ---- 系统级标识 ----
    # DMI UUID（需要 root 权限，失败则跳过）
    _push_value(system, _run_command("cat", ["/sys/class/dmi/id/product_uuid"]))
    _push_value(system, _run_command("cat", ["/sys/class/dmi/id/product_serial"]))
    _push_value(system, _run_command("cat", ["/sys/class/dmi/id/board_serial"]))

    # CPU model name
    cpuinfo = _run_command("cat", ["/proc/cpuinfo"])
    for line in cpuinfo.splitlines():
        if line.strip().lower().startswith("model name"):
            if ":" in line:
                _, right = line.split(":", 1)
                _push_value(system, right)
            break  # 只取第一个 CPU

    # ---- 磁盘序列号 ----
    # 通过 lsblk 获取磁盘序列号
    lsblk = _run_command("lsblk", ["-dno", "SERIAL"])
    _push_lines(disk, lsblk)

    # ---- GPU 信息 ----
    # 通过 lspci 获取 GPU 信息
    lspci = _run_command("lspci", [])
    for line in lspci.splitlines():
        lowered = line.lower()
        if "vga" in lowered or "3d controller" in lowered or "display controller" in lowered:
            _push_value(gpu, line)

    # ---- 网卡 MAC 地址（仅物理网卡）----
    ip_link = _run_command("ip", ["link", "show"])
    current_iface = ""
    for line in ip_link.splitlines():
        stripped = line.strip()
        # 接口行格式: "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ..."
        if not stripped.startswith("link/"):
            parts = stripped.split(":")
            if len(parts) >= 2:
                current_iface = parts[1].strip().split("@")[0]
        # MAC 地址行格式: "link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff"
        if stripped.startswith("link/ether"):
            mac = stripped.split()[1] if len(stripped.split()) > 1 else ""
            # 排除虚拟网卡（常见前缀：lo, veth, docker, br-, virbr）
            if mac and not any(current_iface.startswith(p) for p in
                               ("lo", "veth", "docker", "br-", "virbr")):
                _push_value(network, mac)

    return system, disk, gpu, network


# ─────────────────────────────────────────────────
# 核心算法：拼接 + SHA-256 哈希
# ─────────────────────────────────────────────────


def _build_payload(
    os_name: str,
    system: set[str],
    disk: set[str],
    gpu: set[str],
    network: set[str],
) -> str:
    """将所有硬件素材拼接为确定性字符串。

    格式：os=<OS>;system=<A|B|...>;disk=<X|Y|...>;gpu=<M|N|...>;network=<P|Q|...>
    各维度内部以 '|' 分隔（sorted 保证顺序稳定），维度间以 ';' 分隔。

    使用 sorted() 模拟 Rust BTreeSet 的排序行为，确保相同硬件产生相同的 payload。
    """
    return (
        f"os={os_name}"
        f";system={'|'.join(sorted(system))}"
        f";disk={'|'.join(sorted(disk))}"
        f";gpu={'|'.join(sorted(gpu))}"
        f";network={'|'.join(sorted(network))}"
    )


def generate_device_fingerprint_id() -> str:
    """生成设备指纹 ID（simei）。

    流程：
      1. 根据当前操作系统选择对应的硬件采集函数
      2. 将采集到的四维硬件素材拼接为确定性字符串
      3. 对拼接结果执行 SHA-256 哈希
      4. 返回 64 位十六进制字符串作为设备唯一 ID

    Raises:
        RuntimeError: 不支持的操作系统或未能采集到任何硬件标识符
    """
    os_name = platform.system().lower()

    # macOS 在 Python 中为 "darwin"，但 Rust 的 std::env::consts::OS 为 "macos"
    # 为保持与 Rust 版本输出一致，统一映射
    os_mapping = {"darwin": "macos", "windows": "windows", "linux": "linux"}
    mapped_os = os_mapping.get(os_name)

    if mapped_os is None:
        raise RuntimeError(f"unsupported OS: {os_name}")

    # 根据操作系统分发到对应的采集函数
    collectors = {
        "macos": _collect_macos_material,
        "windows": _collect_windows_material,
        "linux": _collect_linux_material,
    }
    system, disk, gpu, network = collectors[mapped_os]()

    # 至少需要采集到一项硬件标识，否则无法生成有意义的指纹
    collected_count = len(system) + len(disk) + len(gpu) + len(network)
    if collected_count == 0:
        raise RuntimeError("unable to collect any hardware identifiers")

    logger.info(
        "device fingerprint material: system=%d disk=%d gpu=%d network=%d",
        len(system), len(disk), len(gpu), len(network),
    )

    # 拼接 → SHA-256 哈希 → 64 位十六进制
    payload = _build_payload(mapped_os, system, disk, gpu, network)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    logger.info("device fingerprint generated: %s...%s", digest[:8], digest[-8:])
    return digest


# ─────────────────────────────────────────────────
# 缓存层：simei 仅需生成一次
# ─────────────────────────────────────────────────

_cached_simei: Optional[str] = None
_cache_lock = threading.Lock()


def get_cached_simei() -> str:
    """获取设备指纹 ID，首次调用时生成并缓存，后续直接返回。

    线程安全：使用锁保证并发场景下只生成一次。
    """
    global _cached_simei
    if _cached_simei is not None:
        return _cached_simei

    with _cache_lock:
        # 双重检查，防止多线程重复生成
        if _cached_simei is not None:
            return _cached_simei
        _cached_simei = generate_device_fingerprint_id()
        return _cached_simei
