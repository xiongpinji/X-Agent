from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app import dependencies
orig = dependencies.get_current_principal
principals = {}
async def fake(*a, **kw):
    p = await orig(*a, **kw)
    principals['p'] = p
    return p
app.dependency_overrides[dependencies.get_current_principal] = fake
with TestClient(app, headers={"X-API-Key": "xagent-dev-key-2024"}) as c:
    c.get("/api/v1/tools")
p = principals.get('p')
print("type:", type(p))
print("scopes:", getattr(p, 'scopes', 'N/A'))
print("permission_scope:", getattr(p, 'permission_scope', 'N/A'))
print("role:", getattr(p, 'role', 'N/A'))
