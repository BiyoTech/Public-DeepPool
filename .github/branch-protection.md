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
| **Require status checks to pass before merging** | ✅ Enabled | CI must pass (see Required Status Checks below) |
| **Require branches to be up to date before merging** | ✅ Enabled | Branch must be current with main |
| **Require conversation resolution before merging** | ✅ Enabled | All review comments must be resolved |
| **Require signed commits** | Optional | Enforce GPG-signed commits |
| **Include administrators** | ✅ Enabled | Rules also apply to admins |
| **Restrict who can push to matching branches** | ✅ Enabled | Only maintainers can merge |
| **Allow force pushes** | ❌ Disabled | Prevent history rewriting |
| **Allow deletions** | ❌ Disabled | Prevent branch deletion |

## Required Status Checks

The following CI jobs **must pass** before a PR can be merged. Add these exact names in **Settings → Branches → Status checks**:

| Job Name | Workflow | Description |
|----------|----------|-------------|
| `go-ci` | `go-ci.yml` | golangci-lint + Go unit tests + coverage |
| `python-ci` | `python-ci.yml` | pytest + coverage (localserver) |
| `frontend-ci (control_web)` | `frontend-ci.yml` | ESLint + vue-tsc + vite build |
| `frontend-ci (portal_web)` | `frontend-ci.yml` | ESLint + vue-tsc + vite build |
| `codeql (go)` | `codeql.yml` | CodeQL security scan (Go) |
| `codeql (javascript-typescript)` | `codeql.yml` | CodeQL security scan (JS/TS) |
| `codeql (python)` | `codeql.yml` | CodeQL security scan (Python) |

> **Note**: Status checks only appear after the workflow has run at least once. Push a change to trigger the workflows first, then configure the protection rule.

## Merge Strategy

| Setting | Recommendation | Reason |
|---------|---------------|--------|
| **Allow squash merging** | ✅ Enabled (preferred) | Clean single-commit history on main |
| **Allow merge commits** | ⚠️ Optional | Use only for large multi-commit PRs |
| **Allow rebase merging** | ❌ Disabled | Avoid confusing linear history |
| **Default merge method** | Squash and merge | Keep main branch history clean |

Configure in: **Settings → General → Pull Requests**

## Permission Levels

| Role | Permissions | Typical Users |
|------|-------------|---------------|
| **Read** (Triage) | View code, open issues, comment on PRs | Community contributors |
| **Write** (Developer) | Push to feature branches, open PRs, cannot merge to main | Regular developers |
| **Maintain** (Maintainer) | Review + merge PRs, manage issues, release tags | Core team (@BiyoTech) |
| **Admin** | Emergency rollback, settings changes, branch protection config | Repository owner |

> **Principle**: Follow the principle of least privilege. Regular developers should only be able to open PRs, not merge them directly.

## GitHub CLI Setup (Alternative)

```bash
# Install GitHub CLI: https://cli.github.com/
# Then run:

gh api repos/{owner}/Public-DeepPool/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["go-ci","python-ci","frontend-ci (control_web)","frontend-ci (portal_web)","codeql (go)","codeql (javascript-typescript)","codeql (python)"]}' \
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
