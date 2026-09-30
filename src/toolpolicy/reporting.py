"""Human-readable rendering for structured policy decisions."""

import json

from rich.console import Console

from toolpolicy.models import (
    ConstraintEvaluation,
    ConstraintOperator,
    PolicyDecision,
    PolicyDefinition,
)

_DECISION_REASONS = {
    "unknown_tool": "No policy exists for the requested tool.",
    "constraint_evaluation_error": "Constraint evaluation failed safely.",
    "constraint_failure_deny": "A policy constraint denied the request.",
    "policy_configured_deny": "The matched policy denies this tool.",
    "constraint_failure_requires_approval": "A policy constraint requires approval.",
    "policy_configured_allow": "The matched policy allows this tool.",
    "policy_requires_approval": "Human approval is required for this action.",
}

_OPERATOR_SYMBOLS = {
    ConstraintOperator.EQUALS: "=",
    ConstraintOperator.NOT_EQUALS: "!=",
    ConstraintOperator.LESS_THAN: "<",
    ConstraintOperator.LESS_THAN_OR_EQUAL: "<=",
    ConstraintOperator.GREATER_THAN: ">",
    ConstraintOperator.GREATER_THAN_OR_EQUAL: ">=",
    ConstraintOperator.IN: "in",
}


def render_policy_decision(
    console: Console,
    policy_definition: PolicyDefinition,
    policy_decision: PolicyDecision,
) -> None:
    """Render a decision without re-evaluating policy semantics."""

    console.print("[bold]ToolPolicy[/bold]")
    console.print()
    _render_section(console, "Tool", policy_decision.tool_name)
    risk = policy_decision.risk.value if policy_decision.risk else "unknown"
    _render_section(console, "Risk", risk)
    _render_section(console, "Decision", policy_decision.outcome.value.upper())
    _render_section(console, "Reason", _decision_reason(policy_decision))

    rule = _failed_constraint_rule(policy_definition, policy_decision)
    if rule is not None:
        _render_section(console, "Rule", rule)


def _render_section(console: Console, heading: str, value: str) -> None:
    console.print(f"[bold]{heading}[/bold]")
    console.print(f"  {value}")
    console.print()


def _decision_reason(policy_decision: PolicyDecision) -> str:
    return " ".join(
        _DECISION_REASONS.get(reason_code, "Policy decision completed.")
        for reason_code in policy_decision.reason_codes
    )


def _failed_constraint_rule(
    policy_definition: PolicyDefinition,
    policy_decision: PolicyDecision,
) -> str | None:
    tool_policy = policy_definition.tools.get(policy_decision.tool_name)
    if tool_policy is None:
        return None

    failed_evaluation = next(
        (
            evaluation
            for evaluation in policy_decision.constraint_evaluations
            if evaluation.failure_outcome is not None
        ),
        None,
    )
    if failed_evaluation is None:
        return None

    matching_constraint = next(
        (
            policy_constraint
            for policy_constraint in tool_policy.constraints
            if _matches_evaluation(policy_constraint, failed_evaluation)
        ),
        None,
    )
    if matching_constraint is None:
        return None

    rendered_value = json.dumps(matching_constraint.value, separators=(",", ":"))
    return (
        f"{matching_constraint.source.value}.{matching_constraint.field} "
        f"{_OPERATOR_SYMBOLS[matching_constraint.operator]} {rendered_value}"
    )


def _matches_evaluation(
    policy_constraint: object,
    constraint_evaluation: ConstraintEvaluation,
) -> bool:
    return (
        policy_constraint.source is constraint_evaluation.source
        and policy_constraint.field == constraint_evaluation.field
        and policy_constraint.operator is constraint_evaluation.operator
    )
