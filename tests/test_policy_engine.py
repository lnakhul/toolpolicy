"""Tests for deterministic PolicyEngine decision orchestration."""

from pathlib import Path

import pytest

from toolpolicy import PolicyEngine
from toolpolicy.models import (
    ConstraintEvaluationStatus,
    ExecutionContext,
    PolicyDefinition,
    PolicyOutcome,
    ToolInvocation,
)
from toolpolicy.parsing import load_policy_definition

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"


@pytest.fixture
def banking_policy_engine() -> PolicyEngine:
    """Create an engine from the representative policy fixture."""

    return PolicyEngine(
        load_policy_definition(FIXTURE_DIRECTORY / "banking-agent-policy.yaml")
    )


def evaluate_tool(
    policy_engine: PolicyEngine,
    tool_name: str,
    arguments: dict[str, object] | None = None,
    context_values: dict[str, object] | None = None,
):
    """Evaluate one tool with explicitly separated agent and trusted inputs."""

    return policy_engine.evaluate(
        ToolInvocation(tool_name=tool_name, arguments=arguments or {}),
        ExecutionContext(values=context_values or {}),
    )


def test_allows_unconstrained_read(banking_policy_engine: PolicyEngine) -> None:
    decision = evaluate_tool(banking_policy_engine, "get_customer")

    assert decision.outcome is PolicyOutcome.ALLOW
    assert decision.reason_codes == ("policy_configured_allow",)


def test_allows_verified_read(banking_policy_engine: PolicyEngine) -> None:
    decision = evaluate_tool(
        banking_policy_engine,
        "get_account_balance",
        context_values={"customer_verified": True},
    )

    assert decision.outcome is PolicyOutcome.ALLOW
    assert (
        decision.constraint_evaluations[0].status is ConstraintEvaluationStatus.PASSED
    )


def test_denies_unverified_read(banking_policy_engine: PolicyEngine) -> None:
    decision = evaluate_tool(
        banking_policy_engine,
        "get_account_balance",
        context_values={"customer_verified": False},
    )

    assert decision.outcome is PolicyOutcome.DENY
    assert decision.reason_codes == ("constraint_failure_deny",)


def test_allows_write_when_policy_permits_it() -> None:
    policy_definition = PolicyDefinition.model_validate(
        {
            "version": "1",
            "tools": {
                "update_address": {
                    "risk": "write",
                    "decision": "allow",
                }
            },
        }
    )
    policy_engine = PolicyEngine(policy_definition)

    decision = evaluate_tool(policy_engine, "update_address")

    assert decision.outcome is PolicyOutcome.ALLOW


def test_requires_approval_for_consequential_action(
    banking_policy_engine: PolicyEngine,
) -> None:
    decision = evaluate_tool(banking_policy_engine, "freeze_card")

    assert decision.outcome is PolicyOutcome.REQUIRE_APPROVAL
    assert decision.reason_codes == ("policy_requires_approval",)


def test_denies_destructive_action(banking_policy_engine: PolicyEngine) -> None:
    decision = evaluate_tool(banking_policy_engine, "close_account")

    assert decision.outcome is PolicyOutcome.DENY
    assert decision.reason_codes == ("policy_configured_deny",)


@pytest.mark.parametrize("amount", [0, 4999, 5000])
def test_transfer_within_configured_limit_requires_approval(
    banking_policy_engine: PolicyEngine,
    amount: int,
) -> None:
    decision = evaluate_tool(
        banking_policy_engine,
        "transfer_funds",
        arguments={"amount": amount},
    )

    assert decision.outcome is PolicyOutcome.REQUIRE_APPROVAL
    assert (
        decision.constraint_evaluations[0].status is ConstraintEvaluationStatus.PASSED
    )


def test_transfer_exceeding_configured_limit_is_denied(
    banking_policy_engine: PolicyEngine,
) -> None:
    decision = evaluate_tool(
        banking_policy_engine,
        "transfer_funds",
        arguments={"amount": 5001},
    )

    assert decision.outcome is PolicyOutcome.DENY
    assert (
        decision.constraint_evaluations[0].status is ConstraintEvaluationStatus.FAILED
    )


def test_denies_unknown_tool_by_default(banking_policy_engine: PolicyEngine) -> None:
    decision = evaluate_tool(banking_policy_engine, "delete_customer")

    assert decision.outcome is PolicyOutcome.DENY
    assert decision.risk is None
    assert decision.reason_codes == ("unknown_tool",)


