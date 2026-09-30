"""Tests for deterministic declarative constraint evaluation."""

import pytest

from toolpolicy.constraints import evaluate_policy_constraint
from toolpolicy.models import (
    ConstraintEvaluationStatus,
    ConstraintOperator,
    ConstraintSource,
    ExecutionContext,
    PolicyConstraint,
    PolicyOutcome,
    ToolInvocation,
)


def build_constraint(
    operator: ConstraintOperator,
    value: object,
    source: ConstraintSource = ConstraintSource.ARGUMENTS,
) -> PolicyConstraint:
    """Build one validated constraint for evaluator tests."""

    return PolicyConstraint(
        source=source,
        field="amount" if source is ConstraintSource.ARGUMENTS else "customer_verified",
        operator=operator,
        value=value,
        on_failure=PolicyOutcome.DENY,
    )


def evaluate_constraint(
    policy_constraint: PolicyConstraint,
    arguments: dict[str, object] | None = None,
    context_values: dict[str, object] | None = None,
):
    """Evaluate a constraint with separate agent and trusted input models."""

    return evaluate_policy_constraint(
        policy_constraint,
        ToolInvocation(tool_name="test_tool", arguments=arguments or {}),
        ExecutionContext(values=context_values or {}),
    )


@pytest.mark.parametrize(
    ("operator", "expected_value", "actual_value"),
    [
        (ConstraintOperator.EQUALS, "approved", "approved"),
        (ConstraintOperator.NOT_EQUALS, "denied", "approved"),
        (ConstraintOperator.LESS_THAN, 5000, 4999),
        (ConstraintOperator.LESS_THAN_OR_EQUAL, 5000, 5000),
        (ConstraintOperator.GREATER_THAN, 5000, 5001),
        (ConstraintOperator.GREATER_THAN_OR_EQUAL, 5000, 5000),
        (ConstraintOperator.IN, ["support", "administrator"], "support"),
    ],
)
def test_supported_operators_pass_when_the_constraint_is_satisfied(
    operator: ConstraintOperator,
    expected_value: object,
    actual_value: object,
) -> None:
    constraint = build_constraint(operator, expected_value)

    evaluation = evaluate_constraint(constraint, arguments={"amount": actual_value})

    assert evaluation.status is ConstraintEvaluationStatus.PASSED
    assert evaluation.reason_code == "constraint_satisfied"
    assert evaluation.failure_outcome is None


@pytest.mark.parametrize(
    ("operator", "expected_value", "actual_value"),
    [
        (ConstraintOperator.EQUALS, "approved", "denied"),
        (ConstraintOperator.NOT_EQUALS, "approved", "approved"),
        (ConstraintOperator.LESS_THAN, 5000, 5000),
        (ConstraintOperator.LESS_THAN_OR_EQUAL, 5000, 5001),
        (ConstraintOperator.GREATER_THAN, 5000, 5000),
        (ConstraintOperator.GREATER_THAN_OR_EQUAL, 5000, 4999),
        (ConstraintOperator.IN, ["support", "administrator"], "customer"),
    ],
)
def test_false_constraints_fail_closed(
    operator: ConstraintOperator,
    expected_value: object,
    actual_value: object,
) -> None:
    constraint = build_constraint(operator, expected_value)

    evaluation = evaluate_constraint(constraint, arguments={"amount": actual_value})

    assert evaluation.status is ConstraintEvaluationStatus.FAILED
    assert evaluation.reason_code == "constraint_not_satisfied"
    assert evaluation.failure_outcome is PolicyOutcome.DENY


def test_missing_argument_is_a_failure_result() -> None:
    constraint = build_constraint(ConstraintOperator.LESS_THAN_OR_EQUAL, 5000)

    evaluation = evaluate_constraint(constraint)

    assert evaluation.status is ConstraintEvaluationStatus.MISSING_FIELD
    assert evaluation.reason_code == "constraint_field_missing"
    assert evaluation.failure_outcome is PolicyOutcome.DENY


def test_missing_trusted_context_value_is_a_failure_result() -> None:
    constraint = build_constraint(
        ConstraintOperator.EQUALS,
        True,
        ConstraintSource.CONTEXT,
    )

    evaluation = evaluate_constraint(constraint, context_values={})

    assert evaluation.status is ConstraintEvaluationStatus.MISSING_FIELD
    assert evaluation.failure_outcome is PolicyOutcome.DENY


@pytest.mark.parametrize(
    ("operator", "expected_value", "actual_value"),
    [
        (ConstraintOperator.EQUALS, 1, True),
        (ConstraintOperator.NOT_EQUALS, "customer", 1),
        (ConstraintOperator.LESS_THAN, 5000, "4999"),
        (ConstraintOperator.GREATER_THAN_OR_EQUAL, 5000, True),
        (ConstraintOperator.IN, [1, 2], "1"),
    ],
)
def test_incompatible_value_types_fail_closed(
    operator: ConstraintOperator,
    expected_value: object,
    actual_value: object,
) -> None:
    constraint = build_constraint(operator, expected_value)

    evaluation = evaluate_constraint(constraint, arguments={"amount": actual_value})

    assert evaluation.status is ConstraintEvaluationStatus.TYPE_MISMATCH
    assert evaluation.reason_code == "constraint_type_mismatch"
    assert evaluation.failure_outcome is PolicyOutcome.DENY


def test_equality_uses_type_sensitive_nested_json_comparison() -> None:
    constraint = build_constraint(
        ConstraintOperator.EQUALS,
        {"verified": True, "limits": [1, 2]},
    )

    evaluation = evaluate_constraint(
        constraint,
        arguments={"amount": {"verified": 1, "limits": [1, 2]}},
    )

    assert evaluation.status is ConstraintEvaluationStatus.FAILED


def test_context_constraint_reads_only_trusted_context() -> None:
    constraint = build_constraint(
        ConstraintOperator.EQUALS,
        True,
        ConstraintSource.CONTEXT,
    )

    evaluation = evaluate_constraint(
        constraint,
        arguments={"customer_verified": False},
        context_values={"customer_verified": True},
    )

    assert evaluation.status is ConstraintEvaluationStatus.PASSED
