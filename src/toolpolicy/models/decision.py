"""Authorization-decision models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from toolpolicy.models.base import DomainModel, NonBlankString, PolicyOutcome
from toolpolicy.models.policy import ConstraintOperator, ConstraintSource, RiskLevel


class ConstraintEvaluationStatus(StrEnum):
    """The result category for one constraint evaluation."""

    PASSED = "passed"
    FAILED = "failed"
    MISSING_FIELD = "missing_field"
    TYPE_MISMATCH = "type_mismatch"
    ERROR = "error"


class ConstraintEvaluation(DomainModel):
    """A value-free record of one constraint's evaluation result."""

    source: ConstraintSource
    field: NonBlankString
    operator: ConstraintOperator
    status: ConstraintEvaluationStatus
    reason_code: NonBlankString
    failure_outcome: PolicyOutcome | None = None


class PolicyDecision(DomainModel):
    """A structured authorization result without tool execution semantics."""

    outcome: PolicyOutcome
    tool_name: NonBlankString
    risk: RiskLevel | None = None
    reason_codes: tuple[NonBlankString, ...] = Field(min_length=1)
    constraint_evaluations: tuple[ConstraintEvaluation, ...] = ()
    policy_version: str = "1"
