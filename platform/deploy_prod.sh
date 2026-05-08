#!/bin/bash
# deploy_prod.sh — Build and deploy all platform components to production ECS server.
#
# This script handles:
#   1. Cross-compile Go services for linux/amd64
#   2. Build frontend assets (control_web + portal_web)
#   3. Upload all artifacts + SSL certificate to the remote ECS server
#   4. Configure Nginx as reverse proxy / ingress (SSL termination)
#   5. Start all services and run health checks
#
# SSL certificate:
#   Uses Alibaba Cloud wildcard certificate (*.deeppool.tech).
#   Download the Nginx-format cert from Alibaba Cloud console and place them in:
#     platform/ssl_cert/deeppool.tech.pem   (certificate + intermediate chain)
#     platform/ssl_cert/deeppool.tech.key   (private key)
#
# Ingress routing:
#   /        -> portal_web
#   /admin/  -> control_web
#   /api/    -> manager :8080
#   /v1/     -> manager :8080
#
# Usage:
#   DEEPPOOL_DOMAIN=deeppool.tech ./deploy_prod.sh
#
# Prerequisites:
#   - sshpass installed locally (brew install hudochenkov/sshpass/sshpass)
#   - Go, Node.js, npm available locally
#   - SSL certificate files in platform/ssl_cert/ directory
set -euo pipefail

# ============================================================
# Remote server configuration
# ============================================================
REMOTE_USER="root"
REMOTE_IP="47.121.115.80"
REMOTE_PASS="AliRoot@123"
REMOTE_HOST="${REMOTE_USER}@${REMOTE_IP}"
REMOTE_DIR="/opt/deeppool"

# SSH/SCP wrapper using sshpass for password-based authentication.
# Use SSHPASS env var + sshpass -e to avoid stdin conflicts with heredoc.
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
export SSHPASS="${REMOTE_PASS}"

do_ssh() {
  sshpass -e ssh ${SSH_OPTS} "${REMOTE_HOST}" "$@"
}

do_scp() {
  sshpass -e scp ${SSH_OPTS} "$@"
}

# ============================================================
# Runtime paths
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$SCRIPT_DIR"
BUILD_DIR="$PLATFORM_DIR/build"
CONFIG_PROD_DIR="$PLATFORM_DIR/config_prod"

# ============================================================
# Domain & certificate configuration
# ============================================================
DOMAIN="${DEEPPOOL_DOMAIN:-deeppool.tech}"
API_DOMAIN="api.${DOMAIN}"
PUBLIC_HOST="${DEEPPOOL_PUBLIC_HOST:-${DOMAIN}}"

# SSL certificate: Alibaba Cloud wildcard cert (*.deeppool.tech)
# Remote path on ECS where cert files will be uploaded
REMOTE_CERT_DIR="/etc/ssl/deeppool"
REMOTE_CERT_FILE="${REMOTE_CERT_DIR}/${DOMAIN}.pem"
REMOTE_KEY_FILE="${REMOTE_CERT_DIR}/${DOMAIN}.key"
# Local path: download from Alibaba Cloud console (Nginx format)
LOCAL_CERT_DIR="${PLATFORM_DIR}/ssl_cert"
LOCAL_CERT_FILE="${LOCAL_CERT_DIR}/${DOMAIN}.pem"
LOCAL_KEY_FILE="${LOCAL_CERT_DIR}/${DOMAIN}.key"

# ============================================================
# Component definitions
# ============================================================
COMPONENTS=(manager scheduler nodemanager)

CONTROL_WEB_DIR="control_web"
CONTROL_WEB_REMOTE_DIR="${REMOTE_DIR}/control_web"
PORTAL_WEB_DIR="portal_web"
PORTAL_WEB_REMOTE_DIR="${REMOTE_DIR}/portal_web"
NGINX_CONF="/etc/nginx/conf.d/deeppool.conf"

# ============================================================
# Cross-compile settings
# ============================================================
export GOOS=linux
export GOARCH=amd64
export CGO_ENABLED=0

