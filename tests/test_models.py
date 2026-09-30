"""Tests for Phase 1 domain contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from toolpolicy.models import (
    AuditEvent,
    ConstraintEvaluation,
    ConstraintEvaluationStatus,
    ConstraintOperator,
    ConstraintSource,
    ExecutionContext,
    PolicyConstraint,
    PolicyDecision,
    PolicyDefinition,
    PolicyOutcome,
    RiskLevel,
    ToolInvocation,
)


def valid_constraint_payload(operator: str = "less_than_or_equal") -> dict[str, object]:
    """Build a valid numeric constraint payload for model tests."""

    return {
        "source": "arguments",
        "field": "amount",
        "operator": operator,
        "value": 5000,
        "on_failure": "deny",
    }


def valid_policy_payload() -> dict[str, object]:
    """Build a valid policy payload for model tests."""

    return {
        "version": "1",
        "tools": {
            "transfer_funds": {
                "risk": "consequential",
                "decision": "require_approval",
                "constraints": [valid_constraint_payload()],
            }
        },
    }


def test_valid_tool_invocation_accepts_nested_json_arguments() -> None:
    invocation = ToolInvocation(
        tool_name="transfer_funds",
        arguments={"amount": 5000, "recipients": ["account-1"], "metadata": None},
        invocation_id="invocation-123",
    )

    assert invocation.arguments["amount"] == 5000
    assert invocation.invocation_id == "invocation-123"


@pytest.mark.parametrize("arguments", [{"invalid": object()}, {"amount": float("inf")}])
def test_invalid_tool_invocation_rejects_non_json_arguments(
    arguments: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ToolInvocation(tool_name="transfer_funds", arguments=arguments)


def test_valid_execution_context_is_independent_from_invocation_arguments() -> None:
    execution_context = ExecutionContext(
        values={"customer_verified": True, "user_role": "support"}
    )

    assert execution_context.values == {
        "customer_verified": True,
        "user_role": "support",
    }


def test_valid_policy_definition() -> None:
    policy_definition = PolicyDefinition.model_validate(valid_policy_payload())

    assert policy_definition.tools["transfer_funds"].risk is RiskLevel.CONSEQUENTIAL


@pytest.mark.parametrize(
    "payload",
    [
        {**valid_policy_payload(), "version": "2"},
        {**valid_policy_payload(), "unexpected": "field"},
        {"version": "1", "tools": {"tool": {"risk": "unknown", "decision": "allow"}}},
    ],
)
def test_invalid_policy_definition_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PolicyDefinition.model_validate(payload)


@pytest.mark.parametrize("operator", list(ConstraintOperator))
def test_supported_constraint_operators_are_accepted(
    operator: ConstraintOperator,
) -> None:
    payload = valid_constraint_payload(operator.value)
    if operator is ConstraintOperator.IN:
        payload["value"] = [1000, 5000]

    constraint = PolicyConstraint.model_validate(payload)

    assert constraint.operator is operator


def test_unsupported_constraint_operator_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PolicyConstraint.model_validate(
            {**valid_constraint_payload(), "operator": "contains"}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {**valid_constraint_payload(), "operator": "in", "value": "not-a-list"},
        {**valid_constraint_payload(), "operator": "less_than", "value": "5000"},
        {**valid_constraint_payload(), "on_failure": "allow"},
        {**valid_constraint_payload(), "expression": "amount <= 5000"},
    ],
)
def test_malformed_constraints_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PolicyConstraint.model_validate(payload)


def test_policy_serialization_round_trip() -> None:
    policy_definition = PolicyDefinition.model_validate(valid_policy_payload())

    restored_policy = PolicyDefinition.model_validate_json(
        policy_definition.model_dump_json()
    )

    assert restored_policy == policy_definition


def test_audit_event_serialization_round_trip_excludes_raw_inputs() -> None:
    constraint_evaluation = ConstraintEvaluation(
        source=ConstraintSource.CONTEXT,
        field="customer_verified",
        operator=ConstraintOperator.EQUALS,
        status=ConstraintEvaluationStatus.PASSED,
        reason_code="constraint_satisfied",
    )
    audit_event = AuditEvent(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        policy_fingerprint="sha256:policy-fingerprint",
        tool_name="get_account_balance",
        outcome=PolicyOutcome.ALLOW,
        risk=RiskLevel.READ,
        reason_codes=("policy_allow",),
        constraint_evaluations=(constraint_evaluation,),
    )

    serialized_event = audit_event.model_dump_json()
    restored_event = AuditEvent.model_validate_json(serialized_event)

    assert restored_event == audit_event
    assert "customer_verified" in serialized_event
    assert "true" not in serialized_event.lower()


def test_policy_outcomes_are_exact_and_explicit() -> None:
    assert set(PolicyOutcome) == {
        PolicyOutcome.ALLOW,
        PolicyOutcome.DENY,
        PolicyOutcome.REQUIRE_APPROVAL,
    }


def test_risk_levels_are_exact_and_explicit() -> None:
    assert set(RiskLevel) == {
        RiskLevel.READ,
        RiskLevel.WRITE,
        RiskLevel.CONSEQUENTIAL,
        RiskLevel.DESTRUCTIVE,
    }


def test_policy_decision_requires_structured_reason_codes() -> None:
    with pytest.raises(ValidationError):
        PolicyDecision(
            outcome=PolicyOutcome.DENY,
            tool_name="unknown_tool",
            reason_codes=(),
        )
