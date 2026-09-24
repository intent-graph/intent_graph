#!/usr/bin/env python3
"""Build an IntentGraph for the SQL Function Sync Validator project.

This script demonstrates the IntentGraph core library end-to-end by modeling
an illustrative "SQL Function Sync Validator" (an invented tool) as an
IntentGraph, used here as a demonstration target for IntentGraph.

It exercises:
  1. Graph construction (nodes, treearcs, intentlinks)
  2. View navigation at 3 depth levels
  3. Lens LOD navigation (promote / demote / focus / prune / expand)
  4. Intentlink projection (lifting)
  5. Agent text format round-trip (serialize → modify → parse → apply)
  6. JSON + YAML persistence

This is a demonstration target built for the IntentGraph repo; every
name, count, and path below is invented for teaching purposes.

Run:
  cd src
  uv run python examples/build_validator_graph.py
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from intentgraph import IntentGraph, View
from intentgraph.models.lens import LOD
from intentgraph.ops import project_links, rep
from intentgraph.ops.lens_ops import (
    build_lens,
    demote,
    expand_subtree,
    focus_on,
    promote,
    prune_subtree,
)
from intentgraph.serial import (
    view_to_text,
    text_to_edits,
    apply_edits,
    save_json,
    graph_to_yaml,
)


# ================================================================== #
#  Helpers                                                            #
# ================================================================== #

SEPARATOR = "=" * 78
SUBSEP = "-" * 78


def section(title: str) -> None:
    """Print a section header."""
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n{SUBSEP}")
    print(f"  {title}")
    print(SUBSEP)


def show_view(f: View, label: str | None = None) -> None:
    """Print a view's nodes with their intent, plus projected links."""
    g = f.graph
    tag = label or f.name
    print(f"\n  View: {tag}  ({len(f)} nodes)")
    print(f"  {'uid':<12} {'name':<36} epistemic")
    print(f"  {'---':<12} {'---':<36} ---")
    for uid in sorted(f.node_uids):
        node = g.get_node(uid)
        eps = node.epistemic_state or ""
        print(f"  {uid:<12} {node.name:<36} {eps}")

    projected = project_links(f)
    if projected:
        print(f"\n  Projected intentlinks ({len(projected)}):")
        for pl in projected:
            lifted = " [LIFTED]" if pl.is_lifted else ""
            print(f"    {pl.display_src} -> {pl.display_dst}: "
                  f"{pl.original.intent}{lifted}")
    else:
        print("\n  (no projected intentlinks at this view)")


# ================================================================== #
#  1. Build the IntentGraph                                           #
# ================================================================== #

