#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use tauri::{
    menu::{MenuBuilder, MenuItem, SubmenuBuilder},
    Emitter, Manager, WindowEvent,
};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

mod utils;

/// 标记是否正在弹出关闭确认对话框，防止重复弹框
static CLOSE_DIALOG_SHOWN: AtomicBool = AtomicBool::new(false);

// ── 简易文件日志 ──────────────────────────────────────
// 将 Tauri 侧少量运行日志写入 ~/.deeppool/logs/deepnode.log，
// 与 localserver 的 Python 日志落在同一目录，方便统一排查。

/// 获取日志目录 ~/.deeppool/logs/，不存在则创建
fn log_dir() -> Option<std::path::PathBuf> {
    dirs::home_dir().map(|h| h.join(".deeppool").join("logs"))
}

/// 向 ~/.deeppool/logs/deepnode.log 追加一行带时间戳的日志，同时输出到 stderr
fn log_to_file(msg: &str) {
    eprintln!("{msg}");
    if let Some(dir) = log_dir() {
        let _ = fs::create_dir_all(&dir);
        if let Ok(mut f) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(dir.join("deepnode.log"))
        {
            // 简易时间戳：使用 SystemTime（不依赖 chrono crate）
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();
            let _ = writeln!(f, "{now} {msg}");
        }
    }
}

/// Tauri command：停止 localserver sidecar 进程。
/// 用户退出登录时由前端调用，确保 localserver 随用户会话一起终止。
#[tauri::command]
fn stop_localserver(app_handle: tauri::AppHandle) {
    if let Some(state) = app_handle.try_state::<LocalServerProcess>() {
        if let Ok(mut guard) = state.0.lock() {
            if let Some(child) = guard.take() {
                log_to_file("[deepnode] stop_localserver: user logged out, killing sidecar");
                kill_sidecar(child);
            }
        }
    }
}

/// 递归收集指定 PID 的所有后代进程（macOS/Unix）。
///
/// 使用 `pgrep -P <pid>` 查找直接子进程，然后递归收集子进程的子进程。
/// 返回的列表按深度优先排列（最深的后代在前），便于从叶子节点开始 kill。
#[cfg(unix)]
fn collect_descendant_pids(pid: u32) -> Vec<u32> {
    use std::process::Command;
    let mut descendants = Vec::new();
    if let Ok(output) = Command::new("pgrep").args(["-P", &pid.to_string()]).output() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        for line in stdout.lines() {
            if let Ok(child_pid) = line.trim().parse::<u32>() {
                // 先递归收集孙进程（深度优先，叶子在前）
                descendants.extend(collect_descendant_pids(child_pid));
                descendants.push(child_pid);
            }
        }
    }
    descendants
}

