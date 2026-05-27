"""
标准化工具实现 - Browser、Desktop、Memory、Workflow、Plugin
"""
from __future__ import annotations

from backend.app.core.tool_schema import (
    ToolSchema,
    ToolCategory,
    ToolRiskLevel,
    ToolParameter,
    ToolReturn,
    ToolExample,
)


# ============================================================================
# Browser 工具
# ============================================================================

BROWSER_NAVIGATE = ToolSchema(
    name="browser_navigate",
    version="1.0.0",
    description="Navigate to a URL in the browser",
    category=ToolCategory.BROWSER,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="The URL to navigate to",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Navigation timeout in seconds",
            required=False,
            default=30,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Navigation result",
        schema={"url": "string", "title": "string", "status": "number"},
    ),
    examples=[
        ToolExample(
            name="Navigate to Google",
            description="Navigate to Google homepage",
            input={"url": "https://google.com"},
            output={"url": "https://google.com", "title": "Google", "status": 200},
        ),
    ],
    permissions=["browser:navigate"],
    tags=["browser", "navigation"],
)

BROWSER_CLICK = ToolSchema(
    name="browser_click",
    version="1.0.0",
    description="Click an element on the page",
    category=ToolCategory.BROWSER,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS selector of the element to click",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Click result",
        schema={"success": "boolean", "message": "string"},
    ),
    permissions=["browser:interact"],
    tags=["browser", "interaction"],
)

BROWSER_FILL = ToolSchema(
    name="browser_fill",
    version="1.0.0",
    description="Fill a form field with text",
    category=ToolCategory.BROWSER,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS selector of the input field",
            required=True,
        ),
        ToolParameter(
            name="value",
            type="string",
            description="Text to fill",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Fill result",
        schema={"success": "boolean", "message": "string"},
    ),
    permissions=["browser:interact"],
    tags=["browser", "form"],
)

BROWSER_SCREENSHOT = ToolSchema(
    name="browser_screenshot",
    version="1.0.0",
    description="Take a screenshot of the current page",
    category=ToolCategory.BROWSER,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to save the screenshot",
            required=False,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Screenshot result",
        schema={"path": "string", "size": "number"},
    ),
    permissions=["browser:screenshot"],
    tags=["browser", "screenshot"],
)

BROWSER_EXTRACT_TEXT = ToolSchema(
    name="browser_extract_text",
    version="1.0.0",
    description="Extract text from the page",
    category=ToolCategory.BROWSER,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS selector to extract text from",
            required=False,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Extracted text",
        schema={"text": "string"},
    ),
    permissions=["browser:read"],
    tags=["browser", "extraction"],
)


# ============================================================================
# Desktop 工具
# ============================================================================

DESKTOP_CLICK = ToolSchema(
    name="desktop_click",
    version="1.0.0",
    description="Click on a desktop element",
    category=ToolCategory.DESKTOP,
    risk_level=ToolRiskLevel.MEDIUM,
    parameters=[
        ToolParameter(
            name="x",
            type="number",
            description="X coordinate",
            required=True,
        ),
        ToolParameter(
            name="y",
            type="number",
            description="Y coordinate",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Click result",
        schema={"success": "boolean"},
    ),
    permissions=["desktop:interact"],
    tags=["desktop", "interaction"],
)

DESKTOP_TYPE = ToolSchema(
    name="desktop_type",
    version="1.0.0",
    description="Type text on the desktop",
    category=ToolCategory.DESKTOP,
    risk_level=ToolRiskLevel.MEDIUM,
    parameters=[
        ToolParameter(
            name="text",
            type="string",
            description="Text to type",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Type result",
        schema={"success": "boolean"},
    ),
    permissions=["desktop:interact"],
    tags=["desktop", "typing"],
)

DESKTOP_SCREENSHOT = ToolSchema(
    name="desktop_screenshot",
    version="1.0.0",
    description="Take a desktop screenshot",
    category=ToolCategory.DESKTOP,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to save the screenshot",
            required=False,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Screenshot result",
        schema={"path": "string"},
    ),
    permissions=["desktop:screenshot"],
    tags=["desktop", "screenshot"],
)


# ============================================================================
# Memory 工具
# ============================================================================

MEMORY_STORE = ToolSchema(
    name="memory_store",
    version="1.0.0",
    description="Store information in memory",
    category=ToolCategory.MEMORY,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="content",
            type="string",
            description="Content to store",
            required=True,
        ),
        ToolParameter(
            name="layer",
            type="number",
            description="Memory layer (1-10)",
            required=False,
            default=5,
        ),
        ToolParameter(
            name="tags",
            type="array",
            description="Tags for the memory",
            required=False,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Store result",
        schema={"memory_id": "string", "created_at": "string"},
    ),
    permissions=["memory:write"],
    tags=["memory", "storage"],
)

