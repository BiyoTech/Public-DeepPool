#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# release.sh — Publish DeepNode to GitHub Release
#
# This script automates the full release workflow:
#   1. Validate build artifacts exist
#   2. Generate install.sh (curl one-liner installer)
#   3. Push README.md + install.sh to GitHub repo
#   4. Create GitHub Release and upload tar.gz assets
#
# Prerequisites:
#   - gh (GitHub CLI) installed and authenticated
#   - Build artifacts in localserver/dist/
#   - Run build_standalone.sh first to produce tar.gz
#
# Usage:
#   cd clients/deepnode && bash release.sh [options]
#
# Options:
#   -h, --help      Show help
#   --dry-run       Validate everything without pushing/releasing
#   --skip-push     Skip git push (only create release)
#   --force         Overwrite existing release tag
# ──────────────────────────────────────────────────────────

set -euo pipefail

# ─── Constants ───────────────────────────────────────────
GITHUB_REPO="BiyoTech/deepnode"
GITHUB_REMOTE="git@github.com:${GITHUB_REPO}.git"
MIN_MACOS_VERSION="13.5"

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

# ─── Parse arguments ────────────────────────────────────
DRY_RUN=false
SKIP_PUSH=false
FORCE=false

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            cat << 'EOF'
Usage:
  cd clients/deepnode && bash release.sh [options]

Options:
  -h, --help      Show this help message
  --dry-run       Validate everything without pushing or releasing
  --skip-push     Skip git push, only create GitHub Release
  --force         Overwrite existing release tag

Environment Variables:
  GITHUB_TOKEN    GitHub personal access token (alternative to gh auth login)

Workflow:
  1. Reads version from VERSION file
  2. Finds all tar.gz artifacts in localserver/dist/
  3. Generates install.sh for curl one-liner installation
  4. Pushes README.md + install.sh to GitHub repository
  5. Creates GitHub Release with all tar.gz as assets

Example:
  # Full release
  bash release.sh

  # Dry run (validate only)
  bash release.sh --dry-run

  # Force overwrite existing release
  bash release.sh --force
EOF
            exit 0
            ;;
        --dry-run)   DRY_RUN=true ;;
        --skip-push) SKIP_PUSH=true ;;
        --force)     FORCE=true ;;
        *) error "Unknown option: $arg. Use --help for usage." ;;
    esac
done

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
ok "Version: $TAG_NAME"

# Find all tar.gz artifacts
ARTIFACTS=()
if [[ -d "$DIST_DIR" ]]; then
    while IFS= read -r -d '' f; do
        ARTIFACTS+=("$f")
    done < <(find "$DIST_DIR" -maxdepth 1 -name "deepnode-${TAG_NAME}-*.tar.gz" -print0 | sort -z)
fi

