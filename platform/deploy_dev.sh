#!/bin/bash
# deploy_dev.sh — build and deploy all platform components to the development server.
#
# Supported ingress modes:
#   - HTTP  (default): best for development servers without an ICP-ready domain/certificate
#   - HTTPS           : requires a resolvable domain and Let's Encrypt certificates
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
REMOTE_HOST="root@101.33.255.185"
REMOTE_DIR="/opt/deeppool"
COMPONENTS=(manager scheduler nodemanager)

CONTROL_WEB_DIR="control_web"
CONTROL_WEB_REMOTE_DIR="$REMOTE_DIR/control_web"
PORTAL_WEB_DIR="portal_web"
PORTAL_WEB_REMOTE_DIR="$REMOTE_DIR/portal_web"
NGINX_CONF="/etc/nginx/conf.d/deeppool.conf"

DEPLOY_MODE_RAW="${DEEPPOOL_DEPLOY_MODE:-http}"
DEPLOY_MODE="$(printf '%s' "$DEPLOY_MODE_RAW" | tr '[:upper:]' '[:lower:]')"
DEPLOY_MODE_DISPLAY="$(printf '%s' "$DEPLOY_MODE" | tr '[:lower:]' '[:upper:]')"
DOMAIN="${DEEPPOOL_DOMAIN:-}"
ADMIN_EMAIL="${DEEPPOOL_ADMIN_EMAIL:-admin@deeppool.tech}"
PUBLIC_HOST="${DEEPPOOL_PUBLIC_HOST:-}"

if [ -z "$PUBLIC_HOST" ]; then
  if [ -n "$DOMAIN" ]; then
    PUBLIC_HOST="$DOMAIN"
  else
    PUBLIC_HOST="${REMOTE_HOST#*@}"
  fi
fi

case "$DEPLOY_MODE" in
  http)
    PUBLIC_SCHEME="http"
    PUBLIC_PORT="80"
    INTERNAL_SCHEME="http"
    TLS_ENABLED="false"
    ;;
  https)
    PUBLIC_SCHEME="https"
    PUBLIC_PORT="443"
    INTERNAL_SCHEME="https"
    TLS_ENABLED="true"
    if [ -z "$DOMAIN" ]; then
      echo "============================================================"
      echo "[ERROR] HTTPS mode requires DEEPPOOL_DOMAIN to be set"
      echo ""
      echo "Examples:"
      echo "  DEEPPOOL_DEPLOY_MODE=https DEEPPOOL_DOMAIN=dev.deeppool.io ./deploy_dev.sh"
      echo ""
      echo "Optional environment variables:"
      echo "  DEEPPOOL_PUBLIC_HOST   Public host shown in the final output"
      echo "  DEEPPOOL_ADMIN_EMAIL   Certificate registration email"
      echo "============================================================"
      exit 1
    fi
    ;;
  *)
    echo "============================================================"
    echo "[ERROR] Unsupported DEEPPOOL_DEPLOY_MODE: $DEPLOY_MODE"
    echo "Allowed values: http, https"
    echo "============================================================"
    exit 1
    ;;
esac

if [ -z "$PUBLIC_HOST" ]; then
  echo "============================================================"
  echo "[ERROR] Unable to determine public host"
  echo "Please set DEEPPOOL_PUBLIC_HOST explicitly"
  echo "============================================================"
  exit 1
fi

CERT_DIR=""
CERT_FILE=""
KEY_FILE=""
if [ "$DEPLOY_MODE" = "https" ]; then
  CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
  CERT_FILE="${CERT_DIR}/fullchain.pem"
  KEY_FILE="${CERT_DIR}/privkey.pem"
fi

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
echo "  DeepPool development deployment"
echo "  Ingress mode: ${DEPLOY_MODE_DISPLAY}"
echo "  Public host:  ${PUBLIC_HOST}"
if [ "$DEPLOY_MODE" = "https" ]; then
  echo "  Domain:       ${DOMAIN}"
  echo "  Cert email:   ${ADMIN_EMAIL}"
fi
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

cp -r "$PLATFORM_DIR/config" "$BUILD_DIR/config"

# ============================================================
# Build control_web
# ============================================================
echo "==> Building control_web (base=/admin/)..."
cd "$PLATFORM_DIR/$CONTROL_WEB_DIR"
npm install --silent
VITE_BASE=/admin/ npm run build
cp -r "$PLATFORM_DIR/$CONTROL_WEB_DIR/dist" "$BUILD_DIR/control_web"
echo "    control_web build completed"
cd "$PLATFORM_DIR"

