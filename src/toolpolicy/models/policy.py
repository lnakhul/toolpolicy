"""Declarative policy-definition models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import field_validator, model_validator

from toolpolicy.models.base import (
    DomainModel,
    JsonValue,
    NonBlankString,
    PolicyOutcome,
    validate_json_value,
)


class RiskLevel(StrEnum):
    """Classification of a tool action's inherent risk."""

    READ = "read"
    WRITE = "write"
    CONSEQUENTIAL = "consequential"
    DESTRUCTIVE = "destructive"


class ConstraintOperator(StrEnum):
    """Fixed deterministic operators available to policy constraints."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    IN = "in"


class ConstraintSource(StrEnum):
    """The separately modeled source a constraint may inspect."""

    ARGUMENTS = "arguments"
    CONTEXT = "context"


class PolicyConstraint(DomainModel):
    """A single declarative comparison against arguments or trusted context."""

    source: ConstraintSource
    field: NonBlankString
    operator: ConstraintOperator
    value: JsonValue
    on_failure: PolicyOutcome

    @field_validator("value", mode="before")
    @classmethod
    def validate_constraint_value_is_json_compatible(cls, value: object) -> object:
        """Keep policy values declarative and JSON-compatible."""

        return validate_json_value(value)

    @model_validator(mode="after")
    def validate_constraint_shape(self) -> PolicyConstraint:
        """Reject structurally unsupported constraint configurations."""

        if self.on_failure is PolicyOutcome.ALLOW:
            raise ValueError("constraint failure cannot result in allow")

        comparison_operators = {
            ConstraintOperator.LESS_THAN,
            ConstraintOperator.LESS_THAN_OR_EQUAL,
            ConstraintOperator.GREATER_THAN,
            ConstraintOperator.GREATER_THAN_OR_EQUAL,
        }
        if self.operator in comparison_operators and (
            isinstance(self.value, bool) or not isinstance(self.value, (int, float))
        ):
            raise ValueError("comparison operators require a numeric value")
        if self.operator is ConstraintOperator.IN and (
            not isinstance(self.value, list) or not self.value
        ):
            raise ValueError("the in operator requires a non-empty list value")
        return self


class ToolPolicy(DomainModel):
    """The declared authorization rule for one named tool."""

    risk: RiskLevel
    decision: PolicyOutcome
    constraints: tuple[PolicyConstraint, ...] = ()


class PolicyDefinition(DomainModel):
    """A complete, versioned, declarative tool policy."""

    version: Literal["1"]
    tools: dict[NonBlankString, ToolPolicy]
