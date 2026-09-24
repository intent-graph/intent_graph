# IntentGraph Agent Primer

Shared context for all IntentGraph agents. Read this before starting any task. The authoritative formalism lives in `foundation_and_formalism/VOCABULARY_AND_FORMALISM.md` — this primer gives you the working subset you need.

---

## What the IntentGraph Is
<!-- Lines 9-20 -->

An IntentGraph captures **what a system does and why** as a refinable graph of intent. Code, documentation, tests, and specs are *projections* — derived artifacts generated from the graph. The graph is the source of truth; implementations are consequences.

Four axioms:

- **P1 — Intent is the source of truth.** Different audiences get different projections of the same truth.
- **P2 — Zooming adds information, never changes meaning.** Refining a node into children increases precision but preserves the intended role. A parent and its children describe the same intent surface at different resolution.
- **P3 — Incompleteness is first-class.** The graph tolerates uncertainty. Unknown is modeled, not hidden.
- **P4 — Projection is orthogonal.** What a system does (product intent) and how that intent is materialized into artifacts (projection intent) are independent concerns. Each gets its own IntentGraph.

---

## Core Vocabulary
<!-- Lines 23-23 -->

### intentnode
<!-- Lines 26-35 -->

A unit of intent at some level of detail. Describes *what* a part of the system is meant to do and *why*, not *how* it is implemented.

Fields: `uid`, `name`, `intent`, `epistemic_state`, `constraints`, `examples`, `design_notes`, `effort`, `impl_pointers`, `history`.

- `intent` — WHAT: the intended behavior/role.
- `design_notes` — WHY: reasoning behind choices, rejected alternatives, accepted tradeoffs.
- `history` — WHO: provenance log (auto-stamped at write boundary with `--role` and `-m` flags on mutating commands). Convention: `agent:extractor`, `agent:critic`, etc. for agents; plain names for humans.
- `impl_pointers` — list of pointer strings (grammar: `path[::Symbol[.member]][ (lines X-Y)]`, e.g., `src/auth.py::AuthParser.parse (lines 40-80)`) recording where in the codebase this intent is realized.

### treearc
<!-- Lines 38-40 -->

A directed `parent → child` refinement edge. All treearcs form a directed rooted tree. Each node has at most one parent; the root has none. Treearcs carry no payload — pure refinement.

### intentlink
<!-- Lines 43-45 -->

A directed, valued relation between two intentnodes. Carries an `intent` sentence describing what must be true *between* nodes (data exchange, dependency, coordination, etc.). Orthogonal to the tree — can connect any two nodes at any depth.

### lens
<!-- Lines 48-50 -->

A shaped view of the full graph tree at variable level of detail (LOD). Ancestor-closed node set with each node at skeleton (uid+name), lean (uid+name+intent+epistemic_state), or full LOD. The lens is your working context: you reason about a local neighborhood with target area in full detail, ancestors visible for orientation, distant nodes minimized.

### IV-shaped context
<!-- Lines 53-64 -->

The canonical LOD-shaping rule for a lens.

- **Node set:** ancestor-closed; includes target and all ancestors up to root, direct neighbors (treearc parent/children and intentlink endpoints), and their subtrees.
- **LOD profile:** selected by the pattern:
  - **`_` (ground bar):** target + direct neighbors → **full LOD**
  - **`I` (vertical stroke):** all ancestors from target to root → **lean LOD**
  - **`V` (brim):** all L1 children of root (top-level modules) → **lean LOD**
  - **Everything else:** **skeleton LOD**

---

## Invariants
<!-- Lines 67-77 -->

You must respect these. Violations are rejected by the core library.

- **T1 — Tree well-formedness.** Treearcs form a directed rooted tree. One parent per node, no cycles.
- **T2 — Lens validity.** A lens is ancestor-closed with valid LOD (target full, ancestors lean, distant nodes skeleton).
- **T3 — Intentlink endpoints exist.** Both `src` and `dst` of every intentlink must exist in the graph.
- **T4 — Refinement coherence.** Expanding a node into children preserves the parent's meaning. Children cover the parent's intent; no child contradicts or extends beyond the parent's scope.
- **T5 — Lens continuity.** Lens viewport operations (focus, promote, demote, prune, expand) preserve lens validity and all pending edits.

