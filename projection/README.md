# Projection

ProjectionIG reference artifacts — the canonical dimension ontology and language-specific defaults.

## Files
<!-- Lines 7-13 -->

| File | What it is | UID prefix |
|------|-----------|------------|
| [projection_dimensions.ig.yaml](projection_dimensions.ig.yaml) | The dimension ontology: which rendering concerns a code-projection ProjectionIG must cover | `PIG-DIM.*` |
| [python_defaults.ig.yaml](../vscode_extension/intentgraph-vscode/python_defaults.ig.yaml) | Default rendering decisions for Python, derived from the Python Development Guidelines KB | `PIG-PY.*` |
| [obsidian_defaults.ig.yaml](obsidian_defaults.ig.yaml) | Projection intent for the **Obsidian vault** target (layout, node/edge encoding, navigation, position persistence, format compatibility) — the design-of-record `ig-tool obsidian export` realizes | `PIG-OBS.*` |

## How these are used
<!-- Lines 16-22 -->

**projection_dimensions** is the "questionnaire" — 24 nodes describing the rendering concerns any code projection needs to address. Every node has `epistemic_state: "undecided"`. It defines the *shape* of a ProjectionIG without prescribing answers.

**python_defaults** is one set of answers — opinionated defaults for Python projects, extracted from `../../ai_tooling/dev_guidelines/python_guidelines/`. A project-specific ProjectionIG starts from these defaults and overrides per project needs.

Both files are valid IntentGraphs (same formalism, same serialization format). They can be loaded by the core library, navigated via lenses, and consumed by agents through `view_to_text()`.

## Workflow integration
<!-- Lines 25-28 -->

- **Declare workflow:** The Elicitor uses `projection_dimensions` to ensure the human addresses all rendering concerns. Starts from `python_defaults` (or another language default) as a baseline.
- **Distill workflow:** The Extractor observes rendering patterns in existing code. The dimension ontology tells it *what to look for*. Observed values are compared against `python_defaults` to highlight deviations.
- **Project workflow:** The Designer and Generator consume the project's ProjectionIG (which was derived from these references) as rendering instructions.
