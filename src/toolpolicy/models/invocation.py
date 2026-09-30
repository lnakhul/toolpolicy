"""Models for agent-proposed tool calls and trusted host context."""

from __future__ import annotations

from pydantic import field_validator

from toolpolicy.models.base import (
    DomainModel,
    JsonValue,
    NonBlankString,
    validate_json_value,
)


class ToolInvocation(DomainModel):
    """An action proposed by an agent, including only agent-controlled arguments."""

    tool_name: NonBlankString
    arguments: dict[NonBlankString, JsonValue]
    invocation_id: NonBlankString | None = None

    @field_validator("arguments", mode="before")
    @classmethod
    def validate_arguments_are_json_compatible(cls, value: object) -> object:
        """Ensure agent arguments remain serializable declarative values."""

        return validate_json_value(value)


class ExecutionContext(DomainModel):
    """Trusted host-supplied values that remain separate from agent arguments."""

    values: dict[NonBlankString, JsonValue]

    @field_validator("values", mode="before")
    @classmethod
    def validate_context_values_are_json_compatible(cls, value: object) -> object:
        """Ensure trusted context can be safely evaluated and serialized."""

        return validate_json_value(value)
