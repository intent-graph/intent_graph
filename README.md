# IntentGraph

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="logo/wordmark-white.svg"/>
    <img src="logo/wordmark.svg" alt="IntentGraph" width="420"/>
  </picture>
</p>

**Code, docs and specs are projections of one intent graph.**

IntentGraph is a model and a toolchain for describing software as a single graph of *intent*: what each part is for, what constrains it, and what is still unknown, written at mixed levels of detail. You refine one corner of the graph without rewriting the rest, and derive code, documentation and specs from it instead of maintaining them as parallel artifacts that drift apart.

It exists so that humans and AI agents can work on a small part of a system without holding the whole system in memory, and without the graph pretending to be complete: unknowns are recorded as unknowns.

> **Status: research prototype (v0.1), source-available under PolyForm Shield 1.0.0.** Working today: the formal model and its invariants, the core Python library (JSON/YAML, lenses), the `ig-tool` command line, Obsidian and VS Code viewers, and one worked example graph; 1134 automated tests pass. In progress: the LLM agent roles (prompt configurations, not trained models) that extract a graph from code, elicit intent and generate code from it. Planned, see [ROADMAP.md](ROADMAP.md): an end-to-end validation (rebuild a real library from its graph alone) and a richer GUI. Expect breaking changes.

## Table of Contents