# ============================================================
# Pre-flight checks
# ============================================================
echo "============================================================"
echo "  DeepPool PRODUCTION Deployment"
echo "  Target:       ${REMOTE_HOST} (${REMOTE_IP})"
echo "  Remote dir:   ${REMOTE_DIR}"
echo "  Domain:       ${DOMAIN}"
echo "  API domain:   ${API_DOMAIN}"
echo "  Public host:  ${PUBLIC_HOST}"
echo "  SSL cert:     ${LOCAL_CERT_DIR}/"
echo "  Config dir:   ${CONFIG_PROD_DIR}"
echo "============================================================"
echo ""

# Check sshpass availability
if ! command -v sshpass &>/dev/null; then
  echo "[ERROR] sshpass is required but not installed."
  echo "  macOS:  brew install hudochenkov/sshpass/sshpass"
  echo "  Linux:  apt-get install sshpass / yum install sshpass"
  exit 1
fi

# Check SSL certificate files exist locally
if [ ! -f "${LOCAL_CERT_FILE}" ] || [ ! -f "${LOCAL_KEY_FILE}" ]; then
  echo "============================================================"
  echo "[ERROR] SSL certificate files not found!"
  echo ""
  echo "  Expected files:"
  echo "    ${LOCAL_CERT_FILE}  (certificate + chain)"
  echo "    ${LOCAL_KEY_FILE}   (private key)"
  echo ""
  echo "  How to prepare:"
  echo "    1. Go to Alibaba Cloud Console -> SSL Certificates"
  echo "    2. Download cert in Nginx format"
  echo "    3. Place .pem and .key files in: ${LOCAL_CERT_DIR}/"
  echo "============================================================"
  exit 1
fi
echo "==> SSL certificate files found."

# Verify SSH connectivity
echo "==> Verifying SSH connectivity..."
if ! do_ssh "echo 'SSH connection OK'"; then
  echo "[ERROR] Cannot connect to ${REMOTE_HOST}"
  exit 1
fi

# ============================================================
# Step 1: Build Go services
# ============================================================
echo "==> Cleaning previous build artifacts..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "==> Cross-compiling Go services (GOOS=${GOOS} GOARCH=${GOARCH})..."
cd "$PLATFORM_DIR"
for comp in "${COMPONENTS[@]}"; do
  echo "    Building ${comp} ..."
  go build -trimpath -ldflags="-s -w" -o "${BUILD_DIR}/${comp}" "./cmd/${comp}"
done
echo "    All Go services built successfully."

# Copy production config files
echo "==> Copying production config from ${CONFIG_PROD_DIR}..."
cp -r "${CONFIG_PROD_DIR}" "${BUILD_DIR}/config"
echo "    Config files copied."

# ============================================================
# Step 2: Build control_web
# ============================================================
echo "==> Building control_web (base=/admin/)..."
cd "${PLATFORM_DIR}/${CONTROL_WEB_DIR}"
npm install --silent
VITE_BASE=/admin/ \
  VITE_API_BASE_URL="https://${API_DOMAIN}/api/v1" \
  VITE_GATEWAY_BASE_URL="https://${API_DOMAIN}/v1" \
  npm run build
cp -r "${PLATFORM_DIR}/${CONTROL_WEB_DIR}/dist" "${BUILD_DIR}/control_web"
echo "    control_web build completed."
cd "$PLATFORM_DIR"

# ============================================================
# Step 3: Build portal_web
# ============================================================
echo "==> Building portal_web..."
cd "${PLATFORM_DIR}/${PORTAL_WEB_DIR}"
npm install --silent
VITE_API_BASE_URL="https://${API_DOMAIN}/api/v1" \
  VITE_GATEWAY_BASE_URL="https://${API_DOMAIN}/v1" \
  npm run build
cp -r "${PLATFORM_DIR}/${PORTAL_WEB_DIR}/dist" "${BUILD_DIR}/portal_web"
echo "    portal_web build completed."
cd "$PLATFORM_DIR"

# ============================================================
# Build summary
# ============================================================
echo "==> Build artifacts summary:"
ls -lh "${BUILD_DIR}"/manager "${BUILD_DIR}"/scheduler "${BUILD_DIR}"/nodemanager
echo "    control_web: $(du -sh "${BUILD_DIR}/control_web" | awk '{print $1}')"
echo "    portal_web:  $(du -sh "${BUILD_DIR}/portal_web" | awk '{print $1}')"
echo ""

