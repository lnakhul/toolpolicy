"""Core deterministic orchestration for declarative tool authorization."""

from toolpolicy.constraints import evaluate_policy_constraint
from toolpolicy.models import (
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
        self._policy_definition = policy_definition

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
