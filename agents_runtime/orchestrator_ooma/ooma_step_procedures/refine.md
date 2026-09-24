# OOMA Procedure: DISTILL.REFINE

**Role:** OOMA self-executes this step (no agent delegation).

**Goal:** Review and refine agent contributions (from READ + EXTRACT). Verify product graph quality and ProjectionIG observations. Apply fixes directly.

---

## Input

- `lens.yaml` — Lens view (updated by READ and EXTRACT agents)
- `input_projection_observations.yaml` — ProjectionIG observations from EXTRACT
- `graph.json` — full IntentGraph (already reflects READ/EXTRACT edits)

---

## Output

- Edits applied directly to graph via `ig-tool` commands
- `output_refine_summary.yaml` — what was fixed, what was created

---

## Algorithm

### Phase 1: Review Product Graph

#### 1a. Load current Lens state

```bash
ig-tool lens show --lens {step_folder}/lens.yaml -o {step_folder}/current_lens.yaml
```

Inspect target node + children + brim (all should be at `full` LOD).

#### 1b. Quality checks

For each `full` LOD node, verify:

**Intent clarity:**
- Is `intent` field present and non-empty?
- Is it a clear "why" statement (not "how")?
- Does it avoid projection-specific language (e.g., "using Python", "via REST API")?

**Epistemic state accuracy:**
- Is `epistemic_state` appropriate?
  - `known` → concrete, grounded in code/docs
  - `constrained` → partial knowledge, some unknowns
  - `undecided` → placeholder, needs investigation
- Do `constraints` match the epistemic state?

**Constraint precision:**
- Are `constraints` testable? (e.g., "Max 1GB file size" is good, "Fast" is bad)
- Are they projection-agnostic? (e.g., "Thread-safe" is good, "Use mutex" is projection-specific)

**Design notes hygiene:**
- Do `design_notes` contain implementation details? (This is correct — design_notes IS for impl pointers)
- Are they concise and relevant?

**Common issues from READ/EXTRACT:**
- Docreader tends to be verbose → trim intent to 1–2 sentences
- Extractor sometimes leaks projection details into product intent → move to ProjectionIG
- Both agents sometimes miss constraints that are implicit in code/docs → add them

#### 1c. Apply fixes

Use `ig-tool` commands for any issues found:

```bash
# Fix intent wording
ig-tool node set {UID} --intent "Revised intent statement"

# Update epistemic state
ig-tool node set {UID} --epistemic-state "constrained"

# Add missing constraints
ig-tool node set {UID} --constraints "Constraint 1" --constraints "Constraint 2"

# Trim design_notes
ig-tool node set {UID} --design-notes "Concise implementation pointer"
```

**Batch edits** (if fixing multiple nodes):

Create `{step_folder}/batch_edits.yaml`:
```yaml
- op: node.set
  uid: ROOT.PARSE
  intent: "Revised intent"

- op: node.set
  uid: ROOT.PARSE.LEX
  constraints:
    - "UTF-8 only"
    - "Max 1GB"
```

Apply:
```bash
ig-tool apply -g graph.json --batch {step_folder}/batch_edits.yaml
```

#### 1d. Check for under-decomposition

If a `full` LOD node has:
- `epistemic_state: undecided` or `constrained`
- AND `intent` suggests it spans multiple concerns
- AND no children yet

**Propose decomposition** (inline dialogue with human):
- Present node: uid, name, intent, constraints
- Ask: "Should this be decomposed into child nodes?"
- If yes: create children via `ig-tool node create --parent {UID}`

### Phase 2: Review ProjectionIG Observations

#### 2a. Load observations

Read `input_projection_observations.yaml` (from EXTRACT step).

Format:
```yaml
observations:
  - uid: PIG-PARSE.IMPL
    name: "Parser Implementation"
    intent: "Module-level rendering: FSM-based tokenizer"
    epistemic_state: "observed"
    parent: PIG-PARSE
    source: "Observed from parser.py structure"
```

#### 2b. Quality checks

For each observation, verify:

**Granularity:**
- Is this the right level of detail? (module-level observations, not function-level)
- Does it correspond to a product node? (PIG-PARSE.IMPL should match ROOT.PARSE in product graph)

