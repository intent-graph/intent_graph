---
name: ig-tool-query
description: >
  Reference for ig-tool read-only commands: validate, query, tree, convert,
  and orchestrator plumbing (step, context, trace, init).
  Use when inspecting, navigating, or setting up an IntentGraph.
user-invocable: false
---

# ig-tool — Query, Inspect & Orchestrator Plumbing

System-wide CLI. Installed via `uv tool install -e .` from the repo root.
Run from any directory. Full reference: `agents/PRIMER_TOOLS.md` (WHY/when) and the ig-tool-* Skills (HOW/syntax).

## Output Contract (all commands)

- **Stdout**: compact YAML summary only (status, metrics, output path). Always <= 5 lines.
- **Full results**: written to `-o <path>`. Agent reads the file only if it needs detail.
- **Errors**: non-zero exit code, message to stderr, never raw tracebacks.

Always pass `-o` in agent/orchestrator invocations.

## Consistent Flags

| Flag | Meaning | Required? |
|------|---------|-----------|
| `-g` | Graph file path (JSON or YAML, by extension) | Always (except `trace`) |
| `-o` | Output file path | Recommended |
| `-t` | Target UID | When target-aware |

---

## validate

```bash
ig-tool validate -g graph.json [-o report.yaml]
```

Checks: orphan nodes, broken parent/child refs, broken link endpoints, empty intents.
Exit code 1 if errors found.

---

## query

Read-only graph navigation. **Choose the right variant:**

| Variant | Content | Use when |
|---------|---------|----------|
| `--structure` | Minimap: uid+name for nodes, uid+endpoints for links | Global orientation, target selection. **Cheapest.** |
| `--overview` | Hierarchy + annotations (children counts, epistemic states) | Need richer structural context |
| `--node` | Full content of a single node (all fields) | Inspecting one specific node |

**Rule of thumb:** start with `--structure`. Escalate to `--overview` only when you need annotations. Use `--node` for single-node detail.

```bash
# Structure (cheapest — start here)
ig-tool query -g graph.json --structure [-o structure.yaml]

# Overview (richer)
ig-tool query -g graph.json --overview [-o overview.yaml]

# Single node (full detail)
ig-tool query -g graph.json --node D [-o node_D.yaml]

# Children of a node
ig-tool query -g graph.json --children D [-o children_D.yaml]

# Ancestors (path to root)
ig-tool query -g graph.json --ancestors D.1 [-o ancestors.yaml]

# Links from a node
ig-tool query -g graph.json --links D [-o links_D.yaml]

# Neighbors (tree + intentlink adjacency)
ig-tool query -g graph.json --neighbors D [-o neighbors_D.yaml]
```

---

## tree

ASCII tree visualization. **Not the same as `query --structure`** — tree renders visual hierarchy, query returns parseable YAML.

```bash
# Basic tree
ig-tool tree -g graph.json

# With intent descriptions
ig-tool tree -g graph.json --show-intent

# Subtree from a specific root
ig-tool tree -g graph.json --root D

# Save to file
ig-tool tree -g graph.json -o tree.txt

# Wider output
ig-tool tree -g graph.json --width 120
```

Flags: `--style {simple,boxed}`, `--indent STR` (default: 4 spaces).

---

## convert

Convert graph between JSON and YAML.

```bash
ig-tool convert -i graph.json -o graph.yaml
ig-tool convert -i graph.yaml -o graph.json
ig-tool convert -i graph.json [-f yaml]   # stdout
```

Format auto-detected from extension. `-f` overrides.

Format auto-detected from extension. `-f` overrides. Both JSON and YAML inputs are accepted by `obsidian export` (Phase 1 fixed this — there is no longer any need to pre-convert).

---

## Orchestrator Plumbing

These commands are used by the orchestrator, not by regular agents.

### init — Create a new graph

```bash
ig-tool init -o graph.json --root --name "My Project"                              # empty graph + ROOT node
ig-tool init -o graph.json --root --root-name "Pipeline" --root-intent "..." \
  --name "ETL"                                                                     # custom root display
ig-tool init -o graph.json --template three-level --name "ETL Pipeline"            # ROOT + 3 modules + 2 components
ig-tool init -o graph.json --name "My Project"                                     # ZERO nodes — use only if creating root manually
```

**CRITICAL:** Without `--root` or `--template`, init creates a graph with **zero nodes**. Any subsequent `ig-tool node create --parent ROOT ...` will fail with `Node 'ROOT' does not exist`. Either:
- pass `--root` (and optionally `--root-name` / `--root-intent`), or
- pass `--template`, or
- omit both and create the first node yourself with `ig-tool node create` (no `--parent` flag — root nodes have no parent).

The `--root` flag hardcodes the root UID to `ROOT`; `--root-name` only sets the display name. To use a different root UID, omit `--root` and create the first node manually.

Templates: `minimal` (ROOT only), `three-level` (ROOT + 3 modules + 2 components + 1 link).
Use `--force` to overwrite existing file.

### workflow step create — Create step folder

```bash
ig-tool workflow step create --dir steps/ --step DISTILL.REFINE --target D \
  --prev steps/017_DISTILL.CHALLENGE \
  --copy output_issues.yaml:input_issues.yaml \
  --copy output_view.yaml:input_view.yaml
```

The `--copy` flag uses `src:dst` syntax (colon-separated, not space). Repeatable.
See the ig-tool-workflow skill for full details.

### workflow step summary — Summarize agent output

```bash
ig-tool workflow step summary steps/017_DISTILL.CHALLENGE/output_issues.yaml
```

Returns compact metrics (issue counts, severity breakdown, word/line counts). Used for routing.

### context — Assemble agent context payload

```bash
ig-tool context -g graph.json --nodes E,T,L [-t E] [-m lean] [-b 4000] [--overview] -o context.yaml
ig-tool context -g graph.json --depth 1 [--name my-view] [--overview] -o context.yaml
```

Combines working-view serialization + IV-context + budget check. Select the view with `--nodes UID,UID,…` **or** `--depth N` (exactly one). For new work, prefer `lens build` — a richer agent-I/O artifact.

### workflow trace record / show

```bash
# Record a trace entry
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.EXTRACT --target D --actor extractor \
  --action "Extracted intent" --result "17 edits proposed"

# Show timeline
ig-tool workflow trace show trace.jsonl [-o timeline.txt]
```
