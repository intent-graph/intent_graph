# Elicitor Step 0: Triage + Pattern Analysis

Read this when entering from Critic with an issue list. Perform this before presenting anything to the human.

## Workflow

```
Receive: Critic issue list + lens
```

### Phase 1: PATTERN DETECTION

Group issues by:
- Pattern type (projection leaks, missing constraints, HOW→WHY, etc.)
- Affected node (multiple issues on same node)
- Sibling pattern (similar issues across siblings)

### Phase 2: RULING EXTRACTION

For each pattern group with N ≥ 3 similar fixes:
- Can one ruling resolve all N instances? → prepare ruling question
- If not → fall back to individual presentation

**Ruling criteria:** ≥3 instances and one governing principle resolves all. Example: "All projection leaks → rewrite to abstract terms + move specifics to PIG."

### Phase 3: MECHANICAL vs DECISION

For each issue/pattern:

- **Auto-resolvable** (mechanical fix, unambiguous): batch for review
  - Projection leak with obvious rewrite
  - Missing constraint where Critic's suggestion is unambiguous
  - HOW→WHY rewrite where the intent is clear
- **Decision-required** (multiple valid interpretations): create a `question_NNN.md` file in `{step_folder}/human_dialogue/` with full context, options, and response tags. Use the two-section turn format (see `ig-elicitor-agent.md` §File-Based Dialogue Protocol).
  - Epistemic gap with multiple options
  - Under-decomposition where children are unclear
  - Conflicting design_notes needing domain knowledge

**Auto-resolve criteria:** A competent reviewer would always make the same edit. When in doubt, escalate to a question file.

### Phase 4: PRESENTATION ORDER (via dialogue files)

Create question files in `{step_folder}/human_dialogue/` following this priority:

1. **Pattern rulings** — one `question_NNN.md` per pattern ruling (highest impact first). Use the pattern ruling turn format (see `ig-elicitor-examples.md` §Good — pattern ruling).
2. **Auto-resolved batch** — summarize in `round_summary.md` for acknowledgment. No question file needed unless human wants veto power.
3. **Node bundles** — one `question_NNN.md` per node with 2+ decision-required issues. Use the node bundle turn format (see `ig-elicitor-examples.md` §Good — node bundle).
4. **Individual decisions** — one `question_NNN.md` per remaining decision point.

If no decisions are needed (all auto-resolvable), skip dialogue files entirely and return `SUCCESS`.

Otherwise, create all question files for this round at once, then return `YIELD_FOR_INPUT`.

### Phase 5: RESUMPTION HANDLING

When resumed after a YIELD round:

1. Regex-extract human responses from each `question_NNN.md` — read only the `<choice>...</choice>` and `<comments>...</comments>` tags. Do NOT re-read the question or context sections.
2. Strip HTML comment placeholders (`<!-- ... -->`). If `<choice>` is empty → treat as unanswered.
3. Apply the chosen resolution for each answered question.
4. If more decisions remain (unanswered questions or new issues surfaced during resolution), create the next batch of `question_NNN.md` files and YIELD again.
5. If all decisions resolved, produce final output files (`output_lens_edits.yaml`, `output_projection_edits.yaml`) and return `SUCCESS`.

**Node bundling criteria:** Node has 2+ issues → present together with minimap so human sees full node context at once.
