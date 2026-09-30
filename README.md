# ToolPolicy
Deterministic runtime authorization for AI-agent actions.
AI agents shouldn't decide their own permissions. ToolPolicy evaluates proposed tool calls against explicit policies before execution.

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
