#!/bin/bash
# deploy_test.sh — build and deploy all platform components to the test server.
#
# HTTPS is mandatory for testing; there is no HTTP-only mode.
#
# Required environment variables:
#   DEEPPOOL_DOMAIN       — resolvable domain for TLS certificate (e.g. test.deeppool.tech)
#
# Optional environment variables:
#   DEEPPOOL_PUBLIC_HOST  — public host shown in the final output (defaults to DOMAIN)
#   DEEPPOOL_ADMIN_EMAIL  — email used for Let's Encrypt registration (defaults to admin@deeppool.tech)
#
# Ingress routing:
#   /        -> portal_web
#   /admin/  -> control_web
#   /api/    -> manager :8080
#   /v1/     -> manager :8080
set -euo pipefail

# ============================================================
# Configuration
# ============================================================
REMOTE_HOST="root@8.135.66.7"
REMOTE_DIR="/opt/deeppool"
COMPONENTS=(manager scheduler nodemanager)

CONTROL_WEB_DIR="control_web"
CONTROL_WEB_REMOTE_DIR="$REMOTE_DIR/control_web"
PORTAL_WEB_DIR="portal_web"
PORTAL_WEB_REMOTE_DIR="$REMOTE_DIR/portal_web"
NGINX_CONF="/etc/nginx/conf.d/deeppool.conf"

# Production always uses HTTPS
DEPLOY_MODE="https"
DEPLOY_MODE_DISPLAY="HTTPS"
PUBLIC_SCHEME="https"
PUBLIC_PORT="443"
INTERNAL_SCHEME="https"
TLS_ENABLED="true"

DOMAIN="${DEEPPOOL_DOMAIN:-}"
ADMIN_EMAIL="${DEEPPOOL_ADMIN_EMAIL:-admin@deeppool.tech}"
PUBLIC_HOST="${DEEPPOOL_PUBLIC_HOST:-}"

if [ -z "$DOMAIN" ]; then
  echo "============================================================"
  echo "[ERROR] Test deployment requires DEEPPOOL_DOMAIN to be set"
  echo ""
  echo "Usage:"
  echo "  DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh"
  echo ""
  echo "Optional environment variables:"
  echo "  DEEPPOOL_PUBLIC_HOST   Public host shown in the final output"
  echo "  DEEPPOOL_ADMIN_EMAIL   Certificate registration email (default: admin@deeppool.tech)"
  echo "============================================================"
  exit 1
fi

if [ -z "$PUBLIC_HOST" ]; then
  PUBLIC_HOST="$DOMAIN"
fi

# API subdomain for dedicated backend access (e.g. deeppool.tech → api.deeppool.tech)
API_DOMAIN="api.${DOMAIN}"

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
CERT_FILE="${CERT_DIR}/fullchain.pem"
KEY_FILE="${CERT_DIR}/privkey.pem"

export GOOS=linux
export GOARCH=amd64
export CGO_ENABLED=0

# ============================================================
# Runtime paths
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$SCRIPT_DIR"
BUILD_DIR="$PLATFORM_DIR/build"

# ============================================================
# Banner
# ============================================================
echo "============================================================"
echo "  DeepPool TEST deployment"
echo "  Ingress mode: ${DEPLOY_MODE_DISPLAY}"
echo "  Target:       ${REMOTE_HOST}"
echo "  Public host:  ${PUBLIC_HOST}"
echo "  Domain:       ${DOMAIN}"
echo "  API domain:   ${API_DOMAIN}"
echo "  Cert email:   ${ADMIN_EMAIL}"
echo "============================================================"
echo ""

# ============================================================
# Build Go components
# ============================================================
echo "==> Cleaning previous build artifacts..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "==> Cross compiling Go services (GOOS=$GOOS GOARCH=$GOARCH)..."
cd "$PLATFORM_DIR"
for comp in "${COMPONENTS[@]}"; do
  echo "    Building $comp ..."
  go build -trimpath -ldflags="-s -w" -o "$BUILD_DIR/$comp" "./cmd/$comp"
done
echo "    Go services built successfully"