# ============================================================
# Step 4: Stop existing remote services
# ============================================================
echo "==> Stopping existing remote services..."
do_ssh bash -s -- "$REMOTE_DIR" <<'STOP_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"

for comp in manager scheduler nodemanager; do
  pid=$(ps -eo pid,args | grep -E "(\./${comp}|${REMOTE_DIR}/${comp})" | grep -v -E "grep|bash|scp" | awk '{print $1}' || true)
  if [ -n "$pid" ]; then
    kill "$pid" 2>/dev/null || true
    echo "    Sent SIGTERM to $comp (pid=$pid)"
  else
    echo "    $comp is not running"
  fi
done

echo "    Waiting for processes to exit..."
sleep 2

for comp in manager scheduler nodemanager; do
  pid=$(ps -eo pid,args | grep -E "(\./${comp}|${REMOTE_DIR}/${comp})" | grep -v -E "grep|bash|scp" | awk '{print $1}' || true)
  if [ -n "$pid" ]; then
    kill -9 "$pid" 2>/dev/null || true
    echo "    Force killed $comp (pid=$pid)"
  fi
done

sleep 1
rm -f "${REMOTE_DIR}/manager" "${REMOTE_DIR}/scheduler" "${REMOTE_DIR}/nodemanager"
echo "    Previous binaries removed."
STOP_SCRIPT

# ============================================================
# Step 5: Upload artifacts
# ============================================================
echo "==> Creating remote directories..."
do_ssh "mkdir -p ${REMOTE_DIR}/config ${REMOTE_DIR}/alipay_cert ${REMOTE_DIR}/wechat_pay_cert ${REMOTE_CERT_DIR} ${CONTROL_WEB_REMOTE_DIR} ${PORTAL_WEB_REMOTE_DIR}"

echo "==> Uploading Go binaries..."
do_scp "${BUILD_DIR}/manager" \
       "${BUILD_DIR}/scheduler" \
       "${BUILD_DIR}/nodemanager" \
       "${REMOTE_HOST}:${REMOTE_DIR}/"

echo "==> Uploading config files..."
do_scp "${BUILD_DIR}/config/"*.yaml \
       "${REMOTE_HOST}:${REMOTE_DIR}/config/"

echo "==> Uploading payment certificates..."
do_scp "${PLATFORM_DIR}/alipay_cert/"*.pem \
       "${REMOTE_HOST}:${REMOTE_DIR}/alipay_cert/"
do_scp "${PLATFORM_DIR}/wechat_pay_cert/"* \
       "${REMOTE_HOST}:${REMOTE_DIR}/wechat_pay_cert/"

echo "==> Uploading SSL certificate (Alibaba Cloud wildcard)..."
do_scp "${LOCAL_CERT_FILE}" "${REMOTE_HOST}:${REMOTE_CERT_FILE}"
do_scp "${LOCAL_KEY_FILE}"  "${REMOTE_HOST}:${REMOTE_KEY_FILE}"
do_ssh "chmod 600 ${REMOTE_CERT_DIR}/*.pem"
echo "    SSL cert uploaded to ${REMOTE_CERT_DIR}/"

echo "==> Uploading control_web..."
do_ssh "rm -rf ${CONTROL_WEB_REMOTE_DIR}/*"
do_scp -r "${BUILD_DIR}/control_web/"* "${REMOTE_HOST}:${CONTROL_WEB_REMOTE_DIR}/"

echo "==> Uploading portal_web..."
do_ssh "rm -rf ${PORTAL_WEB_REMOTE_DIR}/*"
do_scp -r "${BUILD_DIR}/portal_web/"* "${REMOTE_HOST}:${PORTAL_WEB_REMOTE_DIR}/"

echo "==> Setting executable permissions..."
do_ssh "chmod +x ${REMOTE_DIR}/manager ${REMOTE_DIR}/scheduler ${REMOTE_DIR}/nodemanager"

echo "==> Upload completed."
echo ""
echo "    Remote file tree:"
do_ssh "tree ${REMOTE_DIR} 2>/dev/null || find ${REMOTE_DIR} -type f | head -50 | sort"
echo ""

# ============================================================
# Step 6: Enable TLS for gRPC services
# ============================================================
echo "==> Synchronizing gRPC TLS settings (using Alibaba Cloud SSL cert)..."
do_ssh bash -s -- "$REMOTE_DIR" "$REMOTE_CERT_FILE" "$REMOTE_KEY_FILE" <<'TLS_SYNC_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
CERT_FILE="$2"
KEY_FILE="$3"