def build_graph() -> IntentGraph:
    """Build the complete IntentGraph for the SQL Function Sync Validator."""

    g = IntentGraph(meta={
        "name": "SQL Function Sync Validator",
        "version": "1.0",
        "description": (
            "Validates that SQL functions stored in PostgreSQL (via generated "
            "cache from pg_get_functiondef) match the source code tracked in "
            "the git repository. Detects DB drift, missing source, signature "
            "mismatches, and body differences."
        ),
    })

    # ---- ROOT ----
    g.add_node(
        "ROOT",
        "SQL Function Sync Validator",
        "Detect and report discrepancies between SQL functions in the database "
        "(represented by generated cache) and their source code definitions in "
        "the repository, so that DB drift is caught before it causes production issues.",
        epistemic_state="known",
        constraints=[
            "Source of truth is the database (generated cache via pg_get_functiondef)",
            "Must scale to repositories with many schemas",
            "Must gracefully skip unparseable SQL (pglast limitations)",
            "Output must be both human-readable (markdown) and machine-readable (JSON)",
        ],
        design_notes=(
            "Pipeline architecture: Discovery -> Parsing -> Validation -> Reporting. "
            "Chosen over a monolithic approach for testability and clear separation of "
            "concerns. Parser uses pglast (the official PostgreSQL parser)."
        ),
        history=[
            {"who": "agent:extractor", "date": "2026-02-12",
             "note": "Created IntentGraph by hand as a demonstration."},
        ],
    )

    # ================================================================== #
    #  Level 1 — Major functional capabilities                           #
    # ================================================================== #

    # DISCOVER = Discovery
    g.add_node_under(
        "DISCOVER", "Discovery", parent_uid="ROOT",
        intent=(
            "Locate all SQL function definitions in both the generated cache "
            "(database source of truth) and the source code directories, then "
            "map each generated function to its source counterpart."
        ),
        epistemic_state="known — well-tested discovery with fallback grep",
        constraints=[
            "Generated cache dir: build/db_dump/functions/",
            "Source dirs: sql/functions/ (recursive)",
            "Exclude dirs: sql/functions/deprecated/",
            "Filenames in generated cache follow schema.function_name.sql convention",
        ],
        design_notes=(
            "Three-pass strategy: (1) scan generated cache, (2) scan source dirs, "
            "(3) fallback grep for unmatched functions. The fallback grep is optional "
            "but catches functions stored in unexpected locations."
        ),
    )

    # PARSE = Parsing
    g.add_node_under(
        "PARSE", "Parsing", parent_uid="ROOT",
        intent=(
            "Parse SQL function definitions from raw .sql files into structured "
            "representations (signature + body), with type normalization to reduce "
            "false positives from PostgreSQL's type aliasing."
        ),
        epistemic_state="known — uses pglast (official PG parser); robust but has edge cases",
        constraints=[
            "Must use pglast for reliable parsing (not regex-only)",
            "pglast may fail on non-standard SQL (non-SQL procedural languages) — must skip gracefully",
            "Must handle both dollar-quoted and single-quoted function bodies",
            "Must handle multi-statement SQL files",
        ],
        design_notes=(
            "pglast was chosen over regex-only parsing because CREATE FUNCTION syntax "
            "is too complex for reliable regex extraction."
        ),
    )

    # VALIDATE = Validation
    g.add_node_under(
        "VALIDATE", "Validation", parent_uid="ROOT",
        intent=(
            "Compare parsed function representations from the database (generated) "
            "against source code, detecting signature mismatches, body differences, "
            "and existence gaps, and classify each discrepancy by severity."
        ),
        epistemic_state="constrained — signature type validation disabled due to PG aliasing limitations",
        constraints=[
            "Severity levels: CRITICAL (missing source, signature mismatch), WARNING (body diff), INFO (minor)",
            "Type comparison uses normalized forms (int8 = bigint, etc.)",
            "Body comparison normalizes whitespace before diffing",
            "Parameter type validation currently disabled — not reliable due to OID resolution",
        ],
        design_notes=(
            "Signature validation is intentionally limited: only language is checked "
            "as a sanity check. Parameter type and return type comparison was disabled "
            "because PostgreSQL's internal type canonicalization and OID resolution in "
            "pg_get_functiondef makes exact comparison unreliable."
        ),
    )

    # REPORT = Reporting
    g.add_node_under(
        "REPORT", "Reporting", parent_uid="ROOT",
        intent=(
            "Generate human-readable and machine-readable reports summarizing "
            "validation results, grouped by severity and issue type, with "
            "actionable information for each discrepancy."
        ),
        epistemic_state="known — stable output format",
        constraints=[
            "Markdown report: VALIDATION_REPORT.md with severity-grouped tables",
            "JSON report: validation_data.json with structured data for tooling",
            "Reports must include pass rate, severity counts, and per-function details",
        ],
    )

    # ORCHESTRATE = Orchestration
    g.add_node_under(
        "ORCHESTRATE", "Orchestration", parent_uid="ROOT",
        intent=(
            "Coordinate the full pipeline: parse CLI arguments, run discovery, "
            "iterate through functions for validation, generate reports, and "
            "print a summary with appropriate exit code."
        ),
        epistemic_state="known — simple linear pipeline",
        constraints=[
            "CLI args: --output-dir, --verbose, --skip-fallback-search",
            "Exit code 0 = all valid, exit code 1 = issues found",
            "Must print progress indicators during execution",
        ],
    )

    # ================================================================== #
    #  Level 2 — Sub-capabilities                                        #
    # ================================================================== #

    # -- Discovery sub-capabilities --
    g.add_node_under(
        "DISCOVER.1", "Generated Cache Scanning", parent_uid="DISCOVER",
        intent=(
            "Scan the generated cache directory for .sql files, parse filenames "
            "to extract schema.function_name, and parse each file's SQL to create "
            "FunctionRecord entries with generated_parsed data."
        ),
        epistemic_state="known",
        constraints=[
            "Files named schema.function_name.sql — skip malformed names",
            "Each file contains one CREATE FUNCTION from pg_get_functiondef()",
        ],
    )

    g.add_node_under(
        "DISCOVER.2", "Source Directory Scanning", parent_uid="DISCOVER",
        intent=(
            "Scan all source function directories for .sql files, parse them "
            "for CREATE FUNCTION statements (possibly multiple per file), and "
            "map each to the corresponding FunctionRecord."
        ),
        epistemic_state="known",
        constraints=[
            "Multiple functions per file are supported",
            "Excluded directories (sql/functions/deprecated/) are skipped",
        ],
    )

    g.add_node_under(
        "DISCOVER.3", "Fallback Grep Search", parent_uid="DISCOVER",
        intent=(
            "For generated functions with no source match after directory scanning, "
            "search the entire repository using grep/ripgrep to find function definitions "
            "in unexpected locations."
        ),
        epistemic_state="known — optional, can be skipped for speed",
        constraints=[
            "Blacklist approach: exclude only docs/ and deprecated/",
            "10-second timeout per grep search",
            "Falls back to ripgrep if grep is not found",
            "Functions found outside sql/functions/ are flagged",
        ],
    )

    # -- Parsing sub-capabilities --
    g.add_node_under(
        "PARSE.1", "Signature Extraction", parent_uid="PARSE",
        intent=(
            "Extract function metadata from pglast AST: schema, name, parameter "
            "types, return type, and language."
        ),
        epistemic_state="known",
        constraints=[
            "Uses pglast AST nodes: CreateFunctionStmt, DefElem, TypeName",
            "Schema defaults to 'public' if not specified",
            "Language defaults to 'plpgsql' if not specified",
        ],
    )

    g.add_node_under(
        "PARSE.2", "Body Extraction", parent_uid="PARSE",
        intent=(
            "Extract the function body text from a CREATE FUNCTION statement, "
            "handling dollar-quoted ($$ ... $$) and single-quoted bodies."
        ),
        epistemic_state="constrained — uses heuristic regex, not pure AST",
        constraints=[
            "Must handle $tag$...$tag$ dollar quoting",
            "Must handle '...' single quoting with escaped quotes",
            "Fallback strips LANGUAGE/IMMUTABLE/etc. clauses via regex",
        ],
        design_notes=(
            "Body extraction is regex-based (not from pglast AST) because pglast "
            "normalizes the body text, losing the original formatting. We need the "
            "raw body for comparison."
        ),
    )

    g.add_node_under(
        "PARSE.3", "Type Normalization", parent_uid="PARSE",
        intent=(
            "Normalize PostgreSQL type aliases to canonical forms so that type "
            "comparisons are not confused by synonyms (e.g., bigint = int8)."
        ),
        epistemic_state="known — covers 9+ type aliases",
        constraints=[
            "Canonical forms: int8, int4, int2, float8, float4, bool, bpchar, varchar, text",
            "Also handles: timestamptz, timestamp",
            "Normalization is case-insensitive and whitespace-normalized",
        ],
    )

    # -- Validation sub-capabilities --
    g.add_node_under(
        "VALIDATE.1", "Existence Checking", parent_uid="VALIDATE",
        intent=(
            "Detect functions that exist in one location but not the other: "
            "in DB but not source (CRITICAL — DB drift), or in source but "
            "not DB (WARNING — not deployed)."
        ),
        epistemic_state="known",
    )

    g.add_node_under(
        "VALIDATE.2", "Signature Comparison", parent_uid="VALIDATE",
        intent=(
            "Compare function signatures between generated and source, currently "
            "limited to language-only checking due to type aliasing limitations."
        ),
        epistemic_state="constrained — parameter and return type comparison disabled",
        constraints=[
            "Only language is compared (sanity check)",
            "Type validation disabled: PostgreSQL OID resolution makes comparison unreliable",
        ],
    )

    g.add_node_under(
        "VALIDATE.3", "Body Comparison", parent_uid="VALIDATE",
        intent=(
            "Compare function bodies after whitespace normalization, using "
            "SequenceMatcher for similarity scoring when bodies differ."
        ),
        epistemic_state="known",
        constraints=[
            "Whitespace normalized: trailing spaces removed, lines stripped",
            "Uses difflib.SequenceMatcher for similarity ratio",
            "Any difference = WARNING severity",
        ],
    )

    g.add_node_under(
        "VALIDATE.4", "Severity Classification", parent_uid="VALIDATE",
        intent=(
            "Assign severity levels to each discrepancy: CRITICAL for missing "
            "source or signature mismatch, WARNING for body differences or "
            "unexpected locations, INFO for minor findings."
        ),
        epistemic_state="known",
    )

    # -- Reporting sub-capabilities --
    g.add_node_under(
        "REPORT.1", "Markdown Report Generation", parent_uid="REPORT",
        intent=(
            "Generate a human-readable markdown report with summary statistics, "
            "severity-grouped tables (missing/misplaced, body mismatch, not deployed), "
            "and valid function counts."
        ),
        epistemic_state="known",
        constraints=[
            "Output: VALIDATION_REPORT.md",
            "Sections: Missing/misplaced, No Match, Outside sql/functions/, Body Mismatch, Not Deployed, Valid",
        ],
    )

    g.add_node_under(
        "REPORT.2", "JSON Report Generation", parent_uid="REPORT",
        intent=(
            "Generate structured JSON data with timestamp, summary statistics, "
            "and per-function results including severity, issues, and details."
        ),
        epistemic_state="known",
        constraints=[
            "Output: validation_data.json",
            "Must include: timestamp, summary (totals, pass_rate, by_severity), results array",
        ],
    )

    # -- Orchestration sub-capabilities --
    g.add_node_under(
        "ORCHESTRATE.1", "CLI Argument Parsing", parent_uid="ORCHESTRATE",
        intent="Parse command-line arguments: --output-dir, --verbose, --skip-fallback-search.",
        epistemic_state="known",
    )

    g.add_node_under(
        "ORCHESTRATE.2", "Pipeline Execution", parent_uid="ORCHESTRATE",
        intent=(
            "Execute the linear pipeline: discover_all() -> validate each function "
            "-> generate_all() reports, with progress output."
        ),
        epistemic_state="known",
    )

    g.add_node_under(
        "ORCHESTRATE.3", "Summary and Exit Code", parent_uid="ORCHESTRATE",
        intent="Print validation summary statistics and return exit code (0 = clean, 1 = issues).",
        epistemic_state="known",
    )

    # ================================================================== #
    #  Intentlinks — data flow and dependencies between components       #
    # ================================================================== #

    # Discovery -> Validation (data_exchange: discovered function records)
    g.add_link(
        "DISCOVER", "VALIDATE",
        "Discovery provides FunctionRecord dict (schema.name -> generated/source parsed data) "
        "consumed by Validation for comparison.",
    )

    # Discovery -> Reporting (data_exchange: function records for context)
    g.add_link(
        "DISCOVER", "REPORT",
        "Discovery provides FunctionRecord dict to Reporter for source location paths "
        "and context in report tables.",
    )

    # Parsing is used by Discovery (dependency: parser is a tool used during scanning)
    g.add_link(
        "PARSE", "DISCOVER",
        "Discovery depends on the Parser to extract signatures and bodies from .sql files "
        "during both generated cache scanning and source directory scanning.",
    )

    # Validation -> Reporting (data_exchange: validation results)
    g.add_link(
        "VALIDATE", "REPORT",
        "Validation produces ValidationReport (list of ValidationResult with severity, "
        "issues, details) consumed by Reporter to generate output files.",
    )

    # Orchestration -> Discovery (coordination: triggers discovery phase)
    g.add_link(
        "ORCHESTRATE", "DISCOVER",
        "Orchestrator calls FunctionDiscovery.discover_all() to start the pipeline.",
    )

    # Orchestration -> Validation (coordination: iterates and validates)
    g.add_link(
        "ORCHESTRATE", "VALIDATE",
        "Orchestrator iterates through discovered functions and calls "
        "FunctionValidator.validate_function() for each.",
    )

    # Orchestration -> Reporting (coordination: triggers report generation)
    g.add_link(
        "ORCHESTRATE", "REPORT",
        "Orchestrator calls ReportGenerator.generate_all() with results and functions.",
    )

    # -- Refined links at level 2 --

    # D.1 uses parser, D.2 uses parser (refined from P -> D)
    g.add_link(
        "PARSE.1", "DISCOVER.1",
        "Generated cache scanning uses signature extraction to create ParsedFunction objects.",
        parent="PARSE_DISCOVER",
    )

    g.add_link(
        "PARSE.1", "DISCOVER.2",
        "Source scanning uses signature extraction to identify functions in multi-statement files.",
        parent="PARSE_DISCOVER",
    )

    g.add_link(
        "PARSE.2", "DISCOVER.1",
        "Generated cache scanning uses body extraction for each function.",
        parent="PARSE_DISCOVER",
        tag="body",
    )

    g.add_link(
        "PARSE.2", "DISCOVER.2",
        "Source scanning uses body extraction for each parsed function.",
        parent="PARSE_DISCOVER",
        tag="body",
    )

    # Type normalization feeds into both signature extraction and validation
    g.add_link(
        "PARSE.3", "PARSE.1",
        "Type normalization is called during signature extraction to normalize parameter "
        "and return types.",
    )

    g.add_link(
        "PARSE.3", "VALIDATE.2",
        "Type normalization enables signature comparison by resolving aliases.",
    )

    g.add_link(
        "PARSE.3", "VALIDATE.3",
        "Type normalization is used during body comparison for consistent type names.",
    )

    # Existence checking -> Severity classification
    g.add_link(
        "VALIDATE.1", "VALIDATE.4",
        "Existence check results (missing source = CRITICAL, missing DB = WARNING) "
        "determine initial severity classification.",
    )

    # Signature comparison -> Severity classification
    g.add_link(
        "VALIDATE.2", "VALIDATE.4",
        "Signature mismatch results (language difference = CRITICAL) feed severity assignment.",
    )

    # Body comparison -> Severity classification
    g.add_link(
        "VALIDATE.3", "VALIDATE.4",
        "Body mismatch results (any difference = WARNING with similarity score) "
        "feed severity assignment.",
    )

    # V.4 -> R.1 and R.2 (refined from V -> R)
    g.add_link(
        "VALIDATE.4", "REPORT.1",
        "Severity-classified results drive the grouping and ordering of the markdown report.",
        parent="VALIDATE_REPORT",
    )

    g.add_link(
        "VALIDATE.4", "REPORT.2",
        "Severity-classified results are serialized into the JSON data structure.",
        parent="VALIDATE_REPORT",
    )

    return g


