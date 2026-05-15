# Branch Protection Rules — Setup Guide

> Branch protection rules **cannot** be configured via repository files.
> You must set them up in **GitHub Settings** (or via the GitHub API).
> This document serves as a reference for the recommended configuration.

## `main` Branch Protection

Navigate to: **Settings → Branches → Add branch protection rule**

| Setting | Value | Description |
|---------|-------|-------------|
| **Branch name pattern** | `main` | Protect the main branch |
| **Require a pull request before merging** | ✅ Enabled | No direct pushes to main |
| **Required approvals** | `1` | At least 1 approval required |
| **Require review from Code Owners** | ✅ Enabled | CODEOWNERS-listed reviewers must approve |
| **Dismiss stale pull request approvals when new commits are pushed** | ✅ Enabled | Re-review needed after force push |
| **Require status checks to pass before merging** | ✅ Enabled | CI must pass |
| **Require branches to be up to date before merging** | ✅ Enabled | Branch must be current with main |
| **Require conversation resolution before merging** | ✅ Enabled | All review comments must be resolved |
| **Require signed commits** | Optional | Enforce GPG-signed commits |
| **Include administrators** | ✅ Enabled | Rules also apply to admins |
| **Restrict who can push to matching branches** | ✅ Enabled | Only maintainers can merge |
| **Allow force pushes** | ❌ Disabled | Prevent history rewriting |
| **Allow deletions** | ❌ Disabled | Prevent branch deletion |

## GitHub CLI Setup (Alternative)

```bash
# Install GitHub CLI: https://cli.github.com/
# Then run:

gh api repos/{owner}/Public-DeepPool/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":[]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field restrictions=null
```

## Tag Protection

Recommend also protecting release tags:

| Setting | Value |
|---------|-------|
| **Tag name pattern** | `v*` |
| **Restrict who can create matching tags** | Maintainers only |