1. [Quick Start](#quick-start) _(Lines 40-100)_
1. [The Idea](#the-idea) _(Lines 103-107)_
1. [Agent Primers — Start Here](#agent-primers--start-here) _(Lines 110-126)_
1. [Core Concepts](#core-concepts) _(Lines 129-140)_
1. [Project Structure](#project-structure) _(Lines 143-166)_
1. [Intended Workflow](#intended-workflow) _(Lines 169-177)_
1. [Lens Implementation](#lens-implementation) _(Lines 180-204)_
1. [ig-tool CLI](#ig-tool-cli) _(Lines 207-233)_
1. [Documentation](#documentation) _(Lines 236-253)_
1. [Companion Repository](#companion-repository) _(Lines 256-264)_
1. [Contributing](#contributing) _(Lines 267-269)_
1. [License](#license) _(Lines 272-276)_




---

## Quick Start
<!-- Lines 40-100 -->

You need [git](https://git-scm.com) and [uv](https://docs.astral.sh/uv/) (uv fetches Python 3.11+ and the dependencies into a `.venv/` in the clone; no system-wide install).

```bash
git clone https://github.com/intent-graph/intent_graph.git
cd intent_graph

# 1. Check a graph that ships in the repo (an invented 21-node example: a SQL function sync validator)
uv run ig-tool validate -g src/examples/validator_graph.json

# 2. See its structure
uv run ig-tool tree -g src/examples/validator_graph.json

# 3. Read one node: its intent, constraints, and epistemic state (what is still unknown)
uv run ig-tool query -g src/examples/validator_graph.json --node VALIDATE

# 4. Build a lens: one target at full detail, its ancestors lean, everything else skeleton
uv run ig-tool lens build -g src/examples/validator_graph.json -t VALIDATE.3 -o lens.yaml

# 5. Look at the lens as a tree: [FULL] / [lean] / [skel] mark the level of detail of each node
uv run ig-tool lens tree -l lens.yaml
```

The first `uv run` creates a `.venv/` in the clone (a few seconds); `lens.yaml` is a scratch file you can delete. Abridged output:

```text
$ uv run ig-tool validate -g src/examples/validator_graph.json
graph: src/examples/validator_graph.json
nodes: 21
links: 19
inter_links: 0
issues: 0
errors: 0
warnings: 0

status: ok
...

$ uv run ig-tool tree -g src/examples/validator_graph.json
└── ROOT: SQL Function Sync Validator
    ├── DISCOVER: Discovery
    │   ├── DISCOVER.1: Generated Cache Scanning
    ...
    └── ORCHESTRATE: Orchestration
        ...

$ uv run ig-tool lens tree -l lens.yaml
└─ [lean] ROOT: SQL Function Sync Validator
   ├─ [lean] DISCOVER: Discovery
   │  ├─ [skel] DISCOVER.1: Generated Cache Scanning
   ...
   ├─ [FULL] VALIDATE: Validation
   │  ├─ [skel] VALIDATE.1: Existence Checking
   │  ├─ [skel] VALIDATE.2: Signature Comparison
   │  ├─ [FULL] VALIDATE.3: Body Comparison
   │  └─ [FULL] VALIDATE.4: Severity Classification
   ...
```

**Next:** edit a graph through the CLI instead of by hand (`ig-tool node create`, `link create`, `apply --batch`; each edit is validated and stamped with provenance, see [agents/PRIMER_TOOLS.md](agents/PRIMER_TOOLS.md)); browse the example as an Obsidian vault in [`src/examples/validator_vault/`](src/examples/validator_vault/); or open any `*.ig.yaml` / `*.ig.json` in the [VS Code extension](vscode_extension/intentgraph-vscode/README.md). To put `ig-tool` on your `PATH`, see [ig-tool CLI](#ig-tool-cli). `ig-tool` writes a local usage log to `~/.cache/ig-tool/usage.jsonl` (never sent anywhere); pass `--no-telemetry` before the subcommand to disable it (`ig-tool --no-telemetry validate ...`).

## The Idea
<!-- Lines 103-107 -->

Center software development on a single Intent Graph that remains coherent under mixed levels of detail, so intent, constraints, and unknowns can be refined locally without rewriting the whole system. **The intent graph is the canonical model; everything else — code, documentation, specs, visual views — is a projection.** Different audiences get different projections of the same truth, all generated from and linked back to the same graph. This repository serves as the source of truth for the IntentGraph specification and tooling.

---

## Agent Primers — Start Here
<!-- Lines 110-126 -->

> **If you are an agent or human working with IntentGraph, read this first.**

The **[agents/README.md](agents/README.md)** is the primary entry point for understanding how to operate within IntentGraph. It contains a structured set of implementation-agnostic primers covering philosophy, semantics, navigation, editing, tools, dialogue, and workflows — applicable to all agent roles.

**Recommended reading order:**
1. [PRIMER_00_PHILOSOPHY.md](agents/PRIMER_00_PHILOSOPHY.md) — Core axioms, invariants, vocabulary
2. [PRIMER_01_SEMANTICS.md](agents/PRIMER_01_SEMANTICS.md) — How to read nodes, fields, tree structure
3. [PRIMER_02_NAVIGATION.md](agents/PRIMER_02_NAVIGATION.md) — Lens navigation, LOD, viewport operations
4. [PRIMER_03A_EDITING.md](agents/PRIMER_03A_EDITING.md) — Graph mutation, decomposition, propagation
5. [PRIMER_TOOLS.md](agents/PRIMER_TOOLS.md) — ig-tool command reference
6. [PRIMER_04_WORKFLOWS.md](agents/PRIMER_04_WORKFLOWS.md) — Operation classes, role guidance

Runtime subagent instructions live in `.claude/agents/` (core `ig-{role}-agent.md` + mode modules).

---

## Core Concepts
<!-- Lines 129-140 -->

The IntentGraph is the canonical model — the source of truth for describing a system at mixed levels of detail. All downstream artifacts are **projections** of the graph.

- **IntentGraph**: The complete multi-level Intent artifact: a graph whose nodes represent units of intent and whose edges capture both refinement structure and cross-node intent relations.
- **intentnode**: A node in the IntentGraph representing a unit of intent at some level of detail.
- **treearc**: A directed edge type forming the refinement tree of the IntentGraph.
- **intentlink**: A directed edge between two intentnodes carrying an explicit, valued relationship (e.g., data exchange, dependency, coordination). **Inter intentlinks** connect nodes across graphs (product ↔ projection) and are stored in-graph with qualified UIDs (`graph_id:node_uid`); see [intentlink_spec.md §3.4](intentlink_spec.md).
- **lens**: A shaped view of the IntentGraph — an ancestor-closed set of intentnodes each at a chosen level of detail (`skeleton < lean < full`). The unit of visualization and agent I/O. (Supersedes the former _display frontier_, which was a lens with binary LOD.)
- **projection**: Any derived artifact generated from the graph through a lens — code (in a chosen language and design flavor), documentation (spec, README, executive summary, Gherkin scenarios), or a visual rendering (GUI). Each projection instance may be backed by a **ProjectionIG** — a full IntentGraph capturing the rendering-specific intent behind it (paradigm choice, naming conventions, audience, tone, etc.). Projections are bidirectional: edits to a projection flow back into the graph.

See [Project Definition](project_definition.md) for full definitions.

## Project Structure
<!-- Lines 143-166 -->

```
/
├── pyproject.toml           # Root package (intentgraph-tools) — install: uv tool install -e .
├── project_definition.md    # Core definitions and goals
├── intentlink_spec.md       # Specification for intent links
├── ROADMAP.md    # Project roadmap (phases 0–5, validation, training)
├── projection/              # ProjectionIG reference artifacts
│   └── projection_dimensions.ig.yaml  # Dimension ontology (PIG-DIM.*)
├── ARCHITECTURE.md          # How the code parts fit together
├── src/                     # Core library `intentgraph`: data model, lens ops, serialization, Obsidian sync
├── agents_runtime/          # Agent infrastructure `ig_agents`: context, sessions, ig-tool CLI
├── foundation_and_formalism/  # Phase 0: vocabulary, formalism, positioning
├── vscode_extension/        # VS Code viewer/editor (intentgraph-vscode/, install: bootstrap.sh)
├── agents/                  # Agent catalog and design
│   └── README.md
├── docs/                    # Detailed documentation and rules
├── src/examples/            # End-to-end example (SQL function validator)
├── schema/                  # Graph schemas and data structures
└── README.md                # This file
```

Python KB intent graphs (philosophy + guidelines/style) live in the sibling [`ai_tooling`](https://github.com/intent-graph/ai_tooling) repo, at **dev_guidelines/python_guidelines/intent_graphs/**.

## Intended Workflow
<!-- Lines 169-177 -->

1. Define or update the IntentGraph through a chosen **lens** (mixed detail allowed) — via the Elicitor, manually, or by extracting from existing code.
2. Validate invariants and produce/refresh lifted intentlinks at the lens. The Critic challenges the graph continuously.
3. Bundle the local lens neighborhood for focused work.
4. **Project** the lens into downstream artifacts: generate code (Generator), materialize documentation (Doc agents), design verification tests (Verifier).
5. When a projection is edited (code modified, doc rewritten), reconcile the change back into the graph; track drift in CI.

This keeps the repo centered on a single idea: **the intent graph is the canonical model; code, docs, and specs are projections that stay in sync. Software evolves by refining intent, not by accumulating untracked meaning in code.**

## Lens Implementation
<!-- Lines 180-204 -->

The **Lens** is the full-tree agent I/O view using Level of Detail (LOD) shaping. It solves two critical agent workflow problems: loss of orientation (the former flat-antichain frontier lost hierarchy) and invalid edit generation (agents mangle raw YAML). The display-frontier concept is removed — a frontier was a lens with binary LOD.

**Core Concept:**
- **Full tree structure preserved** — agents always see hierarchy for orientation and structural reasoning
- **Variable LOD** (skeleton < lean < full) — budget-friendly detail control via IV_ pattern (target=full, ancestors=lean, context=skeleton)
- **CLI-mediated edits** — 25 new atomic validated commands replace raw YAML editing

**Key Features:**
- Nodes carry explicit `lod` field determining serialized content
- Intentlinks appear only if both endpoints are ≥ lean LOD; description shown only if ≥1 endpoint is full
- Pruning removes most-distant branches first to fit budget while preserving tree validity
- The `view:` agent-text format remains for uniform full-detail working views (legacy `frontier:` header still accepted on read)

**ig-tool Commands (25 total):**
- **lens** (15 subcommands): `build`, `show`, `tree`, `info`, `focus`, `promote`, `demote`, `set-lod`, `prune`, `expand`, `set-budget`, `list-pruned`, `diff`, `apply`, `discard`
- **node** (6 subcommands): `create`, `set`, `reparent`, `reorder`, `remove`, `show`
- **link** (3 subcommands): `create`, `set`, `remove`
- **apply --batch**: Atomic multi-operation changes from a YAML file

**Design & Implementation:**
- [Lens Redesign Specification](foundation_and_formalism/LENS_REDESIGN_SPEC.md) — full concept, LOD system, closure invariants, CLI surface

**Status:** Core implementation complete, production-ready. Files: `models/lens.py`, `ops/lens_ops.py`, `serial/lens_file.py`, CLI commands registered in `agents_runtime/src/ig_agents/cli/`.

## ig-tool CLI
<!-- Lines 207-233 -->

System-wide command-line interface for graph queries, lens operations, edit pipeline, context assembly, and workflow trace. Used by agents, orchestrator, and humans.

**Install (once):**

```bash
uv tool install -e . --reinstall  # from the repo root
```

The install is **editable**: `ig-tool` runs straight from `src/` and `agents_runtime/`, so
code changes apply without reinstalling. The price is an absolute path baked into the
tool environment. **After moving or renaming the repo, re-run the command above**, or else
`ig-tool` fails with `ModuleNotFoundError: No module named 'ig_agents'`. The VS Code
extension's `bootstrap.sh` does this for you, and relinks the editor too.

**Usage (from any directory):**

```bash
ig-tool validate -g graph.json -o report.yaml
ig-tool query -g graph.json --node DISCOVER -o node.yaml
ig-tool tree -g graph.json --show-intent            # ASCII tree visualization
ig-tool apply -g graph.json -i edits.yaml -o updated.json --role extractor
ig-tool lens build -g graph.json -t DISCOVER -b 30 -o lens.yaml
```

Command guide (WHY/when): [agents/PRIMER_TOOLS.md](agents/PRIMER_TOOLS.md). Exact syntax: `.claude/skills/ig-tool-*/SKILL.md`.

## Documentation
<!-- Lines 236-253 -->

**Documentation Manifests** (CLIs from the companion [`ai_tooling`](https://github.com/intent-graph/ai_tooling) repo): generated on demand, not committed (gitignored):

```bash
md-doc-tree-rich . > DOC_MANIFEST_RICH.txt   # compact tree view with stats
md-doc-tree-full . -o DOC_MANIFEST           # full sections + cross-refs YAML
```

**Key Documents:**

- **[Project Definition](project_definition.md)**: Goals, philosophy, and vocabulary.
- **[Roadmap](ROADMAP.md)**: Project phases (0–5), validation criterion, agent implementation, training.
- **[Architecture](ARCHITECTURE.md)**: How the code parts fit together — Phase 0 (formalism) and Phase 1 (core library + Obsidian GUI) both complete.
- **[Agents](agents/README.md)**: See [Agent Primers — Start Here](#agent-primers--start-here) above.
- **[Projection](projection/README.md)**: ProjectionIG dimension ontology and language-specific defaults (valid IntentGraphs).
- **[Serialization Format](foundation_and_formalism/SERIALIZATION_FORMAT.md)**: Wire format spec for persistence, agent I/O, and graph overview. Graph files store nodes and treearcs in **breadth-first** order (root, then by level).
- **[Examples](src/examples/README.md)**: Practical examples of Intent Graphs.

## Companion Repository
<!-- Lines 256-264 -->

[`ai_tooling`](https://github.com/intent-graph/ai_tooling) holds the generic tools and knowledge bases this project builds on: `codemap` (structural code graph for Python), `md-structure-sync` and `md-doc-tree-*` (documentation tooling), the level-of-detail practice, and guideline knowledge bases held as IntentGraphs. It is not needed for the Quick Start above. Some documents here link to it with relative paths such as `../ai_tooling/...`; those links resolve when the two repositories are cloned side by side:

```text
some_folder/
├── intent_graph/
└── ai_tooling/
```

## Contributing
<!-- Lines 267-269 -->

Issues are welcome. A pull request gives its content entirely to the owner: read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## License
<!-- Lines 272-276 -->

Source-available under the [PolyForm Shield License 1.0.0](LICENSE.md): free to use, modify and
distribute for any purpose, including at work, except to provide a product that competes with
IntentGraph. This is not an OSI-approved license. Copyright 2026 Rémi Cura. For other terms,
contact the author.