# ================================================================== #
#  2. Demonstrate View Navigation                                     #
# ================================================================== #

def demo_views(g: IntentGraph) -> None:
    """Show views at depth 0, 1, and 2."""
    section("VIEW NAVIGATION (3 depth levels)")

    # Level 0: ROOT only
    f0 = View.from_depth(g, "level-0-root", depth=0)
    show_view(f0, "Level 0 — Root only")

    # Level 1: major capabilities
    f1 = View.from_depth(g, "level-1-capabilities", depth=1)
    show_view(f1, "Level 1 — Major capabilities (DISCOVER, PARSE, VALIDATE, REPORT, ORCHESTRATE)")

    # Level 2: all sub-capabilities
    f2 = View.from_depth(g, "level-2-subcapabilities", depth=2)
    show_view(f2, "Level 2 — Sub-capabilities (full detail)")


# ================================================================== #
#  3. Demonstrate Lens Navigation (LOD + scope)                       #
# ================================================================== #

def demo_lens_navigation(g: IntentGraph) -> None:
    """Build a Lens and walk through its LOD/scope operations.

    The former DisplayFrontier `expand`/`collapse` pair (which grew or
    shrank a fixed antichain of visible nodes) has been replaced by the
    Lens: a full-tree view where every node is always present, but shown
    at a variable Level of Detail (skeleton < lean < full). "Expand" and
    "collapse" become `promote`/`demote` (finer/coarser LOD on a node
    already in the lens) plus `expand_subtree`/`prune_subtree` (bring a
    pruned branch back into scope, or drop one out of scope).
    """
    section("LENS NAVIGATION (LOD promote/demote, focus, prune/expand)")

    # Build a lens centered on Validation: target + neighbors get `full`,
    # ancestors + L1 siblings get `lean`, everything else `skeleton`.
    lens = build_lens(g, target_uid="VALIDATE", budget=30, name="lens-demo")
    print("\n  Lens built with target='VALIDATE':")
    print(f"  Node count: {lens.node_count()}   LOD stats: {lens.lod_stats()}")
    print(f"  VALIDATE.1 LOD (distant, no direct edge to target): {lens.get_lod('VALIDATE.1').value}")

    # Promote: bring a skeleton-level node into working detail
    subsection("Promote 'VALIDATE.1' skeleton -> lean -> full")
    promote(lens, "VALIDATE.1")
    print(f"  After 1 promote: {lens.get_lod('VALIDATE.1').value}")
    promote(lens, "VALIDATE.1")
    print(f"  After 2nd promote: {lens.get_lod('VALIDATE.1').value}")

    # Demote: pull a node back out of working detail
    subsection("Demote 'VALIDATE.1' full -> lean -> skeleton")
    demote(lens, "VALIDATE.1")
    print(f"  After 1 demote: {lens.get_lod('VALIDATE.1').value}")
    demote(lens, "VALIDATE.1")
    print(f"  After 2nd demote: {lens.get_lod('VALIDATE.1').value}")

    # Focus: refocus the whole lens on a new target, recomputing all LODs
    subsection("Focus lens on 'PARSE' (recomputes IV_ LOD for every node)")
    focus_on(lens, g, "PARSE")
    print(f"  New target: {lens.meta.target_uid}")
    print(f"  PARSE LOD: {lens.get_lod('PARSE').value}   VALIDATE LOD: {lens.get_lod('VALIDATE').value}")

    # Prune: drop a subtree from scope entirely (viewport-only, no graph edit)
    subsection("Prune 'REPORT' subtree out of scope")
    before = lens.node_count()
    prune_subtree(lens, "REPORT")
    print(f"  Node count {before} -> {lens.node_count()}   Pruned subtrees: {lens.pruned_subtrees}")

    # Expand: bring a pruned subtree back into scope
    subsection("Expand 'REPORT' subtree back into scope")
    expand_subtree(lens, g, "REPORT")
    print(f"  Node count now: {lens.node_count()}   Pruned subtrees: {lens.pruned_subtrees}")


