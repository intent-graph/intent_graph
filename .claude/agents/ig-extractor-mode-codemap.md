# Extractor — CodeMap-Assisted Extraction

Read this when a CodeMap structural overview is provided in your context (as a `## Codebase Structure` section).

## Using CodeMap for Extraction

**Orientation first:** Read the CodeMap `overview()` YAML before diving into source code. It shows you the full structural skeleton — packages, modules, classes, functions — so you know what exists and where. This prevents blind file-by-file reading.

**Structural hierarchy as a guide, not a template:** The CodeMap containment hierarchy (package → module → class → method) is a useful starting point for intentnode hierarchy, but do NOT copy it 1:1. Code structure reflects how a developer organized files; intent structure reflects what the system does and why. A single module may contain multiple intent concepts; a single intent concept may span multiple modules.

**Edges as intentlink candidates:** CodeMap `~calls` and `~inherits` edges are candidate intentlinks. For each:
- Ask: "Does this structural relationship represent a meaningful intent relationship?"
- A call edge that is a data transformation pipeline → likely a `data_exchange` intentlink
- An inheritance edge that represents a type taxonomy → likely a `dependency` intentlink
- A call edge that is internal plumbing (logging, utility) → probably not worth an intentlink

**IV-context for deepening:** When deepening a specific subtree, request CodeMap `context()` for the focus node. This gives you an IV-context view: orientation path + target neighborhood, with selectable `full` vs `lean` detail — without reading unrelated code.

**Extract intent from source, not metadata:** CodeMap gives you structure (what exists, where). Intent (why it exists) must come from reading the actual source code, docstrings, tests, and inline comments. Do not generate intent statements from function signatures alone.
