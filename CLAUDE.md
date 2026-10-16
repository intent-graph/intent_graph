# Agent contract (CLAUDE.md)

You are operating in a repository where **Intent is the source of truth** and code is downstream.
For the full project overview: [README.md](README.md).

## Core concepts (do not rename)

- IntentGraph, intentnode, intentlink, treearc, lens

## Mandatory primer reading

Whenever "IG" or "IntentGraph" is mentioned, or work touches this directory, read the primers before acting:

- **Start with** `agents/README.md`.
- **Minimal set (default for any IG task):** the compressed primers —
  `agents/compressed/PRIMER_00_PHILOSOPHY.md`, `agents/compressed/PRIMER_01_SEMANTICS.md`,
  `agents/compressed/PRIMER_02_NAVIGATION.md`, `agents/compressed/PRIMER_03A_EDITING.md`,
  `agents/compressed/PRIMER_TOOLS.md`.
- **Advanced work** (new feature, in-depth design/thinking): read the full, non-compressed primers
  in `agents/` instead of the compressed set.

## Epistemic discipline

- Never invent missing intent.
- If information is missing, record it explicitly as an unknown.
- Prefer marking uncertainty over guessing.

## Editing discipline

- Prefer **small diffs** and **local edits**.
- Keep changes reviewable: update intentnodes/intentlinks/treearcs explicitly.
- Avoid sweeping renames unless required by the user.
- Maintain UID stability unless specifically instructed to renumber.
- **`README.md` has no table of contents, on purpose**: it is the GitHub landing page and GitHub shows its own outline. Do not add one; other docs keep their line-number TOC.
- **Links to the sibling `ai_tooling` repo** are relative (`../ai_tooling/...`): they work on a side-by-side checkout, not on GitHub. Only a few chosen high-level links (an entry README pointing at the other repo's entry doc) also carry the GitHub URL after the local link: `[X](../ai_tooling/X.md) ([GitHub](https://github.com/intent-graph/ai_tooling/blob/main/X.md))`. Deep documents keep the local link only.
- **Provenance is automatic**: every save stamps changed nodes (write-boundary). Pass `--role <role>` and `-m "<one-liner why>"` on mutating commands; never hand-edit `history`.

## Agent I/O: Lens

Agents use the **Lens** for agent I/O: a full-tree view with variable LOD per node (`skeleton < lean < full`). Target area full, ancestors lean, distant branches skeleton. Preserves hierarchy for orientation.

The former **display frontier** concept is removed — a frontier was just a lens with binary LOD. The §2 agent text format ("view") remains for uniform full-detail working views (`view:` header; legacy `frontier:` accepted on read).

See [foundation_and_formalism/LENS_REDESIGN_SPEC.md](foundation_and_formalism/LENS_REDESIGN_SPEC.md) for design and implementation details.

## Serialization

All agents reading or writing IntentGraph data must conform to [SERIALIZATION_FORMAT.md](foundation_and_formalism/SERIALIZATION_FORMAT.md). Full-graph and lens files can be stored as `.json` or `.yaml`/`.yml`; tools accept both (format inferred from extension). Full-graph persistence stores **nodes** and **treearcs** in **breadth-first** order: root(s) first, then each level; stable and deterministic.

For Lens-based workflows: Lens extends agent text format with `lod` field on nodes and intentlink visibility rules (present if both endpoints ≥ lean; description if ≥1 endpoint is full).

## ProjectionIG

Dual-graph architecture: product IG (what to build) + ProjectionIG (how to render). Reference artifacts in `projection/`. See [README.md](README.md) for details.

## Workflows

Three workflows with codified step UIDs:

- **Declare** — Build intent from scratch. See `agents_runtime/WORKFLOW_DECLARE.md`
- **Distill** — Extract intent from existing code/docs. See `agents_runtime/WORKFLOW_DISTILL.md`
- **Project** — Generate code from intent. See `agents_runtime/WORKFLOW_PROJECT.md`

Design guidelines: `agents_runtime/workflow_design_guidelines.md`

## Key references

- Tool guide (WHY/when): `agents/PRIMER_TOOLS.md`; exact syntax: `.claude/skills/ig-tool-*/SKILL.md`
- Agent primer: `agents_runtime/AGENT_PRIMER.md`
- Agent instructions: `.claude/agents/ig-*-agent.md` (catalog: `.claude/agents/README.md`)
- Orchestrator protocol: `agents_runtime/orchestrator/orchestrator_protocol.md`
- IntentLink spec: `docs/intentlink_spec.md`
- Project definition & vocabulary: `docs/project_definition.md`