MEMORY_RETRIEVE = ToolSchema(
    name="memory_retrieve",
    version="1.0.0",
    description="Retrieve information from memory",
    category=ToolCategory.MEMORY,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Search query",
            required=True,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Maximum results",
            required=False,
            default=10,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Retrieve result",
        schema={"items": "array", "total": "number"},
    ),
    permissions=["memory:read"],
    tags=["memory", "retrieval"],
)

MEMORY_UPDATE = ToolSchema(
    name="memory_update",
    version="1.0.0",
    description="Update memory content",
    category=ToolCategory.MEMORY,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="memory_id",
            type="string",
            description="Memory ID to update",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="New content",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Update result",
        schema={"success": "boolean"},
    ),
    permissions=["memory:write"],
    tags=["memory", "update"],
)


# ============================================================================
# Workflow 工具
# ============================================================================

WORKFLOW_EXECUTE = ToolSchema(
    name="workflow_execute",
    version="1.0.0",
    description="Execute a workflow",
    category=ToolCategory.WORKFLOW,
    risk_level=ToolRiskLevel.MEDIUM,
    parameters=[
        ToolParameter(
            name="workflow_id",
            type="string",
            description="Workflow ID to execute",
            required=True,
        ),
        ToolParameter(
            name="input",
            type="object",
            description="Workflow input",
            required=False,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Execution result",
        schema={"run_id": "string", "status": "string"},
    ),
    permissions=["workflow:execute"],
    requires_approval=True,
    tags=["workflow", "execution"],
)

WORKFLOW_STATUS = ToolSchema(
    name="workflow_status",
    version="1.0.0",
    description="Get workflow execution status",
    category=ToolCategory.WORKFLOW,
    risk_level=ToolRiskLevel.LOW,
    parameters=[
        ToolParameter(
            name="run_id",
            type="string",
            description="Run ID",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Status result",
        schema={"status": "string", "progress": "number"},
    ),
    permissions=["workflow:read"],
    tags=["workflow", "status"],
)


# ============================================================================
# Plugin 工具
# ============================================================================

PLUGIN_INSTALL = ToolSchema(
    name="plugin_install",
    version="1.0.0",
    description="Install a plugin",
    category=ToolCategory.PLUGIN,
    risk_level=ToolRiskLevel.HIGH,
    parameters=[
        ToolParameter(
            name="plugin_name",
            type="string",
            description="Plugin name",
            required=True,
        ),
        ToolParameter(
            name="version",
            type="string",
            description="Plugin version",
            required=False,
            default="latest",
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Install result",
        schema={"plugin_id": "string", "status": "string"},
    ),
    permissions=["plugin:install"],
    requires_approval=True,
    tags=["plugin", "install"],
)

PLUGIN_UNINSTALL = ToolSchema(
    name="plugin_uninstall",
    version="1.0.0",
    description="Uninstall a plugin",
    category=ToolCategory.PLUGIN,
    risk_level=ToolRiskLevel.HIGH,
    parameters=[
        ToolParameter(
            name="plugin_id",
            type="string",
            description="Plugin ID",
            required=True,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Uninstall result",
        schema={"success": "boolean"},
    ),
    permissions=["plugin:uninstall"],
    requires_approval=True,
    tags=["plugin", "uninstall"],
)

PLUGIN_EXECUTE = ToolSchema(
    name="plugin_execute",
    version="1.0.0",
    description="Execute a plugin action",
    category=ToolCategory.PLUGIN,
    risk_level=ToolRiskLevel.MEDIUM,
    parameters=[
        ToolParameter(
            name="plugin_id",
            type="string",
            description="Plugin ID",
            required=True,
        ),
        ToolParameter(
            name="action",
            type="string",
            description="Action to execute",
            required=True,
        ),
        ToolParameter(
            name="params",
            type="object",
            description="Action parameters",
            required=False,
        ),
    ],
    returns=ToolReturn(
        type="object",
        description="Execution result",
        schema={"success": "boolean", "output": "object"},
    ),
    permissions=["plugin:execute"],
    tags=["plugin", "execution"],
)


# 工具集合
STANDARD_TOOLS = [
    # Browser
    BROWSER_NAVIGATE,
    BROWSER_CLICK,
    BROWSER_FILL,
    BROWSER_SCREENSHOT,
    BROWSER_EXTRACT_TEXT,
    # Desktop
    DESKTOP_CLICK,
    DESKTOP_TYPE,
    DESKTOP_SCREENSHOT,
    # Memory
    MEMORY_STORE,
    MEMORY_RETRIEVE,
    MEMORY_UPDATE,
    # Workflow
    WORKFLOW_EXECUTE,
    WORKFLOW_STATUS,
    # Plugin
    PLUGIN_INSTALL,
    PLUGIN_UNINSTALL,
    PLUGIN_EXECUTE,
]