---

## Epistemic State
<!-- Lines 80-96 -->

Free-text field on every node — not an enum. Write what is true, don't squeeze reality into a label.

Recommended vocabulary (building blocks, not a closed set):

| Term | Meaning |
|------|---------|
| known | Well-understood and stable |
| constrained | Some boundaries set, full picture not resolved |
| undecided | Multiple viable options, no decision yet |
| risky | Decision made but carries identified risks |
| deferred | Deliberately postponed |
| speculative | Best guess, low confidence |
| inherited | Assumed from parent/context, not independently validated |

If omitted, the state is *unassessed* — not "known."

### Multi-Issue Convention
<!-- Lines 99-119 -->

When discovering problems during workflows, append issue annotations using pipe (`|`) separation:

```
epistemic_state: "<base_state>: <description> | <issue_type>: <issue> | <issue_type>: <issue> ..."
```

**Issue types:** `gap:`, `conflict:`, `missing:`, `unclear:`, `unvalidated:`

**Examples:**
- `"observed: extracted from auth.py | gap: performance requirements not specified"`
- `"known | missing: no intentlink to ROOT.5 concurrency constraint"`
- `"undecided: three strategies proposed | unvalidated: no test coverage data"`

**Workflow integration:**
- Issues accumulate during Distill/Refine steps as agents discover problems
- Steward and Elicitor prioritize nodes with `|` in epistemic_state
- Resolve by updating the base state and removing the issue annotation

---

## The Dual-Graph Model
<!-- Lines 122-136 -->

P4 establishes that product intent and projection intent are independent concerns. This section describes the two-graph architecture that implements that separation.

Choosing to render code in Python with a functional style, or documentation as an executive summary, or tests as property-based specs — these are intentional decisions with their own WHAT, WHY, constraints, and uncertainty. Therefore the system uses two full IntentGraphs:

**Product IntentGraph** — captures *what the system does and why*. Projection-agnostic. A constraint like "output is a keyed mapping of function records" belongs here. Language-specific typing (`Dict[str, FunctionRecord]`) does not.

**ProjectionIG (PIG)** — a full IntentGraph (same formalism, same invariants, same lens mechanics) that captures the **intent behind a specific projection**: *how* the rendering should be produced and *why* those choices were made. It is not a config file or a style guide — it is a proper graph of intent about rendering, with its own refinement hierarchy, intentlinks, epistemic states, and review cycles. Nodes use the `PIG-<TAG>.` UID prefix (e.g., `PIG-PY.1.3`) to avoid collision with product nodes.

A code PIG encodes paradigm, naming, error handling, performance tradeoffs. A doc PIG encodes audience, tone, emphasis. A test PIG encodes coverage strategy and assertion style. The same product intent can yield different projections by swapping the PIG — OOP vs. functional, executive summary vs. technical spec, property-based vs. example-based tests.

The **language-swap test** is the litmus: if a constraint or intent sentence would break under a different projection (e.g., C++ instead of Python), it's projection-specific and belongs in the PIG, not the product graph.

---

## Context Delivery Formats
<!-- Lines 139-139 -->

### Context Format (Current — Lens-Based)
<!-- Lines 142-221 -->

You receive a **Lens** — a structured view of the full graph tree with variable detail levels.

A Lens contains:
- **All nodes in scope** (not a flat antichain) organized as a valid tree
- **LOD (Level of Detail)** per node: `skeleton` (uid+name) < `lean` (uid+name+intent+epistemic_state) < `full` (all fields)
- **Complete treearc structure** — hierarchy is always visible for orientation
- **Intentlinks** — present only if both endpoints are at lean LOD or above
- **Budget constraints** — token estimate for all full/lean nodes; skeleton is free
- **Pruned node tracking** — which branches were removed to fit budget

**Example Lens YAML structure:**

