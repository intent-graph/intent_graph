# Step I/O Protocol

How the orchestrator communicates with sub-agents: what goes in the prompt, what goes on disk, and how both are structured for observability and token efficiency.

**This protocol is opt-in.** The orchestrator activates it by creating step folders and composing prompts per this spec. Agents do not assume filesystem I/O by default — they work with whatever context the prompt provides (inline or file-referenced). The prompt itself signals which mode is active: if it contains a `## Step Context` section with a step folder path, the agent reads files from disk. If not, the agent works from inline context only.

**Agent I/O Format:**
- **Primary (recommended):** Lens YAML format + CLI-mediated edits via `ig-tool`
- **Legacy (backwards compatible):** Working view YAML format + manual edit YAML (deprecated)

## Table of Contents

1. [Design Principles](#design-principles) _(Lines 64-76)_
1. [Step Folder Layout](#step-folder-layout) _(Lines 79-156)_
1. [Prompt Structure](#prompt-structure) _(Lines 159-194)_
1. [Agent I/O Formats: Primary (Lens) & Legacy (View)](#agent-io-formats-primary-lens--legacy-view) _(Lines 197-197)_
   1. [Lens Format (Primary, Recommended)](#lens-format-primary-recommended) _(Lines 200-371)_
   1. [Working View Format (Legacy, Backwards Compatible)](#working-view-format-legacy-backwards-compatible) _(Lines 374-393)_
1. [Inline vs. Filesystem Split](#inline-vs-filesystem-split) _(Lines 396-396)_
   1. [Always inlined in prompt (costs tokens, ensures reliability)](#always-inlined-in-prompt-costs-tokens-ensures-reliability) _(Lines 399-409)_
   1. [Always on filesystem (agent reads via path)](#always-on-filesystem-agent-reads-via-path) _(Lines 412-424)_
   1. [Judgment call (context-dependent)](#judgment-call-context-dependent) _(Lines 427-435)_
1. [Tool Invocation Catalog: ig-tool Subcommands](#tool-invocation-catalog-ig-tool-subcommands) _(Lines 438-440)_
   1. [Lens Commands](#lens-commands) _(Lines 443-476)_
   1. [Node Commands](#node-commands) _(Lines 479-508)_
   1. [Link Commands](#link-commands) _(Lines 511-529)_
   1. [Batch Operations](#batch-operations) _(Lines 532-563)_
   1. [Context: Query without Mutation](#context-query-without-mutation) _(Lines 566-576)_
1. [Orchestrator Procedure](#orchestrator-procedure) _(Lines 579-583)_
   1. [1. Create step folder and copy inputs](#1-create-step-folder-and-copy-inputs) _(Lines 586-600)_
   1. [2. Build Lens context (Primary)](#2-build-lens-context-primary) _(Lines 603-619)_
   1. [3. Copy prompt template to step folder](#3-copy-prompt-template-to-step-folder) _(Lines 622-647)_
   1. [4. Look up template parameters in dispatch table](#4-look-up-template-parameters-in-dispatch-table) _(Lines 650-661)_
   1. [5. Generate simplified invocation prompt](#5-generate-simplified-invocation-prompt) _(Lines 664-705)_
   1. [6. Invoke agent with typed subagent and simplified prompt](#6-invoke-agent-with-typed-subagent-and-simplified-prompt) _(Lines 708-733)_
   1. [6a. Resume agent (when re-entering a step for the same target)](#6a-resume-agent-when-re-entering-a-step-for-the-same-target) _(Lines 736-774)_
   1. [6b. Handle YIELD_FOR_INPUT with file-based dialogue](#6b-handle-yield_for_input-with-file-based-dialogue) _(Lines 777-804)_
   1. [7. Collect output](#7-collect-output) _(Lines 807-818)_
   1. [8. Record trace](#8-record-trace) _(Lines 821-825)_
   1. [9. Apply results](#9-apply-results) _(Lines 828-860)_
1. [Agent Contract](#agent-contract) _(Lines 863-865)_
   1. [Input](#input) _(Lines 868-874)_
   1. [Output](#output) _(Lines 877-929)_
   1. [Prohibitions](#prohibitions) _(Lines 932-947)_
   1. [Reporting gaps](#reporting-gaps) _(Lines 950-967)_
1. [File-Dialogue Specification](#file-dialogue-specification) _(Lines 970-972)_
   1. [Folder layout](#folder-layout) _(Lines 975-983)_
   1. [`round_summary.md` — cumulative context](#round_summarymd--cumulative-context) _(Lines 986-1003)_
   1. [`question_NNN.md` — decision file](#question_nnnmd--decision-file) _(Lines 1006-1050)_
   1. [Response extraction protocol](#response-extraction-protocol) _(Lines 1053-1071)_
   1. [Batch semantics](#batch-semantics) _(Lines 1074-1076)_
   1. [Constraints](#constraints) _(Lines 1079-1086)_







---

## Design Principles
<!-- Lines 64-76 -->

1. **Prompt = task description + pointers.** The prompt tells the agent what to do, which step it's executing, what target it's working on, and which files to read. It does not contain bulk data.

2. **Filesystem = bulk data.** IntentGraph JSON, ProjectionIG, CodeMap YAML, source code, documentation — all live on disk. The agent reads them via explicit absolute paths provided in the prompt.

3. **Every step gets a folder.** Before invoking an agent, the orchestrator creates a timestamped step folder containing all input files. After the agent finishes, its output files go into the same folder. This makes every agent invocation fully observable post-hoc.

4. **Input manifest.** The step folder contains a `_manifest.yaml` listing every file, its role, and whether the agent should read it. The agent can read the manifest to orient itself, but the prompt also lists the key files explicitly.

5. **Output convention.** The agent writes its output to a well-known filename in the step folder (e.g., `output_edits.yaml`, `output_issues.yaml`, `output_code/`). The orchestrator reads from these paths after the agent finishes.

---

## Step Folder Layout
<!-- Lines 79-156 -->

```text
{workflow_root}/
├── graph.json                          # Current IntentGraph (updated after each COMMIT)
├── projection_ig.yaml                  # Current ProjectionIG
├── workflow_state.json                 # Orchestrator state (target queue, current step, etc.)
├── trace.jsonl                         # Workflow trace (append-only)
├── .ig_logs/                           # Agent I/O logs (per-role JSONL for Phase 5)
└── steps/                              # Step I/O folders
    ├── 001_DISTILL.MAP/                # Sequential numbering + step UID
    │   ├── _manifest.yaml
    │   ├── _prompt.md                  # Prompt sent to agent (for observability)
    │   ├── input_codemap_overview.yaml # CodeMap output (if available)
    │   └── output_projection_ig.yaml   # Initial ProjectionIG skeleton
    ├── 002_DISTILL.PICK/
    │   ├── _manifest.yaml
    │   ├── _prompt.md                  # Prompt sent to agent
    │   └── output_target_recommendation.yaml  # Steward target recommendation + rationale
    ├── 003_DISTILL.SCOPE/
    │   ├── _manifest.yaml
    │   ├── _prompt.md                  # Prompt sent to agent
    │   ├── input_lens.yaml             # [PRIMARY] Lens format: full tree with LOD fields
    │   └── output_summary.yaml         # Summary of lens construction (budget, pruning info)
    ├── 004_DISTILL.READ/
    │   ├── _manifest.yaml
    │   ├── _prompt.md                  # Prompt sent to agent
    │   ├── input_lens.yaml             # [PRIMARY] Lens format with target refined
    │   ├── input_docs/                 # Relevant doc files (copied or symlinked)
    │   │   ├── README.md
    │   │   └── FUNCTION_VALIDATION_PATTERNS.md
    │   └── output_summary.yaml         # Summary: nodes modified, edits applied via ig-tool
    ├── 005_DISTILL.EXTRACT/
    │   ├── _manifest.yaml
    │   ├── _prompt.md                  # Prompt sent to agent
    │   ├── input_lens.yaml             # [PRIMARY] Lens format with Docreader contributions
    │   ├── input_source/               # Source code files in scope
    │   │   ├── parser.py
    │   │   └── validator.py
    │   ├── input_codemap_context.yaml  # CodeMap IV-context for target area
    │   └── output_summary.yaml         # Summary: nodes modified, edits applied via ig-tool
    ├── 006_DISTILL.CHALLENGE/
    │   ├── _manifest.yaml
    │   ├── _prompt.md                  # Prompt sent to agent
    │   ├── input_lens.yaml             # [PRIMARY] Lens format (self-contained working copy)
    │   ├── input_projection_observations.yaml  # Extractor's ProjectionIG observations
    │   └── output_issues.yaml          # Structured issue list (no edits; read-only analysis)
    ├── 007_DISTILL.REFINE/
    │   ├── _manifest.yaml
    │   ├── _prompt.md
    │   ├── input_lens.yaml             # [PRIMARY] Lens format (working copy for refinement)
    │   ├── input_projection_observations.yaml
    │   ├── input_issues.yaml
    │   └── human_dialogue/             # Created by agent on YIELD_FOR_INPUT (not orchestrator)
    │       ├── round_summary.md        # Cumulative context (what's resolved, what's next)
    │       ├── question_001.md         # Human edits in-place (one per decision point)
    │       └── question_002.md
    ├── 008_DISTILL.COMMIT/
    │   ├── _manifest.yaml
    │   ├── _prompt.md
    │   ├── input_lens.yaml             # [PRIMARY] Lens working copy with all refinements
    │   ├── input_graph.json            # Copied from workflow root (graph.json)
    │   ├── input_projection_ig.yaml    # Copied from workflow root (projection_ig.yaml)
    │   ├── input_workflow_state.json   # Copied from workflow root (workflow_state.json)
    │   ├── output_graph.json           # Updated product IntentGraph (lens applied + committed)
    │   ├── output_projection_ig.yaml   # Updated ProjectionIG
    │   ├── output_workflow_state.json  # Updated workflow state
    │   └── output_steward_report.yaml  # Steward report (audit, queue, etc.)
    └── ...
```

**Lens file format** — added to workflow steps. Agents read `input_lens.yaml` and use `ig-tool` to modify graph structure. Changes are applied via `ig-tool lens apply` before COMMIT step collects outputs.

**Legacy format** (backwards compatible) — older workflows may still use `input_view.yaml` + manual `output_edits.yaml`. Orchestrator detects format and handles accordingly.

**Naming convention:** `{NNN}_{STEP_UID}/` where NNN is a zero-padded sequence number. This gives chronological ordering in `ls` and makes it trivial to find the latest step.

---

## Prompt Structure
<!-- Lines 159-194 -->

Each prompt template follows the canonical 3-section structure from [ai_tooling/howto/programming_subagents.md](../../../ai_tooling/howto/programming_subagents.md). Parameters use `{{double_braces}}` to distinguish from literal text.

```text
# AGENT TASK PAYLOAD: {{STEP_UID}}

## 1. INPUT
### 1.1 Context (immutable orientation — step metadata + external reference docs)
### 1.2 Working Material (files the agent reads and transforms)
### 1.3 Environment (execution flags: dry_run, verbosity, effort_hint)

## 2. INSTRUCTIONS
### 2.1 Primary Objective (one-sentence goal)
### 2.2 Initialization (agent files to read, shared context)
### 2.3 Algorithm / Execution Path (step-by-step procedure)
### 2.4 Constraints, Exits & Escalations

## 3. OUTPUT CONTRACT
### 3.1 Artifacts (filenames + formats)
### 3.2 Epistemology (confidence score + unknowns)
### 3.3 Control Flow & Telemetry (status enum + summary)
### 3.4 Escalation Payload (only if YIELD_FOR_INPUT)
```

Parameters are declared in dispatch tables (§Parameter Registry), not in templates. Templates consume parameters; dispatch tables declare them.

**Key design decisions:**

- **Absolute paths** for step folders and workflow artifacts. Reference documents and agent files use project-root-relative paths — this works because the orchestrator guarantees CWD = project root (see [orchestrator_protocol.md §CWD Invariant](orchestrator_protocol.md#cwd-invariant)).
- **File table** — agent sees exactly what's available and whether each file is required or optional.
- **Anti-foraging rule** — explicit, in every prompt. Prevents FINDING-001.
- **Output path** — agent knows where to write. Orchestrator knows where to read.
- **Mode module line** — allows modular agent files: core always + mode-specific module only when needed.

---

## Agent I/O Formats: Primary (Lens) & Legacy (View)
<!-- Lines 197-197 -->

### Lens Format (Primary, Recommended)
<!-- Lines 200-371 -->

The **Lens** is the primary agent I/O format. It provides:
1. **Full tree structure** — not a flat antichain, but a valid subtree with hierarchical context
2. **Variable detail via Level-of-Detail (LOD)** — skeleton (uid + name), lean (+ intent + epistemic_state), or full (all fields)
3. **IV_-shaped detail** — target node + direct neighbors at full LOD, ancestors at lean LOD, L1 brim at lean LOD, everything else at skeleton
4. **Pruning metadata** — branches beyond budget show `[+N children pruned]` markers
5. **Collapsed children context** — agents can see that subtrees exist even if pruned

**Lens input structure** — agent receives `input_lens.yaml`:

```yaml
lens:
  name: "working-on-parser"
  target: ROOT.PARSE
  budget: 30
  source_graph: "graph.json"

nodes:
  - uid: ROOT
    name: "Sync Validator"
    lod: skeleton

  - uid: ROOT.PARSE
    name: "Parser"
    lod: full
    intent: "Extract and validate CSV rows"
    epistemic_state: "known"
    constraints:
      - "Must handle UTF-8 encoding"
      - "Max 1GB file size"
    design_notes: "Using custom FSM to avoid regex overhead"

  - uid: ROOT.PARSE.LEX
    name: "Lexer"
    lod: full
    intent: "Tokenize input stream"
    epistemic_state: "known"

  - uid: ROOT.PARSE.SYN
    name: "Syntax Analysis"
    lod: full
    intent: "Build parse tree from tokens"
    epistemic_state: "constrained"

  - uid: ROOT.NORM
    name: "Normalizer"
    lod: lean
    intent: "Clean and canonicalize data"
    epistemic_state: "undecided"

treearcs:
  - { parent: ROOT, child: ROOT.PARSE }
  - { parent: ROOT, child: ROOT.NORM }
  - { parent: ROOT.PARSE, child: ROOT.PARSE.LEX }
  - { parent: ROOT.PARSE, child: ROOT.PARSE.SYN }

intentlinks:
  # Full-LOD endpoints: show complete detail
  - uid: link_01
    src: ROOT.PARSE.LEX
    dst: ROOT.PARSE.SYN
    relation: data_flow
    description: "Lexer output feeds syntax analyzer"

  # Lean-LOD endpoints: show structure only
  - uid: link_02
    src: ROOT.PARSE
    dst: ROOT.NORM
    relation: dependency
    # Note: description omitted for lean-LOD links
```

**Lens manipulation** — agents interact via `ig-tool lens` commands:

```bash
# Focus operations (change target and LOD)
ig-tool lens focus <uid>              # set as target, recalculate LODs via IV_
ig-tool lens promote <uid>            # increase LOD: skeleton→lean or lean→full
ig-tool lens demote <uid>             # decrease LOD: full→lean or lean→skeleton
ig-tool lens set-lod <uid> <lod>      # explicit LOD: skeleton | lean | full

# Scope operations (prune/expand branches)
ig-tool lens prune <uid>              # remove subtree from lens
ig-tool lens expand <uid>             # add subtree back from full graph
ig-tool lens expand <uid> --depth 2   # add back with depth limit
ig-tool lens set-budget <N>           # resize; auto-prune/expand to fit

# View operations (inspect current state)
ig-tool lens show                     # current lens as YAML
ig-tool lens info                     # meta: target, budget, node count, LOD stats
ig-tool lens list-pruned              # what branches have been cut
ig-tool lens tree                     # ASCII tree view (uid + name + LOD indicators)
ig-tool lens diff                     # changes made by agent (before apply)
```

**Agent edits via CLI** — agents use atomic, validated commands instead of producing YAML edits:

```bash
# Create — whole object via named flags
ig-tool node create --parent ROOT.PARSE \
  --name "Error Handler" \
  --intent "Report and recover from parse errors" \
  --epistemic_state "undecided" \
  --constraints "Must not crash on malformed input"

# Edit — field-level via named flags
ig-tool node set ROOT.PARSE --intent "New intent text"
ig-tool node set ROOT.PARSE.LEX --constraints "UTF-8 only" --constraints "Max 1GB"

# Move — structural changes
ig-tool node reparent ROOT.PARSE.LEX --under ROOT.PARSE.SYN
ig-tool node reorder ROOT.PARSE --children ROOT.PARSE.SYN --children ROOT.PARSE.LEX

# Delete
ig-tool node remove ROOT.PARSE.UNUSED --recursive
ig-tool link remove link_01

# Links
ig-tool link create --src ROOT.PARSE --dst ROOT.NORM \
  --relation data_flow \
  --description "Parser output feeds normalizer"

ig-tool link set link_01 --description "Updated description"
```

**Batch operations** — for multiple edits, use atomic batches:

```bash
ig-tool apply --batch /tmp/edits.yaml -g graph.json -o updated_graph.json
```

Where `edits.yaml` follows the same field names:

```yaml
- op: node.set
  uid: ROOT.PARSE
  intent: "New intent"

- op: node.create
  parent: ROOT.PARSE
  name: "Error Handler"
  intent: "Handle parse errors"

- op: node.reparent
  uid: ROOT.PARSE.LEX
  under: ROOT.PARSE.SYN
```

**Agent output contract** — for Lens format:

1. **Use `ig-tool` commands exclusively** — no manual YAML edits
2. **Verify changes before applying:**
   ```bash
   ig-tool lens diff  # inspect all changes
   ```
3. **Apply atomically:**
   ```bash
   ig-tool lens apply  # patches full graph, resets lens
   ```
4. **Return summary to orchestrator:**
   ```yaml
   output_file: "output_summary.yaml"
   summary: "Reviewed 8 nodes. Refined intent on ROOT.PARSE, created ROOT.PARSE.ERR_HANDLER."
   metrics:
     nodes_modified: 1
     nodes_created: 1
     links_created: 1
   status: "complete"
   ```

---

### Working View Format (Legacy, Backwards Compatible)
<!-- Lines 374-393 -->

The **working view** is a full-tree view with uniform detail — a legacy agent I/O format that agents can still receive for backwards compatibility. Agents should prefer Lens format (which offers variable LOD).

**When working view is used:**

- Agents receive `input_view.yaml` (full tree, all nodes at full detail)
- Agents produce `output_edits.yaml` in manual YAML format
- Orchestrator applies via `ig-tool apply` (may require manual intervention if malformed)

**Working view limitations vs. Lens:**

- No budget metadata: agents see everything, loss of context prioritization
- Uniform detail only: no variable LOD for context management
- Manual edits: error-prone YAML manipulation
- Coarser focus: harder to know which area is the actual target

**Migration path:** New workflows and agents use Lens. Existing workflows using working view continue to work with existing tooling. No forced migration.

---

## Inline vs. Filesystem Split
<!-- Lines 396-396 -->

### Always inlined in prompt (costs tokens, ensures reliability)
<!-- Lines 399-409 -->

| Content | Why inline |
|---------|-----------|
| Agent instructions reference | Agent must know which `.claude/agents/` file to read |
| Step UID + workflow type + target UID | Minimal, critical for orientation |
| Task description (1 paragraph) | Agent must know what to do without reading anything |
| Input file table (paths + roles) | Agent must know what to read and where |
| Output format + path | Agent must know what to produce |
| Anti-foraging constraint | Prevents filesystem exploration |
| Working view summary (1-3 lines) | Quick orientation: "ROOT has 5 children, you're working on PARSER" |

### Always on filesystem (agent reads via path)
<!-- Lines 412-424 -->

| Content | Why filesystem |
|---------|---------------|
| IntentGraph JSON | Large, versioned, reusable across steps |
| ProjectionIG JSON/YAML | Same — persistent artifact |
| Lens YAML (primary agent I/O) | Full tree structure with LOD metadata — too large to inline reliably |
| Working view YAML (legacy format) | Can be 1000+ words — too large to inline reliably |
| Source code files | Bulk data, varies per target |
| Documentation files | Bulk data, varies per target |
| CodeMap overview/context YAML | Structural data, potentially large |
| Previous step outputs (edits, issues) | Observable chain — each step can see prior step output |
| Target CodeMap YAML (Designer output) | Architecture artifact for Generator |

### Judgment call (context-dependent)
<!-- Lines 427-435 -->

| Content | When to inline | When to put on disk |
|---------|---------------|-------------------|
| Critic issue list | If < 500 words (small issue list) | If > 500 words (many issues) |
| Conversation history (Elicitor) | Last 2-3 turns | Full history |
| Budget check results | Always inline (2 lines) | — |

---

## Tool Invocation Catalog: ig-tool Subcommands
<!-- Lines 438-440 -->

Agents working with Lens format use `ig-tool` to read, navigate, and edit the graph. All commands support `--dry-run` for validation without applying changes. Refer to `agents/PRIMER_TOOLS.md` (WHY/when) and `.claude/skills/ig-tool-*/SKILL.md` (exact syntax) for the full command reference and examples.

### Lens Commands
<!-- Lines 443-476 -->

**Build and inspect:**
```bash
ig-tool lens build --source graph.json --target UID --budget 30 --output lens.yaml
ig-tool lens show                      # Current lens as YAML
ig-tool lens info                      # Meta: target, budget, LOD stats
ig-tool lens tree                      # ASCII tree view with uid + name + LOD indicators
ig-tool lens list-pruned               # Pruned branches and markers
```

**Adjust focus and detail:**
```bash
ig-tool lens focus <uid>               # Set as target, recalculate LODs via IV_
ig-tool lens promote <uid>             # skeleton→lean or lean→full
ig-tool lens demote <uid>              # full→lean or lean→skeleton
ig-tool lens set-lod <uid> <lod>       # Explicit LOD assignment
```

**Prune and expand scope:**
```bash
ig-tool lens prune <uid>               # Remove subtree from lens
ig-tool lens expand <uid>              # Add subtree back from full graph
ig-tool lens expand <uid> --depth 2    # Add back with depth limit
ig-tool lens set-budget <N>            # Resize; auto-prune/expand to fit
```

**Persist and validate:**
```bash
ig-tool lens diff                      # Changes made vs. full graph (before apply)
ig-tool lens apply                     # Patch full graph with lens changes, reset lens
ig-tool lens apply --dry-run           # Validate patch without applying
ig-tool lens discard                   # Throw away changes, reset to graph state
```

### Node Commands
<!-- Lines 479-508 -->

**Create and read:**
```bash
ig-tool node create --parent UID \
  --name "Name" \
  --intent "Intent text" \
  --epistemic_state "undecided|constrained|known" \
  --constraints "Constraint 1" --constraints "Constraint 2" \
  --design_notes "Implementation details"

ig-tool node show UID                  # Full node detail
```

**Edit — field-level mutations:**
```bash
ig-tool node set UID --intent "New intent"
ig-tool node set UID --name "New name"
ig-tool node set UID --epistemic_state "known"
ig-tool node set UID --constraints "C1" --constraints "C2"  # Replaces list
ig-tool node set UID --design_notes "Notes"
```

**Structural changes:**
```bash
ig-tool node reparent UID --under NEW_PARENT_UID
ig-tool node reorder PARENT_UID --children UID1 --children UID2 --children UID3
ig-tool node remove UID                # Leaf only
ig-tool node remove UID --recursive     # Remove subtree
```

### Link Commands
<!-- Lines 511-529 -->

**Create and read:**
```bash
ig-tool link create --src SOURCE_UID --dst DEST_UID \
  --relation "dependency|data_flow|control_flow|..." \
  --description "Link description"
```

**Edit:**
```bash
ig-tool link set LINK_UID --description "Updated description"
ig-tool link set LINK_UID --relation "new_relation"
```

**Delete:**
```bash
ig-tool link remove LINK_UID
```

### Batch Operations
<!-- Lines 532-563 -->

Execute multiple commands atomically:

```bash
ig-tool apply --batch edits.yaml -g graph.json -o updated_graph.json
```

Format (YAML with same field names):

```yaml
- op: node.create
  parent: ROOT
  name: "New Module"
  intent: "Purpose"

- op: node.set
  uid: ROOT.PARSER
  intent: "Revised intent"

- op: link.create
  src: ROOT.PARSER
  dst: ROOT.LEXER
  relation: data_flow
  description: "Parser feeds lexer"

- op: node.reparent
  uid: ROOT.OLD.CHILD
  under: ROOT.NEW.PARENT
```

All commands validate before applying. Batch rolls back entirely on any error (atomic transaction).

### Context: Query without Mutation
<!-- Lines 566-576 -->

For ad-hoc queries (useful in conjunction with Lens):

```bash
ig-tool query --graph graph.json --node ROOT.PARSER       # Single node
ig-tool query --graph graph.json --children ROOT.PARSER   # Direct children
ig-tool query --graph graph.json --ancestors ROOT.PARSER.LEX  # Path to root
```

---

## Orchestrator Procedure
<!-- Lines 579-583 -->

For each step, the orchestrator does:

**Key principle:** Copy templates, don't compose prompts. Use Bash to copy canonical templates from `agent_invocation_prompt_templates/`, then generate a minimal invocation prompt with just pointers and parameters.

### 1. Create step folder and copy inputs
<!-- Lines 586-600 -->

Use `ig-tool workflow step create` to create the folder, copy files from the previous step, and write the manifest — all in one command without reading any file content:

```bash
ig-tool workflow step create \
  --dir {workflow_root}/steps/ \
  --step DISTILL.CHALLENGE \
  --target PARSER \
  --prev {workflow_root}/steps/005_DISTILL.EXTRACT \
  --copy output_view.yaml:input_view.yaml \
  --copy output_projection_observations.yaml:input_projection_observations.yaml
```

For source code, docs, or CodeMap context, use additional `--copy` flags or copy with `Bash("cp ...")` after creation.

### 2. Build Lens context (Primary)
<!-- Lines 603-619 -->

Use `ig-tool lens build` to produce the scoped Lens with IV_-shaped detail:

```bash
ig-tool lens build \
  --source graph.json \
  --target PARSER \
  --budget 30 \
  --output {step_folder}/input_lens.yaml
```

The result is a valid tree view with variable LOD (skeleton < lean < full), IV_-shaped detail assignment (full at target + neighbors, lean at ancestors + L1 brim, skeleton elsewhere), and pruning markers for nodes beyond budget. The orchestrator sees only stdout summary (node count, budget status, pruned branches). The full `graph.json` stays in the workflow root for reference.

**For legacy workflows:** Use project-specific conversion to produce working view YAML (backwards-compatible, but agents should migrate to Lens).

The exact mechanism varies; consult the agent guide for instructions.

### 3. Copy prompt template to step folder
<!-- Lines 622-647 -->

**CRITICAL: You MUST use the Bash tool to copy the canonical prompt template. DO NOT manually compose or write the prompt.**

The canonical templates live in:

```text
agents_runtime/orchestrator/agent_invocation_prompt_templates/workflow_{workflow_type}/{step_name}.md
```

For example, for DISTILL.PICK:

```bash
cp agents_runtime/orchestrator/agent_invocation_prompt_templates/workflow_distill/pick.md \
   {step_folder}/_prompt.md
```

**Step name mapping:** DISTILL.PICK → `pick.md`, DISTILL.CHALLENGE → `challenge.md`, etc. (lowercase, no prefix)

**Why copy with Bash, not Write:**

- Templates are version-controlled and reviewed
- Manual composition introduces drift and errors
- Templates contain canonical structure, constraints, and file tables
- Observability: same template used every time
- **Forces you to use existing templates, not invent new prompts**

### 4. Look up template parameters in dispatch table
<!-- Lines 650-661 -->

Look up the required parameters in the dispatch table's **§Parameter Registry** for the current step. Do NOT read the template to discover parameters — the registry is the single source of truth.

Example: For DISTILL.PICK, the registry says:

| Parameter | Type | Source |
| --------- | ---- | ------ |
| `{{step_folder}}` | path | `ig-tool workflow step create` output |
| `{{agent_mode_modules}}` | text | Module Routing Table → always `ig-steward-mode-pick.md` |

**Do NOT fill these in the `_prompt.md` file. Leave the template as-is.** The agent will substitute them when it reads the template.

### 5. Generate simplified invocation prompt
<!-- Lines 664-705 -->

Create a minimal prompt that contains **only**:

1. Pointer to the full prompt template
2. Template parameter values (using `{{double_braces}}`)

Example for DISTILL.PICK:

```text
Execute the task described in:
/abs/path/to/steps/021_DISTILL.PICK/_prompt.md

To do so, you can use these template parameters:
- {{step_folder}}: /abs/path/to/steps/021_DISTILL.PICK
- {{agent_mode_modules}}: - `.claude/agents/ig-steward-mode-pick.md` (Mode 3: Target recommendation)

All other content is literal text from the template.
```

**Generate this programmatically:**

```python
# Determine mode module from dispatch table §Module Routing Table
mode_module_line = f"- `.claude/agents/{mode_module_file}` ({mode_description})"

simplified_prompt = f"""Execute the task described in:
{step_folder}/_prompt.md

To do so, you can use these template parameters:
- {{{{step_folder}}}}: {step_folder}
- {{{{agent_mode_modules}}}}: {mode_module_line}

All other content is literal text from the template.
"""
```

Write this to disk using the Write tool:

```python
Write(file_path=f"{step_folder}/_invocation.md", content=simplified_prompt)
```

### 6. Invoke agent with typed subagent and simplified prompt
<!-- Lines 708-733 -->

```text
Task(
  subagent_type="{agent_type}",  # e.g., "ig-elicitor-agent", "ig-critic-agent"
  description="{STEP_UID}: {short description}",
  prompt=simplified_prompt  # NOT the full composed prompt
)
```

**Agent type mapping** (from dispatch table):
- PICK → `"ig-steward-agent"`
- READ → `"ig-docreader-agent"`
- EXTRACT → `"ig-extractor-agent"`
- CHALLENGE → `"ig-critic-agent"`
- REFINE → `"ig-elicitor-agent"`
- COMMIT → `"ig-steward-agent"`
- RECHECK → `"ig-critic-agent"`
- DESIGN → `"ig-designer-agent"`
- GENERATE → `"ig-generator-agent"`
- VERIFY → `"ig-verifier-agent"`
- CLARIFY → `"ig-elicitor-agent"`

**CRITICAL:** Do NOT use `"general-purpose"` — it loads 150-180K tokens of unnecessary Claude Code system context (git protocols, tool docs, project CLAUDE.md, agent catalog). Typed agents load only their agent definition (~10-15K tokens).

**Rationale:** Typed invocation keeps the agent's context window lean (~10-15K for agent def + inputs) vs. 200K+ for general-purpose. This reduces runtime from 8-10 minutes to 1-2 minutes per step.

### 6a. Resume agent (when re-entering a step for the same target)
<!-- Lines 736-774 -->

Some steps can be re-entered for the same target — notably `*.REFINE` after a RECHECK loop-back or after a YIELD dialogue round. When this happens, the orchestrator should **resume the existing agent** instead of creating a fresh one, so the agent retains its full dialogue context.

**Decision logic:**

```text
if refine_agent_id is not null AND refine_agent_target == current_target:
    # Resume: agent retains prior context
    Task(
      resume=refine_agent_id,
      description="{STEP_UID} (resumed): round {N} for {target}",
      prompt=resumption_prompt
    )
else:
    # Fresh invocation (standard §6 path)
    Task(subagent_type="ig-elicitor-agent", ...)  # Typed agent, not "general-purpose"
    # Store returned agent_id in workflow_state.json
```

**Resumption prompt** — minimal, since the agent already has full context:

```text
You are being resumed for another REFINE pass on target {{target_uid}}.
New inputs in: {{step_folder}}/
- input_issues.yaml (updated from RECHECK)
- input_view.yaml (current)
This is round {{refine_dialogue_round}}. You retain full context from prior rounds.
```

**State fields** (stored in `workflow_state.json`, managed by orchestrator):

| Field | Type | Purpose |
| ----- | ---- | ------- |
| `refine_agent_id` | string or null | Task tool's returned agent_id |
| `refine_agent_target` | string or null | Target UID when agent was created |
| `refine_dialogue_round` | int | Counter, incremented on each YIELD or RECHECK loop-back |

Cleared when PICK selects a new target or human overrides the target.

### 6b. Handle YIELD_FOR_INPUT with file-based dialogue
<!-- Lines 777-804 -->

When an agent returns `YIELD_FOR_INPUT` with `target: HUMAN`, it has created dialogue files in `{step_folder}/human_dialogue/` for the human to review and edit. The orchestrator is a **dumb relay** — it passes the folder path to the human without reading any dialogue files.

**Procedure:**

1. Agent returns `YIELD_FOR_INPUT` with `dialogue_folder` in escalation payload.
2. Orchestrator prints to human:

   ```text
   The Elicitor needs your input. Please review and edit the question files in:
   {step_folder}/human_dialogue/
   When done, confirm here.
   ```

3. Orchestrator does NOT read or interpret the dialogue files.
4. Human edits the `question_NNN.md` files in-place (filling in `<choice>` and `<comments>` tags).
5. Human confirms.
6. Orchestrator resumes the agent (§6a):

   ```text
   Human has responded. Read updated files in {step_folder}/human_dialogue/ and continue.
   ```
7. Agent reads human responses, processes them, and either:
   - Returns `SUCCESS` or `PARTIAL` → proceed to next step
   - Returns `YIELD_FOR_INPUT` again → repeat from step 2 (new round)

See [§File-Dialogue Specification](#file-dialogue-specification) for the dialogue file format.

### 7. Collect output
<!-- Lines 807-818 -->

After the agent finishes:
- Use the agent's task result (`summary`, `metrics`, `status`) for routing decisions
- If you need a metric the summary doesn't cover, use `ig-tool workflow step summary`:

  ```bash
  ig-tool workflow step summary {step_folder}/output_issues.yaml
  ```

- Do NOT read full output files into your context — see [orchestrator_protocol.md §Context Protection](orchestrator_protocol.md#context-protection)
- If output is missing or unparseable, log error and handle per [orchestrator_protocol.md §Error Handling](orchestrator_protocol.md#error-handling)

### 8. Record trace
<!-- Lines 821-825 -->

```bash
ig-tool workflow trace record trace.jsonl --step S --target T --actor A --action "..." --result "..."
```

### 9. Apply results
<!-- Lines 828-860 -->

**For Lens-based workflows (primary):**

- Non-COMMIT steps: Agent applies changes via `ig-tool lens apply` before returning. The Lens is atomically patched to the full graph. The agent returns a summary (nodes modified, links created, etc.) to the orchestrator.

  ```bash
  # Agent verifies changes
  ig-tool lens diff

  # Agent applies (patches graph, resets lens)
  ig-tool lens apply
  ```

- COMMIT step: The Steward reads the current graph.json (already updated by prior steps' lens apply), performs validation, and writes output files to the step folder. The orchestrator copies outputs back to the workflow root:

  ```bash
  cp {step_folder}/output_graph.json {workflow_root}/graph.json
  cp {step_folder}/output_projection_ig.yaml {workflow_root}/projection_ig.yaml
  cp {step_folder}/output_workflow_state.json {workflow_root}/workflow_state.json
  ```

**For legacy working-view workflows (backwards-compatible):**

- Non-COMMIT steps: apply edits via `ig-tool apply` (not manually). Accepts both full view (§2) and diff (§5) format — auto-detected.
- COMMIT steps: same as above.

**Common:**

- Update workflow state (current step, queue)
- After COMMIT: run Obsidian export (see `orchestrator_protocol.md` §Obsidian Visualization)

---

## Agent Contract
<!-- Lines 863-865 -->

Every agent operating under this protocol must follow these rules:

### Input
<!-- Lines 868-874 -->

1. **Read the agent instructions file** referenced in the prompt first.
2. **Read the shared context** (`AGENT_PRIMER.md`) referenced in the prompt's `## Shared Context` section.
3. **Read the input files** listed in the prompt's file table from the step folder.
4. **Read reference documents** listed in the prompt's `## Reference Documents` table. These are explicitly whitelisted by the orchestrator and exempt from the anti-foraging rule. Read on demand when needed — not all upfront.
5. **Do not search the filesystem** for files not listed in the prompt. If you need context that isn't provided, report the gap in your output.

### Output
<!-- Lines 877-929 -->

**CRITICAL: Use CLI for mutations, write summaries to disk, summarize to orchestrator.**

Agents follow a three-phase output protocol:

**1. Lens-based edits (Primary workflow):**
   - For mutation steps (READ, EXTRACT, REFINE): use `ig-tool` commands to edit the Lens
   - Apply changes atomically: `ig-tool lens apply`
   - Write summary only: `output_summary.yaml` (1-3 lines per decision)

**2. Read-only steps (CHALLENGE):**
   - Do NOT edit — produce analysis only
   - Write `output_issues.yaml` with structured findings
   - No graph mutations

**3. Return minimal summary to orchestrator** via the task result:
   - `output_file`: filename (relative to step folder)
   - `summary`: 1-3 sentence high-level summary
   - `metrics`: key counts/stats only (e.g., `{nodes_modified: 3, nodes_created: 1}`)
   - `status`: `"complete"`, `"incomplete"`, `"error"`, or `"yield_for_input"`
   - `dialogue_folder`: (only if `yield_for_input`) path to `human_dialogue/` subfolder
   - `gaps`: (optional) list of missing context if incomplete

**Example task result (Lens-based mutation):**

```yaml
output_file: "output_summary.yaml"
summary: "Refined intent on PARSER and LEXER. Created PARSER.ERR_HANDLER. Applied 3 edits via ig-tool."
metrics:
  nodes_modified: 2
  nodes_created: 1
  links_created: 1
status: "complete"
```

**Example task result (read-only analysis):**

```yaml
output_file: "output_issues.yaml"
summary: "Reviewed 8 nodes + 5 intentlinks. Found 12 issues: 2 major (structural), 10 minor (wording)."
metrics:
  issues: 12
  major: 2
  minor: 10
status: "complete"
```

**Why this matters:** The orchestrator's context window is limited. Full outputs (10-50KB) bloat context quickly. Summaries (200 bytes) + CLI-applied changes keep the orchestrator efficient while preserving full observability on disk.

**Key rule for Lens workflows:** All graph mutations go through `ig-tool` commands. The Lens file itself is the working copy. Apply before returning. Do not produce manual YAML edits.

**Use Write tool, not Bash:** Always use the Write tool to create output files. Never use `cat`, `echo`, or heredoc with Bash. Write tool handles permissions correctly.

### Prohibitions
<!-- Lines 932-947 -->

**For Lens-based workflows:**

1. **Do not produce manual YAML edits.** Use `ig-tool` commands exclusively.
2. **Do not modify the graph.json directly.** All changes go through `ig-tool node/link/lens` commands.
3. **Do not edit the Lens YAML by hand.** Use `ig-tool lens` commands to adjust focus, detail, and scope.
4. **Do apply lens changes before returning.** Call `ig-tool lens apply` before the agent finishes.

**For all workflows:**

1. **Do not read files outside the step folder** unless they are listed in the `## Agent Instructions`, `## Shared Context`, or `## Reference Documents` sections of the prompt.
2. **Do not modify input files.** They are read-only context.
3. **Do not create files outside the step folder.** All output stays within the step boundary. Exception: the `human_dialogue/` subfolder is created inside the step folder by agents returning `YIELD_FOR_INPUT` — this is the only permitted subdirectory creation.
4. **Do not return full output content in the task result.** Write to disk, return summary only.
5. **Do not bypass the orchestrator's context protection.** If an input file is missing, report it in `gaps` instead of searching the filesystem.

### Reporting gaps
<!-- Lines 950-967 -->

If context is insufficient, include in your task result:

```yaml
output_file: "output_partial.yaml"
summary: "Partial analysis completed. Missing source code for 3 referenced modules."
status: "incomplete"
gaps:
  - type: missing_source
    description: "No source code provided for module X referenced in lens"
  - type: missing_docs
    description: "Lens references PARSER but no parser documentation provided"
```

The orchestrator reads the gaps list and decides whether to re-invoke with more context, enter `*.ESCAPE`, or escalate to the human.

---

## File-Dialogue Specification
<!-- Lines 970-972 -->

When an agent needs human judgment (design decisions, ambiguous intent, scope questions), it creates structured dialogue files instead of returning an inline escalation payload. The orchestrator relays the folder path to the human without reading the files. The human edits in-place. The agent reads responses on resumption.

### Folder layout
<!-- Lines 975-983 -->

```text
{step_folder}/human_dialogue/
  round_summary.md     — Cumulative context (what's resolved, what's next)
  question_001.md      — One per decision point (sequential across all rounds)
  question_002.md
  ...
```

### `round_summary.md` — cumulative context
<!-- Lines 986-1003 -->

Written by the agent before each YIELD. Appended (not overwritten) each round.

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

### `question_NNN.md` — decision file
<!-- Lines 1006-1050 -->

Each question file mirrors the Elicitor's **two-section turn format** (see `ig-elicitor-agent.md` §Elicitation Turn Format). The file IS the Elicitor's turn, written to disk instead of presented in conversation.

**Structure:**

```markdown
# Question NNN: {Short title}

## Section 1: Context + Ask

**Minimap:**
```
[ASCII tree from ig-tool tree command, target in brackets]
    ROOT "Sync validator"
       │
 ┌─────┼──────┬──────┬──────┐
DISC  PARSE  [VAL]  RPT   NORM
```

**Critic ({issue_type}, {severity}):** {Issue description}

{The ask with options}

**A** — {First option, 1-2 lines}
**B** — {Second option, 1-2 lines}

{Elicitor's recommendation with reasoning, 1-2 lines}

**Your choice:**

<choice>
<!-- write A, B, or your own option -->
</choice>

---

## Section 2: Deepened Context

{Target node in full — uid, name, intent, epistemic_state, constraints, design_notes, etc.}

{Brim summary — siblings, parent, intentlink neighbors, one line each}
```

**Variants:** For pattern rulings and node bundles, the file follows the corresponding Elicitor turn format (see `ig-elicitor-examples.md`).

### Response extraction protocol
<!-- Lines 1053-1071 -->

**CRITICAL:** The agent uses **Grep tool only** to extract human responses. **NEVER Read the question files** — they contain agent-generated context that wastes tokens.

**Extraction procedure:**

1. **Use Grep tool** with pattern `<choice>(.*?)</choice>` and `multiline: true` to extract responses
2. **NEVER use Read tool** on `question_NNN.md` files
3. Strip HTML comment placeholders (`<!-- ... -->`) before processing
4. If `<choice>` content is empty or only whitespace → treat as unanswered, re-prompt in next round

**Example:**
```bash
# CORRECT: Extract choice via Grep
Grep(pattern="<choice>(.*?)</choice>", path="{dialogue_folder}", glob="question_*.md", multiline=true, output_mode="content")

# WRONG: Never read question files
Read("{dialogue_folder}/question_001.md")  # ❌ Re-ingests agent's own context
```

### Batch semantics
<!-- Lines 1074-1076 -->

The agent creates **all question files for a round at once** before returning `YIELD_FOR_INPUT`. The human answers all of them, then confirms. This minimizes round-trips while still keeping one decision per file for clarity.

### Constraints
<!-- Lines 1079-1086 -->

| Rule | Detail |
| ---- | ------ |
| Max files per round | 5 question files + 1 round_summary |
| Max lines per question (before response) | 50 |
| Human writes only below separator | Everything above `---` / `## YOUR RESPONSE` is read-only |
| Numbering | Sequential across all rounds: round 1 uses 001-003, round 2 uses 004-005, etc. |
| Orchestrator reads dialogue files | **Never.** The orchestrator is a relay — it passes the folder path, nothing more. |
