"""Value-safe audit model for authorization decisions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from toolpolicy.models.base import DomainModel, NonBlankString, PolicyOutcome
from toolpolicy.models.decision import ConstraintEvaluation
from toolpolicy.models.policy import RiskLevel


class AuditEvent(DomainModel):
    """A decision audit record that intentionally excludes raw input values."""

    event_id: UUID
    occurred_at: datetime
    policy_fingerprint: NonBlankString
    tool_name: NonBlankString
    outcome: PolicyOutcome
    risk: RiskLevel | None = None
    invocation_id: NonBlankString | None = None
    reason_codes: tuple[NonBlankString, ...] = Field(min_length=1)
    constraint_evaluations: tuple[ConstraintEvaluation, ...] = ()

    @field_validator("occurred_at")
    @classmethod
    def validate_timestamp_has_timezone(cls, value: datetime) -> datetime:
        """Require an unambiguous audit timestamp."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value