```yaml
lens:
  name: "Target-focused view"
  target: D.1
  budget: 30000
  pruned_uids: []

nodes:
  - uid: ROOT
    name: "Root"
    lod: lean
    intent: "System root"
    epistemic_state: "known"

  - uid: D
    name: "Module D"
    lod: lean
    intent: "..."
    epistemic_state: "..."

  - uid: D.1
    name: "Component D.1"
    lod: full
    intent: "..."
    epistemic_state: "..."
    constraints: [...]
    design_notes: "..."
    impl_pointers:
      - "src/module.py::ComponentD1"
      - "docs/design.md (lines 15-30)"
    history: [...]

  - uid: D.2
    name: "Component D.2"
    lod: lean
    intent: "..."
    epistemic_state: "..."

  - uid: E
    name: "Module E"
    lod: skeleton

treearcs:
  - parent: ROOT
    child: D
  - parent: D
    child: D.1
  - parent: D
    child: D.2

intentlinks:
  - uid: D.1_E
    src: D.1
    dst: E
    intent: "D.1 passes data to E"
    lod_descriptor: "full-lean"    # endpoints visible to at least full/lean
```

**LOD Assignment (IV_ pattern):**

- **`_` (ground bar):** target + direct neighbors (treearc parent/children + intentlink endpoints) → **full LOD**
- **`I` (vertical stroke):** all ancestors from target to root → **lean LOD**
- **`V` (brim):** all L1 children of root (top-level modules) → **lean LOD**
- **Everything else:** **skeleton LOD**

This ensures: target is fully detailed, "where am I" path is visible, project structure is visible, distant irrelevant nodes are minimized.

### Legacy Context Format (Frontier-Based)
<!-- Lines 224-251 -->

Previously, agents received a **DisplayFrontier** — a flat antichain with full or lean IV-context. This format is deprecated. Lens is the current agent context mechanism.

```yaml
# LEGACY — for reference only
frontier:
  name: "..."
nodes:
  - uid: E.1
    name: "..."
    intent: "..."
    epistemic_state: "..."
    constraints: [...]
    design_notes: "..."
    impl_pointers:
      - "src/module.py::E1_function"
    history:
      - {who: "agent:extractor", date: "2026-02-15", note: "..."}
    collapsed_children: [...]
intentlinks:
  - uid: E.1_T.1
    src: E.1
    dst: T.1
    intent: "..."
```

**Status:** Deprecated format (frontier concept removed; Lens replaces it). Agents now receive full-tree Lens views. Legacy `frontier:` header still accepted on input for backwards compatibility; new outputs use `view:` for uniform full-detail working views.

## Edit Protocol
<!-- Lines 254-254 -->

### Current Workflow (Lens-Based CLI Editing)
<!-- Lines 257-344 -->

**Status:** Recommended for all new workflows.

When you need to modify the graph, **use `ig-tool` commands, not YAML editing.**

**Workflow:**

1. **Receive a Lens** (lens.yaml) showing the full tree with variable LOD
2. **Use tree structure for orientation** — understand where nodes belong in the hierarchy
3. **Invoke ig-tool commands** to make changes (all operations are atomic and validated):
   - **Node operations:** `ig-tool node create`, `ig-tool node set`, `ig-tool node reparent`, `ig-tool node remove`
   - **Link operations:** `ig-tool link create`, `ig-tool link set`, `ig-tool link remove`
   - **Batch operations:** `ig-tool apply --batch` (combine multiple edits in one YAML file)
4. **Viewport adjustments** (if needed to reorient the Lens):
   - `ig-tool lens focus` — shift target to a different node
   - `ig-tool lens promote` / `ig-tool lens demote` — increase/decrease LOD of a node
   - `ig-tool lens prune` — hide a subtree to fit budget
   - `ig-tool lens expand` — show children of a collapsed node
5. **Orchestrator applies changes** via `ig-tool lens diff` → `ig-tool lens apply`

**Example: Create a new child node under ROOT.1**

```bash
# 1. You see ROOT.1 in the Lens, understand it's a child of ROOT
# 2. You invoke the node creation command:
ig-tool node create -g graph.json \
  --uid ROOT.1.5 \
  --name "New capability" \
  --intent "Does X and Y" \
  --parent ROOT.1 \
  -o graph.json
```

**Example: Update a node's intent and epistemic state**

```bash
ig-tool node set -g graph.json \
  --uid D.1 \
  --intent "Updated intent description" \
  --epistemic-state risky \
  -o graph.json
```

**Example: Create an intentlink**

```bash
ig-tool link create -g graph.json \
  --src D.1 \
  --dst E \
  --intent "D.1 feeds data to E via a queue" \
  -o graph.json
```