for comp in manager scheduler nodemanager; do
  cfg="${REMOTE_DIR}/config/${comp}.yaml"
  if [ ! -f "$cfg" ]; then
    echo "    [SKIP] $cfg not found"
    continue
  fi

  sed -i \
    -e 's/enabled: false/enabled: true/' \
    -e 's/enabled: true/enabled: true/' \
    -e "s|cert_file: \".*\"|cert_file: \"${CERT_FILE}\"|" \
    -e "s|key_file: \".*\"|key_file: \"${KEY_FILE}\"|" \
    "$cfg"
  echo "    ${comp}: gRPC TLS enabled (cert=${CERT_FILE})"
done
TLS_SYNC_SCRIPT

# ============================================================
# Step 7: Start services
# ============================================================
echo "==> Starting services..."
do_ssh bash -s -- "$REMOTE_DIR" <<'START_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
cd "$REMOTE_DIR"

for comp in manager scheduler nodemanager; do
  nohup "${REMOTE_DIR}/${comp}" > "${REMOTE_DIR}/${comp}.log" 2>&1 &
  echo "    Started ${comp} (pid=$!)"
done
START_SCRIPT

for comp in "${COMPONENTS[@]}"; do
  echo "    Log: ${REMOTE_DIR}/${comp}.log"
done

# ============================================================
# Step 8: Configure Nginx ingress
# ============================================================
echo "==> Configuring Nginx reverse proxy..."
do_ssh bash -s -- \
  "$CONTROL_WEB_REMOTE_DIR" "$PORTAL_WEB_REMOTE_DIR" "$NGINX_CONF" \
  "$PUBLIC_HOST" "$REMOTE_CERT_DIR" "$API_DOMAIN" "$DOMAIN" <<'NGINX_SCRIPT'
set -euo pipefail
CW_DIR="$1"
PW_DIR="$2"
CONF="$3"
SERVER_NAME="$4"
CERT_DIR="$5"
API_SERVER_NAME="$6"
DOMAIN="$7"

# Install Nginx if not present
if ! command -v nginx &>/dev/null; then
  echo "    Installing Nginx..."
  if command -v dnf &>/dev/null; then
    dnf install -y -q nginx >/dev/null 2>&1
  elif command -v yum &>/dev/null; then
    yum install -y -q nginx >/dev/null 2>&1
  elif command -v apt-get &>/dev/null; then
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq nginx >/dev/null 2>&1
  fi
fi

# Disable default inline server block if present
if grep -q '^    server {' /etc/nginx/nginx.conf 2>/dev/null; then
  sed -i '/^    server {$/,/^    }$/s/^/#/' /etc/nginx/nginx.conf
  echo "    Disabled default inline server block."
fi

# Clean up legacy config fragments
rm -f /etc/nginx/conf.d/deeppool_*.conf 2>/dev/null

cat > "$CONF" <<NGINX_EOF
# ============================================================
# DeepPool PRODUCTION ingress — HTTPS with SSL termination
# Generated by deploy_prod.sh
# ============================================================

# HTTP -> HTTPS redirect
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

# Main site: portal + control + API
server {
    listen 443 ssl;
    server_name ${SERVER_NAME};

    ssl_certificate     ${CERT_DIR}/${DOMAIN}.pem;
    ssl_certificate_key ${CERT_DIR}/${DOMAIN}.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # Allow large multi-modal requests (images/files encoded as base64).
    # Aligned with gRPC MaxCallRecvMsgSize (128 MiB) on the NodeManager hop.
    client_max_body_size    128m;
    client_body_buffer_size 1m;
    client_body_timeout     300s;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;

    # API proxy -> manager :8080 (TLS backend)
    # Includes misszhao SSE chat via /api/misszhao/chat/*, so SSE settings required.
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

    # Gateway proxy -> manager :8080 (SSE/streaming, TLS backend)
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

    # Admin console
    location /admin/ {
        alias ${CW_DIR}/;
        index index.html;
        try_files \$uri \$uri/ /admin/index.html;
    }

    # Portal (default)
    location / {
        root ${PW_DIR};
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }
}

