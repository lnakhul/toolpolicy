"""Pure deterministic evaluation of declarative policy constraints."""

from toolpolicy.models import (
    ConstraintEvaluation,
    ConstraintEvaluationStatus,
    ConstraintOperator,
    ConstraintSource,
    ExecutionContext,
    PolicyConstraint,
    ToolInvocation,
)


def evaluate_policy_constraint(
    policy_constraint: PolicyConstraint,
    tool_invocation: ToolInvocation,
    execution_context: ExecutionContext,
) -> ConstraintEvaluation:
    """Evaluate one constraint against agent arguments or trusted context.

    Missing fields and type mismatches are constraint failures represented in
    the returned value. Invalid domain objects remain programming errors.
    """

    source_values = _select_source_values(
        policy_constraint.source,
        tool_invocation,
        execution_context,
    )
    if policy_constraint.field not in source_values:
        return _constraint_evaluation(
            policy_constraint,
            ConstraintEvaluationStatus.MISSING_FIELD,
            "constraint_field_missing",
        )

    actual_value = source_values[policy_constraint.field]
    evaluation_status = _evaluate_operator(policy_constraint, actual_value)
    reason_code = {
        ConstraintEvaluationStatus.PASSED: "constraint_satisfied",
        ConstraintEvaluationStatus.FAILED: "constraint_not_satisfied",
        ConstraintEvaluationStatus.TYPE_MISMATCH: "constraint_type_mismatch",
    }[evaluation_status]
    return _constraint_evaluation(policy_constraint, evaluation_status, reason_code)


def _select_source_values(
    source: ConstraintSource,
    tool_invocation: ToolInvocation,
    execution_context: ExecutionContext,
) -> dict[str, object]:
    match source:
        case ConstraintSource.ARGUMENTS:
            return tool_invocation.arguments
        case ConstraintSource.CONTEXT:
            return execution_context.values
        case _:
            raise ValueError(f"unsupported constraint source: {source}")


def _evaluate_operator(
    policy_constraint: PolicyConstraint,
    actual_value: object,
) -> ConstraintEvaluationStatus:
    match policy_constraint.operator:
        case ConstraintOperator.EQUALS:
            return _evaluate_equality(policy_constraint.value, actual_value, True)
        case ConstraintOperator.NOT_EQUALS:
            return _evaluate_equality(policy_constraint.value, actual_value, False)
        case ConstraintOperator.LESS_THAN:
            return _evaluate_numeric_comparison(
                actual_value,
                policy_constraint.value,
                lambda actual, expected: actual < expected,
            )
        case ConstraintOperator.LESS_THAN_OR_EQUAL:
            return _evaluate_numeric_comparison(
                actual_value,
                policy_constraint.value,
                lambda actual, expected: actual <= expected,
            )
        case ConstraintOperator.GREATER_THAN:
            return _evaluate_numeric_comparison(
                actual_value,
                policy_constraint.value,
                lambda actual, expected: actual > expected,
            )
        case ConstraintOperator.GREATER_THAN_OR_EQUAL:
            return _evaluate_numeric_comparison(
                actual_value,
                policy_constraint.value,
                lambda actual, expected: actual >= expected,
            )
        case ConstraintOperator.IN:
            return _evaluate_membership(policy_constraint.value, actual_value)
        case _:
            raise ValueError(
                f"unsupported constraint operator: {policy_constraint.operator}"
            )


def _evaluate_equality(
    expected_value: object,
    actual_value: object,
    requires_equality: bool,
) -> ConstraintEvaluationStatus:
    if type(actual_value) is not type(expected_value):
        return ConstraintEvaluationStatus.TYPE_MISMATCH

    values_are_equal = _json_values_are_equal(actual_value, expected_value)
    constraint_passed = values_are_equal is requires_equality
    return (
        ConstraintEvaluationStatus.PASSED
        if constraint_passed
        else ConstraintEvaluationStatus.FAILED
    )


def _evaluate_numeric_comparison(
    actual_value: object,
    expected_value: object,
    comparison: object,
) -> ConstraintEvaluationStatus:
    if not _is_json_number(actual_value) or not _is_json_number(expected_value):
        return ConstraintEvaluationStatus.TYPE_MISMATCH

    if comparison(actual_value, expected_value):
        return ConstraintEvaluationStatus.PASSED
    return ConstraintEvaluationStatus.FAILED


def _evaluate_membership(
    expected_value: object,
    actual_value: object,
) -> ConstraintEvaluationStatus:
    if not isinstance(expected_value, list):
        raise ValueError("the in operator requires a validated list value")

    compatible_values = [
        candidate_value
        for candidate_value in expected_value
        if type(candidate_value) is type(actual_value)
    ]
    if not compatible_values:
        return ConstraintEvaluationStatus.TYPE_MISMATCH
    if any(
        _json_values_are_equal(actual_value, candidate)
        for candidate in compatible_values
    ):
        return ConstraintEvaluationStatus.PASSED
    return ConstraintEvaluationStatus.FAILED


def _is_json_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _json_values_are_equal(left_value: object, right_value: object) -> bool:
    if type(left_value) is not type(right_value):
        return False
    if isinstance(left_value, list):
        return (
            isinstance(right_value, list)
            and len(left_value) == len(right_value)
            and all(
                _json_values_are_equal(left_element, right_element)
                for left_element, right_element in zip(
                    left_value, right_value, strict=True
                )
            )
        )
    if isinstance(left_value, dict):
        return (
            isinstance(right_value, dict)
            and left_value.keys() == right_value.keys()
            and all(
                _json_values_are_equal(left_value[key], right_value[key])
                for key in left_value
            )
        )
    return left_value == right_value


def _constraint_evaluation(
    policy_constraint: PolicyConstraint,
    status: ConstraintEvaluationStatus,
    reason_code: str,
) -> ConstraintEvaluation:
    failure_outcome = (
        None
        if status is ConstraintEvaluationStatus.PASSED
        else policy_constraint.on_failure
    )
    return ConstraintEvaluation(
        source=policy_constraint.source,
        field=policy_constraint.field,
        operator=policy_constraint.operator,
        status=status,
        reason_code=reason_code,
        failure_outcome=failure_outcome,
    )
