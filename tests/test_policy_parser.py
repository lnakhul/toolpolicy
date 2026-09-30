"""Tests for safe YAML policy loading and structural validation."""

from pathlib import Path

import pytest

from toolpolicy.errors import (
    InvalidPolicyStructureError,
    MalformedPolicyYamlError,
    PolicyFileNotFoundError,
)
from toolpolicy.models import PolicyOutcome, RiskLevel
from toolpolicy.parsing import load_policy_definition

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"


def write_policy(policy_path: Path, policy_text: str) -> Path:
    """Write a temporary policy file and return its path."""

    policy_path.write_text(policy_text, encoding="utf-8")
    return policy_path


def test_loads_valid_policy_fixture() -> None:
    policy_definition = load_policy_definition(
        FIXTURE_DIRECTORY / "banking-agent-policy.yaml"
    )

    assert set(policy_definition.tools) == {
        "get_customer",
        "get_account_balance",
        "update_address",
        "freeze_card",
        "transfer_funds",
        "close_account",
    }
    assert policy_definition.tools["transfer_funds"].risk is RiskLevel.CONSEQUENTIAL
    assert (
        policy_definition.tools["freeze_card"].decision
        is PolicyOutcome.REQUIRE_APPROVAL
    )


def test_rejects_malformed_yaml(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "malformed.yaml",
        'version: "1"\ntools:\n  get_customer: [\n',
    )

    with pytest.raises(MalformedPolicyYamlError):
        load_policy_definition(policy_path)


def test_rejects_invalid_policy_schema(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "invalid-schema.yaml",
        'version: "1"\ntools: {}\nunknown_configuration: true\n',
    )

    with pytest.raises(InvalidPolicyStructureError):
        load_policy_definition(policy_path)


def test_rejects_unsupported_operator(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "unsupported-operator.yaml",
        (
            'version: "1"\n'
            "tools:\n"
            "  transfer_funds:\n"
            "    risk: consequential\n"
            "    decision: require_approval\n"
            "    constraints:\n"
            "      - source: arguments\n"
            "        field: amount\n"
            "        operator: contains\n"
            "        value: 5000\n"
            "        on_failure: deny\n"
        ),
    )

    with pytest.raises(InvalidPolicyStructureError):
        load_policy_definition(policy_path)


def test_rejects_invalid_outcome(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "invalid-outcome.yaml",
        (
            'version: "1"\n'
            "tools:\n"
            "  get_customer:\n"
            "    risk: read\n"
            "    decision: prompt_agent\n"
        ),
    )

    with pytest.raises(InvalidPolicyStructureError):
        load_policy_definition(policy_path)


def test_rejects_invalid_risk_classification(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "invalid-risk.yaml",
        (
            'version: "1"\n'
            "tools:\n"
            "  get_customer:\n"
            "    risk: safe\n"
            "    decision: allow\n"
        ),
    )

    with pytest.raises(InvalidPolicyStructureError):
        load_policy_definition(policy_path)


def test_rejects_malformed_constraint(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "malformed-constraint.yaml",
        (
            'version: "1"\n'
            "tools:\n"
            "  transfer_funds:\n"
            "    risk: consequential\n"
            "    decision: require_approval\n"
            "    constraints:\n"
            "      - source: arguments\n"
            "        field: amount\n"
            "        operator: less_than_or_equal\n"
            '        value: "5000"\n'
            "        on_failure: deny\n"
        ),
    )

    with pytest.raises(InvalidPolicyStructureError):
        load_policy_definition(policy_path)


def test_rejects_missing_policy_file(tmp_path: Path) -> None:
    with pytest.raises(PolicyFileNotFoundError):
        load_policy_definition(tmp_path / "missing-policy.yaml")
