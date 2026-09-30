"""Tests for the ToolPolicy demonstration CLI."""

from pathlib import Path

from typer.testing import CliRunner

from toolpolicy.cli import (
    ALLOW_EXIT_CODE,
    DENY_EXIT_CODE,
    INTERNAL_ERROR_EXIT_CODE,
    INVALID_INPUT_EXIT_CODE,
    REQUIRE_APPROVAL_EXIT_CODE,
    app,
)

FIXTURE_POLICY_PATH = Path(__file__).parent / "fixtures" / "banking-agent-policy.yaml"
runner = CliRunner()


def invoke_check(*arguments: str):
    """Invoke the check command against the representative policy fixture."""

    return runner.invoke(
        app,
        ["check", "--policy", str(FIXTURE_POLICY_PATH), *arguments],
    )


def test_check_renders_allow_decision() -> None:
    result = invoke_check("--tool", "get_customer")

    assert result.exit_code == ALLOW_EXIT_CODE
    assert "ToolPolicy" in result.output
    assert "Decision" in result.output
    assert "ALLOW" in result.output


def test_check_renders_denial_with_failed_rule() -> None:
    result = invoke_check("--tool", "transfer_funds", "--arg", "amount=7500")

    assert result.exit_code == DENY_EXIT_CODE
    assert "DENY" in result.output
    assert "arguments.amount <= 5000" in result.output


def test_check_renders_approval_requirement() -> None:
    result = invoke_check("--tool", "freeze_card")

    assert result.exit_code == REQUIRE_APPROVAL_EXIT_CODE
    assert "REQUIRE_APPROVAL" in result.output
    assert "Human approval is required for this action." in result.output


def test_check_rejects_invalid_assignment() -> None:
    result = invoke_check("--tool", "get_customer", "--arg", "customer_id")

    assert result.exit_code == INVALID_INPUT_EXIT_CODE
    assert "key=value" in result.output


def test_check_rejects_invalid_policy_configuration(tmp_path: Path) -> None:
    invalid_policy_path = tmp_path / "invalid-policy.yaml"
    invalid_policy_path.write_text('version: "2"\ntools: {}\n', encoding="utf-8")

    result = runner.invoke(
        app,
        ["check", "--policy", str(invalid_policy_path), "--tool", "get_customer"],
    )

    assert result.exit_code == INVALID_INPUT_EXIT_CODE
    assert "Input error" in result.output


def test_check_maps_unexpected_errors_to_internal_exit_code(
    monkeypatch,
) -> None:
    def raise_evaluation_error(*_arguments: object) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr("toolpolicy.cli.PolicyEngine.evaluate", raise_evaluation_error)

    result = invoke_check("--tool", "get_customer")

    assert result.exit_code == INTERNAL_ERROR_EXIT_CODE
    assert "Internal error" in result.output


def test_check_maps_rendering_errors_to_internal_exit_code(
    monkeypatch,
) -> None:
    def raise_rendering_error(*_arguments: object) -> None:
        raise RuntimeError("unexpected rendering failure")

    monkeypatch.setattr("toolpolicy.cli.render_policy_decision", raise_rendering_error)

    result = invoke_check("--tool", "get_customer")

    assert result.exit_code == INTERNAL_ERROR_EXIT_CODE
    assert "Internal error" in result.output
    assert "ALLOW" not in result.output
