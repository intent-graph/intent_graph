# Usage Scenarios

This document outlines primary usage patterns for the Intent Graph workflow, demonstrating how it applies to various stages of development.

## Table of Contents

1. [Starting From Scratch](#starting-from-scratch) _(Lines 18-28)_
2. [Refining the Graph](#refining-the-graph) _(Lines 31-40)_
3. [Generating Code](#generating-code) _(Lines 43-53)_
4. [Reverse Engineering](#reverse-engineering) _(Lines 56-66)_
5. [Exploration](#exploration) _(Lines 69-78)_
6. [GUI Experience](#gui-experience) _(Lines 81-90)_

---

## Starting From Scratch
<!-- Lines 18-28 -->

**Scenario:** Building a new system where requirements are vague.

1.  **Initialize**: User creates a root `intentnode` (System Goal).
2.  **Decompose**: User splits root into ~3-5 L1 `intentnodes` (Core Functional Flows).
3.  **Connect**: User draws `intentlinks` between L1 nodes to define logical data flow.
4.  **Validate**: User verifies the architecture at this high level (no code yet).
5.  **Iterate**: User selectively refines one L1 node into L2 sub-components (mixed detail).

*Outcome: A validated architectural map before a single line of code is written.*

## Refining the Graph
<!-- Lines 31-40 -->

**Scenario:** Making an existing design more specific without losing context.

1.  **Select**: User selects a coarse `intentnode` ("Auth System") in the lens.
2.  **Expand**: User adds children nodes (Login, Signup, Recovery) via `treearcs`.
3.  **Rewire**: System prompts user to "push down" existing connections—links to "Auth System" must now connect to specific children (e.g., "Login").
4.  **Review**: User collapses the node to verify that the "lifted" abstraction still makes sense.

*Outcome: Detailed specificity that remains consistent with the high-level intent.*

## Generating Code
<!-- Lines 43-53 -->

**Scenario:** Turning the graph into executable software.

1.  **Bundle**: User defines a "Working Lens" (a specific set of nodes to implement).
2.  **Generate**: Tool scaffolds file structures, types, and function signatures based on `intentnodes` and `intentlinks`.
3.  **Trace**: Generated code includes metadata comments referencing Intent IDs.
4.  **Fill**: User (or AI) implements the logic within the scaffolded boundaries.
5.  **Guard**: CI checks ensure implementation doesn't violate defined Intent constraints.

*Outcome: Code that is structurally guaranteed to match the design.*

## Reverse Engineering
<!-- Lines 56-66 -->

**Scenario:** Migrating a legacy codebase to Intent Graph.

1.  **Scan**: Agent crawls the codebase, identifying modules (directories) and dependencies (imports/calls).
2.  **Draft**: Agent proposes a coarse Intent Graph (File = Node, Import = Link).
3.  **Curate**: User renames nodes to reflect *Intent* ("UserAuth" instead of "utils/auth.ts").
4.  **Refine**: User groups low-level nodes into high-level logical concepts (creating `treearcs`).
5.  **Re-Gen**: User generates a *new* clean implementation plan from this purified graph, identifying technical debt.

*Outcome: A recovered "Source of Truth" from a chaotic codebase.*

## Exploration
<!-- Lines 69-78 -->

**Scenario:** Onboarding a new engineer to a large system.

1.  **Load Root**: User sees only top-level system components (e.g., Frontend, API, DB).
2.  **Inspect**: User clicks an `intentlink` between API and DB to see a "lifted" summary of their interaction.
3.  **Drill Down**: User expands "API" to see controllers, but keeps "DB" collapsed.
4.  **Context**: The graph displays how specific controllers interact with the generic DB node (contextual lifting).

*Outcome: Understanding system flow without being overwhelmed by million-line details.*

## GUI Experience
<!-- Lines 81-90 -->

**Scenario:** Visual interaction with the Intent Graph.

*   **Lens Map**: A canvas showing currently visible nodes and their connections.
*   **Zoom Controls**: "+" on a node expands it (replaces with children); "-" collapses it (replaces with parent).
*   **Ghost Links**: When hovering a link, show its "lifted" origin (real source/destination deep in the tree).
*   **Drift/Alerts**: Visual indicators (red borders) on nodes where implementation diverges from intent.
*   **Properties Panel**: Sidebar to edit "Why" (Purpose), "Constraints", and "Examples" for a selected node.

*Outcome: A CAD-like tool for software architecture.*
