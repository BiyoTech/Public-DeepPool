#!/bin/bash
# sync_opensource.sh — Incrementally sync latest code from the private repo
# to an existing open-source repo, excluding sensitive files.
#
# This script uses rsync (not git merge) because the two repos have
# divergent histories (git-filter-repo rewrites commit hashes).
#
# Usage:
#   ./sync_opensource.sh /path/to/DeepPool-opensource [commit-message]
#
# Example:
#   ./sync_opensource.sh ../DeepPool-opensource "sync: update from private repo"
#
# Prerequisites:
#   brew install rsync  (macOS)

set -euo pipefail

DEST="${1:?Usage: $0 <opensource-repo-path> [commit-message]}"
COMMIT_MSG="${2:-sync: update from private repo}"
SRC="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$DEST/.git" ]; then
  echo "ERROR: '$DEST' is not a Git repository. Run prepare_opensource.sh first."
  exit 1
fi

# Sensitive paths to exclude — must match prepare_opensource.sh
EXCLUDES=(
  --exclude='platform/config_prod/'
  --exclude='platform/config_test/'
  --exclude='platform/ssl_cert/'
  --exclude='platform/wechat_pay_cert/'
  --exclude='platform/alipay_cert/'
  --exclude='platform/config/manager.yaml'
  --exclude='platform/config/nodemanager.yaml'
  --exclude='platform/config/experiment.yaml'
  --exclude='platform/config/scheduler.yaml'
  --exclude='misszhao/'
  --exclude='.git/'
  --exclude='node_modules/'
)

echo "==> Syncing files from $SRC to $DEST ..."
rsync -av --delete "${EXCLUDES[@]}" "$SRC/" "$DEST/"

echo ""
echo "==> Checking for potential secrets in synced files ..."
cd "$DEST"
SECRETS=$(git grep -l -i 'root@123\|AliRoot@123\|3857358a44c4a49a55309e5d3e54497e\|mch_id.*[0-9]\{10\}\|23412432431' -- ':!*.example' ':!prepare_opensource.sh' ':!sync_opensource.sh' || true)
if [ -n "$SECRETS" ]; then
  echo "WARNING: potential secrets found in these files:"
  echo "$SECRETS"
  echo "Please review and sanitize before committing."
  echo ""
  read -rp "Continue anyway? [y/N] " CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

echo ""
echo "==> Staging and committing changes ..."
cd "$DEST"
git add -A

STAGED=$(git diff --cached --stat)
if [ -z "$STAGED" ]; then
  echo "No changes to commit. Already up to date."
  exit 0
fi

echo "$STAGED"
echo ""
git commit -m "$COMMIT_MSG"

echo ""
echo "==> Done! Changes committed to open-source repo."
echo ""
echo "Next steps:"
echo "  cd $DEST"
echo "  git push origin main"