# ============================================================
# Build portal_web
# ============================================================
echo "==> Building portal_web..."
cd "$PLATFORM_DIR/$PORTAL_WEB_DIR"
npm install --silent
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
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/config $CONTROL_WEB_REMOTE_DIR $PORTAL_WEB_REMOTE_DIR"

scp "${BUILD_DIR}/manager" \
    "${BUILD_DIR}/scheduler" \
    "${BUILD_DIR}/nodemanager" \
    "$REMOTE_HOST:$REMOTE_DIR/"

scp "${BUILD_DIR}/config/"*.yaml \
    "$REMOTE_HOST:$REMOTE_DIR/config/"

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
# Provision HTTPS certificate when needed
# ============================================================
if [ "$DEPLOY_MODE" = "https" ]; then
  echo "==> Installing Certbot and provisioning Let's Encrypt certificate..."
  set +e
  ssh "$REMOTE_HOST" bash -s -- "$DOMAIN" "$ADMIN_EMAIL" "$CERT_FILE" "$KEY_FILE" <<'CERT_SCRIPT'
set -euo pipefail
DOMAIN="$1"
ADMIN_EMAIL="$2"
CERT_FILE="$3"
KEY_FILE="$4"

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
    echo "  2. Inbound port 80 is open"
    echo "  3. ssh ${REMOTE_HOST} 'cat /var/log/letsencrypt/letsencrypt.log'"
    echo "============================================================"
    exit 1
  fi
else
  echo "==> HTTP mode selected, skipping certificate provisioning"
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

  if [ "$TLS_ENABLED" = "true" ]; then
    if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
      echo "    [ERROR] Missing certificate files for $comp"
      exit 1
    fi
    sed -i \
      -e 's/enabled: false/enabled: true/' \
      -e 's/enabled: true/enabled: true/' \
      -e "s|cert_file: \".*\"|cert_file: \"${CERT_FILE}\"|" \
      -e "s|key_file: \".*\"|key_file: \"${KEY_FILE}\"|" \
      "$cfg"
    echo "    $comp TLS enabled"
  else
    sed -i \
      -e 's/enabled: true/enabled: false/' \
      -e 's/enabled: false/enabled: false/' \
      -e 's|cert_file: ".*"|cert_file: ""|' \
      -e 's|key_file: ".*"|key_file: ""|' \
      "$cfg"
    echo "    $comp TLS disabled"
  fi
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
# Configure Nginx ingress
# ============================================================
echo "==> Writing Nginx ingress configuration for ${DEPLOY_MODE_DISPLAY} mode..."
ssh "$REMOTE_HOST" bash -s -- \
  "$CONTROL_WEB_REMOTE_DIR" "$PORTAL_WEB_REMOTE_DIR" "$NGINX_CONF" \
  "$DEPLOY_MODE" "$PUBLIC_HOST" "$INTERNAL_SCHEME" "$CERT_DIR" <<'NGINX_SCRIPT'
set -euo pipefail
CW_DIR="$1"
PW_DIR="$2"
CONF="$3"
DEPLOY_MODE="$4"
SERVER_NAME="$5"
UPSTREAM_SCHEME="$6"
CERT_DIR="${7:-}"

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

if grep -q '^    server {' /etc/nginx/nginx.conf 2>/dev/null; then
  sed -i '/^    server {$/,/^    }$/s/^/#/' /etc/nginx/nginx.conf
  echo "    Disabled the default inline server block"
fi

rm -f /etc/nginx/conf.d/deeppool_control_web.conf \
      /etc/nginx/conf.d/deeppool_portal_web.conf \
      /etc/nginx/conf.d/deeppool_grpc.conf 2>/dev/null

echo "    Removed legacy DeepPool Nginx fragments"

if [ "$DEPLOY_MODE" = "https" ]; then
  cat > "$CONF" <<NGINX_EOF