cp -r "$PLATFORM_DIR/config_test" "$BUILD_DIR/config"

# ============================================================
# Build control_web
# ============================================================
echo "==> Building control_web (base=/admin/)..."
cd "$PLATFORM_DIR/$CONTROL_WEB_DIR"
npm install --silent
VITE_BASE=/admin/ \
  VITE_API_BASE_URL="https://${API_DOMAIN}/api/v1" \
  VITE_GATEWAY_BASE_URL="https://${API_DOMAIN}/v1" \
  npm run build
cp -r "$PLATFORM_DIR/$CONTROL_WEB_DIR/dist" "$BUILD_DIR/control_web"
echo "    control_web build completed"
cd "$PLATFORM_DIR"

# ============================================================
# Build portal_web
# ============================================================
echo "==> Building portal_web..."
cd "$PLATFORM_DIR/$PORTAL_WEB_DIR"
npm install --silent
VITE_API_BASE_URL="https://${API_DOMAIN}/api/v1" \
  VITE_GATEWAY_BASE_URL="https://${API_DOMAIN}/v1" \
  npm run build
cp -r "$PLATFORM_DIR/$PORTAL_WEB_DIR/dist" "$BUILD_DIR/portal_web"
echo "    portal_web build completed"
cd "$PLATFORM_DIR"

echo "==> Build artifacts summary:"
ls -lh "$BUILD_DIR"/manager "$BUILD_DIR"/scheduler "$BUILD_DIR"/nodemanager
echo "    control_web: $(du -sh "$BUILD_DIR/control_web" | awk '{print $1}')"
echo "    portal_web:  $(du -sh "$BUILD_DIR/portal_web" | awk '{print $1}')"
echo ""

# ============================================================
# Stop previous services
# ============================================================
echo "==> Stopping existing remote services..."
ssh "$REMOTE_HOST" bash -s -- "$REMOTE_DIR" <<'STOP_SCRIPT'
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

echo "    Waiting for old processes to exit..."
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
echo "    Previous binaries removed"
STOP_SCRIPT

# ============================================================
# Upload files
# ============================================================
echo "==> Uploading artifacts to $REMOTE_HOST:$REMOTE_DIR ..."
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/config $REMOTE_DIR/alipay_cert $REMOTE_DIR/wechat_pay_cert $CONTROL_WEB_REMOTE_DIR $PORTAL_WEB_REMOTE_DIR"

scp "${BUILD_DIR}/manager" \
    "${BUILD_DIR}/scheduler" \
    "${BUILD_DIR}/nodemanager" \
    "$REMOTE_HOST:$REMOTE_DIR/"

scp "${BUILD_DIR}/config/"*.yaml \
    "$REMOTE_HOST:$REMOTE_DIR/config/"

# Upload payment certificate files
scp "${PLATFORM_DIR}/alipay_cert/"*.pem \
    "$REMOTE_HOST:$REMOTE_DIR/alipay_cert/"
scp "${PLATFORM_DIR}/wechat_pay_cert/"* \
    "$REMOTE_HOST:$REMOTE_DIR/wechat_pay_cert/"

ssh "$REMOTE_HOST" "rm -rf $CONTROL_WEB_REMOTE_DIR/*"
scp -r "${BUILD_DIR}/control_web/"* "$REMOTE_HOST:$CONTROL_WEB_REMOTE_DIR/"

ssh "$REMOTE_HOST" "rm -rf $PORTAL_WEB_REMOTE_DIR/*"
scp -r "${BUILD_DIR}/portal_web/"* "$REMOTE_HOST:$PORTAL_WEB_REMOTE_DIR/"

ssh "$REMOTE_HOST" "chmod +x $REMOTE_DIR/manager $REMOTE_DIR/scheduler $REMOTE_DIR/nodemanager"

echo "==> Upload completed"
echo ""
echo "Remote tree:"
ssh "$REMOTE_HOST" "tree $REMOTE_DIR 2>/dev/null || find $REMOTE_DIR -type f | sort"
echo ""

