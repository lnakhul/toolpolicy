# ToolPolicy - Copilot Engineering Instructions

## Project purpose

ToolPolicy is a small open-source Python library and CLI that provides deterministic runtime authorization for AI-agent tool calls.

AI agents can propose actions, but they should not determine their own permissions.

ToolPolicy sits between an agent and the tools it wants to execute.

The core workflow is:

Agent
    ↓
proposed ToolInvocation
    ↓
ToolPolicy
    ↓
deterministic policy evaluation
    ↓
ALLOW / DENY / REQUIRE_APPROVAL
    ↓
tool execution or intervention

ToolPolicy evaluates explicit policy definitions before consequential actions are executed.

The policy engine must not depend on an LLM.

## Core principle

The agent proposes actions.

ToolPolicy decides whether those actions are permitted.

The agent must never be able to override a policy decision.

Unknown tools must fail closed by default.

Policy evaluation must be deterministic and explainable.

## Engineering philosophy

Write this project as if it were developed and reviewed by senior software engineers.

Prioritize:

1. correctness
2. security boundaries
3. deterministic behavior
4. clear domain modeling
5. readability
6. explicit behavior
7. testability
8. maintainability
9. simplicity

Do not optimize for feature count.

Avoid speculative abstractions.

Do not introduce:

- databases
- web servers
- React
- Docker
- cloud infrastructure
- queues
- microservices
- dependency-injection frameworks
- generic repository patterns
- plugin architectures
- LLM dependencies
- agent framework dependencies
- MCP integration

unless explicitly requested in a later phase.

## Python

Target Python 3.14.

Use modern Python typing.

Prefer:

- pathlib.Path
- enums for finite domain states
- Pydantic v2 for external/domain contracts
- explicit return types
- small focused functions
- immutable models where appropriate
- structural pattern matching where it improves clarity

Use:

- Pydantic v2
- PyYAML
- Typer
- Rich
- pytest
- Ruff

## Naming

Use descriptive domain-specific names.

Avoid vague identifiers such as:

- data
- obj
- item
- res
- req
- ctx
- mgr
- helper
- util
- tmp
- x
- y

unless their meaning is genuinely obvious in a tiny local scope.

Prefer names such as:

- tool_invocation
- policy_definition
- tool_policy
- policy_decision
- policy_outcome
- policy_constraint
- execution_context
- audit_event
- constraint_evaluation

Prefer:

    evaluate_tool_invocation()

over:

    process()

Prefer:

    PolicyEngine

over:

    Manager

Descriptive names should remain readable and should not become unnecessarily verbose.

## Domain terminology

Use consistent terminology:

ToolInvocation
ExecutionContext
PolicyDefinition
ToolPolicy
PolicyConstraint
PolicyDecision
PolicyOutcome
RiskLevel
AuditEvent
ConstraintEvaluation

Do not invent multiple terms for the same concept.

## Policy outcomes

V1 supports exactly three authorization outcomes:

ALLOW
DENY
REQUIRE_APPROVAL

These outcomes must be represented explicitly.

Do not represent authorization decisions using booleans.

## Risk classification

Policies may classify tools using explicit risk levels such as:

READ
WRITE
CONSEQUENTIAL
DESTRUCTIVE

Risk classification describes the action.

Risk level must not itself silently determine authorization behavior.

The policy definition determines the authorization outcome.

## Fail-closed behavior

Unknown tools must be denied by default.

Malformed policies must never silently degrade into permissive behavior.

Unsupported operators must fail policy loading rather than being ignored.

Unexpected policy-engine failures must never result in ALLOW.

## Constraints

V1 should support a deliberately small deterministic constraint language.

Potential supported operators:

- equals
- not_equals
- less_than
- less_than_or_equal
- greater_than
- greater_than_or_equal
- in

Constraints may inspect:

- tool arguments
- trusted execution context

Do not use eval(), exec(), dynamic Python expressions, or arbitrary executable policy code.

Do not build a general-purpose policy language.

## Trusted execution context

ExecutionContext represents trusted information supplied by the host application, such as:

- customer_verified
- user_role
- environment
- approval state

Do not treat agent-provided arguments as trusted execution context.

Maintain this boundary clearly in the domain model.

## Architecture

Keep these concerns separated:

1. Domain models
2. Policy parsing and validation
3. Constraint evaluation
4. Policy decision orchestration
5. Audit event generation
6. Human-readable reporting
7. CLI

The CLI must not contain authorization logic.

The parser must not make authorization decisions.

Constraint evaluators must not perform I/O.

The core PolicyEngine must be usable as a Python library without the CLI.

## V1 requirements

V1 must support:

- YAML policy definitions
- typed ToolInvocation
- trusted ExecutionContext
- typed PolicyDecision
- ALLOW
- DENY
- REQUIRE_APPROVAL
- explicit risk classifications
- deterministic argument constraints
- deterministic execution-context constraints
- default-deny behavior for unknown tools
- structured decision reasons
- structured audit events
- CLI policy testing
- meaningful process exit codes
- automated tests
- GitHub Actions

## Out of scope for V1

Do not implement:

- live LLM execution
- OpenAI integration
- Anthropic integration
- MCP integration
- LangChain integration
- agent framework integrations
- OAuth
- authentication systems
- persistent approval workflows
- databases
- dashboards
- hosted services
- distributed policy evaluation
- natural-language policies
- LLM-based policy decisions

## Security

Never use eval() or exec() to evaluate policy expressions.

Do not dynamically import code specified by policy files.

Policy files are declarative configuration, not executable programs.

Avoid exposing sensitive tool arguments unnecessarily in logs or human-readable reports.

Audit events should contain enough information to explain a decision without automatically copying all invocation arguments.

## Testing

Test security boundaries and failure behavior aggressively.

Each policy feature should have:

- passing cases
- failing cases
- malformed-input cases
- boundary cases

Explicitly test fail-closed behavior.

Important tests include:

- unknown tool
- malformed policy
- unsupported operator
- missing argument
- missing execution-context value
- numeric boundary
- denied destructive action
- approval-required action
- allowed read action

Do not mock deterministic domain objects unnecessarily.

## Error handling

Differentiate:

- invalid policy configuration
- invalid invocation input
- authorization decision
- unexpected internal failure

DENY is a valid authorization decision.

It is not an exception.

REQUIRE_APPROVAL is a valid authorization decision.

It is not an exception.

Malformed policy configuration is an error.

## Documentation

Public APIs and important domain models should have useful docstrings.

Comments should explain WHY rather than restating WHAT the code already expresses.

Avoid excessive comments.

## Scope control

Before implementing each requested phase:

1. inspect the existing repository
2. summarize the relevant current architecture
3. describe the files you intend to create or modify
4. identify architectural or security trade-offs
5. implement only the requested phase

Do not silently introduce major architectural decisions.

After each phase:

1. run relevant tests
2. run Ruff
3. summarize what changed
4. identify remaining limitations
5. suggest a concise Git commit message

Do not automatically begin the next phase.