**Completeness:**
- Are all major rendering decisions captured?
- Are there gaps (e.g., EXTRACT observed database schema but didn't propose PIG-DB.SCHEMA)?

**Duplication:**
- Are multiple observations describing the same rendering concern?

#### 2c. Apply fixes

**Add missing observations:**
```bash
ig-tool node create --parent PIG-ROOT \
  --name "Database Schema" \
  --intent "Rendering: Postgres with JSONB columns for flexibility" \
  --epistemic-state "observed" \
  --design-notes "Observed from schema.sql"
```

**Merge duplicates:**
```bash
# Remove redundant node
ig-tool node remove PIG-PARSE.IMPL_DUP

# Update remaining node to capture both
ig-tool node set PIG-PARSE.IMPL --intent "Merged intent from both observations"
```

**Refine granularity:**
```bash
# Too fine-grained → merge up
ig-tool node remove PIG-PARSE.TOKENIZE
ig-tool node set PIG-PARSE.IMPL --intent "FSM-based tokenizer (was separate node)"

# Too coarse-grained → split
ig-tool node create --parent PIG-PARSE \
  --name "Lexer Strategy" \
  --intent "Rendering: regex-free FSM"
```

### Phase 3: Cross-Graph Consistency

#### 3a. Projection leak check

For each `full` LOD product node, check if `intent` or `constraints` mention:
- Programming languages (Python, Rust, etc.)
- Libraries/frameworks (Django, React, etc.)
- Protocols (HTTP, gRPC, etc.)
- Data structures (HashMap, List, etc.)

If found:
1. **Abstract the product intent** (remove projection-specific detail)
2. **Relocate to ProjectionIG** (create or update PIG node with the specific choice)

Example:
```yaml
# BEFORE (projection leak)
- uid: ROOT.CACHE
  intent: "Cache query results using Redis"

# AFTER (fixed)
- uid: ROOT.CACHE
  intent: "Cache query results to avoid redundant computation"
  constraints:
    - "Sub-second lookup time"
    - "Thread-safe access"

- uid: PIG-CACHE.IMPL
  intent: "Rendering: Redis with key-value storage"
  epistemic_state: "observed"
```

Commands:
```bash
# Fix product node
ig-tool node set ROOT.CACHE --intent "Abstracted intent" \
  --constraints "Sub-second lookup" --constraints "Thread-safe"

# Create PIG node
ig-tool node create --parent PIG-CACHE \
  --name "Cache Implementation" \
  --intent "Rendering: Redis with key-value storage" \
  --epistemic-state "observed"
```

### Phase 4: Summarize and Escalate (if needed)

#### 4a. Write summary

Create `{step_folder}/output_refine_summary.yaml`:
```yaml
product_edits:
  nodes_modified: 3
  nodes_created: 1
  issues_fixed:
    - "Trimmed verbose intent on ROOT.PARSE"
    - "Added missing constraint on ROOT.LEXER"
    - "Fixed projection leak: ROOT.CACHE now abstract"

projection_edits:
  nodes_created: 2
  nodes_merged: 1
  observations_refined:
    - "Created PIG-CACHE.IMPL for Redis decision"
    - "Merged duplicate PIG-PARSE observations"

escalations:
  - node: ROOT.VALIDATE
    issue: "Under-decomposition: spans input validation + business rules"
    recommendation: "Split into ROOT.VALIDATE.INPUT and ROOT.VALIDATE.BUSINESS"
    human_decision: "pending"
```

#### 4b. Escalate to human (inline dialogue)

If major design decisions needed (e.g., decomposition, scope changes):

1. **Present context** (target node, brim, parent/siblings)
2. **Describe issue** (1–2 sentences)
3. **Propose options** (A, B, or custom)
4. **Recommend** (with reasoning)

Wait for human response. Apply approved edits immediately.

**No file-based dialogue** — OOMA retains context naturally across the session. Present inline, wait for response, continue.

---

## Edge Cases

| Case | Response |
| ---- | -------- |
| READ/EXTRACT made no edits | Acceptable — REFINE is a no-op. Write empty summary, advance to CHALLENGE. |
| All nodes are `known` and perfect | Acceptable — REFINE confirms quality. Write summary, advance to CHALLENGE. |
| Human rejects all OOMA proposals | Log in trace, write summary with `escalations: rejected`, advance to CHALLENGE (Critic will find issues if any). |
| Projection leak pervasive (20+ nodes) | Batch fix. Create `batch_edits.yaml` with all fixes, apply atomically. |

---

## Trace Entry

```bash
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.REFINE \
  --target {target_uid} \
  --actor "ooma" \
  --action "Refined product graph ({N} edits) + ProjectionIG ({M} edits)" \
  --result "nodes_modified={N}, nodes_created={M}, escalations={E}"
```

---

## Next Step

Advance to `DISTILL.CHALLENGE`.

The Critic will now review the refined graph (product + ProjectionIG) and report any remaining issues.
