# X-Agent Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x (current development) | Security fixes applied to `main` |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

### Responsible Disclosure

1. **Email**: Send details to `security@x-agent.dev` (or the project maintainer's security contact)
2. **Encrypted**: Use our PGP key (fingerprint published at `/.well-known/security.txt`)
3. **Response SLA**: We acknowledge receipt within **48 hours** and provide a substantive response within **5 business days**

### What to Include

- Description of the vulnerability
- Steps to reproduce (PoC or detailed instructions)
- Affected component/version
- Potential impact assessment
- Suggested fix (optional but appreciated)

### Scope

In-scope:
- Backend API (`backend/`)
- Authentication/authorization flows
- Data isolation between tenants
- MCP tool execution sandbox
- Desktop/mobile/extension clients

Out-of-scope:
- Social engineering attacks
- Physical access attacks
- Denial of service (DoS/DDoS)
- Vulnerabilities in third-party services

### Safe Harbor

We consider security research conducted in good faith under this policy to be authorized. We will not initiate legal action against researchers who:
- Act in good faith and follow this policy
- Avoid privacy violations, data destruction, and service disruption
- Only interact with accounts they own or with explicit permission

## Security Measures

### Authentication & Authorization
- OIDC/SAML 2.0 SSO integration
- SCIM 2.0 user provisioning
- Role-based access control (RBAC)
- Multi-tenant isolation with enforced boundaries

### Data Protection
- AES-256 encryption at rest (via KMS)
- TLS 1.3+ for all communications
- Zero Data Retention (ZDR) mode available
- Audit log integrity via HMAC chain

### Infrastructure
- Dependency vulnerability scanning (pip-audit + npm audit) in CI
- SAST analysis (Semgrep + Bandit) on every PR
- Secret detection (TruffleHog) on all commits
- SBOM generation (CycloneDX) for supply chain transparency

### Compliance
- SOC 2 Type I evidence collection framework
- Audit log retention with WORM semantics
- SIEM export (CEF/Syslog/JSON Lines)
- Incident response procedures documented and tested

## Security Decisions Log

See `commercial_audit/security_decisions_closure_2026-07-19.md` for historical security decisions and their rationale.
