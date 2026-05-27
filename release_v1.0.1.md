# Release Note — DeepPool v1.0.1

**Release Date**: May 19, 2026

v1.0.1 is a quality and engineering infrastructure release. No new user-facing features are introduced — the focus is on CI/CD pipeline setup, code quality enforcement, and bug fixes.

---

## Highlights

### CI/CD Pipeline (GitHub Actions)

Added automated continuous integration pipelines for all three tech stacks:

- **Frontend CI** (`frontend-ci.yml`) — Runs ESLint, `vue-tsc` type-check, and production build for both `portal_web` and `control_web`
- **Go CI** (`go-ci.yml`) — Runs `go build`, `go test`, and `golangci-lint v2` for the platform backend and shared libs
- **Python CI** (`python-ci.yml`) — Runs syntax checks for the DeepNode local server and MissZhao agent

### Code Quality Enforcement

- **ESLint + Prettier** configured for both `portal_web` and `control_web` with flat config format (`eslint.config.js`)
- **golangci-lint v2** configured (`.golangci.yml`) with formatters section, focused linter set (govet, staticcheck, unused, ineffassign, bodyclose, nilerr)
- **vue-tsc type-check** added as `npm run type-check` script for both frontend apps

### GitHub Community Templates

- Issue templates: Bug Report, Feature Request, Question
- Pull Request template
- CODEOWNERS file
- Dependabot configuration
- Branch protection guidelines

---

## Detailed Changes

### Backend (Go)

#### Removed
- Deleted unused `scheduler` service (`platform/cmd/scheduler/main.go`, `platform/internal/scheduler/server.go`)
- Removed unused code: `templateDir` in `builtin_scorers.go`, `traceMatchKey` type in `trace_matcher.go`, `validateEndpointURL` in `model_service.go`, helper functions in `trace_service.go`, `registerTimeout` in `tunnel_handler.go`

#### Fixed
- Fixed ineffectual assignment in `alipay.go` (payment status variable)
- Optimized string concatenation in `judge_service.go` (`sb.WriteString(fmt.Sprintf(...))` → `fmt.Fprintf(&sb, ...)`)
- Fixed test mock interfaces to match updated `UserService`/`UserRepository`/`EmailService` signatures
- Downgraded Go x/ dependencies to Go 1.24-compatible versions (x/crypto, x/net, x/sys, x/text)

#### Config
- Added `toolchain go1.24.3` directive in `go.work`
- Cleaned up `config.go` (removed scheduler-related config fields)

### Frontend (Vue 3 + TypeScript)

#### Tooling
- Added `vue-tsc` devDependency and `type-check`/`lint` npm scripts to both `portal_web` and `control_web`
- Added `eslint.config.js` (flat config) and `.prettierrc` to both frontend apps
- Added `env.d.ts` for Vite client type declarations

#### Type Safety Fixes
- `tsconfig.json`: Added `skipLibCheck: true`, removed deprecated `baseUrl`, updated `paths` mapping
- Added `UpdateTraceParams` export type in `experiment.ts`
- Fixed `MarkdownRenderer.vue`: explicit `MarkdownIt` type annotation and `: string` return type
- Fixed `PlaygroundPanel.vue`: widened `chatMessages` type to allow `'system'` role
- Fixed `PortalLayout.vue`: added generic type to `navItems` computed property
- Fixed `ExperimentLayout.vue`: added generic type with `badge?` field
- Fixed `JudgeView.vue`: narrowed `resolveScope()` return type union
- Fixed `TraceView.vue`: added type cast for `apiUpdateTrace` call
- Fixed `ModelsView.vue`: added optional chaining for `model.tags`

#### Admin Dashboard (`control_web`)
- Updated `DeepPoolLogo.vue` component
- Fixed router and layout type issues
- Resolved ESLint errors across multiple views (ChatView, DashboardView, DevicesView, EndpointsView, ModelsView, etc.)

#### User Portal (`portal_web`)
- Enhanced `ApiKeyManager.vue` with improved key management UI
- Enhanced `PlaygroundPanel.vue` with expanded chat capabilities
- Improved `JudgeView.vue` and `TraceView.vue` experiment evaluation experience
- Enhanced `TraceLogDetailDialog.vue` with richer detail display
- Updated wallet views (BankCards, Recharge, Withdraw)
- Refined `HomeView.vue`, `DataView.vue`, `MissZhaoView.vue` layouts
- Fixed i18n configuration and locale files

---

## Upgrade Guide

### For Developers

1. **Pull the latest code** and run `npm install` in both `portal_web/` and `control_web/`
2. **Install golangci-lint v2** if not already available:
   ```bash
   # macOS
   brew install golangci-lint
   # or install latest binary from https://github.com/golangci-lint/golangci-lint/releases
   ```
3. **Run quality checks locally**:
   ```bash
   # Frontend
   cd platform/portal_web && npm run lint && npm run type-check && npm run build
   cd platform/control_web && npm run lint && npm run type-check && npm run build

   # Backend
   golangci-lint run --timeout=5m ./platform/cmd/... ./platform/internal/... ./libs/...
   go test ./platform/...
   ```

### For Deployments

No database migration or config changes are required for v1.0.1. The scheduler service was removed — if you had it running, it can be safely stopped.

---

## Full Commit Log (since v1.0.0)

| Commit | Date | Message |
|--------|------|---------|
| `342c937` | 2026-05-19 | add cicd workflow |
| `a92bf7d` | 2026-05-19 | fix code check workflow |
| `6b27e84` | 2026-05-19 | fix eslint |
| `5927eeb` | 2026-05-19 | fix eslint |
| `e56c5b2` | 2026-05-19 | fix go-cli type-check problem |
| `50f550a` | 2026-05-19 | fix go ci |
| `8891410` | 2026-05-19 | fix go ci |

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

---

<p align="center">
  <sub>Built with ❤️ by the DeepPool Team</sub>
</p>
