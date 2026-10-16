# Architecture

How the IntentGraph code parts fit together, organized by roadmap phase.

---

## Current Status
<!-- Lines 9-13 -->

Phases 0–2 are implemented: the formalism, the core library (`src/`), and the agent runtime with the `ig-tool` CLI (`agents_runtime/`). The core library enforces the graph invariants and provides JSON/YAML round-trip, the agent text format, and bidirectional Obsidian sync (export, import, diff, merge, View/Lens canvases with pinned layout). The **Lens** provides full-tree agent I/O with variable LOD shaping and replaced the former display frontier. **CLI-mediated edits** (lens, node, link, batch) make graph changes atomic and validated. The library runs end-to-end on a demonstration example, a SQL Function Sync Validator (21 nodes, 19 intentlinks; see `src/examples/README.md`).

---

## src/
<!-- Lines 16-24 -->

**Phase 1 — Core Library**

Standalone Python library implementing the IntentGraph data model, Lens/View operations, and agent serialization. See [src/README.md](src/README.md).

Includes a demonstration example (an illustrative, invented tool): `src/examples/build_validator_graph.py`.

---

## agents_runtime/
<!-- Lines 27-41 -->

**Phase 2 — Agents as Configuration** (work in progress)

Workflow orchestration and subagent infrastructure live in `agents_runtime/` (`WORKFLOW_*.md`, dispatch tables, orchestrator protocol, context/trace/session utilities).

Agent instructions are modular to reduce prompt/context load:

- Core file: `ig-{role}-agent.md` (always read)
- Mode modules: `ig-{role}-mode-*.md` or `ig-{role}-review-*.md` (read per step/mode)
- Examples: `ig-{role}-examples.md` (read on demand)

The orchestrator specifies mode modules through the prompt preamble (`{mode_module_line}`) documented in `agents_runtime/orchestrator/orchestrator_protocol.md`.

---

## foundation_and_formalism/
<!-- Lines 44-54 -->

**Phase 0 — Foundations & Formalism** (from [ROADMAP.md](ROADMAP.md))

Consolidation of scattered definitions, rules, schemas, and positioning into single-reference documents.

| Document | What it covers | Roadmap WPs |
|----------|---------------|-------------|
| [VOCABULARY_AND_FORMALISM.md](foundation_and_formalism/VOCABULARY_AND_FORMALISM.md) | Vocabulary (7 terms), notation (`IG`, `inode`, `tarc`, `ilink`, `L`), node/link/graph/lens schemas, invariants (T1–T5), operations catalog, ilink lifting & projection, epistemic state, ID/PK scheme, provenance model | WP-0.2 (formal model & notation) |
| [SERIALIZATION_FORMAT.md](foundation_and_formalism/SERIALIZATION_FORMAT.md) | Wire format spec: persistence (JSON/YAML full graph), agent text (view/lens I/O), graph overview (navigation). Omission rules, YAML style, ID conventions. | WP-1.3 (agent serialization) |
| [POSITIONING_SUMMARY.md](foundation_and_formalism/POSITIONING_SUMMARY.md) | How IntentGraph differs from spec-driven dev, formal methods, projectional editing, and intent-native runtimes. Comparison table, strategic position. | WP-0.1 (state of the art & positioning) |

### Sources consolidated
<!-- Lines 57-63 -->

These documents pull from and supersede the scattered definitions in:

- `intentlink_spec.md` — link payload, refinement, projection
- `project_definition.md` — goal and vocabulary
- `schema/*.v0.yaml` — node, link, graph field schemas
- `STATE_OF_THE_ART__INTENT_FIRST_AND_SPEC_DRIVEN.md` — competitive landscape
