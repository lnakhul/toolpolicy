"""Safe YAML loading and structural validation for policy definitions."""

from collections.abc import Hashable
from pathlib import Path

import yaml
from pydantic import ValidationError
from yaml.constructor import ConstructorError

from toolpolicy.errors import (
    InvalidPolicyStructureError,
    MalformedPolicyYamlError,
    PolicyFileNotFoundError,
    PolicyFileReadError,
)
from toolpolicy.models import PolicyDefinition


class DuplicateKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous mapping definitions."""


def _construct_mapping_without_duplicates(
    loader: DuplicateKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    """Construct one mapping while rejecting duplicate keys at every level."""

    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, Hashable):
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found unhashable key",
                key_node.start_mark,
            )
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicates,
)


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
        policy_document = yaml.load(policy_text, Loader=DuplicateKeySafeLoader)
    except yaml.YAMLError as error:
        raise MalformedPolicyYamlError(
            policy_path,
            f"policy file contains malformed YAML: {error}",
        ) from error

    try:
        return PolicyDefinition.model_validate(policy_document)
    except ValidationError as error:
        raise InvalidPolicyStructureError(
            policy_path,
            f"policy file does not match the supported schema: {policy_path}",
        ) from error
