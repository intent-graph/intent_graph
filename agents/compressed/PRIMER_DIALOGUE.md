# PRIMER_DIALOGUE

How to gather human feedback during workflows. For agents needing human judgment.

---

## When to Use Dialogue

Agents cannot invent intent (Cardinal Rule #1). Use dialogue when you need the human to **choose** (options A/B), **validate** (confirm extracted intent), or **resolve** a conflict.

**When NOT to use dialogue:** If you only need to record that something is under-specified, set `epistemic_state` and continue. Example: `undecided: under-specified, refinement pending`. Don't block the workflow.

---

## Why File-Based (Not Inline)

Each round costs: human time, orchestrator context, agent context, workflow latency.

Rules: (1) Batch questions with shared context. (2) Provide context once. (3) Keep orchestrator lean — dialogue on disk, not in context. (4) Extract via Grep, don't re-read your own questions.

Effort hint steers tightness: quick → batch aggressively, ask only blocking questions; thorough → add follow-ups.

---

## Folder Structure

```
{step_folder}/human_dialogue/
  round_summary.md     — Cumulative history
  question_001.md      — One decision per file
  question_002.md      — Numbering sequential across rounds
```

---

## Question File Format

```markdown
# Question NNN: {Short title}

## Section 1: Context + Ask

**Minimap:** {`ig-tool lens tree` output}

**Critic ({issue_type}, {severity}):** {Issue description}

{The ask}

**A** — {Option 1}
**B** — {Option 2}

{Your recommendation}

**Your choice:**
<choice>
<!-- write A, B, or your own option -->
</choice>

---

## Section 2: Deepened Context
{Target node FULL + Brim (parent, siblings, links)}
```

Max 50 lines per question (before response).

---

## Round Summary Format

Appended each round. Max 30 lines per round.

```markdown
## Round N
- Auto-resolved M mechanical issues
- Remaining: K decisions → see question_NNN.md through question_NNN.md
```

---

## Workflow

1. Create `{step_folder}/human_dialogue/`
2. Write `round_summary.md` + all question files (batch)
3. Yield: `status: "yield_for_input", dialogue_folder: "{path}", questions_created: N`
4. Human edits `<choice>` tags
5. **Extract via Grep** (CRITICAL — never Read question files):
   `pattern="<choice>(.*?)</choice>" path="{folder}" glob="question_*.md" multiline=true`
6. Parse answers, act
7. If more questions needed: new files (increment numbers), yield again

---

## Constraints

| Rule | Value |
|------|-------|
| Max files per round | 5 questions + 1 round_summary |
| Max lines per question | 50 (before response) |
| Numbering | Sequential across rounds |
| Orchestrator reads files | Never |
| Agent re-reads questions | Never (Grep for `<choice>` only) |
