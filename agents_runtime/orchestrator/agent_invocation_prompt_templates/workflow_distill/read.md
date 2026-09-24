# AGENT TASK PAYLOAD: DISTILL.READ

## 1. INPUT

### 1.1 Context

**Inline (critical for orientation):**

- **Step:** DISTILL.READ
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Target repository:** {{target_repo_path}}
- **Step folder:** {{step_folder}}

**External (read in this order before accessing Working Material):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `agents_runtime/AGENT_PRIMER.md` | **First** — vocabulary, invariants, agent text format, dual-graph model |
| Lens Primer | `agents_runtime/LENS_PRIMER.md` | **Second** — understand lens views and detail levels before reading lens files |
| Serialization Format | `foundation_and_formalism/SERIALIZATION_FORMAT.md` | When writing lens edits |
| md-doc-tree-rich CLI | System-wide command (`md-doc-tree-rich <path>`) | For generating the doc manifest — run via Bash |
| Edit Primer | `agents_runtime/AGENT_EDIT_PRIMER_V2.md` | When proposing children (Step 4) |

### 1.2 Working Material

Read these files from {{step_folder}}:

| File | Role | Required |
|------|------|----------|
| `input_lens.yaml` | Target node + target-adj IV-context lens (full tree with variable LOD) | Yes |

### 1.3 Environment

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}

---

## 2. INSTRUCTIONS

### 2.1 Primary Objective

> Discover relevant documentation for the target and extract intent from prose. Propose intent, constraints, epistemic state, and decomposition from documentation alone.

### 2.2 Initialization

Read and follow:

- `.claude/agents/ig-docreader-agent.md` (core agent definition)
{{agent_mode_modules}}

Refer to §1.1 External for primer reading order.

### 2.3 Algorithm / Execution Path

#### Step 1: Discover Documentation

- Run `md-doc-tree-rich {{target_repo_path}}` via Bash to generate a rich manifest of the target repository's documentation
- The manifest gives you a structured index of markdown files (titles, line counts, section counts)
- Use the manifest to **select docs relevant to the current target** `{{target_uid}}`

#### Step 2: Read Selected Documentation

- Read the selected docs (use manifest to prioritize — don't read everything)
- Focus on content that describes the target's purpose, behavior, constraints, and design decisions

#### Step 3: Propose Intent from Prose

- **Extract intent statements** — what the target is supposed to do (the "why" and "what")
- **Extract constraints** — rules, invariants, requirements mentioned in docs
- **Set epistemic_state** — `"unknown"` if docs are ambiguous, `"risky"` if docs suggest complexity
- **Distinguish intent from implementation notes** — docs may describe both; only intent goes in the `intent` field

#### Step 4: Propose Decomposition (Children)

**This step is mandatory for every non-leaf target.** Read the **Edit Primer** (`agents_runtime/AGENT_EDIT_PRIMER_V2.md` §Expansion Protocol) for signals, mechanics, content migration, and intentlink handling.

**Docreader-specific guidance:**

- Propose children based on documentation structure — distinct sub-sections, functional descriptions, or architectural components described in the docs.
- Each child gets `epistemic_state: "unknown"` (code hasn't confirmed yet).
- If genuinely atomic (single responsibility, no sub-phases) → state "no decomposition warranted" with rationale.
- **Do not skip this step.** A target without children and without an explicit "no decomposition" statement is incomplete.

#### If No Docs Found

If the manifest returns empty or no relevant docs exist:

- Record `result: "no docs found — skipped"` in your output
- Pass through the input lens unchanged (the Extractor will work from code alone)

### 2.4 Constraints, Exits & Escalations

**Constraints:**

- Read ONLY files listed in §1.1 and §1.2, plus docs discovered via the manifest
- If the manifest is empty, report it and pass through — do not forage for docs
- Do not modify input files. Propose edits in output files.
- Do not read source code — that is the Extractor's job in the next step

**Exit Conditions:**

- If `input_lens.yaml` is missing → FAILURE
- If `md-doc-tree-rich` command fails → report error, pass through lens as-is (PARTIAL)

**Escalation Rules:**

- If docs contain contradictory information about the target's purpose, yield to HUMAN with both interpretations
- Default Escalation Target: HUMAN

---

## 3. OUTPUT CONTRACT

### 3.1 Artifacts

Use `ig-tool` commands to apply all changes. The orchestrator will apply changes via lens diff/apply.

**Commands to use:**
```bash
# Update node fields
ig-tool node set --uid UID --intent "Intent from docs" --epistemic-state undecided

# Add constraints from documentation
ig-tool node set --uid UID --constraints "Constraint 1" --constraints "Constraint 2"

# Add design notes documenting doc sources
ig-tool node set --uid UID --design-notes "Extracted from: README.md, ARCHITECTURE.md"
```

All changes are applied via CLI commands, not manual YAML edits.

### 3.2 Epistemology

- Confidence Score: 0.0–1.0 (how well docs covered the target's purpose)
- Unknowns / Assumptions: list any areas where docs were silent or ambiguous

### 3.3 Control Flow & Telemetry

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of what was extracted from docs
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
