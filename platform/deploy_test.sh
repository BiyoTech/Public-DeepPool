#!/bin/bash
# deploy_test.sh — build and deploy platform components to the test server.
#
# HTTPS is mandatory for testing; there is no HTTP-only mode.
#
# Usage:
#   DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh                         # deploy all components
#   DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh experiment              # deploy only experiment
#   DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh manager experiment      # deploy specific backend services
#   DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh portal_web              # deploy only portal frontend
#   DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh portal_web control_web  # deploy both frontends
#   DEEPPOOL_DOMAIN=test.deeppool.tech ./deploy_test.sh manager portal_web      # mix backend + frontend
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

# All deployable components: backend services + frontend web apps
ALL_BACKEND=(manager scheduler nodemanager experiment)
ALL_WEB=(portal_web control_web)
ALL_COMPONENTS=("${ALL_BACKEND[@]}" "${ALL_WEB[@]}")

# Bash 3.x compatible port lookup (macOS ships with bash 3.2, no associative arrays)
# Returns "http:<port>" for HTTP services, "grpc:<port>" for gRPC-only services.
get_component_port() {
  case "$1" in
    manager)     echo "http:8080" ;;
    scheduler)   echo "http:8081" ;;
    nodemanager) echo "http:8082" ;;
    experiment)  echo "grpc:9093" ;;
    *) echo "http:0" ;;
  esac
}

# Determine which components to deploy: from CLI args or all
DEPLOY_PORTAL_WEB=false
DEPLOY_CONTROL_WEB=false
COMPONENTS=()  # backend components to build/deploy

