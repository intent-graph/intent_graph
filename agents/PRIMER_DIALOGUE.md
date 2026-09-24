# PRIMER_DIALOGUE

Purpose: How to gather human feedback efficiently during workflows. For agents conducting dialogue (Elicitor, any agent in REFINE/CLARIFY steps).

Audience: Agents that need human judgment.

---

## Why Human Feedback?

Agents cannot invent intent (Cardinal Rule #1). When you encounter genuine uncertainty — multiple valid options, ambiguous requirements, trade-off decisions — you must consult the human who understands the system's purpose.

Human feedback is the mechanism for:
- Resolving `undecided` epistemic states
- Choosing between valid design alternatives
- Validating `speculative` or `inherited` nodes
- Breaking deadlocks when constraints conflict
- Confirming intent extracted from incomplete docs/code

---

## When to Defer: Document First, Dialogue When Needed

You don't always need human input immediately. If the only need is to record that a node is under-specified or that a decision is pending, set `epistemic_state` (see PRIMER_01_SEMANTICS §epistemic_state) and continue — e.g. `undecided: under-specified, refinement pending` or `observed | gap: performance requirements not specified`. That keeps the graph honest without blocking. Use file-based dialogue when you need the human to **choose** (options A/B), **validate** (confirm extracted intent), or **resolve** a conflict. See PRIMER_00_PHILOSOPHY §When Rules Can Be Temporarily Relaxed and PRIMER_03A_EDITING §Intermediate States.

---

## Why Human Feedback Is Expensive

Each dialogue round consumes:
- Human time (context switch, decision load)
- Orchestrator context (if feedback goes inline)
- Agent context (re-reading prior questions)
- Workflow latency (waiting for human response)

This means:
1. **Batch questions** — if you need 3 decisions with shared context, ask all 3 at once (not 3 rounds)
2. **Provide context once** — human shouldn't re-read the same node description 3 times
3. **Keep orchestrator lean** — dialogue content stays on disk, not in orchestrator's context window
4. **Extract efficiently** — use Grep to pull answers, don't re-read your own questions

**Execution context:** Your **effort hint** (PRIMER_04_WORKFLOWS §Execution context) can tighten or loosen dialogue: quick pass → batch aggressively, ask only blocking questions; thorough → you may add follow-ups or clarify options in more detail.

---

## File-Based Dialogue: The Solution

**Problem:** Inline dialogue (back-and-forth in agent returns) bloats the orchestrator's context.

**Solution:** Write questions to disk files. Human edits in-place. You extract answers via Grep. Orchestrator never reads dialogue content — just passes folder path.

**Benefits:**
- Orchestrator context protected (folder path is ~20 tokens, dialogue content is 1000+)
- Questions share context (one minimap + target node serves all questions in round)
- Human edits at own pace (files persist, can review/edit/save incrementally)
- Agent extracts efficiently (Grep for `<choice>` tags, don't re-read full files)

---

## Folder Structure

```
{step_folder}/human_dialogue/
  round_summary.md     — Cumulative history (what's resolved, what remains)
  question_001.md      — One decision per file
  question_002.md
  ...
```

Numbering sequential across all rounds: Round 1 uses 001-003, Round 2 uses 004-005.

---

## Question File Format

Two sections: minimal ask (Section 1) + full context (Section 2).

```markdown
# Question NNN: {Short title}

## Section 1: Context + Ask

**Minimap:**

{Paste `ig-tool lens tree -l lens.yaml` output — shows where target sits}

**Critic ({issue_type}, {severity}):** {Issue description}

{The ask}

**A** — {Option 1, 1-2 lines}
**B** — {Option 2, 1-2 lines}

{Your recommendation, 1-2 lines}

**Your choice:**

<choice>
<!-- write A, B, or your own option -->
</choice>

---

## Section 2: Deepened Context

**Target node (FULL):**

uid: VALIDATE
name: "Validation Engine"
intent: "..."
epistemic_state: "..."
constraints: [...]
design_notes: "..."
examples: [...]
impl_pointers: ["src/validate.py::Validator (lines 10-60)"]
history: [...]

**Brim (context):**

- Parent (DISCOVER): "Discover all SQL functions..."
- Sibling (PARSE): "Parse SQL definitions..."
- Link (VALIDATE→REPORT): "Validation results feed reporter"
```

**Rationale:**
- Section 1: Human scans this quickly, makes decision
- Section 2: If human needs detail, it's there (don't make them search)
- Minimap: Shows structure (where am I?)
- Brim: Shows neighbors (what's around me?)
- Full target node: All fields available

Max 50 lines per question (before human response).

---

## Round Summary Format

`round_summary.md` — appended each round, not overwritten.

```markdown
# Refinement Summary

## Round 1
- Auto-resolved 12 mechanical issues (typos, missing constraints)
- Pattern ruling: all projection leaks → abstract + relocate to PIG (approved)
- Remaining: 3 design decisions → see question_001.md through question_003.md

## Round 2
- Decisions 1-2 resolved per human input
- Decision 3 spawned follow-up → see question_004.md
```

Max 30 lines added per round.

---

## Workflow

1. Create folder: `{step_folder}/human_dialogue/`
2. Write `round_summary.md` (append current round section)
3. Write all question files for round (batch)
4. Yield: `status: "yield_for_input", dialogue_folder: "{path}", questions_created: N`
5. Human edits `<choice>` tags, confirms
6. Extract via Grep: `pattern="<choice>(.*?)</choice>" multiline=true`
7. Parse answers, act
8. If need more questions: create new files (increment numbers), yield again
9. If done: return SUCCESS/PARTIAL

---

## Extraction: Use Grep, Not Read

CRITICAL: Use Grep tool to extract `<choice>` content. Never Read question files.

Why: Question files contain your own context (minimap, target node, brim). Re-reading wastes 500-1000 tokens per file. You only need the human's answer (5-50 tokens).

```bash
# CORRECT
Grep pattern="<choice>(.*?)</choice>" path="{dialogue_folder}" glob="question_*.md" multiline=true output_mode="content"

# WRONG - wastes tokens
Read "{dialogue_folder}/question_001.md"
```

Strip HTML comments (`<!-- ... -->`) from extracted text before processing.

---

## Constraints

| Rule | Value |
|------|-------|
| Max files per round | 5 questions + 1 round_summary |
| Max lines per question | 50 (before response) |
| Question numbering | Sequential across rounds (001, 002, ...) |
| Orchestrator reads files | Never (relay only) |
| Agent re-reads questions | Never (Grep for `<choice>` only) |

---

## Next Steps

After reading this primer:

- For Elicitor-specific turn format: See ig-elicitor-agent.md
- For workflow integration: Read PRIMER_04_WORKFLOWS (when dialogue happens)
- For when nodes can stay under-defined: PRIMER_00_PHILOSOPHY §When Rules Can Be Temporarily Relaxed, PRIMER_03A_EDITING §Intermediate States
- For epistemic_state and issue annotations: PRIMER_01_SEMANTICS §epistemic_state
