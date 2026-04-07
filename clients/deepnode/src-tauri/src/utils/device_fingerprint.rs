//! 设备指纹simei生成模块
//!
//! 通过采集本机硬件信息（系统标识、磁盘序列号、GPU 信息、网卡 MAC 地址等），
//! 拼接后经 SHA-256 哈希，生成一个 64 位十六进制字符串作为设备唯一 ID。
//! 当前支持 macOS 与 Windows 平台。

#![allow(dead_code)]

use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::process::Command;

/// 无效硬件值黑名单：这些值通常表示硬件信息缺失或未正确填写，
/// 在采集时应予以过滤，避免不同设备产生相同的指纹。
const INVALID_VALUES: &[&str] = &[
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "to be filled by o.e.m.",
    "default string",
    "system serial number",
];

/// 执行系统命令并返回 stdout 输出（去除首尾空白）。
/// 如果命令执行失败或返回非零状态码，则返回空字符串。
fn run_command(cmd: &str, args: &[&str]) -> String {
    let output = Command::new(cmd).args(args).output();
    match output {
        Ok(o) if o.status.success() => String::from_utf8_lossy(&o.stdout).trim().to_string(),
        _ => String::new(),
    }
}

/// 将原始硬件值进行标准化处理：
/// 1. 合并连续空白为单个空格
/// 2. 转为小写
/// 3. 与黑名单比对，命中则返回空字符串
fn normalize(value: &str) -> String {
    let compact = value.split_whitespace().collect::<Vec<_>>().join(" ");
    let lowered = compact.trim().to_lowercase();
    if INVALID_VALUES.iter().any(|x| *x == lowered) {
        return String::new();
    }
    lowered
}

/// 将一个硬件值标准化后插入到有序集合中（自动去重排序）。
/// 空值会被丢弃。
fn push_value(set: &mut BTreeSet<String>, value: &str) {
    let v = normalize(value);
    if !v.is_empty() {
        set.insert(v);
    }
}

/// 按行拆分文本，将每一行作为独立硬件值插入集合。
fn push_lines(set: &mut BTreeSet<String>, text: &str) {
    for line in text.lines() {
        push_value(set, line);
    }
}

/// 从命令输出中提取 "key: value" 格式的数据。
/// 只有当冒号左侧的 key（忽略大小写）匹配 `keys` 列表中的某一项时，
/// 才会将冒号右侧的 value 插入集合。
fn extract_after_colon(output: &str, keys: &[&str], set: &mut BTreeSet<String>) {
    for line in output.lines() {
        let raw = line.trim();
        if let Some((left, right)) = raw.split_once(':') {
            let key = left.trim().to_lowercase();
            if keys.iter().any(|k| *k == key) {
                push_value(set, right);
            }
        }
    }
}

/// 执行 PowerShell 脚本并返回输出（仅 Windows 使用）。
fn collect_ps(script: &str) -> String {
    run_command("powershell", &["-NoProfile", "-Command", script])
}

/// 采集 Windows 平台的硬件指纹素材。
///
/// 返回四个有序集合，分别对应：
/// - `system`  : 系统级标识（UUID、BIOS 序列号、主板序列号、CPU ID）
/// - `disk`    : 磁盘序列号
/// - `gpu`     : 显卡 PNP 设备 ID
/// - `network` : 物理网卡 MAC 地址
fn collect_windows_material() -> (BTreeSet<String>, BTreeSet<String>, BTreeSet<String>, BTreeSet<String>) {
    let mut system = BTreeSet::new();
    let mut disk = BTreeSet::new();
    let mut gpu = BTreeSet::new();
    let mut network = BTreeSet::new();

    // ---- 系统级标识 ----
    push_value(&mut system, &collect_ps("(Get-CimInstance Win32_ComputerSystemProduct).UUID"));
    push_value(&mut system, &collect_ps("(Get-CimInstance Win32_BIOS).SerialNumber"));
    push_value(&mut system, &collect_ps("(Get-CimInstance Win32_BaseBoard).SerialNumber"));
    push_value(&mut system, &collect_ps("(Get-CimInstance Win32_Processor | Select-Object -First 1).ProcessorId"));

    // ---- 磁盘序列号：优先使用 PhysicalMedia，退而求其次用 DiskDrive ----
    let disk_serials = collect_ps("Get-CimInstance Win32_PhysicalMedia | Select-Object -ExpandProperty SerialNumber");
    if disk_serials.is_empty() {
        push_lines(
            &mut disk,
            &collect_ps("Get-CimInstance Win32_DiskDrive | Select-Object -ExpandProperty SerialNumber"),
        );
    } else {
        push_lines(&mut disk, &disk_serials);
    }

    // ---- GPU PNP 设备 ID ----
    push_lines(
        &mut gpu,
        &collect_ps("Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty PNPDeviceID"),
    );

    // ---- 物理网卡 MAC 地址（排除虚拟/VPN 适配器）----
    // 条件：PhysicalAdapter=True + 有 MAC + PNPDeviceID 以 PCI 开头（过滤 Hyper-V/VPN/蓝牙等虚拟适配器）
    push_lines(
        &mut network,
        &collect_ps(
            "Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -eq $true -and $_.MACAddress -and $_.PNPDeviceID -match '^PCI' } | Select-Object -ExpandProperty MACAddress",
        ),
    );

    (system, disk, gpu, network)
}

