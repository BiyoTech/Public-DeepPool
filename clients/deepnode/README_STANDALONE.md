# DeepNode Server — 独立运行版

## 快速开始

```bash
# 解压
tar xzf deepnode-*.tar.gz
cd deepnode-server

# 启动（需提供 Platform 账号）
./deepnode-server --standalone --account <用户名> --password <密码>

# 或使用 token 认证
./deepnode-server --standalone --token <your_token>
```

启动后访问 http://127.0.0.1:8765/ 查看服务状态。

---

## 操作系统版本要求

| 系统 | 最低版本 | 架构 |
|------|----------|------|
| macOS | 13.5 Ventura | arm64 (M 系列芯片) |
| macOS | 13.5 Ventura | x86_64 (Intel) |

> **重要**：请使用与打包文件名中标注的系统版本和架构匹配的制品。例如
> `deepnode-v1.0.0-macos15-arm64.tar.gz` 适用于 macOS 15+ 的 M 系列 Mac。

### Metal 兼容性说明

DeepNode 使用 Apple Metal 加速推理。不同 macOS 版本内置的 Metal 版本不同：

- macOS 13 — Metal 3.0
- macOS 14 — Metal 3.1
- macOS 15 — Metal 3.2

打包时已锁定目标 Metal 版本，**低版本 macOS 无法运行高版本打包的制品**。
请根据目标机器的 macOS 版本选择对应的安装包。

---

## macOS 安全运行指引

由于本程序未经 Apple 公证，首次运行时 macOS Gatekeeper 可能阻止执行。

### 方法一：移除 quarantine 标记（推荐）

```bash
# 解压后，在 deepnode-server 目录下执行
xattr -rd com.apple.quarantine .
```

### 方法二：系统偏好设置放行

1. 运行 `./deepnode-server`，出现"无法打开"提示时点击"取消"
2. 打开 **系统设置 → 隐私与安全性**
3. 在底部找到被阻止的程序，点击 **仍要打开**

### 方法三：命令行单次放行

```bash
spctl --add --label "DeepNode" ./deepnode-server-bin
```

---

## 目录结构

```
deepnode-server/
├── deepnode-server          # 启动入口（shell wrapper）
├── deepnode-server-bin      # PyInstaller 打包的二进制主程序
├── config.yaml              # 用户可修改的配置文件
├── VERSION                  # 版本号
├── _internal/               # PyInstaller 运行时依赖（勿修改）
└── mlx-packages/            # MLX 推理引擎依赖包（勿修改）
```

---

## 配置说明

编辑 `config.yaml` 可调整以下配置：

- **server.port** — 本地服务端口（默认 8765）
- **platform.\*_grpc_target** — Platform 各组件 gRPC 地址
- **log.level** — 日志级别（debug / info / warning / error）
- **engine.\*** — 推理引擎性能参数（KV Cache、线程池等）
- **multi_model.max_loaded_models** — 最大同时加载模型数

---

## 常见问题 (Q&A)

### Q: 启动报错 "Abort trap: 6"

**A**: 这通常是 Metal shader 版本不兼容导致的。请确认：
1. 使用的安装包与当前 macOS 版本匹配
2. 未混用不同版本的安装包文件

### Q: 启动报错 "Metal is not available" 或 "mlx.core pre-load failed"

**A**: 请确认：
1. Mac 配备了支持 Metal 的 GPU
2. macOS 版本满足最低要求（≥ 13.5）
3. 未通过远程桌面等方式屏蔽了 GPU

### Q: 如何更换连接的 Platform 服务器？

**A**: 编辑 `config.yaml` 中的 `platform` 段，修改各 `*_grpc_target` 地址。

### Q: 如何查看详细日志？

**A**: 日志默认输出到 `~/.deeppool/logs/localserver.log`，可通过修改
`config.yaml` 中 `log.level` 为 `debug` 获取更详细的日志。

### Q: 能否同时运行多个实例？

**A**: 可以，但需要修改 `config.yaml` 中 `server.port` 为不同端口。

### Q: 模型文件存放在哪里？

**A**: 模型文件默认下载到 `~/.cache/huggingface/hub/`，由 Hugging Face Hub 管理。

---

## 技术支持

如遇到其他问题，请收集以下信息后联系技术支持：

1. 打包文件名（含版本号和平台信息）
2. `sw_vers` 命令输出（macOS 版本）
3. `uname -m` 命令输出（CPU 架构）
4. `~/.deeppool/logs/localserver.log` 日志文件
