# State of the Art: Intent-First and Spec-Driven Software Systems

*Competitive research on intent-first and spec-driven software systems.*

---

## 1. Executive Summary

The software engineering industry is currently undergoing a "shift left" from **Code-First** to **Intent-First** methodologies. This transition is driven by the rise of Generative AI, which has exposed the fragility of "Vibe Coding" (unstructured prompting) and created a need for rigorous, machine-readable specifications that act as a "Source of Truth."

The landscape is currently dominated by **Spec-Driven Development (SDD)** tools that rely on textual specifications (Markdown) to guide AI agents. However, there is a significant gap in the market for **Graph-Based** intent systems that model relationships, constraints, and multi-level refinement explicitly, rather than inferring them from flat text.

**Key Finding:** While tools like **Tessl** and **Traycer** are pioneering "Spec-as-Source," they largely map intent 1:1 to files or text documents. A true **Intent Graph**—where the topology of goals and constraints drives generation—remains a "frontier" concept found primarily in academic research (SemanticForge) and specialized runtimes (Embabel/GOAP), rather than mainstream developer tools.

---

## 2. Taxonomy of Approaches

We categorize the landscape based on how "Intent" is represented and its relationship to the executable code.

### A. Spec-Driven Development (SDD)

*Philosophy: "The Spec is the Prompt." Intent is captured in structured natural language documents.*

| Player | Type | Representation | Role of Code | Alignment with Intent Graph |
| :----- | :--- | :-------------- | :----------- | :-------------------------- |
| **Tessl** | Startup | **Spec-as-Source** | **Derivative**. Code is a read-only build artifact generated from .spec files. | **Medium**. Shares the "Code is Derivative" philosophy but relies on linear text files rather than a relational graph. |
| **Traycer** | Startup | **Living Specs** | **Managed**. Intent is captured via dialogue into "Mini-Specs" and "Tickets." | **Low/Medium**. Focuses on the *workflow* of eliciting intent, but the artifact is still largely textual requirements. |
| **GitHub Spec Kit** | Tool | **Spec-Anchored** | **Co-Equal**. Specs (spec.md) and Code evolve together; synced via "Constitution" rules. | **Low**. The spec is a guide, not a strict mathematical source of truth. Heavy reliance on developer discipline. |
| **Kiro (AWS)** | IDE | **Spec-First** | **Draft**. Converts prompts to "EARS" syntax (Easy Approach to Requirements Syntax). | **Low**. Primarily a "bootstrapping" tool to get from idea to initial code quickly. |

### B. Intent-Native Runtimes & Languages

*Philosophy: "The Structure is the Meaning." Intent is baked into the storage or runtime model.*

| Player | Type | Representation | Role of Code | Alignment with Intent Graph |
| :----- | :--- | :-------------- | :----------- | :-------------------------- |
| **Unison** | OSS | **Content-Addressable** | **Identity**. Code is identified by the hash of its AST (logic), not its file location/name. | **High**. Renaming a function doesn't break dependencies. The *intent* (logic) is the immutable ID. |
| **Darklang** | Startup | **Trace-Driven** | **Implicit**. Infrastructure (DBs, Queues) is provisioned instantly based on code usage. | **Medium**. Removes the "Deployment" step, making the code the direct definition of the architecture. |
| **Embabel** | Framework | **GOAP (Goal Oriented)** | **Dynamic**. Developers define "Goals" and "Actions"; the runtime plans the path. | **High**. This is "Intent at Runtime." The system doesn't run a script; it solves a graph to meet a goal. |

### C. Research & Academic Roots

*Philosophy: "Formalize the Why." Mathematical modeling of goals and constraints.*

| Player | Focus | Key Mechanism | Relevance |
| :----- | :---- | :------------- | :-------- |
| **SemanticForge** | Research | **Constraint Satisfaction** | Uses a Knowledge Graph of the repo to *mask* invalid LLM tokens during generation. |
| **JetBrains MPS** | Commercial | **Projectional Editing** | Code is stored as an AST graph, not text. Users edit "projections" (views). |
| **KAOS / i\*** | Academic | **Goal Modeling** | Explicit graph modeling of "Goals," "Agents," and "Obstacles." |

---

## 3. Deep Dive: Key Competitors

### 1. Tessl (The "Spec-as-Source" Leader)

**Positioning:** Tessl is the most aggressive proponent of "Code as Derivative." They argue that in an AI world, maintaining implementation code is technical debt.

- **Mechanism:** Developers write feature.spec.md. The Tessl engine (LLM + Symbolic Verification) generates the code.
- **Contrast:** Tessl is **File-Centric**. It organizes intent into file-like units. An Intent Graph is **Node-Centric**, allowing a single goal to span multiple files or services without being bound by file hierarchy.

### 2. Embabel (The Agentic Architect)

**Positioning:** Created by Rod Johnson (Spring Framework founder), Embabel brings **Goal-Oriented Action Planning (GOAP)** to enterprise Java.

- **Mechanism:** Instead of writing "If X then Y," you define a **Goal** (e.g., "Schedule Meeting") and a set of **Actions** (e.g., "Check Calendar", "Send Email"). The engine calculates the optimal graph path at runtime.
- **Contrast:** Embabel handles **Execution Intent** (runtime), whereas Intent Graph typically handles **Definition Intent** (design time). Merging these two (Design = Execution) is a massive opportunity.

### 3. SemanticForge (The Research Benchmark)

**Positioning:** A research framework for repository-level code generation.

- **Mechanism:** It builds a **Repository Knowledge Graph** (classes, methods, dependencies). When the AI generates code, a "Constraint Decoder" checks the graph in real-time. If the AI tries to call a non-existent method, the decoder *blocks* that token.
- **Contrast:** This is the technical proof-of-concept for the "Correctness" layer of an Intent Graph. It moves verification from "Post-Hoc Test" to "Real-Time Generation Constraint."

---

## 4. Strategic Gap Analysis

The current market is bifurcated:

1. **Textual/Vague:** Tools like Cursor and Spec Kit are easy to use but lack structural rigor (Text Specs).
2. **Rigid/Complex:** Tools like formal verification or MPS are rigorous but hard to use.

**The "Intent Graph" Opportunity:**

There is no dominant tool that combines the **Usability** of a visual whiteboard with the **Rigor** of a graph database.

- **The Missing Link:** A tool where you drag-and-drop "Goals" and "Constraints" (like a whiteboard), but underneath, it builds a rigorous dependency graph that *generates* and *locks* the code.
- **Visual Frontier:** Most tools are still text editors. A true Intent Graph system should feel like a CAD tool for logic, utilizing "Semantic Zoom" to hide complexity.