/// 采集 macOS 平台的硬件指纹素材。
///
/// 返回四个有序集合，分别对应：
/// - `system`  : 平台 UUID、序列号、机型标识、CPU 品牌
/// - `disk`    : NVMe / SATA 磁盘序列号与型号
/// - `gpu`     : 显卡芯片型号、设备 ID、厂商
/// - `network` : 以太网 MAC 地址
fn collect_macos_material() -> (BTreeSet<String>, BTreeSet<String>, BTreeSet<String>, BTreeSet<String>) {
    let mut system = BTreeSet::new();
    let mut disk = BTreeSet::new();
    let mut gpu = BTreeSet::new();
    let mut network = BTreeSet::new();

    // ---- 通过 ioreg 获取平台 UUID 和序列号 ----
    let ioreg = run_command("ioreg", &["-rd1", "-c", "IOPlatformExpertDevice"]);
    for line in ioreg.lines() {
        let row = line.trim();
        if row.contains("\"IOPlatformUUID\"") {
            if let Some((_, right)) = row.split_once('=') {
                push_value(&mut system, right.trim().trim_matches('"'));
            }
        }
        if row.contains("\"IOPlatformSerialNumber\"") {
            if let Some((_, right)) = row.split_once('=') {
                push_value(&mut system, right.trim().trim_matches('"'));
            }
        }
    }

    // ---- 通过 system_profiler 获取硬件概要信息 ----
    let hardware = run_command("system_profiler", &["SPHardwareDataType"]);
    extract_after_colon(
        &hardware,
        &[
            "hardware uuid",
            "serial number (system)",
            "serial number",
            "model identifier",
        ],
        &mut system,
    );

    // ---- CPU 品牌字符串 ----
    let cpu_brand = run_command("sysctl", &["-n", "machdep.cpu.brand_string"]);
    push_value(&mut system, &cpu_brand);

    // ---- 磁盘信息：合并 NVMe 与 SATA 数据 ----
    let nvme = run_command("system_profiler", &["SPNVMeDataType"]);
    let sata = run_command("system_profiler", &["SPSerialATADataType"]);
    let disk_joined = format!("{}\n{}", nvme, sata);
    extract_after_colon(
        &disk_joined,
        &["serial number", "device / media name", "model"],
        &mut disk,
    );

    // ---- GPU / 显示器信息 ----
    let displays = run_command("system_profiler", &["SPDisplaysDataType"]);
    extract_after_colon(&displays, &["chipset model", "device id", "vendor"], &mut gpu);

    // ---- 网卡 MAC 地址（仅采集真实硬件端口，排除虚拟/VPN 网卡）----
    // `networksetup -listallhardwareports` 只列出系统识别的物理硬件端口，
    // 输出格式：
    //   Hardware Port: Wi-Fi
    //   Device: en0
    //   Ethernet Address: aa:bb:cc:dd:ee:ff
    // 只提取 "Ethernet Address:" 后面的 MAC，天然排除 utun/ppp/bridge 等虚拟接口。
    let hw_ports = run_command("networksetup", &["-listallhardwareports"]);
    for line in hw_ports.lines() {
        let row = line.trim();
        if let Some(rest) = row.strip_prefix("Ethernet Address:") {
            let mac = rest.trim();
            // 跳过未分配的占位值（部分端口可能显示 N/A）
            if !mac.is_empty() && mac != "N/A" {
                push_value(&mut network, mac);
            }
        }
    }

    (system, disk, gpu, network)
}

/// 将所有硬件素材拼接为一个确定性字符串，用于后续哈希。
///
/// 格式：`os=<OS>;system=<A|B|...>;disk=<X|Y|...>;gpu=<M|N|...>;network=<P|Q|...>`
/// 各维度内部以 `|` 分隔（BTreeSet 保证顺序稳定），维度之间以 `;` 分隔。
fn build_payload(
    os_name: &str,
    system: &BTreeSet<String>,
    disk: &BTreeSet<String>,
    gpu: &BTreeSet<String>,
    network: &BTreeSet<String>,
) -> String {
    format!(
        "os={};system={};disk={};gpu={};network={}",
        os_name,
        system.iter().cloned().collect::<Vec<_>>().join("|"),
        disk.iter().cloned().collect::<Vec<_>>().join("|"),
        gpu.iter().cloned().collect::<Vec<_>>().join("|"),
        network.iter().cloned().collect::<Vec<_>>().join("|"),
    )
}

/// 将字节切片转为小写十六进制字符串。
fn to_hex(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push_str(&format!("{:02x}", b));
    }
    out
}

/// 生成设备指纹 ID(simei)（对外公开的唯一入口）。
///
/// 流程：
/// 1. 根据当前操作系统选择对应的硬件采集函数
/// 2. 将采集到的四维硬件素材拼接为确定性字符串
/// 3. 对拼接结果执行 SHA-256 哈希
/// 4. 返回 64 位十六进制字符串作为设备唯一 ID
///
/// # Errors
/// - 不支持的操作系统（仅支持 macOS / Windows）
/// - 未能采集到任何硬件标识符
pub fn generate_device_fingerprint_id() -> Result<String, String> {
    let os_name = std::env::consts::OS;

    // 根据操作系统分发到对应的采集函数
    let (system, disk, gpu, network) = match os_name {
        "windows" => collect_windows_material(),
        "macos" => collect_macos_material(),
        _ => return Err("only macOS and Windows are supported".to_string()),
    };

    // 至少需要采集到一项硬件标识，否则无法生成有意义的指纹
    let collected_count = system.len() + disk.len() + gpu.len() + network.len();
    if collected_count == 0 {
        return Err("unable to collect hardware identifiers".to_string());
    }

    // 拼接 → 哈希 → 十六进制
    let payload = build_payload(os_name, &system, &disk, &gpu, &network);
    let digest = Sha256::digest(payload.as_bytes());
    Ok(to_hex(&digest))
}