/// Kill sidecar 进程及其所有后代进程。
///
/// PyInstaller 单文件模式下 bootloader 会 fork 出真正的 Python 进程，
/// 且子进程可能不在同一个进程组中（setsid 或继承父进程组），
/// 导致 `kill -TERM -<pid>` 无法覆盖所有子进程。
/// 因此采用递归遍历进程树的方式，逐个 kill 所有后代进程。
fn kill_sidecar(child: tauri_plugin_shell::process::CommandChild) {
    let pid = child.pid();
    log_to_file(&format!("[deepnode] killing localserver sidecar (pid={pid})"));

    #[cfg(unix)]
    {
        use std::process::Command;

        // 收集所有后代进程（深度优先，叶子在前）
        let descendants = collect_descendant_pids(pid);
        let all_pids: Vec<u32> = descendants.into_iter().chain(std::iter::once(pid)).collect();
        log_to_file(&format!("[deepnode] process tree to kill: {:?}", all_pids));

        // 第一轮：SIGTERM 优雅终止
        for &p in &all_pids {
            let _ = Command::new("kill").args(["-TERM", &p.to_string()]).output();
        }

        // 等待进程优雅退出
        std::thread::sleep(std::time::Duration::from_secs(1));

        // 第二轮：检查存活并 SIGKILL 强制终止
        for &p in &all_pids {
            // kill -0 检查进程是否存活
            if Command::new("kill").args(["-0", &p.to_string()]).output()
                .map(|o| o.status.success()).unwrap_or(false)
            {
                log_to_file(&format!("[deepnode] process {p} still alive, sending SIGKILL"));
                let _ = Command::new("kill").args(["-9", &p.to_string()]).output();
            }
        }
    }

    // Tauri 原生 kill 作为兜底
    let _ = child.kill();
    log_to_file(&format!("[deepnode] localserver sidecar killed (pid={pid})"));
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![stop_localserver])
        .setup(|app| {
            // ── 菜单 ──
            let settings = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            let system_submenu = SubmenuBuilder::new(app, "System")
                .item(&settings)
                .build()?;
            let menu = MenuBuilder::new(app).item(&system_submenu).build()?;
            app.set_menu(menu)?;

            // ── 启动 localserver sidecar ──
            // dev 模式下由 run_client.sh 独立管理 Python 进程，不启动 sidecar
            #[cfg(not(debug_assertions))]
            {
                // 先清理可能残留的旧 localserver 进程（上次未正常退出时会残留）
                cleanup_stale_localserver();

                match start_localserver_sidecar(app) {
                    Ok(child) => {
                        app.manage(LocalServerProcess(Mutex::new(Some(child))));
                        log_to_file("[deepnode] localserver sidecar spawned");
                        // 后台线程轮询 localserver 端口就绪，通知前端
                        let handle = app.handle().clone();
                        std::thread::spawn(move || wait_for_localserver(handle));
                    }
                    Err(e) => {
                        app.manage(LocalServerProcess(Mutex::new(None)));
                        log_to_file(&format!("[deepnode] WARNING: failed to start localserver sidecar: {e}"));
                        // sidecar 启动失败，直接通知前端
                        let _ = app.emit("localserver-failed", ());
                    }
                }
            }

            #[cfg(debug_assertions)]
            {
                app.manage(LocalServerProcess(Mutex::new(None)));
                log_to_file("[deepnode] dev mode: sidecar skipped, use run_client.sh to start localserver");
            }

            Ok(())
        })
        .on_menu_event(|app, event| {
            if event.id().as_ref() == "settings" {
                let _ = app.emit("open-settings", ());
            }
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                // 阻止默认关闭，由对话框回调决定操作
                api.prevent_close();

                // 防止重复弹框
                if CLOSE_DIALOG_SHOWN.swap(true, Ordering::SeqCst) {
                    return;
                }

                let win = window.clone();
                let app_handle = window.app_handle().clone();
                window
                    .dialog()
                    .message("关闭窗口后，后台推理服务将继续运行。\n选择「确定」彻底退出，选择「取消」仅隐藏窗口。")
                    .title("退出 DeepNode")
                    .kind(MessageDialogKind::Info)
                    .buttons(MessageDialogButtons::OkCancelCustom(
                        "彻底退出".into(),
                        "后台运行".into(),
                    ))
                    .show(move |confirmed| {
                        CLOSE_DIALOG_SHOWN.store(false, Ordering::SeqCst);
                        if confirmed {
                            // 彻底退出：先清除 WebView 中的登录状态，确保下次启动需重新登录。
                            // Tauri v2 中 eval 在 WebviewWindow 上，通过 Manager trait 获取。
                            if let Some(wv) = app_handle.get_webview_window("main") {
                                let _ = wv.eval(
                                    "localStorage.removeItem('deepnode_token'); \
                                     localStorage.removeItem('deepnode_user');"
                                );
                            }
                            // kill sidecar 进程组后退出应用
                            if let Some(state) = app_handle.try_state::<LocalServerProcess>() {
                                if let Ok(mut guard) = state.0.lock() {
                                    if let Some(child) = guard.take() {
                                        kill_sidecar(child);
                                    }
                                }
                            }
                            let _ = win.destroy();
                            app_handle.exit(0);
                        } else {
                            // 后台运行：仅隐藏窗口
                            let _ = win.hide();
                        }
                    });
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running deepnode");
}

/// 持有 localserver 子进程句柄，应用退出时自动 kill
struct LocalServerProcess(Mutex<Option<tauri_plugin_shell::process::CommandChild>>);

impl Drop for LocalServerProcess {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.0.lock() {
            if let Some(child) = guard.take() {
                kill_sidecar(child);
            }
        }
    }
}

