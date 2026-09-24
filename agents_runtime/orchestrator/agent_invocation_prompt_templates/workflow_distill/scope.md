# CLI EXECUTION SPEC: DISTILL.SCOPE

**Type:** System step — no agent invocation. The orchestrator runs CLI commands directly.

---

## Purpose

Build the target-adjacent IV-context lens for the current target. This is a deterministic operation: the `ig-tool lens build` command assembles parent + siblings + children + intentlink neighbors, serializes them with variable LOD, and checks the token budget — no LLM judgment needed.

---

## Procedure

### 1. Create step folder

```bash
ig-tool workflow step create --dir {steps_dir} --step DISTILL.SCOPE --target {target_uid} \
  --prev {prev_step_folder}
```

### 2. Assemble lens context

```bash
ig-tool lens build -g {graph_path} -t {target_uid} -b 30 \
  -o {step_folder}/lens.yaml

ig-tool lens show -l {step_folder}/lens.yaml \
  -o {step_folder}/input_lens.yaml
```

**Budget selection:**
- **Distill/Declare:** `-b 30` (target + direct neighbors full LOD, others lean, distant branches skeleton).
- **Project:** `-b 50` (wider context, more nodes at full LOD).

### 3. Handle budget overflow

If `ig-tool lens build` reports pruning:

1. Retry with reduced budget: `-b 15`
2. If still over: log warning, proceed anyway (downstream agents can use `ig-tool lens expand` for specifics)
3. The lens automatically prunes most-distant branches first while preserving tree validity

### 4. Record trace

```bash
ig-tool workflow trace record {trace_path} --step "DISTILL.SCOPE" --target "{target_uid}" \
  --actor "system" --action "assembled lens context" \
  --result "lens: {N} nodes, {W} words, pruned: {P} branches"
```

Extract node/word/pruning counts from the `ig-tool lens build` stdout summary.

---

## Output

| File | Content |
|------|---------|
| `{step_folder}/input_lens.yaml` | Scoped lens context (full tree with variable LOD) — consumed by downstream agents (READ, EXTRACT, etc.) |

---

## Error Handling

| Condition | Action |
|-----------|--------|
| Target UID not found in graph | Log error, enter `DISTILL.ESCAPE` |
| Graph file missing | Log error, halt workflow |
| Budget overflow after all retries | Proceed with warning — agents can expand lens or query specific nodes |

---

## Migration Note

This step was previously an agent invocation (Navigator). It was converted to a System/CLI step because lens construction is a deterministic algorithm fully implemented by `ig-tool lens build`. The Navigator agent (`.claude/agents/ig-navigator-agent.md`) is preserved for future evolution (adaptive detail modes, cross-workflow memory, multi-target batching).
