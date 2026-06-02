"""X-Agent Hooks system.

Provides a control-plane interception layer over agent tool execution and
lifecycle events. Unlike the EventBus (observation only), hooks can deny,
modify, or require approval for actions before they run.

Public API:
    - HookEvent: lifecycle/tool event types
    - HookAction: allow / deny / ask / modify
    - HookDecision: a hook's verdict for a given event
    - HookContext: immutable payload passed to a hook
    - HookResult: aggregated outcome after running all hooks for an event
    - Hook: protocol every hook implements
    - HookManager / get_hook_manager: registration and dispatch
"""

from __future__ import annotations

from backend.app.core.hooks.manager import (
    HookManager,
    get_hook_manager,
    set_hook_manager,
)
from backend.app.core.hooks.types import (
    Hook,
    HookAction,
    HookContext,
    HookDecision,
    HookEvent,
    HookResult,
)
from backend.app.core.hooks.config import (
    DEFAULT_CONFIG_RELPATH,
    HookDefinition,
    HooksConfig,
)
from backend.app.core.hooks.executors import (
    CommandHook,
    PythonHook,
    build_hook,
    load_hooks_from_config,
    register_hooks_from_config,
)

__all__ = [
    "Hook",
    "HookAction",
    "HookContext",
    "HookDecision",
    "HookEvent",
    "HookResult",
    "HookManager",
    "get_hook_manager",
    "set_hook_manager",
    "DEFAULT_CONFIG_RELPATH",
    "HookDefinition",
    "HooksConfig",
    "CommandHook",
    "PythonHook",
    "build_hook",
    "load_hooks_from_config",
    "register_hooks_from_config",
]
