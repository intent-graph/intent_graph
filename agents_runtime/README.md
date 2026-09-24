# IntentGraph Agent Infrastructure (Phase 2)

Agent orchestration layer for IntentGraph — session management, I/O logging, context assembly, evaluation harness, and the `ig-tool` CLI. Sits above the core library (`intentgraph`) and below the agent markdown files (`.claude/agents/ig-*-agent.md`).

## Quick Start

```bash
# Install ig-tool system-wide (from intent_graph root):
cd intent_graph && uv tool install -e .

# Or for development with tests:
cd agents_runtime
uv run --no-project --with pytest --with pydantic --with pyyaml \
  env PYTHONPATH=src:../src/src pytest
```

## Package Structure

```
src/ig_agents/
├── __init__.py
├── cli.py              # ig-tool CLI (unified entry point for all hard tools)
├── context.py          # Context assembly + budget management
├── session.py          # Multi-turn session state + persistence
├── logger.py           # JSONL I/O logging for training data
├── trace.py            # Workflow trace (JSONL step/actor/action log)
├── codemap_bridge.py   # Bridge to CodeMap structural analysis
└── eval/
    ├── __init__.py
    └── harness.py      # Quality evaluation per agent role
```

## ig-tool CLI

Installed system-wide via `uv tool install -e .` from the repo root. Works from any directory.

```bash
# Core operations
ig-tool validate -g graph.json -o report.yaml
ig-tool query -g graph.json --node D -o node.yaml
ig-tool apply -g graph.json -i edits.yaml -o updated.json --role extractor

# Lens-based agent I/O
ig-tool lens build -g graph.json -t TARGET -o lens.yaml -b 30
ig-tool lens show -l lens.yaml -o view.yaml
ig-tool lens tree -l lens.yaml
ig-tool node create -g graph.json --uid UID --name "Node Name" --intent "..." -o graph.json
ig-tool link create -g graph.json --src SRC --dst DST --intent "..." -o graph.json
ig-tool apply -g graph.json --batch changes.yaml -o updated.json

# Context & trace
ig-tool context -g graph.json -f NAME -t UID -b 4000 -o context.yaml
ig-tool workflow trace show trace.jsonl -o timeline.txt
```

Command guide (WHY/when): [../agents/PRIMER_TOOLS.md](../agents/PRIMER_TOOLS.md). Exact syntax: `.claude/skills/ig-tool-*/SKILL.md`.

## Modules

**Note:** The following examples document the `ig_agents` package API for orchestrator and infrastructure code. Agents should use the `ig-tool` CLI (documented above) for graph operations.

### context.py — Context Assembly

Prepares IntentGraph context for agent consumption:

```python
from ig_agents.context import assemble_agent_context, check_view_budget, build_working_view

# Build a working view (lens) — by node set or depth cut
view = build_working_view(graph, node_uids={"E", "T", "L"})

# Check if the view fits in token budget
budget = check_view_budget(view, word_budget=4000)
# {'within_budget': True, 'size': {'chars': 1200, 'words': 180, 'lines': 40}, 'budget': 4000}

# Full context assembly
ctx = assemble_agent_context(graph, view, include_overview=True, style_path="style.md")
# ctx['view_text'], ctx['tree_overview'], ctx['edge_overview'], ctx['style_text']
```

### session.py — Session Management

Multi-turn state for Elicitor and iterative Extractor loops:

```python
from ig_agents.session import Session, SessionStore

session = Session(agent_role="elicitor", graph_path="graph.json", view_name="auth-detail")
session.add_turn(input_summary="Asked about auth flow", output_summary="Proposed 3 children for AUTH node",
                 edits_proposed=3, edits_accepted=2, edits_rejected=1)

store = SessionStore(".ig_sessions")
store.save(session)

# Later: resume
resumed = store.load(session.session_id)
```

### logger.py — I/O Logging

Every agent invocation is logged as training data for Phase 5:

```python
from ig_agents.logger import AgentLogger

logger = AgentLogger(".ig_logs")

# Context manager for automatic timing and logging
with logger.track("extractor", model="opus", graph_path="g.json") as entry:
    entry.input_text = view_text
    # ... run agent ...
    entry.output_text = result
    entry.edits_count = 5

# Read stats
stats = logger.stats("extractor")
# {'count': 42, 'total_edits': 156, 'avg_duration': 12.3, 'success_rate': 0.95, ...}
```

### eval/harness.py — Evaluation Harness

Quality metrics per agent role:

```python
from ig_agents.eval.harness import eval_extractor_output, eval_critic_output

result = eval_extractor_output(graph, agent_output_yaml)
print(result.summary())
# [PASS] extractor/unnamed: parse_success=1.00, invariant_compliance=0.95, ...
```

## Lens Workflow

The **Lens** replaces frontier-based agent I/O. All agents now use:

```
1. Agent receives full-tree Lens with variable LOD (skeleton < lean < full)
2. Agent reasons about tree structure for orientation
3. Agent proposes edits via CLI commands (not raw YAML): lens, node, link, batch
4. Orchestrator applies edits atomically, validating structure
```

**Design & Implementation:**
- [Lens Redesign Specification](../foundation_and_formalism/LENS_REDESIGN_SPEC.md) — Lens concept, LOD system, closure invariants, CLI command surface

**Benefits:**
- Agents always see hierarchy for structural reasoning
- CLI commands validated atomically (no YAML mangling)
- Budget-aware detail control (IV_ pattern: target=full, ancestors=lean, context=skeleton)
- Full-tree view prevents orientation loss (the former flat-antichain frontier lost hierarchy)

## Agent Markdown Files

The agent configurations live in `.claude/agents/`:

| Agent | File | Role | I/O Format |
|-------|------|------|------------|
| Extractor | `ig-extractor-agent.md` | Code → Graph | Lens |
| Critic | `ig-critic-agent.md` | Graph quality review | Lens |
| Elicitor | `ig-elicitor-agent.md` | Dialogue refinement | Lens + CLI commands |
| Generator | `ig-generator-agent.md` | Graph → Code | Lens |
| Verifier | `ig-verifier-agent.md` | Intent → Tests | Lens |
| Navigator | `ig-navigator-agent.md` | Target recommendation | Lens |

## Related

- [Core library](../src/README.md) — IntentGraph data model and operations
- [Agent catalog](../agents/README.md) — Full agent descriptions
- [Roadmap](../INTENTCODE_ROADMAP.md) — Phase 2 in context