# ============================================================
# DeepPool ingress - HTTP redirect + HTTPS routing
# ============================================================
server {
    listen 80;
    server_name ${SERVER_NAME};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

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
NGINX_EOF
else
  cat > "$CONF" <<NGINX_EOF
# ============================================================
# DeepPool ingress - HTTP routing only
# ============================================================
server {
    listen 80;
    server_name ${SERVER_NAME};

    location /api/ {
        proxy_pass ${UPSTREAM_SCHEME}://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /v1/ {
        proxy_pass ${UPSTREAM_SCHEME}://127.0.0.1:8080;
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
NGINX_EOF
fi

echo "    Nginx config written to $CONF"
nginx -t 2>&1 && nginx -s reload 2>/dev/null || systemctl restart nginx
echo "    Nginx reloaded"
NGINX_SCRIPT

echo "    Ingress routes:"
echo "      /        -> portal_web"
echo "      /admin/  -> control_web"
echo "      /api/    -> manager :8080 (${INTERNAL_SCHEME})"
echo "      /v1/     -> manager :8080 (${INTERNAL_SCHEME})"

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

  if [ "$INTERNAL_SCHEME" = "https" ]; then
    result=$(ssh "$REMOTE_HOST" "curl -sf --cacert ${CERT_FILE} https://127.0.0.1:${port}/health 2>/dev/null || curl -sf -k https://127.0.0.1:${port}/health 2>/dev/null || echo 'FAIL'")
  else
    result=$(ssh "$REMOTE_HOST" "curl -sf http://127.0.0.1:${port}/health 2>/dev/null || echo 'FAIL'")
  fi
  echo "    $comp (:${port}, ${INTERNAL_SCHEME}): $result"
done

if [ "$PUBLIC_SCHEME" = "https" ]; then
  portal_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
  admin_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/admin/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
  api_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/api/v1/public/stats 2>/dev/null || echo 'FAIL'")
else
  portal_result=$(ssh "$REMOTE_HOST" "curl -sf http://127.0.0.1/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
  admin_result=$(ssh "$REMOTE_HOST" "curl -sf http://127.0.0.1/admin/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
  api_result=$(ssh "$REMOTE_HOST" "curl -sf http://127.0.0.1/api/v1/public/stats 2>/dev/null || echo 'FAIL'")
fi
echo "    portal_web  (${PUBLIC_SCHEME} :${PUBLIC_PORT} /): $portal_result"
echo "    control_web (${PUBLIC_SCHEME} :${PUBLIC_PORT} /admin/): $admin_result"
echo "    API proxy   (${PUBLIC_SCHEME} :${PUBLIC_PORT} /api/): $api_result"
echo ""

# ============================================================
# Final summary
# ============================================================
echo "==> Deployment finished"
echo ""
echo "  Public endpoints:"
echo "    Portal:     ${PUBLIC_SCHEME}://${PUBLIC_HOST}/"
echo "    Admin:      ${PUBLIC_SCHEME}://${PUBLIC_HOST}/admin/"
echo "    API:        ${PUBLIC_SCHEME}://${PUBLIC_HOST}/api/"
echo "    Gateway:    ${PUBLIC_SCHEME}://${PUBLIC_HOST}/v1/"
echo ""

echo "  Direct service endpoints (${INTERNAL_SCHEME}):"
echo "    manager:     ${INTERNAL_SCHEME}://${PUBLIC_HOST}:8080"
echo "    scheduler:   ${INTERNAL_SCHEME}://${PUBLIC_HOST}:8081"
echo "    nodemanager: ${INTERNAL_SCHEME}://${PUBLIC_HOST}:8082"
echo ""

if [ "$DEPLOY_MODE" = "https" ]; then
  echo "  gRPC endpoints (TLS):"
else
  echo "  gRPC endpoints (plaintext):"
fi
echo "    manager:     ${PUBLIC_HOST}:9090"
echo "    scheduler:   ${PUBLIC_HOST}:9091"
echo "    nodemanager: ${PUBLIC_HOST}:9092"
echo ""

if [ "$DEPLOY_MODE" = "https" ]; then
  echo "  Certificate management:"
  echo "    Directory:     ${CERT_DIR}/"
  echo "    Renew cron:    daily at 03:00"
  echo "    Manual renew:  ssh ${REMOTE_HOST} 'certbot renew'"
  echo "    Inspect certs: ssh ${REMOTE_HOST} 'certbot certificates'"
  echo ""
else
  echo "  Certificate management: skipped in HTTP mode"
  echo ""
fi

echo "  Logs:"
for comp in "${COMPONENTS[@]}"; do
  echo "    ssh $REMOTE_HOST 'tail -f $REMOTE_DIR/${comp}.log'"
done
