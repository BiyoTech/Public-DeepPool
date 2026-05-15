# Contributing to DeepPool

Thank you for your interest in contributing to DeepPool! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Security Vulnerabilities](#security-vulnerabilities)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [security@deeppool.tech](mailto:security@deeppool.tech).

---

## How to Contribute

### Reporting Bugs

1. Search [existing issues](https://github.com/BiyoTech/Public-DeepPool/issues) to avoid duplicates.
2. Use the **Bug Report** issue template.
3. Include reproduction steps, expected vs. actual behavior, and environment details.
4. Attach relevant logs (redact sensitive information such as API keys).

### Suggesting Features

1. Search existing issues and discussions for similar ideas.
2. Use the **Feature Request** issue template.
3. Clearly describe the problem, proposed solution, and alternatives considered.

### Submitting Code

1. **Fork** this repository.
2. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature
   ```
3. Make your changes following the [Coding Standards](#coding-standards).
4. Commit using [Conventional Commits](#commit-convention).
5. Push and open a **Pull Request** against `main`.

---

## Development Setup

### Prerequisites

| Dependency | Version | Purpose |
|-----------|---------|---------|
| **Go** | >= 1.23 | Platform backend |
| **Node.js** | >= 18 | Frontend build |
| **MySQL** | >= 8.0 | Data storage |
| **Python** | >= 3.13 | DeepNode local inference service |
| **protoc** | >= 3.x | Protobuf compilation (only when modifying .proto) |
| **Rust / Cargo** | latest stable | Tauri desktop client (optional) |

### Quick Start

```bash
# Clone your fork
git clone https://github.com/<your-username>/Public-DeepPool.git
cd Public-DeepPool

# Create MySQL database
mysql -u root -p -e "CREATE DATABASE deeppool CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Configure
cp platform/config/manager.yaml.example platform/config/manager.yaml
vim platform/config/manager.yaml  # Set your MySQL connection

# One-click dev mode (starts all components)
./dev.sh all
```

### Component-Level Startup

```bash
# Backend only
./run_platformserver.sh manager

# Frontend only (admin + portal)
./run_platformweb.sh all

# DeepNode client only
cd clients/deepnode && ./run_standalone.sh
```

### Verify

```bash
curl http://localhost:8080/api/v1/health
# {"code":0,"message":"ok","data":{"status":"healthy"}}
```

---

## Coding Standards

### General

- **Language**: All code comments, log messages, and documentation must be in **English**.
- **Time**: Use **UTC** for all timestamps (multi-timezone aware).
- **Logging**: ERROR/WARN logs must include the cause and relevant context.

### Go (Platform Backend)

- Format with `gofmt` / `goimports`.
- Follow standard Go project layout conventions.
- Use `net/http` stdlib (no web frameworks).
- **SQL**: Always use parameterized queries (`?` placeholders). **Never** concatenate user input into SQL.
- **Passwords**: Always hash with `bcrypt`.
- **Error handling**: Wrap errors with context; never silently discard errors.
- Focus on good abstraction, add necessary comments.

### Frontend (Vue 3)

- Use **Composition API** with `<script setup>`.
- Use **TypeScript** for all new files.
- Follow TDesign component library conventions.
- Use `vue-i18n` for user-facing strings.

### Python (DeepNode LocalServer)

- Target Python **3.13+**.
- Use **type hints** for all function signatures.
- Follow PEP 8 style guidelines.
- Use `async`/`await` for I/O operations (FastAPI).

### Protobuf

- Follow [Google Protobuf Style Guide](https://protobuf.dev/programming-guides/style/).
- Regenerate code after modifying `.proto` files: `./build.sh proto`.

---

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code refactoring |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `build` | Build system or dependencies |
| `ci` | CI/CD configuration |
| `chore` | Other maintenance tasks |

### Scopes (optional)

`gateway`, `manager`, `nodemanager`, `experiment`, `guardrails`, `trace`, `control-web`, `portal-web`, `deepnode`, `localserver`, `proto`, `deploy`

### Examples

```
feat(gateway): add vision content detection for hybrid routing
fix(guardrails): handle timeout when evaluator model is unreachable
docs: update API documentation for streaming endpoints
refactor(nodemanager): extract dispatch logic into dedicated service
```

---

## Pull Request Process

### Before Submitting

1. Ensure your branch is up to date with `main`:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```
2. Run tests locally:
   ```bash
   cd platform && go test ./...
   ```
3. Ensure `gofmt` produces no changes.
4. Verify your changes don't break the health check endpoint.

### PR Requirements

- **Title**: Follow Conventional Commits format (e.g., `feat(gateway): add X`).
- **Description**: Fill in the PR template completely.
- **Linked Issue**: Reference related issue(s) with `Closes #xxx`.
- **Review**: All PRs to `main` require review from the project maintainer (`@BiyoTech`).
- **CI**: All status checks must pass before merging.
- **Conversations**: All review comments must be resolved.

### Review Process

1. Maintainer reviews the PR within **3 business days**.
2. Address requested changes by pushing new commits (do not force push during review).
3. Once approved, the maintainer will merge the PR.

### Merge Strategy

- **Squash merge** is preferred for feature branches (clean commit history).
- **Merge commit** is acceptable for large PRs with meaningful individual commits.
- **Rebase merge** may be used when the branch history is clean and linear.

---

## Issue Guidelines

- Use the provided issue templates (Bug Report / Feature Request / Question).
- Search existing issues before creating a new one.
- One issue per topic — do not combine unrelated bugs or features.
- Be respectful and constructive in discussions.

---

## Security Vulnerabilities

**Do NOT open a public issue for security vulnerabilities.**

Please refer to [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

---

## License

By contributing to DeepPool, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

---

Thank you for contributing to DeepPool!
