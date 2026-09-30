"""Shared validation primitives for ToolPolicy domain models."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonBlankString = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
]
type JsonPrimitive = None | bool | int | float | str
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]


class PolicyOutcome(StrEnum):
    """The only authorization outcomes supported by ToolPolicy V1."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class DomainModel(BaseModel):
    """Base model that rejects unspecified fields and prevents reassignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def validate_json_value(value: object) -> object:
    """Reject values that cannot be represented by standard JSON."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, list):
        return [validate_json_value(element) for element in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {
            key: validate_json_value(nested_value)
            for key, nested_value in value.items()
        }
    raise ValueError("value must be JSON-compatible")
