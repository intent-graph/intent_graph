"""Tests for evaluation harness."""

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.view import View
from intentgraph.serial.agent_text import view_to_text

from ig_agents.eval.harness import eval_extractor_output, eval_critic_output


class TestEvalExtractorOutput:

    def test_valid_output_passes(self, sample_graph: IntentGraph):
        """Valid YAML that creates a new node should parse and pass."""
        output = yaml.dump({
            "view": {"name": "test"},
            "nodes": [
                {
                    "uid": "NEW.1",
                    "name": "New Component",
                    "intent": "Does something new",
                    "epistemic_state": "undecided",
                },
            ],
            "intentlinks": [],
        }, sort_keys=False)

        result = eval_extractor_output(sample_graph, output, test_case="new_node")
        assert result.scores["parse_success"] == 1.0
        assert result.scores["edit_count"] == 1.0
        assert result.scores["has_epistemic_states"] == 1.0
        assert result.passed is True

    def test_invalid_yaml_fails(self, sample_graph: IntentGraph):
        result = eval_extractor_output(sample_graph, "{{not yaml", test_case="bad_yaml")
        assert result.scores["parse_success"] == 0.0
        assert result.passed is False

    def test_no_changes_still_passes(self, sample_graph: IntentGraph):
        """Parsing the graph's own view should produce zero edits — still valid."""
        f = View.from_node_set(sample_graph, "test", {"E", "T", "L"})
        text = view_to_text(f)
        result = eval_extractor_output(sample_graph, text, test_case="no_change")
        assert result.scores["parse_success"] == 1.0
        assert result.scores["edit_count"] == 0.0
        assert result.passed is True

    def test_new_node_without_epistemic(self, sample_graph: IntentGraph):
        """New node without epistemic_state should score lower on that metric."""
        output = yaml.dump({
            "view": {"name": "test"},
            "nodes": [
                {"uid": "X.1", "name": "X", "intent": "Does X"},
            ],
            "intentlinks": [],
        }, sort_keys=False)

        result = eval_extractor_output(sample_graph, output, test_case="no_ep")
        assert result.scores["has_epistemic_states"] == 0.0


class TestEvalCriticOutput:

    def test_well_structured_issues(self):
        output = yaml.dump({
            "issues": [
                {
                    "type": "intent_quality",
                    "node": "E.1",
                    "severity": "major",
                    "description": "Intent is HOW not WHY",
                    "suggestion": "Rewrite as purpose",
                },
                {
                    "type": "missing_constraint",
                    "node": "T.2",
                    "severity": "moderate",
                    "description": "Missing uniqueness constraint",
                    "suggestion": "Add constraint",
                },
            ]
        }, sort_keys=False)

        result = eval_critic_output(output, test_case="good_critic")
        assert result.scores["parse_success"] == 1.0
        assert result.scores["issue_count"] == 2.0
        assert result.scores["has_severity"] == 1.0
        assert result.scores["has_suggestion"] == 1.0
        assert result.scores["has_node_ref"] == 1.0
        assert result.passed is True

    def test_invalid_yaml(self):
        result = eval_critic_output("{{bad", test_case="bad_yaml")
        assert result.scores["parse_success"] == 0.0
        assert result.passed is False

    def test_missing_issues_key(self):
        output = yaml.dump({"review": "looks good"})
        result = eval_critic_output(output, test_case="no_issues")
        assert result.scores["parse_success"] == 0.0

    def test_issues_without_severity(self):
        output = yaml.dump({
            "issues": [
                {"type": "vague", "description": "not great"},
            ]
        }, sort_keys=False)

        result = eval_critic_output(output, test_case="no_severity")
        assert result.scores["has_severity"] == 0.0
        assert result.scores["has_node_ref"] == 0.0
        assert result.passed is False

    def test_empty_issues_list(self):
        output = yaml.dump({"issues": []})
        result = eval_critic_output(output, test_case="empty")
        assert result.scores["parse_success"] == 1.0
        assert result.scores["issue_count"] == 0.0
        assert result.passed is True  # no issues is valid
