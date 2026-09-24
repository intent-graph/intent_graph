# AGENT TASK PAYLOAD: DISTILL.REFINE

## 1. INPUT

### 1.1 Context

**Inline (critical for orientation):**

- **Step:** DISTILL.REFINE
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Step folder:** {{step_folder}}

**External (read in this order before accessing Working Material):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `agents_runtime/AGENT_PRIMER.md` | **First** — vocabulary, invariants, agent text format, dual-graph model |
| Lens Primer | `agents_runtime/LENS_PRIMER.md` | **Second** — understand lens views and detail levels before reading lens files |
| Serialization Format | `foundation_and_formalism/SERIALIZATION_FORMAT.md` | Only if you encounter issues parsing or writing agent text YAML |
| Edit Primer | `agents_runtime/AGENT_EDIT_PRIMER_V2.md` | When expanding nodes (under_decomposition issues) |

### 1.2 Working Material

You will receive a **lens view** of both graphs:

- **Product Graph:** `input_lens.json` — Lens view of IntentGraph with variable LOD per node
  - Tree structure always visible
  - LOD levels: `skeleton` (uid+name), `lean` (uid+name+intent+epistemic_state), `full` (all fields)
- **ProjectionIG:** `input_projection_observations.json` — Lens view of PIG observations
- **Issues:** `input_issues.yaml` — Critic issue list from CHALLENGE (or RECHECK)

### 1.3 Environment

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}
- `is_resumption`: {{is_resumption}}
- `dialogue_round`: {{refine_dialogue_round}}
- `dialogue_folder`: {{step_folder}}/human_dialogue/

---

## 2. INSTRUCTIONS

### 2.1 Primary Objective

> Resolve the Critic's issues through structured dialogue with the human. Work on both graphs — product lens AND ProjectionIG observations.

### 2.2 Initialization

Read and follow:

- `.claude/agents/ig-elicitor-agent.md` (core agent definition)
{{agent_mode_modules}}

Refer to §1.1 External for primer reading order.

### 2.3 Algorithm / Execution Path

#### Step 1: Triage Issues

Read the issue list and classify each issue:

- **Auto-resolve:** Mechanical fixes you can apply without human input (e.g., typos, obvious missing constraints, formatting)
- **Escalate:** Design decisions that require human judgment (e.g., ambiguous intent, conflicting constraints, scope questions)

**If `is_resumption` is true:** You are being resumed with new issues from RECHECK or after a human dialogue round. You retain context from your previous pass. Focus on the delta — new issues only. Do not re-triage already-resolved issues.

#### Step 2: Resolve Product Issues

For issues targeting the product lens:

- Present escalated issues to the human **one at a time**
- Propose concrete edits for each issue
- Use `ig-tool` commands to apply approved edits

**Commands for Product Graph Edits:**
```bash
# Update node fields
ig-tool node set --uid UID --intent "Updated intent" --epistemic-state known

# Create new child nodes
ig-tool node create --uid UID --name "Name" --intent "Intent" --parent PARENT

# Reparent nodes for decomposition
ig-tool node reparent --uid CHILD --under NEW_PARENT

# Update intentlinks
ig-tool link create --src SRC --dst DST --intent "Relationship"
```

#### Step 2a: File-Based Dialogue (when escalation needed)

When you need human judgment on design decisions:

1. Create `{{step_folder}}/human_dialogue/` if it does not exist.
2. Write or update `round_summary.md` — cumulative context of what's been resolved and what remains.
3. Write one `question_NNN.md` per decision point with this structure:
   - **Section 1:** ASCII tree minimap (use `ig-tool tree` format) + Critic issue + the ask + `<choice>` response tag
   - **Section 2:** Full node context + brim summary
   - See `ig-elicitor-agent.md` §Elicitation Turn Format and `STEP_IO_PROTOCOL.md` §File-Dialogue Specification for examples.
4. Create all question files for this round at once (batch), then return `YIELD_FOR_INPUT` with `dialogue_folder` in your escalation payload.
5. **On resumption: Use Grep to extract human choice from `<choice>...</choice>` tags in each question file.** **CRITICAL: NEVER use Read tool on question_NNN.md files** — they contain your own generated context and will waste tokens. Use Grep with pattern `<choice>(.*?)</choice>` and multiline mode to extract only the human's response. Incorporate into your resolution and continue.

#### Step 2b: Expand Under-Decomposed Nodes

For `under_decomposition` issues in the Critic's list:

