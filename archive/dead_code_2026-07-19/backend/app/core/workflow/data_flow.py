"""Data Flow Management for Workflows

Implements data flow constructs:
- Variable scoping and lifecycle
- Data transformations
- Expression evaluation
- Template rendering
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ScopeLevel(StrEnum):
    GLOBAL = "global"
    WORKFLOW = "workflow"
    NODE = "node"
    LOOP = "loop"


@dataclass
class VariableScope:
    """Manages variable scoping"""
    level: ScopeLevel
    parent: VariableScope | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get(self, name: str, default: Any = None) -> Any:
        """Get variable value, checking parent scopes"""
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.get(name, default)
        return default

    def set(self, name: str, value: Any) -> None:
        """Set variable in current scope"""
        self.variables[name] = value

    def set_in_parent(self, name: str, value: Any) -> None:
        """Set variable in parent scope"""
        if self.parent:
            self.parent.set(name, value)
        else:
            self.set(name, value)

    def create_child(self, level: ScopeLevel) -> VariableScope:
        """Create child scope"""
        return VariableScope(level=level, parent=self)

    def to_dict(self) -> dict[str, Any]:
        """Convert scope to dictionary"""
        result = {}
        if self.parent:
            result.update(self.parent.to_dict())
        result.update(self.variables)
        return result


class DataTransformer:
    """Transforms data between formats"""

    @staticmethod
    def transform(
        data: Any,
        transformation: dict[str, Any],
    ) -> Any:
        """Apply transformation to data"""
        transform_type = transformation.get("type", "identity")

        if transform_type == "identity":
            return data

        if transform_type == "map":
            mapping = transformation.get("mapping", {})
            if isinstance(data, list):
                # Map each element in the list (consistent with filter/reduce/sort)
                return [
                    {new_key: item.get(old_key) for new_key, old_key in mapping.items()}
                    if isinstance(item, dict) else item
                    for item in data
                ]
            if isinstance(data, dict):
                return {
                    new_key: data.get(old_key)
                    for new_key, old_key in mapping.items()
                }
            return data

        if transform_type == "filter":
            if isinstance(data, list):
                predicate = transformation.get("predicate")
                return [
                    item for item in data
                    if ExpressionEvaluator.evaluate_predicate(item, predicate)
                ]
            return data

        if transform_type == "reduce":
            if isinstance(data, list):
                initial = transformation.get("initial", None)
                operation = transformation.get("operation", "sum")
                return DataTransformer._reduce_operation(data, operation, initial)
            return data

        if transform_type == "flatten":
            if isinstance(data, list):
                depth = transformation.get("depth", 1)
                return DataTransformer._flatten(data, depth)
            return data

        if transform_type == "group":
            if isinstance(data, list):
                key_expr = transformation.get("key")
                return DataTransformer._group_by(data, key_expr)
            return data

        if transform_type == "sort":
            if isinstance(data, list):
                key_expr = transformation.get("key")
                reverse = transformation.get("reverse", False)
                return sorted(
                    data,
                    key=lambda x: ExpressionEvaluator.evaluate_expression(x, key_expr),
                    reverse=reverse,
                )
            return data

        if transform_type == "merge":
            if isinstance(data, list):
                return {k: v for item in data if isinstance(item, dict) for k, v in item.items()}
            return data

        if transform_type == "template":
            template = transformation.get("template", "")
            return ExpressionEvaluator.render_template(template, data)

        return data

    @staticmethod
    def _reduce_operation(data: list, operation: str, initial: Any) -> Any:
        """Perform reduce operation"""
        if operation == "sum":
            return sum(data) if data else initial
        if operation == "product":
            result = initial or 1
            for item in data:
                result *= item
            return result
        if operation == "concat":
            result = initial or ""
            for item in data:
                result += str(item)
            return result
        if operation == "max":
            return max(data) if data else initial
        if operation == "min":
            return min(data) if data else initial
        return initial

    @staticmethod
    def _flatten(data: list, depth: int) -> list:
        """Flatten nested list"""
        if depth <= 0:
            return data
        result = []
        for item in data:
            if isinstance(item, list):
                result.extend(DataTransformer._flatten(item, depth - 1))
            else:
                result.append(item)
        return result

    @staticmethod
    def _group_by(data: list, key_expr: str) -> dict[str, list]:
        """Group list by key expression"""
        result = {}
        for item in data:
            key = ExpressionEvaluator.evaluate_expression(item, key_expr)
            key_str = str(key)
            if key_str not in result:
                result[key_str] = []
            result[key_str].append(item)
        return result


class ExpressionEvaluator:
    """Evaluates expressions and templates"""

    # Supported operators.
    # NOTE: ordering matters — the evaluate() loop splits on the FIRST matching
    # operator, so looser-binding operators (comparison/logical) are listed
    # before tighter-binding arithmetic so that e.g. "$a + $b > $c" splits on
    # ">" first (outermost), yielding ($a + $b) > $c.
    OPERATORS = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
        "and": lambda a, b: a and b,
        "or": lambda a, b: a or b,
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
        "contains": lambda a, b: b in a if isinstance(a, (str, list)) else False,
        "starts_with": lambda a, b: a.startswith(b) if isinstance(a, str) else False,
        "ends_with": lambda a, b: a.endswith(b) if isinstance(a, str) else False,
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "*": lambda a, b: a * b,
        "/": lambda a, b: a / b,
    }

    @staticmethod
    def evaluate(expression: str, context: dict[str, Any]) -> Any:
        """Evaluate expression in context"""
        if not isinstance(expression, str):
            return expression

        expression = expression.strip()

        # Handle literals
        if expression.startswith('"') and expression.endswith('"'):
            return expression[1:-1]
        if expression.startswith("'") and expression.endswith("'"):
            return expression[1:-1]
        if expression.lower() in ("true", "false"):
            return expression.lower() == "true"
        if expression.lower() in ("null", "none"):
            return None

        # Try to parse as number
        try:
            if "." in expression:
                return float(expression)
            return int(expression)
        except ValueError:
            pass

        # Handle operators BEFORE variable references so that "$x > $y" is
        # correctly split on the operator rather than mis-resolved as a single
        # variable named "x > $y".
        for op in ExpressionEvaluator.OPERATORS:
            if f" {op} " in expression:
                parts = expression.split(f" {op} ", 1)
                left = ExpressionEvaluator.evaluate(parts[0], context)
                right = ExpressionEvaluator.evaluate(parts[1], context)
                return ExpressionEvaluator.OPERATORS[op](left, right)

        # Handle variable references (simple $var with no operators)
        if expression.startswith("$"):
            var_name = expression[1:]
            return ExpressionEvaluator._resolve_variable(var_name, context)

        # Handle function calls
        if "(" in expression and ")" in expression:
            return ExpressionEvaluator._evaluate_function(expression, context)

        # Default: treat as variable reference
        return context.get(expression)

    @staticmethod
    def evaluate_predicate(item: Any, predicate: str) -> bool:
        """Evaluate predicate for filtering"""
        context = {"item": item}
        if isinstance(item, dict):
            context.update(item)
        result = ExpressionEvaluator.evaluate(predicate, context)
        return bool(result)

    @staticmethod
    def evaluate_expression(item: Any, expression: str) -> Any:
        """Evaluate expression for mapping/grouping"""
        context = {"item": item}
        if isinstance(item, dict):
            context.update(item)
        return ExpressionEvaluator.evaluate(expression, context)

    @staticmethod
    def _resolve_variable(var_name: str, context: dict[str, Any]) -> Any:
        """Resolve variable reference"""
        # Handle nested access: $obj.field.subfield
        parts = var_name.split(".")
        value = context.get(parts[0])

        for part in parts[1:]:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None

        return value

    @staticmethod
    def _evaluate_function(expression: str, context: dict[str, Any]) -> Any:
        """Evaluate function call"""
        match = re.match(r"(\w+)\((.*)\)", expression)
        if not match:
            return None

        func_name = match.group(1)
        args_str = match.group(2)

        # Parse arguments
        args = [
            ExpressionEvaluator.evaluate(arg.strip(), context)
            for arg in args_str.split(",")
            if arg.strip()
        ]

        # Built-in functions
        if func_name == "len":
            return len(args[0]) if args else 0
        if func_name == "str":
            return str(args[0]) if args else ""
        if func_name == "int":
            return int(args[0]) if args else 0
        if func_name == "float":
            return float(args[0]) if args else 0.0
        if func_name == "bool":
            return bool(args[0]) if args else False
        if func_name == "list":
            return list(args[0]) if args and hasattr(args[0], "__iter__") else []
        if func_name == "dict":
            return dict(args[0]) if args and isinstance(args[0], dict) else {}
        if func_name == "min":
            return min(args) if args else None
        if func_name == "max":
            return max(args) if args else None
        if func_name == "sum":
            return sum(args) if args else 0
        if func_name == "abs":
            return abs(args[0]) if args else 0
        if func_name == "upper":
            return args[0].upper() if args and isinstance(args[0], str) else ""
        if func_name == "lower":
            return args[0].lower() if args and isinstance(args[0], str) else ""
        if func_name == "strip":
            return args[0].strip() if args and isinstance(args[0], str) else ""
        if func_name == "split":
            sep = args[1] if len(args) > 1 else " "
            return args[0].split(sep) if args and isinstance(args[0], str) else []
        if func_name == "join":
            sep = args[0] if args else ""
            items = args[1] if len(args) > 1 else []
            return sep.join(str(i) for i in items) if hasattr(items, "__iter__") else ""

        return None

    @staticmethod
    def render_template(template: str, context: dict[str, Any] | Any) -> str:
        """Render template with context"""
        if not isinstance(context, dict):
            context = {"value": context}

        # Replace ${var} patterns
        def replace_var(match):
            var_expr = match.group(1)
            value = ExpressionEvaluator.evaluate(var_expr, context)
            return str(value) if value is not None else ""

        result = re.sub(r"\$\{([^}]+)\}", replace_var, template)

        # Replace $var patterns
        def replace_simple_var(match):
            var_name = match.group(1)
            value = context.get(var_name)
            return str(value) if value is not None else ""

        result = re.sub(r"\$(\w+)", replace_simple_var, result)

        return result


class DataFlowManager:
    """Manages data flow in workflows"""

    def __init__(self):
        self.global_scope = VariableScope(level=ScopeLevel.GLOBAL)
        self.current_scope = self.global_scope
        self.scope_stack: list[VariableScope] = [self.global_scope]

    def push_scope(self, level: ScopeLevel) -> VariableScope:
        """Push new scope"""
        new_scope = self.current_scope.create_child(level)
        self.scope_stack.append(new_scope)
        self.current_scope = new_scope
        return new_scope

    def pop_scope(self) -> VariableScope | None:
        """Pop current scope"""
        if len(self.scope_stack) > 1:
            popped = self.scope_stack.pop()
            self.current_scope = self.scope_stack[-1]
            return popped
        return None

    def set_variable(self, name: str, value: Any) -> None:
        """Set variable in current scope"""
        self.current_scope.set(name, value)

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get variable from current scope"""
        return self.current_scope.get(name, default)

    def evaluate_expression(self, expression: str) -> Any:
        """Evaluate expression in current scope"""
        context = self.current_scope.to_dict()
        return ExpressionEvaluator.evaluate(expression, context)

    def render_template(self, template: str) -> str:
        """Render template in current scope"""
        context = self.current_scope.to_dict()
        return ExpressionEvaluator.render_template(template, context)

    def transform_data(
        self,
        data: Any,
        transformation: dict[str, Any],
    ) -> Any:
        """Transform data"""
        return DataTransformer.transform(data, transformation)

    def get_scope_snapshot(self) -> dict[str, Any]:
        """Get snapshot of current scope"""
        return {
            "level": self.current_scope.level,
            "variables": self.current_scope.to_dict(),
            "depth": len(self.scope_stack),
        }
