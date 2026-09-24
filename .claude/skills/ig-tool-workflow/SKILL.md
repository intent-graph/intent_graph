---
name: ig-tool-workflow
description: >
  Reference for ig-tool workflow commands: workflow step {create, summary} and
  workflow trace {show, record}. Use when managing orchestrator step folders
  or recording/inspecting workflow execution traces.
user-invocable: false
---

# ig-tool — Workflow Plumbing

Orchestrator-facing commands. Used by the orchestrator (not regular agents) to manage step folders and workflow execution traces.

---

## workflow step — Step Folder Management

### create — Create a new step folder

```bash
ig-tool workflow step create --dir steps/ --step DISTILL.REFINE --target D \
  --prev steps/017_DISTILL.CHALLENGE \
  --copy output_issues.yaml:input_issues.yaml \
  --copy output_view.yaml:input_view.yaml
```

| Flag | Required | Notes |
|------|----------|-------|
| `--dir` | Yes | Steps directory root |
| `--step` | Yes | Step UID (e.g. `DISTILL.REFINE`) |
| `--target` | Yes | Target node UID for this step |
| `--prev` | No | Previous step folder path (source for `--copy`) |
| `--copy SRC:DST` | No | Copy file from prev step. `SRC:DST` = colon-separated. Repeatable. |
| `-o` | No | Write output to path instead of stdout |

**Note:** `--copy` uses colon `:` as separator (not space). Both `SRC:DST` and just `filename` (same name) are accepted.

---

### summary — Summarize agent output file for orchestrator routing

```bash
ig-tool workflow step summary steps/017_DISTILL.CHALLENGE/output_issues.yaml
ig-tool workflow step summary steps/017_DISTILL.CHALLENGE/output_issues.yaml -o summary.yaml
```

| Positional | Required | Notes |
|------------|----------|-------|
| `file` | Yes | Path to the agent output YAML file |
| `-o` | No | Write summary to this path |

Returns compact metrics (issue counts, severity breakdown, word/line counts). Used by the orchestrator for routing decisions.

---

## workflow trace — Execution Trace Management

### record — Append a trace entry

```bash
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.EXTRACT --target D --actor extractor \
  --action "Extracted intent" --result "17 edits proposed"
```

| Positional | Required | Notes |
|------------|----------|-------|
| `trace_file` | Yes | Path to trace JSONL file (created if absent) |
| `--step` | Yes | Step UID |
| `--target` | Yes | Target node UID |
| `--actor` | Yes | Actor name (e.g. `extractor`, `steward`) |
| `--action` | Yes | Short action description |
| `--result` | Yes | Short result description |

Trace entries: 6 fields — `ts`, `step`, `target`, `actor`, `action`, `result`.

---

### show — Display workflow timeline

```bash
ig-tool workflow trace show trace.jsonl
ig-tool workflow trace show trace.jsonl -o timeline.txt
```

| Positional | Required | Notes |
|------------|----------|-------|
| `trace_file` | Yes | Path to trace JSONL file |
| `-o` | No | Write timeline to path (default: stdout) |
| `--workflow` | No | Filter by workflow name |
| `--graph-name` | No | Filter by graph name |

---

## Common Mistakes

1. **`step summary` takes a positional file path** — not a `-i` flag. Run as `ig-tool workflow step summary path/to/file.yaml`.
2. **`trace record` and `trace show` also take a positional `trace_file`** — the JSONL path comes before subaction flags.
3. **Old names**: `ig-tool step create` and `ig-tool trace record` were renamed. Use `ig-tool workflow step create` and `ig-tool workflow trace record`.