1. Read the **Edit Primer** (`agents_runtime/AGENT_EDIT_PRIMER_V2.md` §Expansion Protocol)
2. **Present the proposed decomposition to the human as a decision** — not auto-resolve. The human chooses the grouping. Create a `question_NNN.md` showing: current node content, proposed children with their migrated content, intentlink handling, and what remains on the parent.
3. After human approval, use `ig-tool node create` and `ig-tool link` commands to emit child nodes and intentlinks
4. Add new child UIDs to `output_queue_additions.yaml`

#### Step 3: Resolve Projection Issues

For issues with types `pig_quality`, `pig_granularity`, `pig_missing`:

- Use `ig-tool node create` and `ig-tool node set` to propose edits to the ProjectionIG observations
- For `projection_leak` issues: rewrite the product constraint to be projection-agnostic AND use `ig-tool node create` to add a PIG node with the projection-specific content

**ProjectionIG-specific commands:**
```bash
# Create new PIG observation node
ig-tool node create --uid "PIG-{TAG}.{SUBTAG}" --name "Pattern" --intent "Rendering pattern" --parent "PIG" --epistemic-state "observed"

# Update PIG node
ig-tool node set --uid "PIG-{TAG}.{SUBTAG}" --design-notes "Code example from module X"
```

#### Step 4: Convergence

- Continue dialogue until all issues are resolved or explicitly deferred
- If resolving issues creates new targets (nodes that need their own distill cycle), add them to a "queue additions" list
- If scope is exceeded (edits needed beyond the target-adjacent lens), signal for `DISTILL.ESCAPE`

### 2.4 Constraints, Exits & Escalations

**Constraints:**

- Read ONLY files listed in §1.1 and §1.2
- Do not modify input files. Propose edits in output files.
- Always present escalated issues to the human — do not auto-resolve design decisions
- If scope is exceeded, signal it clearly in your output rather than attempting out-of-scope edits

**Exit Conditions:**

- If `input_issues.yaml` is missing or empty → SUCCESS (nothing to refine)
- If `input_lens.yaml` is missing → FAILURE

**Escalation Rules:**

- Design decisions always escalate to HUMAN
- If a single issue touches 3+ nodes beyond the target-adjacent lens, yield to ORCHESTRATOR for scope decision
- Default Escalation Target: HUMAN

---

## 3. OUTPUT CONTRACT

### 3.1 Artifacts

Use `ig-tool` commands to apply all changes. The orchestrator will apply changes via lens diff/apply.

**Commands to use:**
```bash
# Update node fields
ig-tool node set --uid UID --intent "Updated" --epistemic-state known --design-notes "Resolution notes"

# Create new nodes (for decomposition or new PIG observations)
ig-tool node create --uid UID --name "Name" --intent "Intent" --parent PARENT --epistemic-state "observed"

# Create intentlinks
ig-tool link create --src SRC --dst DST --intent "Relationship"

# Batch multiple operations
ig-tool apply --batch batch.yaml -g graph.json -o updated_graph.json
```

**Output files:**
- `output_queue_additions.yaml` — New target UIDs to queue (if any; omit if none)

**Important:**
- Do NOT write YAML diffs manually — use `ig-tool` commands which handle validation and invariant enforcement
- Viewport changes (lens focus/promote/demote) don't persist — only use them for navigation
- All graph mutations go through `ig-tool` CLI commands

### 3.2 Epistemology

- Confidence Score: 0.0–1.0 (how thoroughly issues were resolved)
- Unknowns / Assumptions: list any deferred issues or unresolved ambiguities

### 3.3 Control Flow & Telemetry

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of resolution results
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)

- Target: [HUMAN | ORCHESTRATOR]
- `dialogue_folder`: `{{step_folder}}/human_dialogue/` (when target is HUMAN)
- `dialogue_round`: current round number
- `questions_created`: list of question filenames in this round (e.g., `["question_001.md", "question_002.md"]`)
- Blockage Summary: what is ambiguous or missing (1-2 sentences for the orchestrator to relay)

**When target is HUMAN with file dialogue:** The `dialogue_folder` contains all context the human needs. The orchestrator prints the folder path — it does not read the files or relay their content. The Blockage Summary is a short label for the orchestrator's message only (e.g., "3 design decisions need your input").

**When target is ORCHESTRATOR:** Use the legacy inline format (Blockage Summary, Impact Assessment, Proposed Options, Agent Recommendation) for scope-exceeded escalations that the orchestrator must handle.
