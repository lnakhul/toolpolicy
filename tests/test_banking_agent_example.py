"""End-to-end scenarios for the entirely synthetic banking-agent example."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from toolpolicy import PolicyEngine
from toolpolicy.cli import (
    ALLOW_EXIT_CODE,
    DENY_EXIT_CODE,
    REQUIRE_APPROVAL_EXIT_CODE,
    app,
)
from toolpolicy.models import ExecutionContext, PolicyOutcome, ToolInvocation
from toolpolicy.parsing import load_policy_definition

EXAMPLE_POLICY_PATH = (
    Path(__file__).parent.parent / "examples" / "banking-agent" / "policy.yaml"
)
runner = CliRunner()


@pytest.fixture
def banking_agent_engine() -> PolicyEngine:
    """Load the published synthetic banking-agent example."""

    return PolicyEngine(load_policy_definition(EXAMPLE_POLICY_PATH))


@pytest.mark.parametrize(
    ("tool_name", "arguments", "context_values", "expected_outcome"),
    [
        ("get_customer", {}, {}, PolicyOutcome.ALLOW),
        (
            "get_account_balance",
            {},
            {"customer_verified": True},
            PolicyOutcome.ALLOW,
        ),
        (
            "get_account_balance",
            {},
            {"customer_verified": False},
            PolicyOutcome.DENY,
        ),
        ("freeze_card", {}, {}, PolicyOutcome.REQUIRE_APPROVAL),
        (
            "transfer_funds",
            {"amount": 5000},
            {},
            PolicyOutcome.REQUIRE_APPROVAL,
        ),
        ("transfer_funds", {"amount": 5001}, {}, PolicyOutcome.DENY),
        ("close_account", {}, {}, PolicyOutcome.DENY),
        ("unknown_tool", {}, {}, PolicyOutcome.DENY),
    ],
)
def test_published_banking_example_outcomes(
    banking_agent_engine: PolicyEngine,
    tool_name: str,
    arguments: dict[str, object],
    context_values: dict[str, object],
    expected_outcome: PolicyOutcome,
) -> None:
    policy_decision = banking_agent_engine.evaluate(
        ToolInvocation(tool_name=tool_name, arguments=arguments),
        ExecutionContext(values=context_values),
    )

    assert policy_decision.outcome is expected_outcome


@pytest.mark.parametrize(
    ("arguments", "expected_exit_code", "expected_output"),
    [
        (("--tool", "get_customer"), ALLOW_EXIT_CODE, "ALLOW"),
        (
            ("--tool", "transfer_funds", "--arg", "amount=7500"),
            DENY_EXIT_CODE,
            "DENY",
        ),
        (
            ("--tool", "freeze_card"),
            REQUIRE_APPROVAL_EXIT_CODE,
            "REQUIRE_APPROVAL",
        ),
    ],
)
def test_published_banking_example_cli_scenarios(
    arguments: tuple[str, ...],
    expected_exit_code: int,
    expected_output: str,
) -> None:
    result = runner.invoke(
        app,
        ["check", "--policy", str(EXAMPLE_POLICY_PATH), *arguments],
    )

    assert result.exit_code == expected_exit_code
    assert expected_output in result.output
