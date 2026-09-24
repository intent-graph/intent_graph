# IntentGraph — Agent Catalog

One row per agent file in this directory (name and role from its frontmatter). Support files
(`*-examples.md`, `*-mode-*.md`, `ig-agent-common-protocol.md`) are shared references the agents
below pull in — not standalone agents.

## Ingestion

| Agent | Role |
|-------|------|
| `ig-docreader-agent` | Extracts intent from documentation into the IntentGraph — manifest-guided, doc-only, no code reading. |
| `ig-extractor-agent` | Reverse-engineers intent from code into the IntentGraph — iterative, piece-wise, high-to-low. |

## Refinement

| Agent | Role |
|-------|------|
| `ig-elicitor-agent` | Refines the IntentGraph through structured dialogue — the conversational agent. |
| `ig-critic-agent` | Reviews IntentGraph quality — finds vagueness, missing constraints, HOW-not-WHY, gaps. Does not edit. |
| `ig-steward-agent` | Manages graph structure and operations — applies edits, audits shape, propagates constraints, reconciles the ProjectionIG. |

## Generation

| Agent | Role |
|-------|------|
| `ig-designer-agent` | Designs code architecture from IntentGraph + ProjectionIG — the grounding step between intent and code. |
| `ig-generator-agent` | Generates code from IntentGraph + ProjectionIG + Designer's plan — code is a projection of intent. |
| `ig-verifier-agent` | Designs and maintains the verification layer between intent and code — intent-derived tests. |

## Orchestration

| Agent | Role |
|-------|------|
| `ig-navigator-agent` | Recommends which lens to work on — manages IV-shaped limited-context. |