# ================================================================== #
#  4. Demonstrate Intentlink Projection                               #
# ================================================================== #

def demo_projection(g: IntentGraph) -> None:
    """Show how intentlinks project (lift) across view levels."""
    section("INTENTLINK PROJECTION (lifting)")

    # Level 1: coarse view
    f1 = View.from_depth(g, "projection-l1", depth=1)
    subsection("Level 1 — Coarse projected links")
    show_view(f1)

    # Mixed view: V's children swapped in for V, rest at level 1
    mixed_uids = (set(f1.node_uids) - {"VALIDATE"}) | {
        "VALIDATE.1", "VALIDATE.2", "VALIDATE.3", "VALIDATE.4"
    }
    f_mixed = View.from_node_set(g, "projection-mixed", mixed_uids)
    subsection("Mixed view — V's sub-capabilities shown, rest at level 1")
    show_view(f_mixed, "Mixed: V expanded")

    # Show rep() for specific nodes
    print("\n  rep() examples at mixed view:")
    for test_uid in ["VALIDATE.1", "VALIDATE.4", "DISCOVER.1", "PARSE.3", "ROOT"]:
        r = rep(f_mixed, test_uid)
        print(f"    rep(F, {test_uid}) = {r}")


# ================================================================== #
#  5. Demonstrate Agent Text Round-Trip                               #
# ================================================================== #

