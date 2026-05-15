# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x  | ✅ Active |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in DeepPool, please report it responsibly:

1. **Email**: Send a detailed report to [security@deeppool.tech](mailto:security@deeppool.tech).
2. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
3. **Response Time**: We will acknowledge your report within **48 hours** and provide an initial assessment within **5 business days**.
4. **Disclosure**: We will coordinate a responsible disclosure timeline with you. We aim to release a fix within **30 days** of a confirmed vulnerability.

## Security Practices in This Project

DeepPool follows these security best practices:

| Area | Practice |
|------|----------|
| **SQL Injection** | All database queries use parameterized statements (`?` placeholders). String concatenation into SQL is prohibited. |
| **Password Storage** | bcrypt hashing for all passwords. No plaintext storage. |
| **API Key Encryption** | AES-256-GCM encryption at rest in the database. SHA-256 hashing for lookup. |
| **Authentication** | Token-based session authentication with 7-day expiry. |
| **Rate Limiting** | Sliding window RPM/TPM rate limiting per API Key. |
| **Input Validation** | Strict validation for all user inputs (regex, length checks). JSON bodies reject unknown fields. |
| **Path Traversal** | Model path resolution includes directory traversal checks. |
| **Content Safety** | Guardrails module provides LLM-based input/output safety evaluation. |
| **Secrets Management** | No hardcoded credentials in source code. Sensitive config is environment-specific. |

## Scope

The following are **in scope** for security reports:

- Platform backend services (Manager, NodeManager, Experiment)
- Gateway inference routing and authentication
- API Key management and encryption
- DeepNode client credential handling
- gRPC tunnel authentication
- Frontend XSS / CSRF vulnerabilities

The following are **out of scope**:

- Vulnerabilities in third-party dependencies (report to the upstream project)
- Social engineering attacks
- Denial of service via excessive legitimate requests (rate limiting is already in place)

## Recognition

We appreciate responsible disclosure. Contributors who report valid security vulnerabilities will be acknowledged in our release notes (unless anonymity is preferred).

---

Thank you for helping keep DeepPool secure!