# ============================================================
# Provision HTTPS certificate
# ============================================================
echo "==> Installing Certbot and provisioning Let's Encrypt certificate..."
set +e
ssh "$REMOTE_HOST" bash -s -- "$DOMAIN" "$API_DOMAIN" "$ADMIN_EMAIL" "$CERT_FILE" "$KEY_FILE" <<'CERT_SCRIPT'
set -euo pipefail
DOMAIN="$1"
API_DOMAIN="$2"
ADMIN_EMAIL="$3"
CERT_FILE="$4"
KEY_FILE="$5"

if ! command -v certbot &>/dev/null; then
  echo "    Installing Certbot..."
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
    echo "    [ERROR] Unable to detect a supported package manager for Certbot" >&2
    exit 1
  fi
  echo "    Certbot installed"
else
  echo "    Certbot already present: $(certbot --version 2>&1)"
fi

if [ -f "$CERT_FILE" ]; then
  echo "    Existing certificate found, running renew check..."
  certbot renew --quiet --no-random-sleep-on-renew 2>/dev/null || true
  echo "    Renew check completed"
else
  echo "    Requesting a new certificate..."
  echo "    Releasing port 80 for ACME challenge..."
  systemctl stop nginx 2>/dev/null || nginx -s stop 2>/dev/null || true
  sleep 1

  PORT80_PIDS=$(ss -tlnp 'sport = :80' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
  if [ -n "$PORT80_PIDS" ]; then
    echo "    Found remaining listeners on port 80: ${PORT80_PIDS}"
    for p in $PORT80_PIDS; do
      kill -9 "$p" 2>/dev/null || true
    done
    sleep 2
  fi

  if ss -tlnp 'sport = :80' 2>/dev/null | grep -q LISTEN; then
    echo "    [ERROR] Port 80 is still occupied, cannot request certificate"
    ss -tlnp 'sport = :80'
    exit 1
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
    echo "    [ERROR] Certificate files were not created after Certbot finished"
    echo "    Expected certificate: $CERT_FILE"
    echo "    Check: /var/log/letsencrypt/letsencrypt.log"
    exit 1
  fi
  echo "    Certificate request succeeded"
fi

if ! crontab -l 2>/dev/null | grep -q 'certbot renew'; then
  echo "    Installing certificate renew cron job..."
  (crontab -l 2>/dev/null || true; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx' >> /var/log/certbot-renew.log 2>&1") | crontab -
  echo "    Renew cron job added"
fi

echo "    Certificate files:"
echo "      cert: $CERT_FILE"
echo "      key:  $KEY_FILE"
CERT_SCRIPT
CERT_RC=$?
set -e

if [ $CERT_RC -ne 0 ]; then
  echo ""
  echo "============================================================"
  echo "[FATAL] Certificate provisioning failed (exit code=${CERT_RC})"
  echo "Check the following items:"
  echo "  1. ${DOMAIN} resolves to ${REMOTE_HOST#*@}"
  echo "  2. Inbound port 80 is open for ACME challenge"
  echo "  3. ssh ${REMOTE_HOST} 'cat /var/log/letsencrypt/letsencrypt.log'"
  echo "============================================================"
  exit 1
fi

# ============================================================
# Sync TLS settings in YAML files
# ============================================================
echo "==> Synchronizing service TLS settings..."
ssh "$REMOTE_HOST" bash -s -- "$REMOTE_DIR" "$TLS_ENABLED" "$CERT_FILE" "$KEY_FILE" <<'TLS_SYNC_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
TLS_ENABLED="$2"
CERT_FILE="${3:-}"
KEY_FILE="${4:-}"

for comp in manager scheduler nodemanager; do
  cfg="${REMOTE_DIR}/config/${comp}.yaml"
  if [ ! -f "$cfg" ]; then
    continue
  fi

  sed -i \
    -e 's/enabled: false/enabled: true/' \
    -e 's/enabled: true/enabled: true/' \
    -e "s|cert_file: \".*\"|cert_file: \"${CERT_FILE}\"|" \
    -e "s|key_file: \".*\"|key_file: \"${KEY_FILE}\"|" \
    "$cfg"
  echo "    $comp TLS enabled"
done
TLS_SYNC_SCRIPT

# ============================================================
# Start services
# ============================================================
echo "==> Starting services..."
ssh "$REMOTE_HOST" bash -s -- "$REMOTE_DIR" <<'START_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
cd "$REMOTE_DIR"

for comp in manager scheduler nodemanager; do
  nohup "${REMOTE_DIR}/${comp}" > "${REMOTE_DIR}/${comp}.log" 2>&1 &
  echo "    Started $comp pid=$!"
done
START_SCRIPT
for comp in "${COMPONENTS[@]}"; do
  echo "    Log file: $REMOTE_DIR/${comp}.log"
done

# ============================================================
# Configure Nginx ingress (HTTPS only)
# ============================================================
echo "==> Writing Nginx ingress configuration for HTTPS mode..."
ssh "$REMOTE_HOST" bash -s -- \
  "$CONTROL_WEB_REMOTE_DIR" "$PORTAL_WEB_REMOTE_DIR" "$NGINX_CONF" \
  "$PUBLIC_HOST" "$INTERNAL_SCHEME" "$CERT_DIR" "$API_DOMAIN" <<'NGINX_SCRIPT'
set -euo pipefail
CW_DIR="$1"
PW_DIR="$2"
CONF="$3"
SERVER_NAME="$4"
UPSTREAM_SCHEME="$5"
CERT_DIR="$6"
API_SERVER_NAME="$7"

if [ -z "$SERVER_NAME" ]; then
  SERVER_NAME="_"
fi

if ! command -v nginx &>/dev/null; then
  echo "    Installing Nginx..."
  if command -v dnf &>/dev/null; then
    dnf install -y -q nginx >/dev/null 2>&1
  elif command -v yum &>/dev/null; then
    yum install -y -q nginx >/dev/null 2>&1
  elif command -v apt-get &>/dev/null; then
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq nginx >/dev/null 2>&1
  else
    echo "    [ERROR] Unable to detect a supported package manager for Nginx" >&2
    exit 1
  fi
fi

# Disable default inline server block if present
if grep -q '^    server {' /etc/nginx/nginx.conf 2>/dev/null; then
  sed -i '/^    server {$/,/^    }$/s/^/#/' /etc/nginx/nginx.conf
  echo "    Disabled the default inline server block"
fi

# Clean up legacy configuration fragments
rm -f /etc/nginx/conf.d/deeppool_control_web.conf \
      /etc/nginx/conf.d/deeppool_portal_web.conf \
      /etc/nginx/conf.d/deeppool_grpc.conf 2>/dev/null

echo "    Removed legacy DeepPool Nginx fragments"

cat > "$CONF" <<NGINX_EOF
# ============================================================
# DeepPool ingress — TEST (HTTP redirect + HTTPS routing)
# ============================================================

# Redirect all HTTP traffic to HTTPS (both main and API domains)
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

# Main site: portal_web + control_web + API proxy
server {
    listen 443 ssl;
    server_name ${SERVER_NAME};

    ssl_certificate     ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;

    location /api/ {
        proxy_pass ${UPSTREAM_SCHEME}://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /v1/ {
        proxy_pass ${UPSTREAM_SCHEME}://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    location /admin/ {
        alias ${CW_DIR}/;
        index index.html;
        try_files \$uri \$uri/ /admin/index.html;
    }

    location / {
        root ${PW_DIR};
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }
}

# Dedicated API domain: handles cross-origin requests from frontend
# NOTE: CORS headers are set by the Go backend (WithCORS middleware),
# do NOT add them here to avoid duplicate header values.
server {
    listen 443 ssl;
    server_name ${API_SERVER_NAME};

    ssl_certificate     ${CERT_DIR}/fullchain.pem;
    ssl_certificate_key ${CERT_DIR}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;

    location /api/ {
        proxy_pass ${UPSTREAM_SCHEME}://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /v1/ {
        proxy_pass ${UPSTREAM_SCHEME}://127.0.0.1:8080;
        proxy_ssl_verify off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Reject all other paths on the API domain
    location / {
        return 404;
    }
}
NGINX_EOF

echo "    Nginx config written to $CONF"
nginx -t 2>&1 && nginx -s reload 2>/dev/null || systemctl restart nginx
echo "    Nginx reloaded"
NGINX_SCRIPT

echo "    Ingress routes:"
echo "      ${PUBLIC_HOST} /        -> portal_web"
echo "      ${PUBLIC_HOST} /admin/  -> control_web"
echo "      ${PUBLIC_HOST} /api/    -> manager :8080 (${INTERNAL_SCHEME})"
echo "      ${PUBLIC_HOST} /v1/     -> manager :8080 (${INTERNAL_SCHEME})"
echo "      ${API_DOMAIN}  /api/    -> manager :8080 (${INTERNAL_SCHEME}, CORS)"
echo "      ${API_DOMAIN}  /v1/     -> manager :8080 (${INTERNAL_SCHEME}, CORS)"

# ============================================================
# Health checks
# ============================================================
sleep 3
echo ""
echo "==> Remote process status:"
ssh "$REMOTE_HOST" "ps aux | grep -E '$(IFS='|'; echo "${COMPONENTS[*]}")|nginx.*master' | grep -v grep || echo '    no active service process detected'"
echo ""

echo "==> Health checks:"
for comp in "${COMPONENTS[@]}"; do
  case $comp in
    manager)     port=8080 ;;
    scheduler)   port=8081 ;;
    nodemanager) port=8082 ;;
  esac

  result=$(ssh "$REMOTE_HOST" "curl -sf --cacert ${CERT_FILE} https://127.0.0.1:${port}/health 2>/dev/null || curl -sf -k https://127.0.0.1:${port}/health 2>/dev/null || echo 'FAIL'")
  echo "    $comp (:${port}, ${INTERNAL_SCHEME}): $result"