def demo_agent_text_roundtrip(g: IntentGraph) -> None:
    """Serialize view to text, modify, parse back, and apply edits."""
    section("AGENT TEXT FORMAT ROUND-TRIP")

    # Create a view at level 1 for the demo
    f1 = View.from_depth(g, "agent-demo", depth=1)

    # Serialize to agent text
    text = view_to_text(f1)
    subsection("Serialized view (agent text format)")
    print(text)

    # Simulate an agent modifying the text:
    # 1. Update Validation's epistemic_state to mark it as "risky"
    # 2. Add a new constraint to Reporting
    subsection("Simulated agent modification")

    modified_text = text.replace(
        'epistemic_state: "constrained \u2014 signature type validation disabled due to PG\n    aliasing limitations"',
        'epistemic_state: "risky \u2014 signature comparison disabled; considering re-enabling\n    with fuzzy matching for v2"',
    )

    # If the simple replace didn't work (YAML formatting may vary), try a
    # more robust approach by working with the YAML directly
    import yaml
    doc = yaml.safe_load(text)

    # Find the Validation node and update its epistemic_state
    for node in doc["nodes"]:
        if node["uid"] == "VALIDATE":
            node["epistemic_state"] = (
                "risky — signature comparison disabled; considering "
                "re-enabling with fuzzy matching for v2"
            )
            print(f"  Modified V.epistemic_state:")
            print(f"    -> \"{node['epistemic_state']}\"")
        if node["uid"] == "REPORT":
            if "constraints" not in node:
                node["constraints"] = []
            node["constraints"].append(
                "Reports must be generated within seconds for large repositories"
            )
            print(f"  Added constraint to R:")
            print(f"    -> \"{node['constraints'][-1]}\"")

    modified_text = yaml.dump(
        doc, default_flow_style=False, allow_unicode=True, sort_keys=False
    )

    # Parse back to edits
    subsection("Parsed edit operations")
    edits = text_to_edits(modified_text, g)
    if edits:
        for edit in edits:
            print(f"  {type(edit).__name__}: {edit}")
    else:
        print("  (no edits detected — text matched graph state)")

    # Apply edits
    if edits:
        subsection("Applying edits to graph")
        log = apply_edits(g, edits)
        for entry in log:
            print(f"  {entry}")

        # Verify the change
        v_node = g.get_node("VALIDATE")
        print(f"\n  Verification — V.epistemic_state is now:")
        print(f"    \"{v_node.epistemic_state}\"")

        r_node = g.get_node("REPORT")
        print(f"\n  Verification — R.constraints now includes:")
        for c in r_node.constraints:
            print(f"    - \"{c}\"")


