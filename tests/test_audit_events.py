"""Tests for deterministic, value-safe authorization audit events."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from toolpolicy import PolicyEngine
from toolpolicy.models import ExecutionContext, PolicyOutcome, ToolInvocation
from toolpolicy.parsing import load_policy_definition

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"
EVENT_ID = UUID("c41fc86a-745a-47cf-813c-e757bbb91094")
OCCURRED_AT = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def build_policy_engine() -> PolicyEngine:
    """Build an engine from the representative policy fixture."""

    return PolicyEngine(
        load_policy_definition(FIXTURE_DIRECTORY / "banking-agent-policy.yaml")
    )


def test_audit_event_records_safe_decision_metadata() -> None:
    policy_engine = build_policy_engine()
    tool_invocation = ToolInvocation(
        tool_name="transfer_funds",
        arguments={"amount": 5000},
        invocation_id="invocation-123",
    )
    policy_decision = policy_engine.evaluate(
        tool_invocation,
        ExecutionContext(values={"customer_verified": True}),
    )

    audit_event = policy_engine.create_audit_event(
        tool_invocation,
        policy_decision,
        event_id=EVENT_ID,
        occurred_at=OCCURRED_AT,
    )

    assert audit_event.policy_version == "1"
    assert audit_event.tool_name == "transfer_funds"
    assert audit_event.matched_policy_tool_name == "transfer_funds"
    assert audit_event.outcome is PolicyOutcome.REQUIRE_APPROVAL
    assert audit_event.decision_reason == "The matched policy requires approval."
    assert audit_event.constraint_evaluations == policy_decision.constraint_evaluations
    assert audit_event.policy_fingerprint.startswith("sha256:")


def test_audit_event_generation_is_deterministic_for_supplied_metadata() -> None:
    policy_engine = build_policy_engine()
    tool_invocation = ToolInvocation(
        tool_name="get_customer",
        arguments={},
        invocation_id="invocation-123",
    )
    policy_decision = policy_engine.evaluate(
        tool_invocation,
        ExecutionContext(values={}),
    )

    first_audit_event = policy_engine.create_audit_event(
        tool_invocation,
        policy_decision,
        event_id=EVENT_ID,
        occurred_at=OCCURRED_AT,
    )
    second_audit_event = policy_engine.create_audit_event(
        tool_invocation,
        policy_decision,
        event_id=EVENT_ID,
        occurred_at=OCCURRED_AT,
    )

    assert first_audit_event == second_audit_event


def test_audit_event_excludes_raw_sensitive_arguments() -> None:
    policy_engine = build_policy_engine()
    tool_invocation = ToolInvocation(
        tool_name="transfer_funds",
        arguments={
            "amount": 5000,
            "authorization_token": "secret-token-value",
            "account_number": "account-123456789",
        },
    )
    policy_decision = policy_engine.evaluate(
        tool_invocation,
        ExecutionContext(values={}),
    )

    audit_event = policy_engine.create_audit_event(
        tool_invocation,
        policy_decision,
        event_id=EVENT_ID,
        occurred_at=OCCURRED_AT,
    )
    serialized_event = audit_event.model_dump_json()

    assert "authorization_token" not in serialized_event
    assert "secret-token-value" not in serialized_event
    assert "account_number" not in serialized_event
    assert "account-123456789" not in serialized_event
    assert "amount" in serialized_event
    assert "5000" not in serialized_event


def test_unknown_tool_audit_event_has_no_matched_policy() -> None:
    policy_engine = build_policy_engine()
    tool_invocation = ToolInvocation(tool_name="delete_customer", arguments={})
    policy_decision = policy_engine.evaluate(
        tool_invocation,
        ExecutionContext(values={}),
    )

    audit_event = policy_engine.create_audit_event(
        tool_invocation,
        policy_decision,
        event_id=EVENT_ID,
        occurred_at=OCCURRED_AT,
    )

    assert audit_event.outcome is PolicyOutcome.DENY
    assert audit_event.matched_policy_tool_name is None
    assert audit_event.decision_reason == "No policy exists for the requested tool."
