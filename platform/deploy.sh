#!/bin/bash
# deploy.sh — 统一部署脚本：构建并部署 DeepPool 平台组件到远程服务器。
#
# 功能：
#   1. 交叉编译 Go 服务 (linux/amd64)
#   2. 构建前端资源 (control_web + portal_web)
#   3. 上传所有产物 + SSL 证书到远程服务器
#   4. 配置 Nginx 反向代理 / Ingress (SSL 终止)
#   5. 启动所有服务并执行健康检查
#
# 用法：
#   ./deploy.sh --help
#   ./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>'
#   ./deploy.sh --domain test.deeppool.tech --server root@<your-server-ip> --config config_test
#   ./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' --components manager,portal_web
#   ./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' --ssl local --ssl-cert-dir ssl_cert
#   ./deploy.sh --domain test.deeppool.tech --server root@<your-server-ip> --ssl letsencrypt --admin-email admin@deeppool.tech
#
# Ingress 路由：
#   /        -> portal_web
#   /admin/  -> control_web
#   /api/    -> manager :8080
#   /v1/     -> manager :8080
set -euo pipefail

# ============================================================
# 默认值
# ============================================================
DOMAIN=""
SERVER=""
PASSWORD=""
CONFIG_DIR=""
REMOTE_DIR="/opt/deeppool"
SSL_MODE=""           # local | letsencrypt (auto-detect if not specified)
SSL_CERT_DIR=""       # 本地证书目录 (SSL_MODE=local 时使用)
ADMIN_EMAIL="admin@deeppool.tech"
DEPLOY_COMPONENTS=""  # 逗号分隔的组件列表，为空则部署全部

# ============================================================
# 帮助信息
# ============================================================
show_help() {
  cat <<EOF
用法: ./deploy.sh [选项]

必选参数:
  --domain <domain>         部署域名 (例如: deeppool.tech, test.deeppool.tech)
  --server <user@host>      远程服务器地址 (例如: root@203.0.113.10)

可选参数:
  --password <password>     SSH 密码 (不指定则使用 SSH Key 认证)
  --config <dir>            配置文件目录名 (默认: config_prod)
                            相对于 platform/ 目录，例如: config_prod, config_test
  --remote-dir <path>       远程部署目录 (默认: /opt/deeppool)
  --components <list>       要部署的组件，逗号分隔 (默认: 全部)
                            可选值: manager, nodemanager, experiment, portal_web, control_web
  --ssl <mode>              SSL 证书模式:
                              local       - 使用本地证书文件上传 (适合阿里云等购买的证书)
                              letsencrypt - 在服务器上自动申请 Let's Encrypt 证书
                            默认: 如果 --ssl-cert-dir 存在则为 local，否则为 letsencrypt
  --ssl-cert-dir <dir>      本地 SSL 证书目录 (默认: ssl_cert)
                            目录下需包含 <domain>.pem 和 <domain>.key
  --admin-email <email>     Let's Encrypt 注册邮箱 (默认: admin@deeppool.tech)
  --help, -h                显示此帮助信息

示例:
  # 生产环境全量部署 (使用本地证书 + 密码认证)
  ./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' \\
              --config config_prod --ssl local --ssl-cert-dir ssl_cert

  # 测试环境全量部署 (Let's Encrypt + SSH Key)
  ./deploy.sh --domain test.deeppool.tech --server root@<your-server-ip> \\
              --config config_test --ssl letsencrypt

  # 仅部署 manager 和 portal_web
  ./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' \\
              --components manager,portal_web

  # 仅部署前端
  ./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' \\
              --components portal_web,control_web
EOF
  exit 0
}

# ============================================================
# 参数解析
# ============================================================
while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      show_help
      ;;
    --domain)
      DOMAIN="$2"; shift 2
      ;;
    --server)
      SERVER="$2"; shift 2
      ;;
    --password)
      PASSWORD="$2"; shift 2
      ;;
    --config)
      CONFIG_DIR="$2"; shift 2
      ;;
    --remote-dir)
      REMOTE_DIR="$2"; shift 2
      ;;
    --components)
      DEPLOY_COMPONENTS="$2"; shift 2
      ;;
    --ssl)
      SSL_MODE="$2"; shift 2
      ;;
    --ssl-cert-dir)
      SSL_CERT_DIR="$2"; shift 2
      ;;
    --admin-email)
      ADMIN_EMAIL="$2"; shift 2
      ;;
    *)
      echo "[ERROR] 未知参数: $1"
      echo "使用 --help 查看帮助信息"
      exit 1
      ;;
  esac
