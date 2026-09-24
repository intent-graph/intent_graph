"""Property-based tests using Hypothesis.

- Random trees: verify T1 invariants.
- Random views: verify projection endpoints stay inside the view.
- Random serialization: verify round-trip identity.
- Random projections: verify all projected endpoints are in the view.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from intentgraph.models.view import View
from intentgraph.models.graph import IntentGraph
from intentgraph.ops.projection import project_links, rep
from intentgraph.serial.json_yaml import dict_to_graph, graph_to_dict


# ================================================================== #
#  Strategies                                                         #
# ================================================================== #


@st.composite
def random_tree(draw, max_children: int = 4, max_depth: int = 4) -> IntentGraph:
    """Generate a random IntentGraph tree.

    Strategy: start with ROOT, then for each node, decide how many children
    (0 to max_children) up to max_depth.
    """
    g = IntentGraph(meta={"name": "random"})
    g.add_node("ROOT", "Root", "Random root")

    counter = [0]
    level = ["ROOT"]

    for _depth in range(max_depth):
        next_level = []
        for parent_uid in level:
            n_children = draw(st.integers(min_value=0, max_value=max_children))
            for _ in range(n_children):
                counter[0] += 1
                # Generate hierarchical UIDs: "N1", "N2", ... under ROOT; "{parent}.{num}" under deeper nodes
                if parent_uid == "ROOT":
                    uid = f"N{counter[0]}"
                else:
                    uid = f"{parent_uid}.{counter[0]}"
                g.add_node_under(uid, f"Node {counter[0]}", f"Intent {counter[0]}", parent_uid=parent_uid)
                next_level.append(uid)
        level = next_level
        if not level:
            break

    return g


@st.composite
def tree_with_links(draw, max_children: int = 3, max_depth: int = 3) -> IntentGraph:
    """Generate a random tree with some random intentlinks."""
    g = draw(random_tree(max_children=max_children, max_depth=max_depth))

    if g.node_count() < 2:
        return g

    node_uids = list(g.nodes.keys())
    n_links = draw(st.integers(min_value=0, max_value=min(len(node_uids), 5)))

    for i in range(n_links):
        src = draw(st.sampled_from(node_uids))
        dst = draw(st.sampled_from(node_uids))
        if src != dst:
            tag = f"rnd{i}"
            try:
                g.add_link(src, dst, f"Random link {i}", tag=tag)
            except Exception:
                pass  # Duplicate or other issue — skip

    return g


# ================================================================== #
#  T1: Tree invariants on random trees                                #
# ================================================================== #


class TestRandomTreeInvariants:

    @given(g=random_tree())
    @settings(max_examples=50)
    def test_exactly_one_root(self, g: IntentGraph):
        roots = g.roots()
        assert len(roots) == 1
        assert roots[0].uid == "ROOT"

    @given(g=random_tree())
    @settings(max_examples=50)
    def test_every_non_root_has_parent(self, g: IntentGraph):
        for node in g.iter_nodes():
            if node.uid == "ROOT":
                assert node.parent_uid is None
            else:
                assert node.parent_uid is not None

    @given(g=random_tree())
    @settings(max_examples=50)
    def test_parent_child_consistency(self, g: IntentGraph):
        for node in g.iter_nodes():
            for child_uid in node.children_uids:
                child = g.get_node(child_uid)
                assert child.parent_uid == node.uid


# ================================================================== #
#  Serialization round-trip on random graphs                          #
# ================================================================== #


class TestRandomSerialization:

    @given(g=tree_with_links())
    @settings(max_examples=50)
    def test_dict_round_trip(self, g: IntentGraph):
        d = graph_to_dict(g)
        g2 = dict_to_graph(d)

        assert g2.node_count() == g.node_count()
        assert g2.link_count() == g.link_count()

        for node in g.iter_nodes():
            node2 = g2.get_node(node.uid)
            assert node2.name == node.name
            assert node2.intent == node.intent

    @given(g=tree_with_links())
    @settings(max_examples=50)
    def test_treearcs_round_trip(self, g: IntentGraph):
        """Treearc adjacency is rebuilt correctly from serialized form."""
        d = graph_to_dict(g)
        g2 = dict_to_graph(d)

        for node in g.iter_nodes():
            node2 = g2.get_node(node.uid)
            assert node2.parent_uid == node.parent_uid
            assert sorted(node2.children_uids) == sorted(node.children_uids)


# ================================================================== #
#  Projection: all projected endpoints in view                        #
# ================================================================== #


class TestRandomProjection:

    @given(g=tree_with_links(max_children=3, max_depth=3))
    @settings(max_examples=50)
    def test_projected_endpoints_in_view(self, g: IntentGraph):
        """All projected link endpoints must be in the view."""
        if g.node_count() < 2:
            return

        f = View.from_depth(g, "test", depth=1)
        projected = project_links(f)

        for pl in projected:
            assert pl.display_src in f, f"Projected src '{pl.display_src}' not in view"
            assert pl.display_dst in f, f"Projected dst '{pl.display_dst}' not in view"

    @given(g=tree_with_links(max_children=3, max_depth=3))
    @settings(max_examples=50)
    def test_no_self_loops_in_projection(self, g: IntentGraph):
        if g.node_count() < 2:
            return

        f = View.from_depth(g, "test", depth=1)
        projected = project_links(f)

        for pl in projected:
            assert pl.display_src != pl.display_dst
