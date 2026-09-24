"""Evaluation harness — measure agent output quality against expected results.

Provides per-agent quality metrics and supports both automated scoring
(where possible) and structured output for human review.

Phase 2 scope: basic metrics framework. Grows with usage and data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.serial.agent_text import text_to_edits, EditOp


# ================================================================== #
#  Evaluation result                                                   #
# ================================================================== #


@dataclass
class EvalResult:
    """Result of evaluating an agent's output."""
    agent_role: str
    test_case: str
    scores: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    passed: bool = False

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        scores_str = ", ".join(f"{k}={v:.2f}" for k, v in self.scores.items())
        return f"[{status}] {self.agent_role}/{self.test_case}: {scores_str}"


# ================================================================== #
#  Extractor evaluation                                                #
# ================================================================== #


def eval_extractor_output(
    graph: IntentGraph,
    agent_output_text: str,
    *,
    test_case: str = "unnamed",
) -> EvalResult:
    """Evaluate Extractor output: are the proposed edits valid?

    Scores:
    - ``parse_success``: 1.0 if output parses, 0.0 otherwise
    - ``invariant_compliance``: fraction of edits that don't violate invariants
    - ``edit_count``: number of edits proposed (informational)
    - ``has_epistemic_states``: fraction of new nodes with epistemic_state set
    """
    result = EvalResult(agent_role="extractor", test_case=test_case)

    # Parse
    try:
        edits = text_to_edits(agent_output_text, graph)
        result.scores["parse_success"] = 1.0
    except Exception as e:
        result.scores["parse_success"] = 0.0
        result.details["parse_error"] = str(e)
        return result

    result.scores["edit_count"] = float(len(edits))

    # Try applying edits to a copy (check invariant compliance)
    from intentgraph.serial.json_yaml import graph_to_dict, dict_to_graph
    graph_copy = dict_to_graph(graph_to_dict(graph))

    valid_count = 0
    for edit in edits:
        try:
            from intentgraph.serial.agent_text import apply_edits
            apply_edits(graph_copy, [edit])
            valid_count += 1
        except Exception:
            pass

    if edits:
        result.scores["invariant_compliance"] = valid_count / len(edits)
    else:
        result.scores["invariant_compliance"] = 1.0

    # Check epistemic state coverage on new nodes
    from intentgraph.serial.agent_text import NodeCreate
    creates = [e for e in edits if isinstance(e, NodeCreate)]
    if creates:
        has_ep = sum(1 for c in creates if c.fields.get("epistemic_state"))
        result.scores["has_epistemic_states"] = has_ep / len(creates)
    else:
        result.scores["has_epistemic_states"] = 1.0

    result.passed = (
        result.scores["parse_success"] == 1.0
        and result.scores["invariant_compliance"] >= 0.8
    )

    return result


# ================================================================== #
#  Critic evaluation                                                   #
# ================================================================== #


def eval_critic_output(
    critic_output_text: str,
    *,
    test_case: str = "unnamed",
) -> EvalResult:
    """Evaluate Critic output: is the issue list well-structured?

    Scores:
    - ``parse_success``: 1.0 if output parses as YAML with 'issues' key
    - ``issue_count``: number of issues found
    - ``has_severity``: fraction of issues with a severity field
    - ``has_suggestion``: fraction of issues with a suggestion field
    - ``has_node_ref``: fraction of issues referencing a node UID
    """
    result = EvalResult(agent_role="critic", test_case=test_case)

    try:
        doc = yaml.safe_load(critic_output_text)
        if not isinstance(doc, dict) or "issues" not in doc:
            result.scores["parse_success"] = 0.0
            result.details["parse_error"] = "Expected YAML with 'issues' key"
            return result
        result.scores["parse_success"] = 1.0
    except Exception as e:
        result.scores["parse_success"] = 0.0
        result.details["parse_error"] = str(e)
        return result

    issues = doc["issues"]
    if not isinstance(issues, list):
        result.scores["parse_success"] = 0.5
        return result

    result.scores["issue_count"] = float(len(issues))

    if issues:
        result.scores["has_severity"] = sum(
            1 for i in issues if isinstance(i, dict) and "severity" in i
        ) / len(issues)
        result.scores["has_suggestion"] = sum(
            1 for i in issues if isinstance(i, dict) and "suggestion" in i
        ) / len(issues)
        result.scores["has_node_ref"] = sum(
            1 for i in issues if isinstance(i, dict) and ("node" in i or "nodes" in i)
        ) / len(issues)
    else:
        result.scores["has_severity"] = 1.0
        result.scores["has_suggestion"] = 1.0
        result.scores["has_node_ref"] = 1.0

    result.passed = (
        result.scores["parse_success"] == 1.0
        and result.scores.get("has_severity", 0) >= 0.8
        and result.scores.get("has_node_ref", 0) >= 0.8
    )

    return result