done

# ============================================================
# 参数校验
# ============================================================
if [ -z "$DOMAIN" ]; then
  echo "[ERROR] 必须指定 --domain 参数"
  echo "使用 --help 查看帮助信息"
  exit 1
fi

if [ -z "$SERVER" ]; then
  echo "[ERROR] 必须指定 --server 参数"
  echo "使用 --help 查看帮助信息"
  exit 1
fi

# ============================================================
# 路径设置
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$SCRIPT_DIR"
BUILD_DIR="$PLATFORM_DIR/build"

# 配置目录默认值
if [ -z "$CONFIG_DIR" ]; then
  CONFIG_DIR="config_prod"
fi
CONFIG_FULL_PATH="$PLATFORM_DIR/$CONFIG_DIR"

if [ ! -d "$CONFIG_FULL_PATH" ]; then
  echo "[ERROR] 配置目录不存在: $CONFIG_FULL_PATH"
  exit 1
fi

# SSL 证书目录
if [ -z "$SSL_CERT_DIR" ]; then
  SSL_CERT_DIR="ssl_cert"
fi
LOCAL_CERT_DIR="${PLATFORM_DIR}/${SSL_CERT_DIR}"
LOCAL_CERT_FILE="${LOCAL_CERT_DIR}/${DOMAIN}.pem"
LOCAL_KEY_FILE="${LOCAL_CERT_DIR}/${DOMAIN}.key"

# 自动检测 SSL 模式
if [ -z "$SSL_MODE" ]; then
  if [ -f "$LOCAL_CERT_FILE" ] && [ -f "$LOCAL_KEY_FILE" ]; then
    SSL_MODE="local"
  else
    SSL_MODE="letsencrypt"
  fi
fi

# 域名相关
API_DOMAIN="api.${DOMAIN}"
PUBLIC_HOST="${DOMAIN}"

# 远程证书路径
if [ "$SSL_MODE" = "local" ]; then
  REMOTE_CERT_DIR="/etc/ssl/deeppool"
  REMOTE_CERT_FILE="${REMOTE_CERT_DIR}/${DOMAIN}.pem"
  REMOTE_KEY_FILE="${REMOTE_CERT_DIR}/${DOMAIN}.key"
  CERT_REF_DIR="$REMOTE_CERT_DIR"
  CERT_FILE_NAME="${DOMAIN}.pem"
  KEY_FILE_NAME="${DOMAIN}.key"
else
  CERT_REF_DIR="/etc/letsencrypt/live/${DOMAIN}"
  CERT_FILE_NAME="fullchain.pem"
  KEY_FILE_NAME="privkey.pem"
fi

# ============================================================
# SSH 封装
# ============================================================
REMOTE_HOST="$SERVER"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

if [ -n "$PASSWORD" ]; then
  # 使用 sshpass 密码认证
  if ! command -v sshpass &>/dev/null; then
    echo "[ERROR] 指定了 --password 但 sshpass 未安装"
    echo "  macOS:  brew install hudochenkov/sshpass/sshpass"
    echo "  Linux:  apt-get install sshpass / yum install sshpass"
    exit 1
  fi
  export SSHPASS="$PASSWORD"
  do_ssh() { sshpass -e ssh ${SSH_OPTS} "${REMOTE_HOST}" "$@"; }
  do_scp() { sshpass -e scp ${SSH_OPTS} "$@"; }
else
  # 使用 SSH Key 认证
  do_ssh() { ssh ${SSH_OPTS} "${REMOTE_HOST}" "$@"; }
  do_scp() { scp ${SSH_OPTS} "$@"; }
fi

# ============================================================
# 组件定义
# ============================================================
ALL_BACKEND=(manager nodemanager experiment)
ALL_WEB=(portal_web control_web)
ALL_COMPONENTS=("${ALL_BACKEND[@]}" "${ALL_WEB[@]}")