if [ $# -gt 0 ]; then
  for arg in "$@"; do
    if [ "$arg" = "portal_web" ]; then
      DEPLOY_PORTAL_WEB=true
    elif [ "$arg" = "control_web" ]; then
      DEPLOY_CONTROL_WEB=true
    elif [[ " ${ALL_BACKEND[*]} " =~ " ${arg} " ]]; then
      COMPONENTS+=("$arg")
    else
      echo "[ERROR] Unknown component: ${arg}"
      echo "  Available: ${ALL_COMPONENTS[*]}"
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
CONTROL_WEB_REMOTE_DIR="$REMOTE_DIR/control_web"
PORTAL_WEB_DIR="portal_web"
PORTAL_WEB_REMOTE_DIR="$REMOTE_DIR/portal_web"
NGINX_CONF="/etc/nginx/conf.d/deeppool.conf"

# Test always uses HTTPS — TLS config is hardcoded in config_test/*.yaml
DEPLOY_MODE="https"
DEPLOY_MODE_DISPLAY="HTTPS"
PUBLIC_SCHEME="https"
PUBLIC_PORT="443"
INTERNAL_SCHEME="https"

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
if [ ${#COMPONENTS[@]} -gt 0 ]; then
echo "  Backend:      ${COMPONENTS[*]}"
fi
echo "  portal_web:   ${DEPLOY_PORTAL_WEB}"
echo "  control_web:  ${DEPLOY_CONTROL_WEB}"
if [ "$PARTIAL_DEPLOY" = true ]; then
echo "  Mode:         PARTIAL"
fi
echo "============================================================"
echo ""

# ============================================================
# Build Go components
# ============================================================
echo "==> Cleaning previous build artifacts..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

if [ ${#COMPONENTS[@]} -gt 0 ]; then
echo "==> Cross compiling Go services (GOOS=$GOOS GOARCH=$GOARCH)..."
cd "$PLATFORM_DIR"
for comp in "${COMPONENTS[@]}"; do
  echo "    Building $comp ..."
  go build -trimpath -ldflags="-s -w" -o "$BUILD_DIR/$comp" "./cmd/$comp"
done
echo "    Go services built successfully"
fi

cp -r "$PLATFORM_DIR/config_test" "$BUILD_DIR/config"

if [ "$DEPLOY_CONTROL_WEB" = true ]; then
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
fi

if [ "$DEPLOY_PORTAL_WEB" = true ]; then
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
fi

echo "==> Build artifacts summary:"
if [ ${#COMPONENTS[@]} -gt 0 ]; then
for comp in "${COMPONENTS[@]}"; do
  ls -lh "$BUILD_DIR/$comp"
done
fi
if [ "$DEPLOY_CONTROL_WEB" = true ]; then
echo "    control_web: $(du -sh "$BUILD_DIR/control_web" | awk '{print $1}')"
fi
if [ "$DEPLOY_PORTAL_WEB" = true ]; then
echo "    portal_web:  $(du -sh "$BUILD_DIR/portal_web" | awk '{print $1}')"
fi
echo ""

# ============================================================
# Stop previous services (only the backend ones being deployed)
# ============================================================
if [ ${#COMPONENTS[@]} -gt 0 ]; then
echo "==> Stopping existing remote services (${COMPONENTS[*]})..."
COMP_LIST=$(IFS=' '; echo "${COMPONENTS[*]}")
ssh "$REMOTE_HOST" bash -s -- "$REMOTE_DIR" "$COMP_LIST" <<'STOP_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
shift
COMP_LIST="$*"

for comp in $COMP_LIST; do
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
for comp in $COMP_LIST; do
  pid=$(ps -eo pid,args | grep -E "(\./${comp}|${REMOTE_DIR}/${comp})" | grep -v -E "grep|bash|scp" | awk '{print $1}' || true)
  if [ -n "$pid" ]; then
    kill -9 "$pid" 2>/dev/null || true
    echo "    Force killed $comp (pid=$pid)"
  fi
done

sleep 1
for comp in $COMP_LIST; do
  rm -f "${REMOTE_DIR}/${comp}"
done
echo "    Previous binaries removed"
STOP_SCRIPT
fi  # end of backend stop guard

# ============================================================
# Upload files
# ============================================================
echo "==> Uploading artifacts to $REMOTE_HOST:$REMOTE_DIR ..."
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/config"

# Upload Go binaries (only the deployed backend components)
if [ ${#COMPONENTS[@]} -gt 0 ]; then
for comp in "${COMPONENTS[@]}"; do
  scp "${BUILD_DIR}/${comp}" "$REMOTE_HOST:$REMOTE_DIR/"
done
fi

scp "${BUILD_DIR}/config/"*.yaml \
    "$REMOTE_HOST:$REMOTE_DIR/config/"

if [ "$PARTIAL_DEPLOY" = false ]; then
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/alipay_cert $REMOTE_DIR/wechat_pay_cert $CONTROL_WEB_REMOTE_DIR $PORTAL_WEB_REMOTE_DIR"

# Upload payment certificate files
scp "${PLATFORM_DIR}/alipay_cert/"*.pem \
    "$REMOTE_HOST:$REMOTE_DIR/alipay_cert/"
scp "${PLATFORM_DIR}/wechat_pay_cert/"* \
    "$REMOTE_HOST:$REMOTE_DIR/wechat_pay_cert/"
fi

if [ "$DEPLOY_CONTROL_WEB" = true ]; then
ssh "$REMOTE_HOST" "mkdir -p $CONTROL_WEB_REMOTE_DIR"
ssh "$REMOTE_HOST" "rm -rf $CONTROL_WEB_REMOTE_DIR/*"
scp -r "${BUILD_DIR}/control_web/"* "$REMOTE_HOST:$CONTROL_WEB_REMOTE_DIR/"
echo "    control_web uploaded"
fi

if [ "$DEPLOY_PORTAL_WEB" = true ]; then
ssh "$REMOTE_HOST" "mkdir -p $PORTAL_WEB_REMOTE_DIR"
ssh "$REMOTE_HOST" "rm -rf $PORTAL_WEB_REMOTE_DIR/*"
scp -r "${BUILD_DIR}/portal_web/"* "$REMOTE_HOST:$PORTAL_WEB_REMOTE_DIR/"
echo "    portal_web uploaded"
fi

# Set executable permissions for deployed backend components
if [ ${#COMPONENTS[@]} -gt 0 ]; then
CHMOD_LIST=""
for comp in "${COMPONENTS[@]}"; do
  CHMOD_LIST="$CHMOD_LIST $REMOTE_DIR/$comp"
done
ssh "$REMOTE_HOST" "chmod +x $CHMOD_LIST"
fi

echo "==> Upload completed"
echo ""
echo "Remote tree:"
ssh "$REMOTE_HOST" "tree $REMOTE_DIR 2>/dev/null || find $REMOTE_DIR -type f | sort"
echo ""

if [ "$PARTIAL_DEPLOY" = false ]; then
# ============================================================
# Provision HTTPS certificate (skipped in partial deploy)
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
fi  # end of PARTIAL_DEPLOY=false guard (cert provisioning)

# ============================================================
# Start services (only the deployed backend components)
# ============================================================
if [ ${#COMPONENTS[@]} -gt 0 ]; then
COMP_LIST=$(IFS=' '; echo "${COMPONENTS[*]}")
echo "==> Starting services (${COMPONENTS[*]})..."
ssh "$REMOTE_HOST" bash -s -- "$REMOTE_DIR" "$COMP_LIST" <<'START_SCRIPT'
set -euo pipefail
REMOTE_DIR="$1"
shift
COMP_LIST="$*"
cd "$REMOTE_DIR"

for comp in $COMP_LIST; do
  nohup "${REMOTE_DIR}/${comp}" > "${REMOTE_DIR}/${comp}.log" 2>&1 &
  echo "    Started $comp pid=$!"
done
START_SCRIPT
for comp in "${COMPONENTS[@]}"; do
  echo "    Log file: $REMOTE_DIR/${comp}.log"
done
fi

if [ "$PARTIAL_DEPLOY" = false ]; then
# ============================================================
# Configure Nginx ingress (HTTPS only, skipped in partial deploy)
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
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
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
fi  # end of PARTIAL_DEPLOY=false guard (cert + nginx)

# ============================================================
# Health checks
# ============================================================
sleep 3
echo ""
echo "==> Remote process status:"
if [ ${#COMPONENTS[@]} -gt 0 ]; then
ssh "$REMOTE_HOST" "ps aux | grep -E '$(IFS='|'; echo "${COMPONENTS[*]}")|nginx.*master' | grep -v grep || echo '    no active service process detected'"
else
ssh "$REMOTE_HOST" "ps aux | grep -E 'nginx.*master' | grep -v grep || echo '    no active service process detected'"
fi
echo ""

if [ ${#COMPONENTS[@]} -gt 0 ]; then
echo "==> Health checks:"
for comp in "${COMPONENTS[@]}"; do
  port_info=$(get_component_port "$comp")
  proto="${port_info%%:*}"
  port="${port_info##*:}"
  if [ "$proto" = "grpc" ]; then
    result=$(ssh "$REMOTE_HOST" "ss -tlnp 'sport = :${port}' 2>/dev/null | grep -q LISTEN && echo '{\"status\":\"ok\",\"service\":\"${comp}\",\"proto\":\"grpc\"}' || echo 'FAIL (port ${port} not listening)'")
    echo "    $comp (:${port}, gRPC): $result"
  else
    result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1:${port}/health 2>/dev/null || echo 'FAIL'")
    echo "    $comp (:${port}, ${INTERNAL_SCHEME}): $result"
  fi
done
fi

if [ "$DEPLOY_PORTAL_WEB" = true ] || [ "$DEPLOY_CONTROL_WEB" = true ]; then
if [ "$DEPLOY_PORTAL_WEB" = true ]; then
portal_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
echo "    portal_web  (${PUBLIC_SCHEME} :${PUBLIC_PORT} /): $portal_result"
fi
if [ "$DEPLOY_CONTROL_WEB" = true ]; then
admin_result=$(ssh "$REMOTE_HOST" "curl -sf -k https://127.0.0.1/admin/ 2>/dev/null | head -c 50 && echo '... OK' || echo 'FAIL'")
echo "    control_web (${PUBLIC_SCHEME} :${PUBLIC_PORT} /admin/): $admin_result"
fi
fi
echo ""

# ============================================================
# Final summary
# ============================================================
DEPLOYED_ITEMS=""
if [ ${#COMPONENTS[@]} -gt 0 ]; then DEPLOYED_ITEMS="${COMPONENTS[*]}"; fi
if [ "$DEPLOY_PORTAL_WEB" = true ]; then DEPLOYED_ITEMS="$DEPLOYED_ITEMS portal_web"; fi
if [ "$DEPLOY_CONTROL_WEB" = true ]; then DEPLOYED_ITEMS="$DEPLOYED_ITEMS control_web"; fi

echo "==> Test deployment finished ($DEPLOYED_ITEMS)"
echo ""
if [ ${#COMPONENTS[@]} -gt 0 ]; then
echo "  Deployed service endpoints:"
for comp in "${COMPONENTS[@]}"; do
  port_info=$(get_component_port "$comp")
  proto="${port_info%%:*}"
  port="${port_info##*:}"
  if [ "$proto" = "grpc" ]; then
    echo "    ${comp}: grpc://${PUBLIC_HOST}:${port}"
  else
    echo "    ${comp}: ${INTERNAL_SCHEME}://${PUBLIC_HOST}:${port}"
  fi
done
echo ""

echo "  Logs:"
for comp in "${COMPONENTS[@]}"; do
  echo "    ssh $REMOTE_HOST 'tail -f $REMOTE_DIR/${comp}.log'"
done
fi
