#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# release.sh — Build & publish DeepNode to GitHub Release
#
# This script automates the full release workflow:
#   1. Build platform-specific artifact (calls build_standalone_mac.sh etc.)
#   2. Validate build artifacts exist
#   3. Generate install.sh (curl one-liner installer)
#   4. Push README.md + install.sh to GitHub repo
#   5. Create GitHub Release and upload tar.gz assets
#
# Prerequisites:
#   - gh (GitHub CLI) installed and authenticated
#   - Python venv at project root (env/)
#   - Node.js + npm for Vue frontend build
#
# Usage:
#   cd clients/deepnode && bash release.sh [options]
#
# Options:
#   --os mac|linux         Target OS (default: mac; linux planned)
#   --os-version VERSION   Target OS version, e.g. 26, 15 (macOS major)
#   --build-profile PROF   Build profile: dev|prod (default: prod)
#   --binary-only          Pass --binary-only to build script
#   --skip-build           Skip build step, use existing artifacts
#   --skip-push            Skip git push (only create release)
#   --dry-run              Validate everything without building/pushing/releasing
#   --force                Overwrite existing release tag
#   -h, --help             Show help
# ──────────────────────────────────────────────────────────

set -euo pipefail

# ─── Constants ───────────────────────────────────────────
GITHUB_REPO="BiyoTech/deepnode"
GITHUB_REMOTE="git@github.com:${GITHUB_REPO}.git"

# ─── Color helpers ───────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── Defaults ────────────────────────────────────────────
TARGET_OS="mac"
TARGET_OS_VERSION=""
BUILD_PROFILE="prod"
BINARY_ONLY=false
SKIP_BUILD=false
SKIP_PUSH=false
DRY_RUN=false
FORCE=false

# ─── Parse arguments ────────────────────────────────────
show_help() {
    cat << 'EOF'
Usage:
  cd clients/deepnode && bash release.sh [options]

Options:
  --os mac|linux         Target operating system (default: mac)
                         Currently supported: mac
                         Planned: linux
  --os-version VERSION   Target OS version (macOS major version, e.g. 26, 15)
                         Passed to build script as --target-os
                         If omitted, auto-detects from current system
  --build-profile PROF   Build profile: dev | prod (default: prod)
  --binary-only          Pass --binary-only to build script (single binary mode)
  --skip-build           Skip the build step; use existing artifacts in dist/
  --skip-push            Skip git push, only create GitHub Release
  --dry-run              Validate everything without building, pushing, or releasing
  --force                Overwrite existing release tag
  -h, --help             Show this help message

Environment Variables:
  GITHUB_TOKEN                GitHub personal access token (alternative to gh auth login)
  DEEPNODE_CODESIGN_IDENTITY  Code signing identity for macOS build

Examples:
  # Full release: build for current macOS + publish
  bash release.sh

  # Build for macOS 26 and release
  bash release.sh --os mac --os-version 26

  # Build for macOS 15 in dev profile
  bash release.sh --os mac --os-version 15 --build-profile dev

  # Skip build, just publish existing artifacts
  bash release.sh --skip-build

  # Dry run (validate only)
  bash release.sh --dry-run

  # Force overwrite existing release
  bash release.sh --force
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) show_help ;;
        --os)
            shift
            [[ $# -eq 0 ]] && error "--os requires a value (mac or linux)"
            TARGET_OS="$1"
            ;;
        --os-version)
            shift
            [[ $# -eq 0 ]] && error "--os-version requires a version number (e.g. 26, 15)"
            TARGET_OS_VERSION="$1"
            ;;
        --build-profile)
            shift
            [[ $# -eq 0 ]] && error "--build-profile requires a value (dev or prod)"
            BUILD_PROFILE="$1"
            ;;
        --binary-only) BINARY_ONLY=true ;;
        --skip-build)  SKIP_BUILD=true ;;
        --skip-push)   SKIP_PUSH=true ;;
        --dry-run)     DRY_RUN=true ;;
        --force)       FORCE=true ;;
        *) error "Unknown option: $1. Use --help for usage." ;;
    esac
    shift