get_component_port() {
  case "$1" in
    manager)     echo "http:8080" ;;
    nodemanager) echo "http:8082" ;;
    experiment)  echo "grpc:9093" ;;
    *) echo "http:0" ;;
  esac
}

# 解析要部署的组件
DEPLOY_PORTAL_WEB=false
DEPLOY_CONTROL_WEB=false
COMPONENTS=()

if [ -n "$DEPLOY_COMPONENTS" ]; then
  IFS=',' read -ra COMP_ARRAY <<< "$DEPLOY_COMPONENTS"
  for arg in "${COMP_ARRAY[@]}"; do
    arg=$(echo "$arg" | xargs)  # trim whitespace
    if [ "$arg" = "portal_web" ]; then
      DEPLOY_PORTAL_WEB=true
    elif [ "$arg" = "control_web" ]; then
      DEPLOY_CONTROL_WEB=true
    elif [[ " ${ALL_BACKEND[*]} " =~ " ${arg} " ]]; then
      COMPONENTS+=("$arg")
    else
      echo "[ERROR] 未知组件: ${arg}"
      echo "  可选值: ${ALL_COMPONENTS[*]}"
      exit 1
    fi
  done
  PARTIAL_DEPLOY=true
else
  COMPONENTS=("${ALL_BACKEND[@]}")
  DEPLOY_PORTAL_WEB=true
  DEPLOY_CONTROL_WEB=true
  PARTIAL_DEPLOY=false
fi

CONTROL_WEB_DIR="control_web"
CONTROL_WEB_REMOTE_DIR="${REMOTE_DIR}/control_web"
PORTAL_WEB_DIR="portal_web"
PORTAL_WEB_REMOTE_DIR="${REMOTE_DIR}/portal_web"
NGINX_CONF="/etc/nginx/conf.d/deeppool.conf"

# ============================================================
# 交叉编译设置
# ============================================================
export GOOS=linux
export GOARCH=amd64
export CGO_ENABLED=0