# Dedicated API domain (CORS handled by Go backend)
server {
    listen 443 ssl;
    server_name ${API_SERVER_NAME};

    ssl_certificate     ${CERT_DIR}/${DOMAIN}.pem;
    ssl_certificate_key ${CERT_DIR}/${DOMAIN}.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # Allow large multi-modal requests (images/files encoded as base64).
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

echo "    Nginx config written to ${CONF}"
nginx -t 2>&1 && nginx -s reload 2>/dev/null || systemctl restart nginx
echo "    Nginx reloaded."
NGINX_SCRIPT

echo "    Ingress routes:"
echo "      ${PUBLIC_HOST}  /        -> portal_web"
echo "      ${PUBLIC_HOST}  /admin/  -> control_web"
echo "      ${PUBLIC_HOST}  /api/    -> manager :8080"
echo "      ${PUBLIC_HOST}  /v1/     -> manager :8080"
echo "      ${API_DOMAIN}   /api/    -> manager :8080 (CORS)"
echo "      ${API_DOMAIN}   /v1/     -> manager :8080 (CORS)"

# ============================================================
# Step 9: Health checks
# ============================================================
echo ""
echo "==> Waiting for services to initialize..."
sleep 3

echo "==> Remote process status:"
do_ssh "ps aux | grep -E '$(IFS='|'; echo "${COMPONENTS[*]}")|nginx.*master' | grep -v grep || echo '    No active service process detected'"
echo ""

echo "==> Health checks:"
for comp in "${COMPONENTS[@]}"; do
  case $comp in
    manager)     port=8080 ;;
    scheduler)   port=8081 ;;
    nodemanager) port=8082 ;;
  esac
  result=$(do_ssh "curl -sf -k https://127.0.0.1:${port}/health 2>/dev/null || echo 'FAIL'")
  echo "    ${comp} (:${port}): ${result}"
done

portal_result=$(do_ssh "curl -sf -k https://127.0.0.1/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
admin_result=$(do_ssh "curl -sf -k https://127.0.0.1/admin/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
api_result=$(do_ssh "curl -sf -k https://127.0.0.1/api/v1/public/stats 2>/dev/null || echo 'FAIL'")
echo "    portal_web  (https /):       ${portal_result}"
echo "    control_web (https /admin/): ${admin_result}"
echo "    API proxy   (https /api/):   ${api_result}"
echo ""

# ============================================================
# Step 10: Deployment summary
# ============================================================
echo "============================================================"
echo "  PRODUCTION deployment completed successfully!"
echo "============================================================"
echo ""
echo "  Public endpoints:"
echo "    Portal:     https://${PUBLIC_HOST}/"
echo "    Admin:      https://${PUBLIC_HOST}/admin/"
echo "    API:        https://${API_DOMAIN}/api/"
echo "    Gateway:    https://${API_DOMAIN}/v1/"
echo ""
echo "  Service endpoints (internal, HTTPS):"
echo "    manager:     https://127.0.0.1:8080"
echo "    scheduler:   https://127.0.0.1:8081"
echo "    nodemanager: https://127.0.0.1:8082"
echo ""
echo "  gRPC endpoints (TLS):"
echo "    manager:     :9090"
echo "    scheduler:   :9091"
echo "    nodemanager: :9092"
echo ""
echo "  SSL Certificate (Alibaba Cloud wildcard *.deeppool.tech):"
echo "    Path:      ${REMOTE_CERT_DIR}/"
echo "    Expires:   2026-10-29 (renew before expiry via Alibaba Cloud console)"
echo ""
echo "  Logs:"
for comp in "${COMPONENTS[@]}"; do
  echo "    ssh ${REMOTE_HOST} 'tail -f ${REMOTE_DIR}/${comp}.log'"
done
echo ""
echo "  Quick commands:"
echo "    Restart all:  ssh ${REMOTE_HOST} 'cd ${REMOTE_DIR} && kill \$(pgrep -f \"manager|scheduler|nodemanager\") 2>/dev/null; for c in manager scheduler nodemanager; do nohup ./${c} > ${c}.log 2>&1 &; done'"
echo "    Check status:  ssh ${REMOTE_HOST} 'ps aux | grep -E \"manager|scheduler|nodemanager\" | grep -v grep'"