done

portal_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
admin_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/admin/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
api_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/api/v1/public/stats 2>/dev/null || echo 'FAIL'")
echo "    portal_web  (${PUBLIC_SCHEME} :${PUBLIC_PORT} /): $portal_result"
echo "    control_web (${PUBLIC_SCHEME} :${PUBLIC_PORT} /admin/): $admin_result"
echo "    API proxy   (${PUBLIC_SCHEME} :${PUBLIC_PORT} /api/): $api_result"
echo ""

# ============================================================
# Final summary
# ============================================================
echo "==> Test deployment finished"
echo ""
echo "  Public endpoints:"
echo "    Portal:     ${PUBLIC_SCHEME}://${PUBLIC_HOST}/"
echo "    Admin:      ${PUBLIC_SCHEME}://${PUBLIC_HOST}/admin/"
echo "    API:        ${PUBLIC_SCHEME}://${API_DOMAIN}/api/"
echo "    Gateway:    ${PUBLIC_SCHEME}://${API_DOMAIN}/v1/"
echo ""

echo "  Direct service endpoints (${INTERNAL_SCHEME}):"
echo "    manager:     ${INTERNAL_SCHEME}://${PUBLIC_HOST}:8080"
echo "    scheduler:   ${INTERNAL_SCHEME}://${PUBLIC_HOST}:8081"
echo "    nodemanager: ${INTERNAL_SCHEME}://${PUBLIC_HOST}:8082"
echo ""

echo "  gRPC endpoints (TLS):"
echo "    manager:     ${PUBLIC_HOST}:9090"
echo "    scheduler:   ${PUBLIC_HOST}:9091"
echo "    nodemanager: ${PUBLIC_HOST}:9092"
echo ""

echo "  Certificate management:"
echo "    Directory:     ${CERT_DIR}/"
echo "    Renew cron:    daily at 03:00"
echo "    Manual renew:  ssh ${REMOTE_HOST} 'certbot renew'"
echo "    Inspect certs: ssh ${REMOTE_HOST} 'certbot certificates'"
echo ""

echo "  Logs:"
for comp in "${COMPONENTS[@]}"; do
  echo "    ssh $REMOTE_HOST 'tail -f $REMOTE_DIR/${comp}.log'"
done