if [[ ${#ARTIFACTS[@]} -eq 0 ]]; then
    error "No artifacts found matching 'deepnode-${TAG_NAME}-*.tar.gz' in $DIST_DIR
Please run build_standalone.sh first."
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

if $DRY_RUN; then
    echo ""
    ok "Dry run passed — all checks OK. Remove --dry-run to execute."
    exit 0
fi

# ─── Step 1: Generate install.sh ────────────────────────
echo ""
info "Step 1/3: Generating install.sh ..."

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
MIN_MACOS_VERSION="13.5"

# ─── Color helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
    local major minor
    major="$(echo "$version" | cut -d. -f1)"
    minor="$(echo "$version" | cut -d. -f2)"

    local req_major req_minor
    req_major="$(echo "$MIN_MACOS_VERSION" | cut -d. -f1)"
    req_minor="$(echo "$MIN_MACOS_VERSION" | cut -d. -f2)"

    if (( major < req_major )) || (( major == req_major && minor < req_minor )); then
        error "macOS $MIN_MACOS_VERSION+ is required. Current version: $version"
    fi

    # Determine the Metal-compatible macOS major version for asset matching
    MACOS_MAJOR="$major"
    ok "macOS version: $version (Metal-compatible target: macOS $MACOS_MAJOR)"
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
        # Ensure version starts with 'v'
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

    # Build expected asset name pattern: deepnode-<version>-macos<major>-<arch>.tar.gz
    local asset_pattern="deepnode-${TAG_NAME}-macos${MACOS_MAJOR}-${ARCH}.tar.gz"
    info "Looking for asset: $asset_pattern"

    DOWNLOAD_URL="$(echo "$release_json" | grep '"browser_download_url"' | grep "$asset_pattern" | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')"

    if [[ -z "$DOWNLOAD_URL" ]]; then
        # Fallback: try macos13 (base compatible build)
        asset_pattern="deepnode-${TAG_NAME}-macos13-${ARCH}.tar.gz"
        warn "Exact macOS $MACOS_MAJOR build not found, trying base build: $asset_pattern"
        DOWNLOAD_URL="$(echo "$release_json" | grep '"browser_download_url"' | grep "$asset_pattern" | head -1 | sed 's/.*"browser_download_url": *"\([^"]*\)".*/\1/')"
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
    # Remove old installation if exists
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

# ─── Print post-install instructions ─────────────────────────────────────────
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
    echo "    # Start with account credentials"
    echo "    ./deepnode-server --standalone --account <user> --password <pass>"
    echo ""
    echo "    # Or start with token"
    echo "    ./deepnode-server --standalone --token <your_token>"
    echo ""
    echo "  After starting, visit: http://127.0.0.1:8765/"
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

# ─── Step 2: Push to GitHub ──────────────────────────────
if ! $SKIP_PUSH; then
    echo ""
    info "Step 2/3: Pushing README + install.sh to GitHub ..."

    WORK_DIR="$SCRIPT_DIR/_release_tmp/repo"
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"

    # Clone or init the repo
    if gh repo view "$GITHUB_REPO" --json name &>/dev/null; then
        info "Cloning existing repo ..."
        git clone --depth=1 "$GITHUB_REMOTE" "$WORK_DIR" 2>/dev/null || {
            # Repo exists but is empty, init fresh
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

    # Copy files
    cp "$README_SRC" "$WORK_DIR/README.md"
    cp "$INSTALL_SCRIPT" "$WORK_DIR/install.sh"

    # Commit and push
    git add README.md install.sh
    if git diff --cached --quiet 2>/dev/null; then
        ok "No changes to push (files already up to date)"
    else
        git commit -m "release: update README and install.sh for ${TAG_NAME}"
        git push origin main
        ok "Pushed README.md + install.sh to GitHub"
    fi
else
    info "Step 2/3: Skipped (--skip-push)"
fi

# ─── Step 3: Create GitHub Release ──────────────────────
echo ""
info "Step 3/3: Creating GitHub Release ${TAG_NAME} ..."

# Build release notes
RELEASE_NOTES="## DeepNode ${TAG_NAME}

### Assets

| File | Platform | Architecture |
|------|----------|-------------|"

for a in "${ARTIFACTS[@]}"; do
    BASENAME="$(basename "$a")"
    # Extract platform and arch from filename: deepnode-v1.0.0-macos13-arm64.tar.gz
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

# Extract and run
tar xzf deepnode.tar.gz && cd deepnode-server
xattr -rd com.apple.quarantine .
./deepnode-server --standalone --account <user> --password <pass>
\`\`\`
"

# Build gh release command
GH_ARGS=(
    "release" "create" "$TAG_NAME"
    "--repo" "$GITHUB_REPO"
    "--title" "DeepNode ${TAG_NAME}"
    "--notes" "$RELEASE_NOTES"
)

if $FORCE; then
    # Delete existing release first if force mode
    gh release delete "$TAG_NAME" --repo "$GITHUB_REPO" --yes 2>/dev/null || true
    git push origin --delete "$TAG_NAME" 2>/dev/null || true
fi

# Add all artifacts
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
