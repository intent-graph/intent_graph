# IG Agent Common Protocol

Shared protocols for all IntentGraph agents.

---

## Tool use protocol (binding)

Before any ig-tool invocation:
  1. Consult the relevant Skill: `ig-tool-{lens,graph,graph-edit,query,obsidian,workflow}`.
  2. If unsure of syntax, run `ig-tool <cmd> --help`.
Inline examples below are illustrative shorthand; the Skill is authoritative on flags.

---

## Tool Usage Rule

You have access to the `ig-tool` CLI for all graph operations. Current top-level commands (15): `validate`, `query`, `parse`, `apply`, `context`, `workflow`, `obsidian`, `convert`, `tree`, `init`, `telemetry`, `lens`, `graph`, `node`, `link`. Use it via Bash.

**NEVER write Python scripts to manipulate the IntentGraph.** You are not a Python process. You are a Claude agent with Bash access. The `ig-tool` CLI wraps the Python library and enforces invariants, history tracking, and output contracts.

If you need an operation that `ig-tool` doesn't support, report the gap — do not work around it with ad-hoc code.

---

## Output Protocol

Shared output protocol for all IntentGraph agents in Step I/O mode.

**Write to disk, summarize to orchestrator.**

1. Write complete outputs to the step folder (filenames per your agent guide).
2. Return minimal summary via task result:

```yaml
output_file: "{primary output filename}"
summary: "{one-line human-readable summary}"
metrics: {agent-specific key-value pairs}
status: "complete"
```

The orchestrator routes on `status` and `metrics` — it never reads your output files. Detailed results live on disk for the next agent in the pipeline.