**Example: Batch multiple changes**

Create `edits.yaml`:
```yaml
operations:
  - op: node.create
    uid: ROOT.5
    name: "New Node"
    intent: "Intent description"
    parent: ROOT

  - op: node.set
    uid: ROOT.1
    intent: "Updated intent"
    epistemic_state: known

  - op: link.create
    src: ROOT.5
    dst: ROOT.1
    intent: "ROOT.5 calls ROOT.1"
```

Then invoke:
```bash
ig-tool apply -g graph.json --batch edits.yaml -o updated_graph.json
```

**Why this workflow:**
- Problem (old): agents mangle YAML (typos in UIDs, broken indentation, lost fields)
- Solution: atomic validated CLI commands — no YAML mangling possible
- Problem (old): agents lose tree orientation working with flat antichain frontiers
- Solution: Lens shows full tree structure at variable LOD — agents can reason about WHERE things belong

---

### Legacy Workflow (Frontier-Based YAML Editing)
<!-- Lines 347-382 -->

**Status:** Deprecated. Do not use in new workflows. Use `ig-tool` commands instead.

Previously, two YAML-based output formats were accepted (system auto-detected which was used).

**Option A: Full frontier YAML** (deprecated)

- Return complete frontier with modifications; system diffs against current graph
- Caveat: prone to YAML mangling (broken indentation, lost fields, UID typos)

**Option B: Diff format** (deprecated)

```yaml
diff_meta:
  base: "graph.json"
  author: "agent:extractor"

nodes:
  - uid: D.1
    intent: "Updated intent"
    _prev: {intent: "Old intent"}
  - uid: D.3
    name: "New Node"
    intent: "Brand new intent"
    parent: D
    _new: true
  - uid: D.2
    _delete: true
```

**Why deprecated:** Agents routinely produce YAML errors (typos, lost fields, malformed indentation). Modern workflow uses `ig-tool` CLI commands instead (atomic, validated, no YAML mangle risk).

Full format spec: `foundation_and_formalism/SERIALIZATION_FORMAT.md` §2 (Agent Text) and §5 (Diff Format).

---

## Hard Tools (ig-tool)
<!-- Lines 385-442 -->

You have access to programmatic tools via the `ig-tool` CLI. Use them instead of writing ad-hoc scripts. Reference: `agents/PRIMER_TOOLS.md` (WHY/when) + `.claude/skills/ig-tool-*/SKILL.md` (exact flags).

**Invocation** (from Shell — works from any directory):

```bash
ig-tool <command> -g graph.json [args] -o result.yaml
```

Installed system-wide via `uv tool install -e .` from the repo root. No PYTHONPATH, no venv activation.

**Output contract:** Full results go to the `-o` file. Stdout shows only a compact summary (status + metrics + output path). Read the output file only if you need the detail.

**Lens workflow commands (current, recommended):**

| Need | Command |
|------|---------|
| Build a Lens around a target node | `ig-tool lens build -g graph.json -t TARGET_UID -b 30 -o lens.yaml` |
| Render Lens to agent-readable format | `ig-tool lens show -l lens.yaml -o agent_view.yaml` |
| View Lens structure as ASCII tree with LOD | `ig-tool lens tree -l lens.yaml` |
| Shift focus to a different target | `ig-tool lens focus -l lens.yaml -g graph.json --uid NEW_TARGET -o lens.yaml` |
| Increase detail for a skeleton node | `ig-tool lens promote -l lens.yaml --uid UID -o lens.yaml` |
| Decrease detail for a full node | `ig-tool lens demote -l lens.yaml --uid UID -o lens.yaml` |
| Hide a subtree to fit budget | `ig-tool lens prune -l lens.yaml --uid SUBTREE_ROOT -o lens.yaml` |
| Expand children of a collapsed node | `ig-tool lens expand -l lens.yaml -g graph.json --uid UID -o lens.yaml` |
| Check Lens metadata and pending edits | `ig-tool lens info -l lens.yaml` |
| Get diff of Lens changes vs source graph | `ig-tool lens diff -l lens.yaml -g graph.json -o diff.yaml` |
| Commit all pending Lens changes | `ig-tool lens apply -l lens.yaml -g graph.json -o updated_graph.json` |
| Discard pending Lens changes | `ig-tool lens discard -l lens.yaml -o lens.yaml` |