# ============================================================
# 部署信息
# ============================================================
echo "============================================================"
echo "  DeepPool 部署"
echo "  目标服务器:   ${REMOTE_HOST}"
echo "  远程目录:     ${REMOTE_DIR}"
echo "  域名:         ${DOMAIN}"
echo "  API 域名:     ${API_DOMAIN}"
echo "  配置目录:     ${CONFIG_DIR}"
echo "  SSL 模式:     ${SSL_MODE}"
if [ "$SSL_MODE" = "local" ]; then
echo "  证书目录:     ${LOCAL_CERT_DIR}"
else
echo "  LE 邮箱:      ${ADMIN_EMAIL}"
fi
if [ ${#COMPONENTS[@]} -gt 0 ]; then
echo "  后端组件:     ${COMPONENTS[*]}"
fi
echo "  portal_web:   ${DEPLOY_PORTAL_WEB}"
echo "  control_web:  ${DEPLOY_CONTROL_WEB}"
if [ "$PARTIAL_DEPLOY" = true ]; then
echo "  部署模式:     部分部署"
else
echo "  部署模式:     全量部署"
fi
echo "============================================================"
echo ""

# ============================================================
# 前置检查
# ============================================================

# 检查 SSL 证书 (local 模式)
if [ "$SSL_MODE" = "local" ] && [ "$PARTIAL_DEPLOY" = false ]; then
  if [ ! -f "${LOCAL_CERT_FILE}" ] || [ ! -f "${LOCAL_KEY_FILE}" ]; then
    echo "============================================================"
    echo "[ERROR] SSL 证书文件未找到!"
    echo ""
    echo "  期望文件:"
    echo "    ${LOCAL_CERT_FILE}  (证书 + 中间链)"
    echo "    ${LOCAL_KEY_FILE}   (私钥)"
    echo ""
    echo "  准备方法:"
    echo "    1. 前往阿里云控制台 -> SSL 证书"
    echo "    2. 下载 Nginx 格式证书"
    echo "    3. 将 .pem 和 .key 文件放入: ${LOCAL_CERT_DIR}/"
    echo "============================================================"
    exit 1
  fi
  echo "==> SSL 证书文件已找到"
fi

# 验证 SSH 连接
echo "==> 验证 SSH 连接..."
if ! do_ssh "echo 'SSH 连接成功'"; then
  echo "[ERROR] 无法连接到 ${REMOTE_HOST}"
  exit 1
fi

# ============================================================
# Step 1: 编译 Go 服务
# ============================================================
echo "==> 清理旧的构建产物..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

if [ ${#COMPONENTS[@]} -gt 0 ]; then
  echo "==> 交叉编译 Go 服务 (GOOS=${GOOS} GOARCH=${GOARCH})..."
  cd "$PLATFORM_DIR"
  for comp in "${COMPONENTS[@]}"; do
    echo "    编译 ${comp} ..."
    go build -trimpath -ldflags="-s -w" -o "${BUILD_DIR}/${comp}" "./cmd/${comp}"
  done
  echo "    所有 Go 服务编译完成"
fi

# 复制配置文件
echo "==> 复制配置文件 (${CONFIG_DIR})..."
cp -r "${CONFIG_FULL_PATH}" "${BUILD_DIR}/config"
echo "    配置文件已复制"

# ============================================================
# Step 2: 构建 control_web
# ============================================================
if [ "$DEPLOY_CONTROL_WEB" = true ]; then
  echo "==> 构建 control_web (base=/admin/)..."
  cd "${PLATFORM_DIR}/${CONTROL_WEB_DIR}"
  npm install --silent
  VITE_BASE=/admin/ \
    VITE_API_BASE_URL="https://${API_DOMAIN}/api/v1" \
    VITE_GATEWAY_BASE_URL="https://${API_DOMAIN}/v1" \
    npm run build
  cp -r "${PLATFORM_DIR}/${CONTROL_WEB_DIR}/dist" "${BUILD_DIR}/control_web"
  echo "    control_web 构建完成"
  cd "$PLATFORM_DIR"
fi

# ============================================================
# Step 3: 构建 portal_web
# ============================================================
if [ "$DEPLOY_PORTAL_WEB" = true ]; then
  echo "==> 构建 portal_web..."
  cd "${PLATFORM_DIR}/${PORTAL_WEB_DIR}"
  npm install --silent
  VITE_API_BASE_URL="https://${API_DOMAIN}/api/v1" \
    VITE_GATEWAY_BASE_URL="https://${API_DOMAIN}/v1" \
    npm run build
  cp -r "${PLATFORM_DIR}/${PORTAL_WEB_DIR}/dist" "${BUILD_DIR}/portal_web"
  echo "    portal_web 构建完成"
  cd "$PLATFORM_DIR"
fi

# ============================================================
# 构建摘要
# ============================================================
echo "==> 构建产物摘要:"
if [ ${#COMPONENTS[@]} -gt 0 ]; then
  for comp in "${COMPONENTS[@]}"; do
    ls -lh "${BUILD_DIR}/${comp}"
  done
fi
if [ "$DEPLOY_CONTROL_WEB" = true ]; then
  echo "    control_web: $(du -sh "${BUILD_DIR}/control_web" | awk '{print $1}')"
fi
if [ "$DEPLOY_PORTAL_WEB" = true ]; then
  echo "    portal_web:  $(du -sh "${BUILD_DIR}/portal_web" | awk '{print $1}')"
fi
echo ""

# ============================================================
# Step 4: 停止远程服务
# ============================================================
if [ ${#COMPONENTS[@]} -gt 0 ]; then
  COMP_LIST=$(IFS=' '; echo "${COMPONENTS[*]}")
  echo "==> 停止远程服务 (${COMPONENTS[*]})..."
  do_ssh bash -s -- "$REMOTE_DIR" "$COMP_LIST" <<'STOP_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
shift
COMP_LIST="$*"

for comp in $COMP_LIST; do
  pid=$(ps -eo pid,args | grep -E "(\./${comp}|${REMOTE_DIR}/${comp})" | grep -v -E "grep|bash|scp" | awk '{print $1}' || true)
  if [ -n "$pid" ]; then
    kill "$pid" 2>/dev/null || true
    echo "    发送 SIGTERM 到 $comp (pid=$pid)"
  else
    echo "    $comp 未运行"
  fi
done

echo "    等待进程退出..."
sleep 2

for comp in $COMP_LIST; do
  pid=$(ps -eo pid,args | grep -E "(\./${comp}|${REMOTE_DIR}/${comp})" | grep -v -E "grep|bash|scp" | awk '{print $1}' || true)
  if [ -n "$pid" ]; then
    kill -9 "$pid" 2>/dev/null || true
    echo "    强制终止 $comp (pid=$pid)"
  fi
done

sleep 1
for comp in $COMP_LIST; do
  rm -f "${REMOTE_DIR}/${comp}"
done
echo "    旧二进制文件已删除"
STOP_SCRIPT
fi

# ============================================================
# Step 5: 上传产物
# ============================================================
echo "==> 创建远程目录..."
do_ssh "mkdir -p ${REMOTE_DIR}/config"

if [ ${#COMPONENTS[@]} -gt 0 ]; then
  echo "==> 上传 Go 二进制文件 (${COMPONENTS[*]})..."
  for comp in "${COMPONENTS[@]}"; do
    do_scp "${BUILD_DIR}/${comp}" "${REMOTE_HOST}:${REMOTE_DIR}/"
  done
fi

echo "==> 上传配置文件..."
do_scp "${BUILD_DIR}/config/"*.yaml "${REMOTE_HOST}:${REMOTE_DIR}/config/"

if [ "$PARTIAL_DEPLOY" = false ]; then
  do_ssh "mkdir -p ${REMOTE_DIR}/alipay_cert ${REMOTE_DIR}/wechat_pay_cert"

  echo "==> 上传支付证书..."
  if [ -d "${PLATFORM_DIR}/alipay_cert" ]; then
    do_scp "${PLATFORM_DIR}/alipay_cert/"*.pem "${REMOTE_HOST}:${REMOTE_DIR}/alipay_cert/" 2>/dev/null || true
  fi
  if [ -d "${PLATFORM_DIR}/wechat_pay_cert" ]; then
    do_scp "${PLATFORM_DIR}/wechat_pay_cert/"* "${REMOTE_HOST}:${REMOTE_DIR}/wechat_pay_cert/" 2>/dev/null || true
  fi

  # 上传 SSL 证书 (local 模式)
  if [ "$SSL_MODE" = "local" ]; then
    do_ssh "mkdir -p ${REMOTE_CERT_DIR}"
    echo "==> 上传 SSL 证书..."
    do_scp "${LOCAL_CERT_FILE}" "${REMOTE_HOST}:${REMOTE_CERT_FILE}"
    do_scp "${LOCAL_KEY_FILE}"  "${REMOTE_HOST}:${REMOTE_KEY_FILE}"
    do_ssh "chmod 600 ${REMOTE_CERT_DIR}/*"
    echo "    SSL 证书已上传到 ${REMOTE_CERT_DIR}/"
  fi
fi

if [ "$DEPLOY_CONTROL_WEB" = true ]; then
  echo "==> 上传 control_web..."
  do_ssh "mkdir -p ${CONTROL_WEB_REMOTE_DIR}"
  do_ssh "rm -rf ${CONTROL_WEB_REMOTE_DIR}/*"
  do_scp -r "${BUILD_DIR}/control_web/"* "${REMOTE_HOST}:${CONTROL_WEB_REMOTE_DIR}/"
fi

if [ "$DEPLOY_PORTAL_WEB" = true ]; then
  echo "==> 上传 portal_web..."
  do_ssh "mkdir -p ${PORTAL_WEB_REMOTE_DIR}"
  do_ssh "rm -rf ${PORTAL_WEB_REMOTE_DIR}/*"
  do_scp -r "${BUILD_DIR}/portal_web/"* "${REMOTE_HOST}:${PORTAL_WEB_REMOTE_DIR}/"
fi

if [ ${#COMPONENTS[@]} -gt 0 ]; then
  echo "==> 设置可执行权限..."
  CHMOD_LIST=""
  for comp in "${COMPONENTS[@]}"; do
    CHMOD_LIST="$CHMOD_LIST ${REMOTE_DIR}/${comp}"
  done
  do_ssh "chmod +x $CHMOD_LIST"
fi

echo "==> 上传完成"
echo ""
echo "    远程文件树:"
do_ssh "tree ${REMOTE_DIR} 2>/dev/null || find ${REMOTE_DIR} -type f | head -50 | sort"
echo ""

# ============================================================
# Step 6: Let's Encrypt 证书申请 (letsencrypt 模式)
# ============================================================
if [ "$SSL_MODE" = "letsencrypt" ] && [ "$PARTIAL_DEPLOY" = false ]; then
  echo "==> 申请 Let's Encrypt 证书..."
  set +e
  do_ssh bash -s -- "$DOMAIN" "$API_DOMAIN" "$ADMIN_EMAIL" "${CERT_REF_DIR}/${CERT_FILE_NAME}" "${CERT_REF_DIR}/${KEY_FILE_NAME}" <<'CERT_SCRIPT'
set -euo pipefail
DOMAIN="$1"
API_DOMAIN="$2"
ADMIN_EMAIL="$3"
CERT_FILE="$4"
KEY_FILE="$5"

if ! command -v certbot &>/dev/null; then
  echo "    安装 Certbot..."
  if command -v dnf &>/dev/null; then
    dnf install -y -q epel-release >/dev/null 2>&1 || true
    dnf install -y -q certbot python3-certbot-nginx >/dev/null 2>&1
  elif command -v yum &>/dev/null; then
    yum install -y -q epel-release >/dev/null 2>&1 || true
    yum install -y -q certbot python3-certbot-nginx >/dev/null 2>&1
  elif command -v apt-get &>/dev/null; then
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq certbot python3-certbot-nginx >/dev/null 2>&1
  else
    echo "    [ERROR] 无法检测到支持的包管理器" >&2
    exit 1
  fi
  echo "    Certbot 已安装"
else
  echo "    Certbot 已存在: $(certbot --version 2>&1)"
fi

if [ -f "$CERT_FILE" ]; then
  echo "    已有证书，执行续期检查..."
  certbot renew --quiet --no-random-sleep-on-renew 2>/dev/null || true
  echo "    续期检查完成"
else
  echo "    申请新证书..."
  echo "    释放端口 80..."
  systemctl stop nginx 2>/dev/null || nginx -s stop 2>/dev/null || true
  sleep 1

  PORT80_PIDS=$(ss -tlnp 'sport = :80' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
  if [ -n "$PORT80_PIDS" ]; then
    for p in $PORT80_PIDS; do
      kill -9 "$p" 2>/dev/null || true
    done
    sleep 2
  fi

  certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email "$ADMIN_EMAIL" \
    -d "$DOMAIN" \
    -d "$API_DOMAIN" \
    --preferred-challenges http

  if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "    [ERROR] 证书文件未创建"
    exit 1
  fi
  echo "    证书申请成功"
fi

if ! crontab -l 2>/dev/null | grep -q 'certbot renew'; then
  echo "    安装证书续期定时任务..."
  (crontab -l 2>/dev/null || true; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx' >> /var/log/certbot-renew.log 2>&1") | crontab -
  echo "    定时任务已添加"
fi
CERT_SCRIPT
  CERT_RC=$?
  set -e

  if [ $CERT_RC -ne 0 ]; then
    echo ""
    echo "============================================================"
    echo "[FATAL] 证书申请失败 (exit code=${CERT_RC})"
    echo "请检查:"
    echo "  1. ${DOMAIN} 是否解析到服务器 IP"
    echo "  2. 入站端口 80 是否开放"
    echo "  3. ssh ${REMOTE_HOST} 'cat /var/log/letsencrypt/letsencrypt.log'"
    echo "============================================================"
    exit 1
  fi
fi

# ============================================================
# Step 7: 启动服务
# ============================================================
if [ ${#COMPONENTS[@]} -gt 0 ]; then
  COMP_LIST=$(IFS=' '; echo "${COMPONENTS[*]}")
  echo "==> 启动服务 (${COMPONENTS[*]})..."
  do_ssh bash -s -- "$REMOTE_DIR" "$COMP_LIST" <<'START_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
shift
COMP_LIST="$*"
cd "$REMOTE_DIR"

for comp in $COMP_LIST; do
  nohup "${REMOTE_DIR}/${comp}" > "${REMOTE_DIR}/${comp}.log" 2>&1 &
  echo "    已启动 ${comp} (pid=$!)"
done
START_SCRIPT

  for comp in "${COMPONENTS[@]}"; do
    echo "    日志: ${REMOTE_DIR}/${comp}.log"
  done
fi

# ============================================================
# Step 8: 配置 Nginx Ingress
# ============================================================
if [ "$PARTIAL_DEPLOY" = false ]; then
  echo "==> 配置 Nginx 反向代理..."
  do_ssh bash -s -- \
    "$CONTROL_WEB_REMOTE_DIR" "$PORTAL_WEB_REMOTE_DIR" "$NGINX_CONF" \
    "$PUBLIC_HOST" "$CERT_REF_DIR" "$API_DOMAIN" "$DOMAIN" \
    "$CERT_FILE_NAME" "$KEY_FILE_NAME" <<'NGINX_SCRIPT'
set -euo pipefail
CW_DIR="$1"
PW_DIR="$2"
CONF="$3"
SERVER_NAME="$4"
CERT_DIR="$5"
API_SERVER_NAME="$6"
DOMAIN="$7"
CERT_FILE_NAME="$8"
KEY_FILE_NAME="$9"

# 安装 Nginx
if ! command -v nginx &>/dev/null; then
  echo "    安装 Nginx..."
  if command -v dnf &>/dev/null; then
    dnf install -y -q nginx >/dev/null 2>&1
  elif command -v yum &>/dev/null; then
    yum install -y -q nginx >/dev/null 2>&1
  elif command -v apt-get &>/dev/null; then
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq nginx >/dev/null 2>&1
  fi
fi

# 禁用默认 server 块
if grep -q '^    server {' /etc/nginx/nginx.conf 2>/dev/null; then
  sed -i '/^    server {$/,/^    }$/s/^/#/' /etc/nginx/nginx.conf
  echo "    已禁用默认 server 块"
fi

# 清理旧配置
rm -f /etc/nginx/conf.d/deeppool_*.conf 2>/dev/null

cat > "$CONF" <<NGINX_EOF
# ============================================================
# DeepPool Ingress — HTTPS (SSL termination)
# Generated by deploy.sh
# ============================================================

# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name ${SERVER_NAME} ${API_SERVER_NAME};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# 主站: portal + control + API
server {
    listen 443 ssl;
    server_name ${SERVER_NAME};

    ssl_certificate     ${CERT_DIR}/${CERT_FILE_NAME};
    ssl_certificate_key ${CERT_DIR}/${KEY_FILE_NAME};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    client_max_body_size    128m;
    client_body_buffer_size 1m;
    client_body_timeout     300s;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;

    # API 代理 -> manager :8080
    location /api/ {
        proxy_pass https://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Gateway 代理 -> manager :8080 (SSE/streaming)
    location /v1/ {
        proxy_pass https://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # 管控后台
    location /admin/ {
        alias ${CW_DIR}/;
        index index.html;
        try_files \$uri \$uri/ /admin/index.html;
    }

    # 门户 (默认)
    location / {
        root ${PW_DIR};
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }
}

# 独立 API 域名 (CORS 由 Go 后端处理)
server {
    listen 443 ssl;
    server_name ${API_SERVER_NAME};

    ssl_certificate     ${CERT_DIR}/${CERT_FILE_NAME};
    ssl_certificate_key ${CERT_DIR}/${KEY_FILE_NAME};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    client_max_body_size    128m;
    client_body_buffer_size 1m;
    client_body_timeout     300s;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;

    location /api/ {
        proxy_pass https://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location /v1/ {
        proxy_pass https://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location / {
        return 404;
    }
}
NGINX_EOF

echo "    Nginx 配置已写入 ${CONF}"
nginx -t 2>&1 && nginx -s reload 2>/dev/null || systemctl restart nginx
echo "    Nginx 已重载"
NGINX_SCRIPT

  echo "    Ingress 路由:"
  echo "      ${PUBLIC_HOST}  /        -> portal_web"
  echo "      ${PUBLIC_HOST}  /admin/  -> control_web"
  echo "      ${PUBLIC_HOST}  /api/    -> manager :8080"
  echo "      ${PUBLIC_HOST}  /v1/     -> manager :8080"
  echo "      ${API_DOMAIN}   /api/    -> manager :8080 (CORS)"
  echo "      ${API_DOMAIN}   /v1/     -> manager :8080 (CORS)"
fi

# ============================================================
# Step 9: 健康检查
# ============================================================
echo ""
echo "==> 等待服务初始化..."
sleep 3

echo "==> 远程进程状态:"
if [ ${#COMPONENTS[@]} -gt 0 ]; then
  do_ssh "ps aux | grep -E '$(IFS='|'; echo "${COMPONENTS[*]}")|nginx.*master' | grep -v grep || echo '    未检测到活跃服务进程'"
else
  do_ssh "ps aux | grep -E 'nginx.*master' | grep -v grep || echo '    未检测到活跃服务进程'"
fi
echo ""

if [ ${#COMPONENTS[@]} -gt 0 ]; then
  echo "==> 健康检查:"
  for comp in "${COMPONENTS[@]}"; do
    port_info=$(get_component_port "$comp")
    proto="${port_info%%:*}"
    port="${port_info##*:}"
    if [ "$proto" = "grpc" ]; then
      result=$(do_ssh "ss -tlnp 'sport = :${port}' 2>/dev/null | grep -q LISTEN && echo '{\"status\":\"ok\",\"service\":\"${comp}\",\"proto\":\"grpc\"}' || echo 'FAIL (端口 ${port} 未监听)'" || echo "FAIL")
      echo "    ${comp} (:${port}, gRPC): ${result}"
    else
      result=$(do_ssh "curl -sf -k https://127.0.0.1:${port}/health 2>/dev/null || echo 'FAIL'" || echo "FAIL")
      echo "    ${comp} (:${port}, HTTPS): ${result}"
    fi
  done
fi

if [ "$DEPLOY_PORTAL_WEB" = true ] || [ "$DEPLOY_CONTROL_WEB" = true ]; then
  if [ "$DEPLOY_PORTAL_WEB" = true ]; then
    portal_result=$(do_ssh "curl -sf -k https://127.0.0.1/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'" || echo "FAIL")
    echo "    portal_web  (https /):       ${portal_result}"
  fi
  if [ "$DEPLOY_CONTROL_WEB" = true ]; then
    admin_result=$(do_ssh "curl -sf -k https://127.0.0.1/admin/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'" || echo "FAIL")
    echo "    control_web (https /admin/): ${admin_result}"
  fi
fi
echo ""

# ============================================================
# Step 10: 部署摘要
# ============================================================
DEPLOYED_ITEMS=""
if [ ${#COMPONENTS[@]} -gt 0 ]; then DEPLOYED_ITEMS="${COMPONENTS[*]}"; fi
if [ "$DEPLOY_PORTAL_WEB" = true ]; then DEPLOYED_ITEMS="$DEPLOYED_ITEMS portal_web"; fi
if [ "$DEPLOY_CONTROL_WEB" = true ]; then DEPLOYED_ITEMS="$DEPLOYED_ITEMS control_web"; fi

echo "============================================================"
echo "  部署完成!"
echo "  组件: $DEPLOYED_ITEMS"
echo "  域名: https://${DOMAIN}"
echo "  API:  https://${API_DOMAIN}"
echo "============================================================"
echo ""

if [ ${#COMPONENTS[@]} -gt 0 ]; then
  echo "  服务端点 (HTTPS):"
  for comp in "${COMPONENTS[@]}"; do
    port_info=$(get_component_port "$comp")
    port="${port_info##*:}"
    echo "    ${comp}: https://127.0.0.1:${port}"
  done
  echo ""

  echo "  日志查看:"
  for comp in "${COMPONENTS[@]}"; do
    echo "    ssh ${REMOTE_HOST} 'tail -f ${REMOTE_DIR}/${comp}.log'"
  done
fi