# ================================================================== #
#  6. Persist the Graph                                               #
# ================================================================== #

def demo_persistence(g: IntentGraph) -> None:
    """Save graph to JSON and show YAML representation."""
    section("PERSISTENCE (JSON + YAML)")

    output_dir = Path(__file__).parent
    json_path = output_dir / "validator_graph.json"

    save_json(g, json_path)
    print(f"\n  Saved graph to: {json_path}")
    print(f"  Nodes: {g.node_count()}, Links: {g.link_count()}")

    # Show YAML excerpt
    subsection("YAML representation (excerpt)")
    yaml_text = graph_to_yaml(g)
    # Show first ~80 lines
    lines = yaml_text.split("\n")
    for line in lines[:80]:
        print(f"  {line}")
    if len(lines) > 80:
        print(f"  ... ({len(lines) - 80} more lines)")


# ================================================================== #
#  7. Summary Statistics                                              #
# ================================================================== #

def print_summary(g: IntentGraph) -> None:
    """Print summary statistics about the built graph."""
    section("GRAPH SUMMARY")

    # Count nodes by depth
    depth_counts: dict[int, int] = {}
    for node in g.iter_nodes():
        depth = 0
        current = node
        while current.parent_uid is not None:
            depth += 1
            current = g.get_node(current.parent_uid)
        depth_counts[depth] = depth_counts.get(depth, 0) + 1

    print(f"\n  Total nodes:  {g.node_count()}")
    print(f"  Total links:  {g.link_count()}")
    print(f"\n  Nodes by depth:")
    for depth in sorted(depth_counts):
        label = {0: "ROOT", 1: "Capabilities", 2: "Sub-capabilities"}.get(depth, f"Level {depth}")
        print(f"    Depth {depth} ({label}): {depth_counts[depth]}")

    # Count epistemic states
    print(f"\n  Epistemic states:")
    for node in g.iter_nodes():
        if node.epistemic_state:
            tag = node.epistemic_state.split("—")[0].strip() if "—" in node.epistemic_state else node.epistemic_state
            print(f"    {node.uid:<8} {tag}")

    # Count constraints
    total_constraints = sum(len(n.constraints) for n in g.iter_nodes())
    print(f"\n  Total constraints across all nodes: {total_constraints}")


# ================================================================== #
#  Main                                                               #
# ================================================================== #

def main() -> None:
    """Run all demonstrations."""
    print(SEPARATOR)
    print("  IntentGraph End-to-End Demo")
    print("  Target: SQL Function Sync Validator")
    print(SEPARATOR)

    # 1. Build
    g = build_graph()
    print_summary(g)

    # 2. Views
    demo_views(g)

    # 3. Lens navigation
    demo_lens_navigation(g)

    # 4. Projection
    demo_projection(g)

    # 5. Agent Text Round-Trip
    demo_agent_text_roundtrip(g)

    # 6. Persistence
    demo_persistence(g)

    section("DONE")
    print("\n  All demonstrations completed successfully.")
    print(f"  The IntentGraph library works end-to-end on an illustrative codebase.\n")


if __name__ == "__main__":
    main()