**Node/Link mutation commands (via CLI, not YAML):**

| Need | Command |
|------|---------|
| Create a new node | `ig-tool node create -g G --uid UID --name "Name" --intent "Intent" --parent PARENT_UID -o G` |
| Update node fields | `ig-tool node set -g G --uid UID --intent "New" --epistemic-state risky -o G` |
| Move node to different parent | `ig-tool node reparent -g G --uid CHILD --under NEW_PARENT -o G` |
| Delete a node | `ig-tool node remove -g G --uid UID -o G` |
| Create an intentlink | `ig-tool link create -g G --src SRC --dst DST --intent "Intent" -o G` |
| Update link intent | `ig-tool link set -g G --uid LINK_UID --intent "New intent" -o G` |
| Delete an intentlink | `ig-tool link remove -g G --uid LINK_UID -o G` |
| Apply multiple edits atomically | `ig-tool apply -g G --batch operations.yaml -o updated_graph.json` |

**Query commands (inspection, no mutation):**

| Need | Command |
|------|---------|
| Inspect a single node | `ig-tool query -g G --node UID -o node.yaml` |
| Get a node's ancestors (parents up to root) | `ig-tool query -g G --ancestors UID -o anc.yaml` |
| See all intentlinks touching a node | `ig-tool query -g G --links UID -o links.yaml` |
| Get full graph overview (tree + link counts) | `ig-tool query -g G --overview -o overview.yaml` |
| Get graph skeleton (uid + name + counts) | `ig-tool query -g G --structure -o structure.yaml` |
| Get neighbors in tree and intentlink space | `ig-tool query -g G --neighbors UID -o neighbors.yaml` |

The graph path (`-g`) points to the graph JSON in the step folder or workflow root. The orchestrator provides this path in the prompt's `## Step Context` section.

---

## Practical Guide: Using the Lens for Structural Reasoning
<!-- Lines 445-447 -->

When you receive a Lens, it contains three key pieces of information that guide structural decisions:

### 1. Tree Navigation
<!-- Lines 450-466 -->

The **treearcs** section shows the full hierarchy. Use it to understand WHERE in the tree you are:

```yaml
treearcs:
  - parent: ROOT
    child: D
  - parent: D
    child: D.1
  - parent: D
    child: D.2
```

This tells you: **D is a child of ROOT; D.1 and D.2 are both children of D.**

When proposing a new node, ask: "What is its parent?" The parent must exist in the graph (or be created in the same batch). If you say "create D.5 under D," the graph knows D exists because it's in the Lens.

### 2. Orientation Via LOD
<!-- Lines 469-477 -->

The **lod** field on each node tells you how close it is to the target:

- **full LOD** = target or a direct neighbor (working zone)
- **lean LOD** = ancestor or top-level sibling
- **skeleton LOD** = distant, know only uid + name

**Use this to avoid over-changing things:** If you're working on `D.1` (full) and you're tempted to refactor `E.3` (skeleton), stop. `E.3` is not in your working zone. You don't have the information to refactor it correctly.

### 3. Viewport Operations (Reorientation)
<!-- Lines 480-495 -->

If you realize you need to see more detail:

- **Focus on a different target:** `ig-tool lens focus -l lens.yaml -g graph.json --uid E -o lens.yaml`
  - Recomputes LOD around E instead of D.
  - All pending edits are preserved.
  - Use when you realize your target was the wrong node.

- **Promote a skeleton node:** `ig-tool lens promote -l lens.yaml --uid SKELETON_UID -o lens.yaml`
  - Fills in more detail (intent, constraints, etc.).
  - Use when you need to understand a distant node before making a decision about it.

- **Prune to focus:** `ig-tool lens prune -l lens.yaml --uid SUBTREE -o lens.yaml`
  - Hide a branch entirely.
  - Use when a subtree is irrelevant to your task and you're hitting budget limits.

### Example: Extracting Intent from a Codebase
<!-- Lines 498-530 -->

You're extracting intent from a Python module and find a new capability that needs structure:

