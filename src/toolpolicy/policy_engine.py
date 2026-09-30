"""Core deterministic orchestration for declarative tool authorization."""

import hashlib
import json
from datetime import datetime
from uuid import UUID

from toolpolicy.constraints import evaluate_policy_constraint
from toolpolicy.models import (
    AuditEvent,
    ConstraintEvaluation,
    ConstraintEvaluationStatus,
    ExecutionContext,
    PolicyConstraint,
    PolicyDecision,
    PolicyDefinition,
    PolicyOutcome,
    ToolInvocation,
)


class PolicyEngine:
    """Evaluate proposed tool invocations against one validated policy definition."""

    def __init__(self, policy_definition: PolicyDefinition) -> None:
        self._policy_definition = policy_definition.model_copy(deep=True)

    def evaluate(
        self,
        tool_invocation: ToolInvocation,
        execution_context: ExecutionContext,
    ) -> PolicyDecision:
        """Return an authorization decision without executing the requested tool."""

        tool_policy = self._policy_definition.tools.get(tool_invocation.tool_name)
        if tool_policy is None:
            return PolicyDecision(
                outcome=PolicyOutcome.DENY,
                tool_name=tool_invocation.tool_name,
                reason_codes=("unknown_tool",),
                policy_version=self._policy_definition.version,
            )

        constraint_evaluations = tuple(
            self._evaluate_constraint_safely(
                policy_constraint,
                tool_invocation,
                execution_context,
            )
            for policy_constraint in tool_policy.constraints
        )
        outcome, reason_codes = self._determine_outcome(
            tool_policy.decision,
            constraint_evaluations,
        )
        return PolicyDecision(
            outcome=outcome,
            tool_name=tool_invocation.tool_name,
            risk=tool_policy.risk,
            reason_codes=reason_codes,
            constraint_evaluations=constraint_evaluations,
            policy_version=self._policy_definition.version,
        )

    def create_audit_event(
        self,
        tool_invocation: ToolInvocation,
        execution_context: ExecutionContext,
        *,
        event_id: UUID,
        occurred_at: datetime,
    ) -> AuditEvent:
        """Evaluate an invocation and create its value-safe audit event.

        The event is not stored by ToolPolicy.
        """

        policy_decision = self.evaluate(tool_invocation, execution_context)

        return AuditEvent(
            event_id=event_id,
            occurred_at=occurred_at,
            policy_version=policy_decision.policy_version,
            policy_fingerprint=self._policy_fingerprint(),
            tool_name=policy_decision.tool_name,
            outcome=policy_decision.outcome,
            risk=policy_decision.risk,
            invocation_id=tool_invocation.invocation_id,
            matched_policy_tool_name=self._matched_policy_tool_name(policy_decision),
            reason_codes=policy_decision.reason_codes,
            decision_reason=self._decision_reason(policy_decision.reason_codes),
            constraint_evaluations=policy_decision.constraint_evaluations,
        )

    def _policy_fingerprint(self) -> str:
        policy_json = json.dumps(
            self._policy_definition.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"sha256:{hashlib.sha256(policy_json.encode()).hexdigest()}"

    def _matched_policy_tool_name(
        self,
        policy_decision: PolicyDecision,
    ) -> str | None:
        if policy_decision.tool_name in self._policy_definition.tools:
            return policy_decision.tool_name
        return None

    @staticmethod
    def _decision_reason(reason_codes: tuple[str, ...]) -> str:
        decision_reasons = {
            "unknown_tool": "No policy exists for the requested tool.",
            "constraint_evaluation_error": "Constraint evaluation failed safely.",
            "constraint_failure_deny": "A policy constraint denied the request.",
            "policy_configured_deny": "The matched policy denies this tool.",
            "constraint_failure_requires_approval": (
                "A policy constraint requires approval."
            ),
            "policy_configured_allow": "The matched policy allows this tool.",
            "policy_requires_approval": "The matched policy requires approval.",
        }
        try:
            return " ".join(
                decision_reasons[reason_code] for reason_code in reason_codes
            )
        except KeyError as error:
            raise ValueError(
                f"unsupported decision reason code: {error.args[0]}"
            ) from error

    @staticmethod
    def _evaluate_constraint_safely(
        policy_constraint: PolicyConstraint,
        tool_invocation: ToolInvocation,
        execution_context: ExecutionContext,
    ) -> ConstraintEvaluation:
        try:
            return evaluate_policy_constraint(
                policy_constraint,
                tool_invocation,
                execution_context,
            )
        except Exception:
            return ConstraintEvaluation(
                source=policy_constraint.source,
                field=policy_constraint.field,
                operator=policy_constraint.operator,
                status=ConstraintEvaluationStatus.ERROR,
                reason_code="constraint_evaluation_error",
                failure_outcome=PolicyOutcome.DENY,
            )

    @staticmethod
    def _determine_outcome(
        configured_outcome: PolicyOutcome,
        constraint_evaluations: tuple[ConstraintEvaluation, ...],
    ) -> tuple[PolicyOutcome, tuple[str, ...]]:
        if any(
            evaluation.status is ConstraintEvaluationStatus.ERROR
            for evaluation in constraint_evaluations
        ):
            return PolicyOutcome.DENY, ("constraint_evaluation_error",)

        if any(
            evaluation.failure_outcome is PolicyOutcome.DENY
            for evaluation in constraint_evaluations
        ):
            return PolicyOutcome.DENY, ("constraint_failure_deny",)

        if configured_outcome is PolicyOutcome.DENY:
            return PolicyOutcome.DENY, ("policy_configured_deny",)

        if any(
            evaluation.failure_outcome is PolicyOutcome.REQUIRE_APPROVAL
            for evaluation in constraint_evaluations
        ):
            return PolicyOutcome.REQUIRE_APPROVAL, (
                "constraint_failure_requires_approval",
            )

        match configured_outcome:
            case PolicyOutcome.ALLOW:
                return PolicyOutcome.ALLOW, ("policy_configured_allow",)
            case PolicyOutcome.REQUIRE_APPROVAL:
                return PolicyOutcome.REQUIRE_APPROVAL, ("policy_requires_approval",)
            case _:
                raise ValueError(f"unsupported policy outcome: {configured_outcome}")