done

# Validate --os
case "$TARGET_OS" in
    mac) ;;
    linux) error "Linux builds are not yet supported. Coming soon." ;;
    *) error "Unsupported --os value: '$TARGET_OS'. Supported: mac" ;;
esac

# Validate --build-profile
if [[ "$BUILD_PROFILE" != "dev" && "$BUILD_PROFILE" != "prod" ]]; then
    error "--build-profile must be 'dev' or 'prod', got '$BUILD_PROFILE'"
fi

# ─── Resolve paths ───────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$SCRIPT_DIR/localserver/dist"
VERSION_FILE="$SCRIPT_DIR/VERSION"

# ─── Step 0: Pre-flight checks ──────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  DeepNode Release Publisher"
echo "═══════════════════════════════════════════════════"
echo ""

# Check VERSION file
if [[ ! -f "$VERSION_FILE" ]]; then
    error "VERSION file not found at $VERSION_FILE"
fi
APP_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [[ ! "$APP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    error "Invalid version format '$APP_VERSION' in $VERSION_FILE (expected: X.Y.Z)"
fi
TAG_NAME="v${APP_VERSION}"

info "Version:       $TAG_NAME"
info "Target OS:     $TARGET_OS"
info "OS Version:    ${TARGET_OS_VERSION:-auto-detect}"
info "Build Profile: $BUILD_PROFILE"
info "Binary-only:   $BINARY_ONLY"
info "Skip Build:    $SKIP_BUILD"

# Check gh CLI
if ! command -v gh &>/dev/null; then
    error "GitHub CLI (gh) not found. Install with: brew install gh"
fi

if ! gh auth status &>/dev/null; then
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        info "Authenticating with GITHUB_TOKEN..."
        echo "$GITHUB_TOKEN" | gh auth login --with-token
    else
        error "Not logged in to GitHub CLI. Run: gh auth login"
    fi
fi
ok "GitHub CLI authenticated"

if $DRY_RUN && $SKIP_BUILD; then
    ok "Dry run passed — all pre-flight checks OK."
    exit 0
fi

# ─── Step 1: Build ───────────────────────────────────────
if ! $SKIP_BUILD; then
    echo ""
    info "Step 1/4: Building artifact ..."

    BUILD_ARGS=("--profile" "$BUILD_PROFILE")

    if [[ -n "$TARGET_OS_VERSION" ]]; then
        BUILD_ARGS+=("--target-os" "$TARGET_OS_VERSION")
    fi

    if $BINARY_ONLY; then
        BUILD_ARGS+=("--binary-only")
    fi

    case "$TARGET_OS" in
        mac)
            BUILD_SCRIPT="$SCRIPT_DIR/build_standalone_mac.sh"
            if [[ ! -f "$BUILD_SCRIPT" ]]; then
                error "Build script not found: $BUILD_SCRIPT"
            fi
            info "Running: bash build_standalone_mac.sh ${BUILD_ARGS[*]}"
            bash "$BUILD_SCRIPT" "${BUILD_ARGS[@]}"
            ;;
    esac

    ok "Build completed"
else
    info "Step 1/4: Skipped (--skip-build)"
fi

if $DRY_RUN; then
    echo ""
    ok "Dry run: build completed. Remove --dry-run to publish."
    exit 0
fi

# ─── Step 2: Validate artifacts ──────────────────────────
echo ""
info "Step 2/4: Validating artifacts ..."

ARTIFACTS=()
if [[ -d "$DIST_DIR" ]]; then
    while IFS= read -r -d '' f; do
        ARTIFACTS+=("$f")
    done < <(find "$DIST_DIR" -maxdepth 1 -name "deepnode-${TAG_NAME}-*.tar.gz" -print0 | sort -z)
fi

if [[ ${#ARTIFACTS[@]} -eq 0 ]]; then
    error "No artifacts found matching 'deepnode-${TAG_NAME}-*.tar.gz' in $DIST_DIR
Please run build_standalone_mac.sh first, or omit --skip-build."
fi

info "Found ${#ARTIFACTS[@]} artifact(s):"
for a in "${ARTIFACTS[@]}"; do
    SIZE=$(du -h "$a" | cut -f1)
    echo "  - $(basename "$a")  ($SIZE)"
done

# Check README
README_SRC="$DIST_DIR/deepnode-server/README.md"
if [[ ! -f "$README_SRC" ]]; then
    README_SRC="$SCRIPT_DIR/README_STANDALONE.md"
fi
if [[ ! -f "$README_SRC" ]]; then
    error "README not found at $DIST_DIR/deepnode-server/README.md or $SCRIPT_DIR/README_STANDALONE.md"
fi
ok "README: $README_SRC"

# ─── Step 3: Generate install.sh + push to GitHub ───────
echo ""
info "Step 3/4: Generating install.sh ..."

INSTALL_SCRIPT="$SCRIPT_DIR/_release_tmp/install.sh"
mkdir -p "$(dirname "$INSTALL_SCRIPT")"

cat > "$INSTALL_SCRIPT" << 'INSTALL_EOF'
#!/usr/bin/env bash
# DeepNode Server - One-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/BiyoTech/deepnode/main/install.sh | bash
#
# Environment variables:
#   DEEPNODE_INSTALL_DIR  — installation directory (default: ~/deepnode-server)
#   DEEPNODE_VERSION      — version to install (default: latest)

set -euo pipefail

# ─── Constants ───────────────────────────────────────────────────────────────
REPO="BiyoTech/deepnode"
DEFAULT_INSTALL_DIR="$HOME/deepnode-server"

# ─── Color helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── Pre-flight checks ──────────────────────────────────────────────────────
check_os() {
    local os
    os="$(uname -s)"
    if [[ "$os" != "Darwin" ]]; then
        error "DeepNode currently only supports macOS. Detected OS: $os"
    fi
    ok "Operating system: macOS"
}

check_arch() {
    ARCH="$(uname -m)"
    if [[ "$ARCH" != "arm64" && "$ARCH" != "x86_64" ]]; then
        error "Unsupported architecture: $ARCH. DeepNode requires arm64 or x86_64."
    fi
    ok "Architecture: $ARCH"
}

check_macos_version() {
    local version
    version="$(sw_vers -productVersion)"
    local major
    major="$(echo "$version" | cut -d. -f1)"

    # Determine the Metal-compatible macOS major version for asset matching
    MACOS_MAJOR="$major"
    ok "macOS version: $version (target: macOS $MACOS_MAJOR)"
}

check_commands() {
    for cmd in curl tar; do
        if ! command -v "$cmd" &>/dev/null; then
            error "Required command '$cmd' not found. Please install it first."
        fi
    done
}

# ─── Resolve version & download URL ─────────────────────────────────────────
resolve_download_url() {
    local version="${DEEPNODE_VERSION:-latest}"
    local api_url

    if [[ "$version" == "latest" ]]; then
        api_url="https://api.github.com/repos/${REPO}/releases/latest"
    else
        [[ "$version" != v* ]] && version="v${version}"
        api_url="https://api.github.com/repos/${REPO}/releases/tags/${version}"
    fi

    info "Fetching release info from: $api_url"

    local release_json
    release_json="$(curl -fsSL "$api_url" 2>/dev/null)" \
        || error "Failed to fetch release info. Check your network and the version tag."

    TAG_NAME="$(echo "$release_json" | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"\([^"]*\)".*/\1/')"
    if [[ -z "$TAG_NAME" ]]; then
        error "Could not parse release tag from API response."
    fi

    # Build expected asset name: deepnode-<version>-macos<major>-<arch>.tar.gz
    local asset_pattern="deepnode-${TAG_NAME}-macos${MACOS_MAJOR}-${ARCH}.tar.gz"
    info "Looking for asset: $asset_pattern"

    DOWNLOAD_URL="$(echo "$release_json" | grep '"browser_download_url"' | grep "$asset_pattern" | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')"

    if [[ -z "$DOWNLOAD_URL" ]]; then
        # Fallback: try any available macOS build for this arch
        local fallback_pattern="deepnode-${TAG_NAME}-macos.*-${ARCH}.tar.gz"
        warn "Exact macOS $MACOS_MAJOR build not found, searching for any compatible build..."
        DOWNLOAD_URL="$(echo "$release_json" | grep '"browser_download_url"' | grep -E "$fallback_pattern" | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')"
    fi

    if [[ -z "$DOWNLOAD_URL" ]]; then
        error "No compatible asset found for macOS ${MACOS_MAJOR} ${ARCH} in release ${TAG_NAME}.
Available assets:
$(echo "$release_json" | grep '"browser_download_url"' | sed 's/.*"browser_download_url": *"\([^"]*\)".*/  \1/')"
    fi

    ok "Found asset: $DOWNLOAD_URL"
}

# ─── Download & install ──────────────────────────────────────────────────────
download_and_install() {
    local install_dir="${DEEPNODE_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT

    local tar_file="${tmp_dir}/deepnode.tar.gz"

    info "Downloading DeepNode ${TAG_NAME} ..."
    curl -fSL --progress-bar -o "$tar_file" "$DOWNLOAD_URL" \
        || error "Download failed. Please check your network connection."

    info "Extracting to $install_dir ..."
    if [[ -d "$install_dir" ]]; then
        warn "Existing installation found at $install_dir — backing up to ${install_dir}.bak"
        rm -rf "${install_dir}.bak"
        mv "$install_dir" "${install_dir}.bak"
    fi

    mkdir -p "$install_dir"
    tar xzf "$tar_file" -C "$install_dir" --strip-components=1

    # Remove macOS quarantine attribute
    info "Removing macOS quarantine attribute ..."
    xattr -rd com.apple.quarantine "$install_dir" 2>/dev/null || true

    ok "Installed to: $install_dir"
}

# ─── Post-install instructions ────────────────────────────────────────────────
print_instructions() {
    local install_dir="${DEEPNODE_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║        DeepNode ${TAG_NAME} installed successfully!        ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Quick start:"
    echo ""
    echo "    cd $install_dir"
    echo ""
    echo "    # Start as background daemon (recommended)"
    echo "    ./deepnode-server --start"
    echo ""
    echo "    # Or run in foreground (see logs directly)"
    echo "    ./deepnode-server"
    echo ""
    echo "  After starting, open Web UI: http://127.0.0.1:8765/"
    echo "  Log in with your DeepPool account to complete device setup."
    echo ""
    echo "  Other commands:"
    echo "    ./deepnode-server --status    # Check running status"
    echo "    ./deepnode-server --log -f    # View logs (follow mode)"
    echo "    ./deepnode-server --stop      # Stop the service"
    echo ""
    echo "  Need help? Email: contact@deeppool.tech"
    echo ""
    echo "  For more details, see:"
    echo "    https://github.com/${REPO}#readme"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────
main() {
    echo ""
    info "DeepNode Server Installer"
    echo ""

    check_os
    check_arch
    check_macos_version
    check_commands
    resolve_download_url
    download_and_install
    print_instructions
}

main "$@"
INSTALL_EOF

chmod +x "$INSTALL_SCRIPT"
ok "Generated install.sh"

# Push README + install.sh to GitHub
if ! $SKIP_PUSH; then
    echo ""
    info "Pushing README + install.sh to GitHub ..."

    WORK_DIR="$SCRIPT_DIR/_release_tmp/repo"
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"

    if gh repo view "$GITHUB_REPO" --json name &>/dev/null; then
        info "Cloning existing repo ..."
        git clone --depth=1 "$GITHUB_REMOTE" "$WORK_DIR" 2>/dev/null || {
            cd "$WORK_DIR"
            git init
            git remote add origin "$GITHUB_REMOTE"
            git checkout -b main
        }
    else
        info "Initializing new repo ..."
        cd "$WORK_DIR"
        git init
        git remote add origin "$GITHUB_REMOTE"
        git checkout -b main
    fi

    cd "$WORK_DIR"
    cp "$README_SRC" "$WORK_DIR/README.md"
    cp "$INSTALL_SCRIPT" "$WORK_DIR/install.sh"

    git add README.md install.sh
    if git diff --cached --quiet 2>/dev/null; then
        ok "No changes to push (files already up to date)"
    else
        git commit -m "release: update README and install.sh for ${TAG_NAME}"
        git push origin main
        ok "Pushed README.md + install.sh to GitHub"
    fi
else
    info "Skipped git push (--skip-push)"
fi

# ─── Step 4: Create GitHub Release ──────────────────────
echo ""
info "Step 4/4: Creating GitHub Release ${TAG_NAME} ..."

# Build release notes
RELEASE_NOTES="## DeepNode ${TAG_NAME}

### Assets

| File | Platform | Architecture |
|------|----------|-------------|"

for a in "${ARTIFACTS[@]}"; do
    BASENAME="$(basename "$a")"
    PLATFORM="$(echo "$BASENAME" | sed 's/.*-\(macos[0-9]*\)-.*/\1/')"
    ASSET_ARCH="$(echo "$BASENAME" | sed 's/.*-\([a-z0-9_]*\)\.tar\.gz/\1/')"
    RELEASE_NOTES="${RELEASE_NOTES}
| \`${BASENAME}\` | ${PLATFORM} | ${ASSET_ARCH} |"
done

RELEASE_NOTES="${RELEASE_NOTES}

### Quick Install

\`\`\`bash
curl -fsSL https://raw.githubusercontent.com/${GITHUB_REPO}/main/install.sh | bash
\`\`\`

### Manual Install

\`\`\`bash
# Download
curl -fSL -o deepnode.tar.gz <asset_url>

# Extract and start
tar xzf deepnode.tar.gz && cd deepnode-server
xattr -rd com.apple.quarantine .
./deepnode-server --start
\`\`\`

Open http://127.0.0.1:8765/ and log in with your DeepPool account.
Don't have an account? Register at https://deeppool.tech/register

### Need Help?

Email: contact@deeppool.tech
"

# Build gh release command
GH_ARGS=(
    "release" "create" "$TAG_NAME"
    "--repo" "$GITHUB_REPO"
    "--title" "DeepNode ${TAG_NAME}"
    "--notes" "$RELEASE_NOTES"
)

if $FORCE; then
    gh release delete "$TAG_NAME" --repo "$GITHUB_REPO" --yes 2>/dev/null || true
    git push origin --delete "$TAG_NAME" 2>/dev/null || true
fi

for a in "${ARTIFACTS[@]}"; do
    GH_ARGS+=("$a")
done

info "Uploading ${#ARTIFACTS[@]} artifact(s) — this may take a while for large files ..."
gh "${GH_ARGS[@]}"

ok "Release ${TAG_NAME} created successfully!"

# ─── Cleanup ────────────────────────────────────────────
rm -rf "$SCRIPT_DIR/_release_tmp"

# ─── Summary ────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Release ${TAG_NAME} published!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  GitHub Release:"
echo "    https://github.com/${GITHUB_REPO}/releases/tag/${TAG_NAME}"
echo ""
echo "  User install command:"
echo "    curl -fsSL https://raw.githubusercontent.com/${GITHUB_REPO}/main/install.sh | bash"
echo ""
echo "  Install specific version:"
echo "    DEEPNODE_VERSION=${APP_VERSION} curl -fsSL https://raw.githubusercontent.com/${GITHUB_REPO}/main/install.sh | bash"
echo ""