def test_missing_required_context_denies_read(
    banking_policy_engine: PolicyEngine,
) -> None:
    decision = evaluate_tool(banking_policy_engine, "get_account_balance")

    assert decision.outcome is PolicyOutcome.DENY
    assert (
        decision.constraint_evaluations[0].status
        is ConstraintEvaluationStatus.MISSING_FIELD
    )


def test_multiple_constraints_compose_with_deny_precedence() -> None:
    policy_definition = PolicyDefinition.model_validate(
        {
            "version": "1",
            "tools": {
                "transfer_funds": {
                    "risk": "consequential",
                    "decision": "allow",
                    "constraints": [
                        {
                            "source": "arguments",
                            "field": "amount",
                            "operator": "less_than_or_equal",
                            "value": 5000,
                            "on_failure": "deny",
                        },
                        {
                            "source": "context",
                            "field": "customer_verified",
                            "operator": "equals",
                            "value": True,
                            "on_failure": "require_approval",
                        },
                    ],
                }
            },
        }
    )
    policy_engine = PolicyEngine(policy_definition)

    decision = evaluate_tool(
        policy_engine,
        "transfer_funds",
        arguments={"amount": 5001},
        context_values={"customer_verified": True},
    )

    assert decision.outcome is PolicyOutcome.DENY
    assert len(decision.constraint_evaluations) == 2
    assert (
        decision.constraint_evaluations[1].status is ConstraintEvaluationStatus.PASSED
    )


def test_constraint_failure_can_require_approval() -> None:
    policy_definition = PolicyDefinition.model_validate(
        {
            "version": "1",
            "tools": {
                "update_address": {
                    "risk": "write",
                    "decision": "allow",
                    "constraints": [
                        {
                            "source": "context",
                            "field": "customer_verified",
                            "operator": "equals",
                            "value": True,
                            "on_failure": "require_approval",
                        }
                    ],
                }
            },
        }
    )
    policy_engine = PolicyEngine(policy_definition)

    decision = evaluate_tool(
        policy_engine,
        "update_address",
        context_values={"customer_verified": False},
    )

    assert decision.outcome is PolicyOutcome.REQUIRE_APPROVAL
    assert decision.reason_codes == ("constraint_failure_requires_approval",)


def test_configured_deny_cannot_be_transformed_into_allow() -> None:
    policy_definition = PolicyDefinition.model_validate(
        {
            "version": "1",
            "tools": {
                "close_account": {
                    "risk": "destructive",
                    "decision": "deny",
                    "constraints": [
                        {
                            "source": "arguments",
                            "field": "confirmation",
                            "operator": "equals",
                            "value": "CLOSE",
                            "on_failure": "require_approval",
                        }
                    ],
                }
            },
        }
    )
    policy_engine = PolicyEngine(policy_definition)

    decision = evaluate_tool(
        policy_engine,
        "close_account",
        arguments={"confirmation": "CLOSE"},
    )

    assert decision.outcome is PolicyOutcome.DENY
    assert decision.reason_codes == ("policy_configured_deny",)


def test_internal_constraint_error_fails_closed(
    banking_policy_engine: PolicyEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_evaluator_error(*_arguments: object) -> None:
        raise RuntimeError("unexpected evaluator failure")

    monkeypatch.setattr(
        "toolpolicy.policy_engine.evaluate_policy_constraint",
        raise_evaluator_error,
    )

    decision = evaluate_tool(
        banking_policy_engine,
        "transfer_funds",
        arguments={"amount": 5000},
    )

    assert decision.outcome is PolicyOutcome.DENY
    assert decision.reason_codes == ("constraint_evaluation_error",)
    assert decision.constraint_evaluations[0].status is ConstraintEvaluationStatus.ERROR


def test_engine_does_not_mutate_invocation_or_context(
    banking_policy_engine: PolicyEngine,
) -> None:
    tool_invocation = ToolInvocation(
        tool_name="transfer_funds",
        arguments={"amount": 5000},
    )
    execution_context = ExecutionContext(values={"customer_verified": True})

    banking_policy_engine.evaluate(tool_invocation, execution_context)

    assert tool_invocation.arguments == {"amount": 5000}
    assert execution_context.values == {"customer_verified": True}
