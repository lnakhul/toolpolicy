"""Safe YAML loading and structural validation for policy definitions."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from toolpolicy.errors import (
    InvalidPolicyStructureError,
    MalformedPolicyYamlError,
    PolicyFileNotFoundError,
    PolicyFileReadError,
)
from toolpolicy.models import PolicyDefinition


def load_policy_definition(policy_path: Path) -> PolicyDefinition:
    """Load one YAML policy file into a validated domain model.

    This function only parses and validates declarative configuration. It does
    not evaluate a tool invocation or make an authorization decision.
    """

    try:
        policy_text = policy_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PolicyFileNotFoundError(
            policy_path,
            f"policy file does not exist: {policy_path}",
        ) from error
    except OSError as error:
        raise PolicyFileReadError(
            policy_path,
            f"policy file could not be read: {policy_path}",
        ) from error

    try:
        policy_document = yaml.safe_load(policy_text)
    except yaml.YAMLError as error:
        raise MalformedPolicyYamlError(
            policy_path,
            f"policy file contains malformed YAML: {policy_path}",
        ) from error

    try:
        return PolicyDefinition.model_validate(policy_document)
    except ValidationError as error:
        raise InvalidPolicyStructureError(
            policy_path,
            f"policy file does not match the supported schema: {policy_path}",
        ) from error
