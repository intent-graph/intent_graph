# IntentGraph — Agent Primers

Foundational primers for agents working with IntentGraph. These are implementation-agnostic: they apply whether you're a specialized subagent, an OOMA (one-man-army) agent, or a full session orchestrating workflows.

---

## Recommended Reading Order
<!-- Lines 9-30 -->

**For all agents (foundational):**

1. [PRIMER_00_PHILOSOPHY.md](PRIMER_00_PHILOSOPHY.md) — Why IntentGraph exists, core axioms (P1-P5), invariants (T1-T4), vocabulary
2. [PRIMER_01_SEMANTICS.md](PRIMER_01_SEMANTICS.md) — How to read/interpret nodes, fields, tree structure, common misreadings

**For agents working with graphs:**

3. [PRIMER_02_NAVIGATION.md](PRIMER_02_NAVIGATION.md) — How to navigate using Lens (LOD, viewport operations, budget management)
4. [PRIMER_03A_EDITING.md](PRIMER_03A_EDITING.md) — How to modify graphs (decomposition, propagation theory, decision framework)

**For practical work:**

5. [PRIMER_TOOLS.md](PRIMER_TOOLS.md) — Command reference (ig-tool syntax for viewport, node, link, batch, query operations)
6. [PRIMER_DIALOGUE.md](PRIMER_DIALOGUE.md) — How to gather human feedback (file-based dialogue protocol)
7. [PRIMER_04_WORKFLOWS.md](PRIMER_04_WORKFLOWS.md) — Understanding workflows (operation classes, fundamental activities, role guidance)
8. [PRIMER_05_INTENT_RESOURCES.md](PRIMER_05_INTENT_RESOURCES.md) — How to use and create `intent_resources.yaml` (project manifest: product + projection graphs + resources)

**Total: ~1650 lines** — Focused, implementation-agnostic primers.

---

## Quick Reference
<!-- Lines 33-47 -->

| Need | Read |
|------|------|
| Understand philosophy | PRIMER_00_PHILOSOPHY |
| Interpret graph structure | PRIMER_01_SEMANTICS |
| Navigate with Lens | PRIMER_02_NAVIGATION |
| Make editing decisions | PRIMER_03A_EDITING |
| Find command syntax | PRIMER_TOOLS |
| Gather human input | PRIMER_DIALOGUE |
| Understand your role/workflow | PRIMER_04_WORKFLOWS |
| Use or create intent_resources.yaml | PRIMER_05_INTENT_RESOURCES |
| Execution context (effort, dry_run, payload) | PRIMER_04_WORKFLOWS §Execution context |

---

## Role-Specific Agent Files
<!-- Lines 50-65 -->

After reading primers, see role-specific guidance in `../.claude/agents/`:

- **ig-extractor-agent.md** — Extracting intent from code
- **ig-critic-agent.md** — Finding graph quality issues
- **ig-elicitor-agent.md** — Conducting human dialogue
- **ig-designer-agent.md** — Designing code architecture from intent
- **ig-generator-agent.md** — Generating code from intent
- **ig-verifier-agent.md** — Creating tests from intent
- **ig-steward-agent.md** — Enforcing structure and propagation
- **ig-navigator-agent.md** — Recommending next targets

Each agent file builds on these primers with role-specific tactics. All IG agents use required reading (full vs compressed primers per role), §1 INPUT → §2 INSTRUCTIONS (including Mission vs. precision) → §3 OUTPUT CONTRACT. Designer, Generator, Verifier are single core files; Docreader, Extractor, Critic, Elicitor, Steward, Navigator may have mode modules and optional examples (see each agent file).

---

## Additional Resources
<!-- Lines 68-71 -->

- **[PRIMER_TOOLS.md](PRIMER_TOOLS.md)** — ig-tool command guide (WHY/when); `.claude/skills/ig-tool-*/SKILL.md` for exact flags
- **[../agents_runtime/AGENT_PRIMER.md](../agents_runtime/AGENT_PRIMER.md)** — Legacy agent primer (being superseded by PRIMER_* files)
- **[../../ai_tooling/howto/programming_subagents.md](../../ai_tooling/howto/programming_subagents.md)** ([GitHub](https://github.com/intent-graph/ai_tooling/blob/main/howto/programming_subagents.md)) — Canonical agent task payload format (INPUT, INSTRUCTIONS, OUTPUT CONTRACT, execution context including effort_hint)
