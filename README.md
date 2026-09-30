# ToolPolicy
Deterministic runtime authorization for AI-agent actions.
AI agents shouldn't decide their own permissions. ToolPolicy evaluates proposed tool calls against explicit policies before execution.

## Synthetic Banking Example

[`examples/banking-agent/policy.yaml`](examples/banking-agent/policy.yaml) is
an entirely fictional banking-agent policy. It demonstrates how a policy can
allow safe reads, require verified context, require approval for consequential
actions, impose an argument limit, deny destructive actions, and fail closed
for unknown tools. The example is policy data only; banking concepts are not
part of the generic ToolPolicy architecture.

## CLI demonstration

Use the CLI to test a local policy file:

```shell
toolpolicy check \
	--policy examples/banking-agent/policy.yaml \
	--tool transfer_funds \
	--arg amount=7500 \
	--context customer_verified=true
```

`--arg` represents agent-controlled input. `--context` is a demonstration-only
convenience for testing policies locally. In a production host application,
trusted `ExecutionContext` values must be constructed independently by trusted
application code, never supplied by an agent.

Exit codes are `0` for `ALLOW`, `10` for `DENY`, `11` for
`REQUIRE_APPROVAL`, `2` for invalid configuration or input, and `70` for an
unexpected internal error.

## Using ToolPolicy In Another Project's CI

An application can run a policy check as one of its own CI steps. Until a
published package is available, install a pinned ToolPolicy revision from its
source repository and run an expected `ALLOW` check:

```yaml
- name: Install ToolPolicy
	run: pip install "git+https://github.com/<owner>/toolpolicy.git@<revision>"

- name: Check agent policy
	run: |
		toolpolicy check \
			--policy policies/agent-policy.yaml \
			--tool get_customer
```

Choose a tool invocation expected to return `ALLOW`; nonzero `DENY` and
`REQUIRE_APPROVAL` exit codes will fail the CI step. The CLI's `--context`
option remains suitable only for controlled demonstrations. Production CI
should generate trusted context from the project's own trusted build or test
fixtures, not from agent-controlled input.
