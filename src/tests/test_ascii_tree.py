"""Tests for ASCII tree visualization."""

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.serial.ascii_tree import render_ascii_tree, render_ascii_tree_boxed


def test_simple_tree():
    """Test basic tree rendering."""
    g = IntentGraph()
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("A", "Module A", "First module", parent_uid="ROOT")
    g.add_node_under("B", "Module B", "Second module", parent_uid="ROOT")
    g.add_node_under("A.1", "Component A1", "Subcomponent of A", parent_uid="A")
    g.add_node_under("A.2", "Component A2", "Another subcomponent", parent_uid="A")

    tree = render_ascii_tree(g)

    # Basic structure checks
    assert "ROOT: Root" in tree
    assert "A: Module A" in tree
    assert "B: Module B" in tree
    assert "A.1: Component A1" in tree
    assert "A.2: Component A2" in tree

    # Tree structure symbols
    assert "├──" in tree or "└──" in tree


def test_tree_with_intent():
    """Test tree rendering with intent descriptions."""
    g = IntentGraph()
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("A", "Module A", "This is a longer intent description that should appear below the node", parent_uid="ROOT")

    tree = render_ascii_tree(g, show_intent=True)

    assert "ROOT: Root" in tree
    assert "System root" in tree
    assert "Module A" in tree
    assert "longer intent description" in tree


def test_tree_with_custom_root():
    """Test tree rendering starting from a non-root node."""
    g = IntentGraph()
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("A", "Module A", "First module", parent_uid="ROOT")
    g.add_node_under("B", "Module B", "Second module", parent_uid="ROOT")
    g.add_node_under("A.1", "Component A1", "Subcomponent of A", parent_uid="A")

    tree = render_ascii_tree(g, root_uid="A")

    # Should only show A and its children
    assert "A: Module A" in tree
    assert "A.1: Component A1" in tree
    assert "ROOT: Root" not in tree
    assert "B: Module B" not in tree


def test_empty_graph():
    """Test rendering an empty graph."""
    g = IntentGraph()
    tree = render_ascii_tree(g)
    assert tree == "(empty graph)"


def test_multiple_roots():
    """Test rendering a graph with multiple root nodes."""
    g = IntentGraph()
    g.add_node("ROOT", "Root", "First root")
    g.add_node("EXTRA", "Extra Root", "Second root")
    g.add_node_under("A", "Child A", "Child of ROOT", parent_uid="ROOT")

    tree = render_ascii_tree(g)

    # Should render both roots
    assert "ROOT: Root" in tree
    assert "EXTRA: Extra Root" in tree
    assert "A: Child A" in tree


def test_text_wrapping():
    """Test that long intent text wraps properly."""
    g = IntentGraph()
    very_long_intent = "This is a very long intent description that should be wrapped when rendered in the tree view " * 3
    g.add_node("ROOT", "Root", very_long_intent)

    tree = render_ascii_tree(g, show_intent=True, max_width=80)

    # Check that wrapping occurred (multiple lines for intent)
    lines = tree.split("\n")
    # Should have more than 2 lines (node + at least one wrapped intent line)
    assert len([l for l in lines if "very long intent" in l]) > 1


def test_boxed_style():
    """Test boxed rendering (currently falls back to simple)."""
    g = IntentGraph()
    g.add_node("ROOT", "Root", "System root")
    g.add_node_under("A", "Module A", "First module", parent_uid="ROOT")

    tree = render_ascii_tree_boxed(g)

    # Currently falls back to simple rendering
    assert "ROOT: Root" in tree
    assert "A: Module A" in tree