```
Current Lens shows:
- D (Module D) — full LOD
- D.1 (Parser) — full LOD
- D.2 (Validator) — lean LOD
- E (Logger) — skeleton

You discover: D.1 needs to be split into D.1.1 (Lexer) and D.1.2 (AST Builder)
```

**Steps:**

1. **Understand the parent:** D.1 is a child of D (visible in treearcs).
2. **Create the children:**
   ```bash
   ig-tool node create -g graph.json --uid D.1.1 --name "Lexer" \
     --intent "Tokenizes input" --parent D.1 -o graph.json
   ig-tool node create -g graph.json --uid D.1.2 --name "AST Builder" \
     --intent "Builds abstract syntax tree from tokens" --parent D.1 -o graph.json
   ```
3. **Create the link:**
   ```bash
   ig-tool link create -g graph.json --src D.1.1 --dst D.1.2 \
     --intent "D.1.1 produces tokens for D.1.2" -o graph.json
   ```

You used the tree structure (treearcs) to reason about parentage, and the LOD (D.1 is full) to know you had enough information to safely refactor it.

---

## Output Protocol: Disk vs. Task Return
<!-- Lines 533-535 -->

Every agent produces two kinds of output. They serve different audiences and have different size constraints.

### Disk output (artifacts)
<!-- Lines 538-540 -->

Write complete work products to the step folder: lens YAML, edit diffs, issue lists, reports, summaries. No size limit. This is the permanent record — the next agent or the human reads these files.

### Task return (to orchestrator)
<!-- Lines 543-568 -->

The Task tool's return value goes into the **orchestrator's context window**. This is expensive real estate shared across an entire multi-step workflow. Bloating it with node content, full YAML, or verbose explanations degrades every subsequent step.

**Hard cap: 80 words maximum.** Use this exact YAML structure:

```yaml
status: "complete"           # complete | partial | yield_for_input | error
output_file: "output_lens.yaml"
summary: "One sentence describing what was done."
metrics:
  nodes_created: 3
  issues_found: 12
  edits_applied: 7
```

Rules:
- `status` + `output_file` + `summary` are required. `metrics` keys are mode-specific.
- `summary` is ONE sentence. Not two. Not a paragraph. One.
- Never include node content, YAML fragments, issue details, or reasoning in the task return. That goes to disk.
- If `status: yield_for_input`, add `dialogue_folder` and `questions_created` keys. Still under 80 words.
- If `status: error`, add `error` key with the failure reason. Still under 80 words.

**Why 80 words?** That's enough for the structured YAML above (typically 30-50 words). It's NOT enough to dump a node's intent, a list of issues, or a reasoning trace — which is exactly the behavior this cap prevents. The orchestrator reads the `output_file` when it needs detail.

---

## Cardinal Rules (All Agents)
<!-- Lines 571-580 -->

1. **Express WHY, not HOW.** If your intent reads like a code summary, rewrite it. The "blind generation test": a developer reading only the intent and constraints should understand the *purpose*, not reproduce the exact code.
2. **Never invent intent.** If you don't know, say so — `epistemic_state: "undecided"`. False certainty is worse than acknowledged uncertainty.
3. **Under-decompose.** Too coarse is correctable; too granular creates noise. Start with fewer, broader nodes.
4. **Respect the lens scope.** Only modify nodes within the lens you were given. Do not forage for additional context.
5. **Never read the full graph.** No agent loads `graph.json` directly — it is too large and defeats the IV-context design. Use the views the orchestrator provides: lens YAML, graph overview (`--overview`), graph skeleton (`--structure`). If you need detail on a specific node outside the lens, query it individually with `ig-tool query --node UID`.
6. **Provenance is automatic.** Pass `--role <role>` and `-m "<one-liner why>"` on mutating commands (`node`, `link`, `apply`); the system auto-stamps history at the write boundary. Never manually edit `history`.
7. **Keep product and projection separate (P4).** Language-specific content belongs in the ProjectionIG, not the product graph.
8. **Use hard tools when they exist.** Check §Hard Tools above before writing scripts. If a tool doesn't exist for what you need, report the gap — do not reinvent.
9. **Task return ≤ 80 words.** All detail goes to disk. The orchestrator's context window is shared across the entire workflow — do not pollute it. See §Output Protocol above.
