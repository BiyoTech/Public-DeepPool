#!/bin/bash
# prepare_opensource.sh — Create a clean open-source copy of DeepPool
# with all sensitive files and their Git history removed.
#
# Usage:
#   ./prepare_opensource.sh /path/to/new/DeepPool-opensource
#
# Prerequisites:
#   brew install git-filter-repo

set -euo pipefail

DEST="${1:?Usage: $0 <destination-path>}"
SRC="$(cd "$(dirname "$0")" && pwd)"

if [ -d "$DEST" ]; then
  echo "ERROR: destination '$DEST' already exists. Remove it first."
  exit 1
fi

echo "==> Cloning repository to $DEST ..."
git clone --no-hardlinks "$SRC" "$DEST"
cd "$DEST"

# Remove the origin remote (points to private repo)
git remote remove origin 2>/dev/null || true

echo "==> Removing sensitive paths from entire Git history ..."
git filter-repo \
  --path platform/config_prod/ \
  --path platform/config_test/ \
  --path platform/ssl_cert/ \
  --path platform/wechat_pay_cert/ \
  --path platform/alipay_cert/ \
  --path platform/config/manager.yaml \
  --path platform/config/nodemanager.yaml \
  --path platform/config/experiment.yaml \
  --path platform/config/scheduler.yaml \
  --path misszhao \
  --invert-paths \
  --force

echo "==> Verifying no sensitive files remain in history ..."
LEAKED=$(git log --all --diff-filter=A --name-only --pretty=format: -- \
  'platform/config_prod/*' 'platform/config_test/*' \
  'platform/ssl_cert/*' 'platform/wechat_pay_cert/*' 'platform/alipay_cert/*' \
  '*.p12' \
  | sort -u | grep -v '^$' || true)

if [ -n "$LEAKED" ]; then
  echo "WARNING: the following sensitive files still exist in history:"
  echo "$LEAKED"
  exit 1
fi

echo "==> Checking for leftover secrets in tracked files ..."
# Quick grep for obvious secret patterns in current HEAD
SECRETS=$(git grep -l -i 'root@123\|AliRoot@123\|3857358a44c4a49a55309e5d3e54497e\|mch_id.*[0-9]\{10\}\|23412432431' -- ':!*.example' ':!prepare_opensource.sh' || true)
if [ -n "$SECRETS" ]; then
  echo "WARNING: potential secrets found in these tracked files:"
  echo "$SECRETS"
  echo "Please review and sanitize before pushing."
fi

echo ""
echo "==> Done! Open-source repo ready at: $DEST"
echo ""
echo "Next steps:"
echo "  cd $DEST"
echo "  git remote add origin git@github.com:YOUR_ORG/DeepPool.git"
echo "  git push -u origin main"
