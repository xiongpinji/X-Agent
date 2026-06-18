# X-Agent RC First-Version Scope

## Ship In First Version

- Auth and RBAC
- Workbench and agent run
- Workspace and file preview
- Memory
- Desktop client/runtime
- DeepSeek LLM backend
- GitHub integration
- Feishu integration
- Stage3 deploy evidence chain

## Deferred From First Version

- Browser extension
- WebAuthn/passkey
- Full OAuth marketplace flows
- Forum
- Analytics dashboards
- Plugin marketplace
- Skill marketplace
- Templates marketplace
- Public notification subscription

## Rule

The frontend must not route users into deferred surfaces. The backend must not mount deferred route modules unless the module is explicitly promoted with tests, route-auth audit coverage, and API contract coverage.
