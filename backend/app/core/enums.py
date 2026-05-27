"""Enumerations for agent execution and recovery."""

from enum import Enum


class StepKind(str, Enum):
    """Agent plan step kinds."""

    OBSERVE = "observe"
    TOOL = "tool"
    REFLECT = "reflect"
    FINAL = "final"


class RecoveryBranch(str, Enum):
    """Recovery branch types for agent execution."""

    CONTINUE = "continue"
    URGENT_CONTINUE = "urgent_continue"
    CAREFUL_CONTINUE = "careful_continue"
    RESUME = "resume"
    APPROVAL_WAIT = "approval_wait"
    BROWSER_OBSERVE = "browser_observe"
    DESKTOP_OBSERVE = "desktop_observe"


class TaskMode(str, Enum):
    """Task execution modes."""

    EDIT = "edit"
    ANALYZE = "analyze"
    SUMMARIZE = "summarize"
    SEARCH = "search"
    GENERAL = "general"


class TaskIntent(str, Enum):
    """Task intent classification."""

    CODE_CHANGE = "code_change"
    ANALYSIS = "analysis"
    SUMMARY = "summary"
    DISCOVERY = "discovery"
    AUTOMATION = "automation"
    GENERAL = "general"


class ToolCategory(str, Enum):
    """Tool categories for prioritization."""

    READ = "read"
    WRITE = "write"
    SEARCH = "search"
    ANALYZE = "analyze"
    BROWSER = "browser"
    DESKTOP = "desktop"
    WORKFLOW = "workflow"
    APPROVAL = "approval"
    MEMORY = "memory"
    TRACE = "trace"
