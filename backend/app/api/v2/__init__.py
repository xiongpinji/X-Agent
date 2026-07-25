"""API v2 route registry.

This package contains v2 API endpoints. Routes here are served under
/api/v2/ prefix. v1 routes remain available but may be deprecated over time.

To add a v2 endpoint:
    1. Create a module in this package (e.g., agents.py)
    2. Define router = APIRouter(prefix="/api/v2/agents", tags=["agents-v2"])
    3. Register it in v2_router below
"""

from fastapi import APIRouter

# v2 aggregate router — mount all v2 sub-routers here
v2_router = APIRouter()


@v2_router.get("/api/v2/status", tags=["v2"])
async def v2_status():
    """API v2 availability check."""
    return {
        "version": "2.0",
        "status": "preview",
        "message": "API v2 is in preview. v1 remains the stable API.",
    }
