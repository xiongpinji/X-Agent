"""Execute skill workflows with variable substitution and control flow."""

import asyncio
import logging
import re
import time
from typing import Any, Optional

from backend.app.core.skills.schema import SkillDefinition, SkillResult, StepResult

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Execute skill workflows with full control flow support.

    Executes skill steps sequentially with:
    - Template variable substitution ({{inputs.X}}, {{steps.Y.output}})
    - Conditional execution (skip steps based on expressions)
    - Iteration support (foreach loops over lists)
    - Error handling and step result tracking

    Attributes:
        tool_registry: Tool registry for looking up tools
        max_iterations: Maximum foreach loop iterations (safety limit)
    """

    def __init__(self, tool_registry: Any, max_iterations: int = 1000):
        """Initialize executor.

        Args:
            tool_registry: Tool registry to get tools from
            max_iterations: Max iterations for foreach loops
        """
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    async def execute(
        self,
        skill: SkillDefinition,
        inputs: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> SkillResult:
        """Execute a skill with given inputs.

        Processes all steps in order, with support for:
        - Variable substitution: {{inputs.name}}, {{steps.step_id.output}}
        - Conditional execution: skip if condition is false
        - Iteration: repeat step for each item in list
        - Error handling: collect errors but continue processing

        Args:
            skill: Skill definition to execute
            inputs: Input values for skill parameters
            context: Optional execution context

        Returns:
            SkillResult with outputs, errors, and step results
        """
        start_time = time.time()
        step_results: list[StepResult] = []
        variables: dict[str, Any] = {
            "inputs": inputs,
            "context": context or {},
            "steps": {},
        }
        errors: list[str] = []

        logger.info(f"Executing skill: {skill.name} v{skill.version}")

        for step in skill.steps:
            try:
                # Evaluate condition if present
                if step.condition:
                    should_run = self._evaluate_condition(step.condition, variables)
                    if not should_run:
                        logger.debug(f"Skipping step {step.id} (condition false)")
                        continue

                # Handle foreach iteration
                if step.foreach:
                    results = await self._execute_step_foreach(
                        step, variables, skill
                    )
                    variables["steps"][step.id] = {
                        "output": results,
                        "count": len(results),
                    }
                    for i, result in enumerate(results):
                        step_results.append(
                            StepResult(
                                step_id=f"{step.id}[{i}]",
                                success=True,
                                output=result,
                                duration_ms=0,
                            )
                        )
                else:
                    # Normal step execution
                    result = await self._execute_step(step, variables, skill)
                    step_results.append(result)

                    if result.success:
                        if step.output_var:
                            variables["steps"][step.id] = {
                                "output": result.output,
                            }
                        else:
                            variables["steps"][step.id] = {
                                "output": result.output,
                            }
                    else:
                        errors.append(f"Step {step.id} failed: {result.error}")

            except Exception as e:
                logger.error(f"Error executing step {step.id}: {e}")
                errors.append(f"Step {step.id} error: {str(e)}")
                step_results.append(
                    StepResult(
                        step_id=step.id,
                        success=False,
                        error=str(e),
                        duration_ms=0,
                    )
                )

        # Extract outputs
        outputs: dict[str, Any] = {}
        for output_def in skill.outputs:
            try:
                outputs[output_def.name] = self._resolve_template(
                    output_def.value, variables
                )
            except Exception as e:
                logger.error(f"Failed to extract output {output_def.name}: {e}")
                errors.append(f"Output extraction failed for {output_def.name}: {str(e)}")

        duration_ms = (time.time() - start_time) * 1000
        success = len(errors) == 0

        logger.info(
            f"Skill {skill.name} completed. Success={success}, "
            f"Steps={len(step_results)}, Errors={len(errors)}, "
            f"Duration={duration_ms:.0f}ms"
        )

        return SkillResult(
            skill_name=skill.name,
            success=success,
            outputs=outputs,
            errors=errors,
            step_results=step_results,
            total_duration_ms=duration_ms,
        )

    async def _execute_step(
        self, step: Any, variables: dict[str, Any], skill: SkillDefinition
    ) -> StepResult:
        """Execute a single step.

        Args:
            step: Step to execute
            variables: Available variables for substitution
            skill: Parent skill definition

        Returns:
            StepResult with output or error
        """
        start_time = time.time()
        step_id = step.id

        try:
            # Resolve arguments with template substitution
            resolved_args = {}
            for key, value in step.args.items():
                if isinstance(value, str):
                    resolved_args[key] = self._resolve_template(value, variables)
                else:
                    resolved_args[key] = value

            logger.debug(f"Executing step {step_id} with tool {step.tool}")
            logger.debug(f"Resolved args: {resolved_args}")

            # Get tool and execute
            tool = await self.tool_registry.get_tool(step.tool)
            if not tool:
                raise ValueError(f"Tool not found: {step.tool}")

            output = await tool.call(**resolved_args)

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Step {step_id} completed in {duration_ms:.0f}ms")

            return StepResult(
                step_id=step_id,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Step {step_id} failed: {e}")
            return StepResult(
                step_id=step_id,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def _execute_step_foreach(
        self, step: Any, variables: dict[str, Any], skill: SkillDefinition
    ) -> list[Any]:
        """Execute a step with foreach iteration.

        Args:
            step: Step with foreach
            variables: Available variables
            skill: Parent skill

        Returns:
            List of outputs from each iteration
        """
        # Resolve foreach expression to get list
        foreach_expr = step.foreach
        items = self._resolve_template(foreach_expr, variables)

        if not isinstance(items, list):
            raise ValueError(
                f"Foreach expression must resolve to a list, got {type(items)}"
            )

        if len(items) > self.max_iterations:
            raise ValueError(
                f"Foreach iteration count ({len(items)}) exceeds maximum "
                f"({self.max_iterations})"
            )

        results = []
        for i, item in enumerate(items):
            # Create loop variable
            loop_vars = dict(variables)
            loop_vars["item"] = item
            loop_vars["index"] = i

            # Execute step with loop context
            result = await self._execute_step(step, loop_vars, skill)
            if result.success:
                results.append(result.output)
            else:
                raise RuntimeError(
                    f"Foreach iteration {i} failed: {result.error}"
                )

        logger.debug(f"Step {step.id} foreach completed {len(results)} iterations")
        return results

    def _resolve_template(self, template: str, variables: dict[str, Any]) -> Any:
        """Resolve {{...}} template expressions.

        Supports:
        - {{inputs.key}} - input values
        - {{steps.step_id.output}} - step outputs
        - {{context.key}} - context values
        - {{item}} - foreach current item
        - {{index}} - foreach current index

        Args:
            template: Template string with {{...}} expressions
            variables: Available variables for substitution

        Returns:
            Resolved value (string if no substitution, else evaluated)

        Raises:
            ValueError: If template references undefined variables
        """
        if not isinstance(template, str):
            return template

        # Find all {{...}} expressions
        pattern = r"\{\{([^}]+)\}\}"
        matches = re.findall(pattern, template)

        if not matches:
            return template

        result = template
        for expr in matches:
            value = self._get_variable(expr, variables)
            if value is None:
                raise ValueError(f"Undefined variable in template: {expr}")

            # Replace in template
            placeholder = f"{{{{{expr}}}}}"
            if isinstance(value, str):
                result = result.replace(placeholder, value)
            else:
                # If only expression in template, return the object
                if result == placeholder:
                    result = value
                else:
                    # Convert to string for inline substitution
                    result = result.replace(placeholder, str(value))

        return result

    @staticmethod
    def _get_variable(expr: str, variables: dict[str, Any]) -> Any:
        """Get a variable from expression path.

        Args:
            expr: Expression like "inputs.key" or "steps.step_id.output"
            variables: Variables dict

        Returns:
            Resolved value or None if not found
        """
        parts = expr.strip().split(".")
        current = variables

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                return None

        return current

    def _evaluate_condition(self, condition: str, variables: dict[str, Any]) -> bool:
        """Evaluate a boolean condition expression.

        Supports:
        - Simple equality: steps.step_id.output == "value"
        - Existence checks: steps.step_id
        - Complex expressions are resolved as truthy/falsy

        Args:
            condition: Condition expression
            variables: Available variables

        Returns:
            Boolean result of condition evaluation
        """
        try:
            # Try to resolve as template first
            resolved = self._resolve_template(condition, variables)

            # Evaluate as boolean
            if isinstance(resolved, bool):
                return resolved
            elif isinstance(resolved, str):
                # Handle string comparisons
                if "==" in condition:
                    return self._evaluate_equality_condition(condition, variables)
                return resolved.lower() not in ("false", "0", "")
            else:
                return bool(resolved)

        except Exception as e:
            logger.warning(f"Condition evaluation error: {e}, defaulting to True")
            return True

    @staticmethod
    def _evaluate_equality_condition(
        condition: str, variables: dict[str, Any]
    ) -> bool:
        """Evaluate equality condition like 'steps.x == "value"'.

        Args:
            condition: Equality condition
            variables: Available variables

        Returns:
            Result of equality check
        """
        pattern = r"(.+?)\s*==\s*(.+)"
        match = re.match(pattern, condition)

        if not match:
            return bool(condition)

        left_expr, right_expr = match.groups()

        # Get values
        executor = SkillExecutor(tool_registry=None)
        left = executor._get_variable(left_expr.strip(), variables)
        right_str = right_expr.strip()

        # Handle string literals
        if right_str.startswith('"') and right_str.endswith('"'):
            right = right_str[1:-1]
        elif right_str.startswith("'") and right_str.endswith("'"):
            right = right_str[1:-1]
        else:
            right = executor._get_variable(right_str, variables)

        return left == right
