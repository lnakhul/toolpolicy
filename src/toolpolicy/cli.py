"""Typer command-line interface for testing ToolPolicy policy decisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from toolpolicy.errors import PolicyLoadError
from toolpolicy.models import ExecutionContext, PolicyOutcome, ToolInvocation
from toolpolicy.parsing import load_policy_definition
from toolpolicy.policy_engine import PolicyEngine
from toolpolicy.reporting import render_policy_decision

ALLOW_EXIT_CODE = 0
DENY_EXIT_CODE = 10
REQUIRE_APPROVAL_EXIT_CODE = 11
INVALID_INPUT_EXIT_CODE = 2
INTERNAL_ERROR_EXIT_CODE = 70

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


class CliInputError(ValueError):
    """Raised when demonstration CLI input cannot form a domain model."""


@app.callback()
def toolpolicy() -> None:
    """ToolPolicy command-line interface."""


@app.command()
def check(
    policy_path: Annotated[Path, typer.Option("--policy")],
    tool_name: Annotated[str, typer.Option("--tool")],
    argument_assignments: Annotated[
        list[str] | None,
        typer.Option("--arg", help="Agent-controlled argument as key=value."),
    ] = None,
    context_assignments: Annotated[
        list[str] | None,
        typer.Option(
            "--context",
            help="Demonstration-only trusted context value as key=value.",
        ),
    ] = None,
) -> None:
    """Evaluate a proposed tool call against a local policy file."""

    try:
        tool_arguments = _parse_assignments(argument_assignments or [], "--arg")
        context_values = _parse_assignments(context_assignments or [], "--context")
        policy_definition = load_policy_definition(policy_path)
        tool_invocation = ToolInvocation(
            tool_name=tool_name,
            arguments=tool_arguments,
        )
        execution_context = ExecutionContext(values=context_values)
        policy_decision = PolicyEngine(policy_definition).evaluate(
            tool_invocation,
            execution_context,
        )
        render_policy_decision(console, policy_definition, policy_decision)
        exit_code = _exit_code_for_outcome(policy_decision.outcome)
    except (CliInputError, PolicyLoadError, ValidationError) as error:
        console.print(f"[red]Input error:[/red] {error}")
        raise typer.Exit(INVALID_INPUT_EXIT_CODE) from error
    except Exception:
        console.print("[red]Internal error:[/red] policy evaluation failed safely.")
        raise typer.Exit(INTERNAL_ERROR_EXIT_CODE) from None

    raise typer.Exit(exit_code)


def _parse_assignments(assignments: list[str], option_name: str) -> dict[str, object]:
    parsed_assignments: dict[str, object] = {}
    for assignment in assignments:
        field_name, separator, raw_value = assignment.partition("=")
        if not separator or not field_name or not raw_value:
            raise CliInputError(f"{option_name} values must use key=value syntax")
        if field_name in parsed_assignments:
            raise CliInputError(f"duplicate {option_name} field: {field_name}")
        parsed_assignments[field_name] = _parse_value(raw_value)
    return parsed_assignments


def _parse_value(raw_value: str) -> object:
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value


def _exit_code_for_outcome(policy_outcome: PolicyOutcome) -> int:
    match policy_outcome:
        case PolicyOutcome.ALLOW:
            return ALLOW_EXIT_CODE
        case PolicyOutcome.DENY:
            return DENY_EXIT_CODE
        case PolicyOutcome.REQUIRE_APPROVAL:
            return REQUIRE_APPROVAL_EXIT_CODE