/// 启动 localserver sidecar 子进程（仅 release 模式使用）
#[cfg(not(debug_assertions))]
fn start_localserver_sidecar(
    app: &tauri::App,
) -> Result<tauri_plugin_shell::process::CommandChild, Box<dyn std::error::Error>> {
    let shell = app.shell();
    let sidecar = shell.sidecar("localserver")?;
    let (_rx, child) = sidecar.spawn()?;
    Ok(child)
}

/// 清理上次运行残留的 localserver 进程。
///
/// 当应用未正常退出（崩溃、强制关闭等）时，localserver 进程可能残留为孤儿进程，
/// 占用 8765 端口导致新实例启动失败。
/// 通过 `lsof` 查找占用 8765 端口的进程并 kill 掉。
#[cfg(not(debug_assertions))]
fn cleanup_stale_localserver() {
    use std::process::Command;

    // 用 lsof 查找监听 8765 端口的进程
    let output = match Command::new("lsof")
        .args(["-ti", "tcp:8765"])
        .output()
    {
        Ok(o) => o,
        Err(e) => {
            log_to_file(&format!("[deepnode] cleanup: lsof failed: {e}"));
            return;
        }
    };

    let stdout = String::from_utf8_lossy(&output.stdout);
    let pids: Vec<u32> = stdout
        .lines()
        .filter_map(|line| line.trim().parse::<u32>().ok())
        .collect();

    if pids.is_empty() {
        log_to_file("[deepnode] cleanup: no stale localserver on port 8765");
        return;
    }

    log_to_file(&format!("[deepnode] cleanup: found stale processes on port 8765: {:?}", pids));

    // SIGTERM → 等待 → SIGKILL
    for &pid in &pids {
        let _ = Command::new("kill").args(["-TERM", &pid.to_string()]).output();
    }
    std::thread::sleep(std::time::Duration::from_secs(1));
    for &pid in &pids {
        if Command::new("kill").args(["-0", &pid.to_string()]).output()
            .map(|o| o.status.success()).unwrap_or(false)
        {
            log_to_file(&format!("[deepnode] cleanup: process {pid} still alive, SIGKILL"));
            let _ = Command::new("kill").args(["-9", &pid.to_string()]).output();
        }
    }

    // 等待端口释放
    std::thread::sleep(std::time::Duration::from_millis(500));
    log_to_file("[deepnode] cleanup: stale localserver processes killed");
}

/// 后台轮询 localserver TCP 端口（127.0.0.1:8765）是否就绪。
/// 就绪后 emit "localserver-ready"，超时 120s 后 emit "localserver-failed"。
/// 仅 release 模式使用（dev 模式由 run_client.sh 预启动 localserver）。
#[cfg(not(debug_assertions))]
fn wait_for_localserver(app_handle: tauri::AppHandle) {
    use std::net::TcpStream;
    use std::time::{Duration, Instant};

    let addr = "127.0.0.1:8765";
    let max_wait = Duration::from_secs(120);
    let interval = Duration::from_millis(200);
    let start = Instant::now();

    log_to_file(&format!("[deepnode] waiting for localserver at {addr} (timeout={max_wait:?})"));

    loop {
        // 尝试 TCP 连接，200ms 超时
        if TcpStream::connect_timeout(
            &addr.parse().unwrap(),
            Duration::from_millis(200),
        ).is_ok() {
            let elapsed = start.elapsed();
            log_to_file(&format!("[deepnode] localserver ready at {addr} (waited {elapsed:.1?})"));
            let _ = app_handle.emit("localserver-ready", ());
            return;
        }

        if start.elapsed() >= max_wait {
            log_to_file(&format!("[deepnode] TIMEOUT: localserver not ready after {max_wait:?}"));
            let _ = app_handle.emit("localserver-failed", ());
            return;
        }

        std::thread::sleep(interval);
    }
}
