"""Tests for UID format validation conventions.

Validates that UIDs follow the IntentGraph conventions:
- ROOT: exactly "ROOT" with no parent
- L1 (parent=ROOT): single segment — one uppercase keyword with optional underscores
  (preferred) or one number
  e.g. ERRORS, API, DISCOVER, LEXER_TOKENS, 1, 2
  Multi-segment compound names (e.g. ERROR.HANDLER) are NOT valid at L1.
  Leading underscores are NOT allowed (e.g. _BAD is rejected).
- L2: parent prefix + dot + either a single uppercase keyword (with optional underscores)
  or a number
  e.g. ERRORS.HANDLER, API.CLIENT, LEXER.PARSER_INTERFACE, DISCOVER.1, PARSE.2
- L3+: parent prefix + dot + sequential numbers only
- ProjectionIG L1: PIG-{SEMANTIC}-{COMPONENT} pattern
"""

import pytest

from intentgraph.errors import InvalidUIDError
from intentgraph.models.graph import IntentGraph


class TestRootNodeValidation:
    """Test validation of ROOT node UID."""

    def test_root_node_valid(self):
        """ROOT is valid as the root node."""
        ig = IntentGraph()
        node = ig.add_node("ROOT", "System Root", "Top-level system goal")
        assert node.uid == "ROOT"
        assert node.parent_uid is None

    def test_root_cannot_have_parent(self):
        """ROOT cannot be attached as a child."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node("INVALID_ROOT", "Another Root", "Should fail")

        with pytest.raises(InvalidUIDError, match="Only the root node can have UID 'ROOT'"):
            ig.attach("INVALID_ROOT", "ROOT")

    def test_non_root_must_have_parent_when_attaching(self):
        """Non-ROOT nodes must have a parent when being attached."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        orphan = ig.add_node("DISCOVER", "Discovery", "Find data sources")

        # Orphan node exists but has no parent yet - this is valid
        assert orphan.parent_uid is None

        # Now attach it - this should work
        ig.attach("ROOT", "DISCOVER")
        assert orphan.parent_uid == "ROOT"


class TestL1NodeValidation:
    """Test validation of L1 nodes (parent=ROOT)."""

    def test_l1_simple_semantic_valid(self):
        """Simple single-keyword L1 UIDs are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        valid_uids = ["DISCOVER", "PARSE", "VALIDATE", "REPORT", "ORCHESTRATE", "API", "V2"]
        for uid in valid_uids:
            node = ig.add_node_under(uid, f"{uid} Phase", "Some intent", "ROOT")
            assert node.uid == uid
            assert node.parent_uid == "ROOT"

    def test_l1_numeric_valid(self):
        """Numeric L1 UIDs are allowed (though keyword is preferred)."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        for uid in ["1", "2", "99"]:
            node = ig.add_node_under(uid, f"Phase {uid}", "Some intent", "ROOT")
            assert node.uid == uid
            assert node.parent_uid == "ROOT"

    def test_l1_compound_dot_invalid(self):
        """Compound dot-notation L1 UIDs are NOT valid — dots are reserved for L2+."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        invalid_uids = [
            "DISCOVER.DB",     # compound — belongs at L2
            "ERROR.HANDLER",   # compound — belongs at L2
            "API.CLIENT",      # compound — belongs at L2
            "PARSE.SQL.1",     # multi-segment
        ]
        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(
                InvalidUIDError,
                match="L1 node UID must be a single segment"
            ):
                ig.attach("ROOT", uid)

    def test_l1_underscore_valid(self):
        """L1 UIDs may contain underscores (policy: underscores permitted in keyword segments)."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        valid_uids = ["ERROR_HANDLER", "API_CLIENT", "DB_CACHE", "LEXER_TOKENS"]
        for uid in valid_uids:
            node = ig.add_node_under(uid, f"{uid} Node", "Some intent", "ROOT")
            assert node.uid == uid
            assert node.parent_uid == "ROOT"

    def test_l1_leading_underscore_invalid(self):
        """L1 UIDs must start with an uppercase letter — leading underscore is rejected."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        invalid_uids = ["_BAD", "_LEAD_UNDERSCORE", "_API"]
        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(InvalidUIDError):
                ig.attach("ROOT", uid)

    def test_l1_lowercase_invalid_with_underscore(self):
        """L1 UIDs with lowercase and underscores are still rejected."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        invalid_uids = ["lower_case", "mixed_Case"]
        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(InvalidUIDError):
                ig.attach("ROOT", uid)

    def test_l1_lowercase_invalid(self):
        """L1 UIDs must be uppercase."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        invalid_uids = ["discover", "Parse", "api"]

        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(
                InvalidUIDError,
                match="L1 node UID must be an uppercase keyword with optional underscores"
            ):
                ig.attach("ROOT", uid)

    def test_l1_single_letter_valid(self):
        """Single-letter L1 UIDs are technically valid (though discouraged)."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        node = ig.add_node_under("D", "Discovery (discouraged)", "Some intent", "ROOT")
        assert node.uid == "D"


class TestL2PlusNodeValidation:
    """Test validation of L2+ nodes (children of L1 or deeper)."""

    def test_l2_numeric_suffix_valid(self):
        """L2 nodes with numeric suffix are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("DISCOVER", "Discovery", "Find sources", "ROOT")

        valid_uids = ["DISCOVER.1", "DISCOVER.2", "DISCOVER.99"]
        for uid in valid_uids:
            node = ig.add_node_under(uid, f"{uid} Child", "Some intent", "DISCOVER")
            assert node.uid == uid
            assert node.parent_uid == "DISCOVER"

    def test_l2_semantic_under_simple_l1_valid(self):
        """L2 semantic keyword nodes under simple L1 parents are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("DISCOVER", "Discovery", "Find sources", "ROOT")

        node = ig.add_node_under("DISCOVER.DB", "DB Discovery", "Find databases", "DISCOVER")
        assert node.uid == "DISCOVER.DB"
        assert node.parent_uid == "DISCOVER"

        # L3 under semantic L2
        node2 = ig.add_node_under("DISCOVER.DB.1", "First DB", "Some intent", "DISCOVER.DB")
        assert node2.uid == "DISCOVER.DB.1"
        assert node2.parent_uid == "DISCOVER.DB"

    def test_l3_multi_level_numeric_valid(self):
        """L3+ nodes with multi-level numeric suffixes are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("PARSE", "Parser", "Parse data", "ROOT")
        ig.add_node_under("PARSE.1", "SQL Parser", "Parse SQL", "PARSE")

        valid_uids = [
            "PARSE.1.1",
            "PARSE.1.2",
            "PARSE.1.1.1",
            "PARSE.1.1.2.3",
        ]

        parent_uid = "PARSE.1"
        for uid in valid_uids:
            parts = uid.split(".")
            # Find correct parent
            if len(parts) == 3:
                parent_uid = "PARSE.1"
            elif len(parts) == 4:
                parent_uid = "PARSE.1.1"
            elif len(parts) == 5:
                parent_uid = "PARSE.1.1.2"

            # Create intermediate nodes if needed
            if parent_uid not in ig.nodes:
                intermediate_parts = parent_uid.split(".")
                intermediate_parent = ".".join(intermediate_parts[:-1])
                ig.add_node_under(
                    parent_uid,
                    f"{parent_uid} Node",
                    "Intermediate",
                    intermediate_parent
                )

            node = ig.add_node_under(uid, f"{uid} Child", "Some intent", parent_uid)
            assert node.uid == uid

    def test_l2_semantic_suffix_valid(self):
        """L2 nodes can have a single uppercase keyword suffix, including with underscores."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("ERRORS", "Errors", "Error handling", "ROOT")
        ig.add_node_under("API", "API", "API layer", "ROOT")
        ig.add_node_under("DISCOVER", "Discovery", "Find sources", "ROOT")
        ig.add_node_under("LEXER", "Lexer", "Tokenize input", "ROOT")

        valid_uids = [
            ("ERRORS", "ERRORS.HANDLER"),
            ("API", "API.CLIENT"),
            ("DISCOVER", "DISCOVER.DB"),
            ("DISCOVER", "DISCOVER.SQL"),
            # New: underscore-containing semantic suffixes (policy: underscores permitted)
            ("LEXER", "LEXER.PARSER_INTERFACE"),
            ("ERRORS", "ERRORS.ERR_HANDLER"),
        ]

        for parent, uid in valid_uids:
            node = ig.add_node_under(uid, f"{uid} Sub-capability", "Some intent", parent)
            assert node.uid == uid
            assert node.parent_uid == parent

    def test_l2_semantic_suffix_with_underscore_children_must_be_numeric(self):
        """Children of a semantic L2 node must use numeric suffixes."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("ERRORS", "Errors", "Error handling", "ROOT")
        ig.add_node_under("ERRORS.HANDLER", "Handler", "Handle errors", "ERRORS")

        node = ig.add_node_under(
            "ERRORS.HANDLER.1", "First handler", "Some intent", "ERRORS.HANDLER"
        )
        assert node.uid == "ERRORS.HANDLER.1"

        invalid = ig.add_node("ERRORS.HANDLER.RETRY", "Bad UID", "Some intent")
        with pytest.raises(
            InvalidUIDError,
            match="suffix must be numeric"
        ):
            ig.attach("ERRORS.HANDLER", "ERRORS.HANDLER.RETRY")

    def test_l2_semantic_suffix_invalid_forms(self):
        """Malformed L2 suffixes are rejected."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("DISCOVER", "Discovery", "Find sources", "ROOT")

        invalid_uids = [
            "DISCOVER.foo",    # Lowercase
            "DISCOVER.1EXTRA", # Mixed digit-start
            "DISCOVER.",       # Empty suffix
        ]

        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(InvalidUIDError):
                ig.attach("DISCOVER", uid)

    def test_l2_missing_parent_prefix_invalid(self):
        """L2+ nodes must start with parent prefix."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("DISCOVER", "Discovery", "Find sources", "ROOT")

        # Try to attach a node with wrong prefix
        node = ig.add_node("PARSE.1", "Wrong Prefix", "Some intent")
        with pytest.raises(
            InvalidUIDError,
            match="Child node UID must start with parent prefix"
        ):
            ig.attach("DISCOVER", "PARSE.1")


class TestProjectionIGValidation:
    """Test validation of ProjectionIG L1 nodes (PIG-* pattern)."""

    def test_pig_l1_valid(self):
        """ProjectionIG L1 nodes with PIG- prefix are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        valid_uids = [
            "PIG-PY-TYPES",
            "PIG-DOC-STYLE",
            "PIG-PY-ERROR.HANDLER",
            "PIG-TS-API_CLIENT",
        ]

        for uid in valid_uids:
            node = ig.add_node_under(uid, f"{uid} Projection", "Some intent", "ROOT")
            assert node.uid == uid
            assert node.parent_uid == "ROOT"

    def test_pig_l1_invalid_format(self):
        """ProjectionIG L1 nodes must follow PIG-{SEMANTIC}-{COMPONENT} pattern."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        invalid_uids = [
            "PIG-TYPES",  # Missing second segment
            "PIG-py-types",  # Lowercase
            "PIG-1-TYPES",  # Numeric semantic
            "PIG-PY-1",  # Numeric component
        ]

        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(
                InvalidUIDError,
                match=r"ProjectionIG L1 node UID must follow pattern PIG-\{SEMANTIC\}-\{COMPONENT\}"
            ):
                ig.attach("ROOT", uid)

    def test_pig_l2_children_valid(self):
        """ProjectionIG L1 nodes can have numeric children like regular L1 nodes."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("PIG-PY-TYPES", "Python Types", "Type constraints", "ROOT")

        node = ig.add_node_under(
            "PIG-PY-TYPES.1",
            "Type Constraint 1",
            "Some specific type rule",
            "PIG-PY-TYPES"
        )
        assert node.uid == "PIG-PY-TYPES.1"
        assert node.parent_uid == "PIG-PY-TYPES"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_keyword_l1_valid(self):
        """Long single-word L1 UIDs are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        node = ig.add_node_under("CONNECTIONPOOLMANAGEMENT", "Long UID", "Some intent", "ROOT")
        assert node.uid == "CONNECTIONPOOLMANAGEMENT"

    def test_compound_dot_l1_invalid(self):
        """Compound dot L1 UIDs (old style) are explicitly rejected."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        node = ig.add_node("ERROR.HANDLER.DATABASE.CONNECTION", "Long compound", "Some intent")
        with pytest.raises(InvalidUIDError, match="single segment"):
            ig.attach("ROOT", "ERROR.HANDLER.DATABASE.CONNECTION")

    def test_deep_numeric_hierarchy(self):
        """Deep numeric hierarchies are valid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")
        ig.add_node_under("PARSE", "Parser", "Parse data", "ROOT")

        # Build a deep hierarchy
        uids = [
            "PARSE.1",
            "PARSE.1.1",
            "PARSE.1.1.1",
            "PARSE.1.1.1.1",
            "PARSE.1.1.1.1.1",
        ]

        parent = "PARSE"
        for uid in uids:
            node = ig.add_node_under(uid, f"{uid} Level", "Some intent", parent)
            assert node.uid == uid
            parent = uid

    def test_special_characters_invalid(self):
        """L1 UIDs with special characters (except dots/underscores) are invalid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        invalid_uids = [
            "DISCOVER-DB",  # Hyphen not allowed
            "PARSE@SQL",  # @ not allowed
            "VALIDATE#1",  # # not allowed
            "REPORT$",  # $ not allowed
        ]

        for uid in invalid_uids:
            node = ig.add_node(uid, f"{uid} Invalid", "Some intent")
            with pytest.raises(InvalidUIDError):
                ig.attach("ROOT", uid)

    def test_empty_segments_invalid(self):
        """UIDs with empty segments (e.g., DISCOVER..DB) are invalid."""
        ig = IntentGraph()
        ig.add_node("ROOT", "System Root", "Top-level goal")

        # Python string won't match the regex due to consecutive dots
        node = ig.add_node("DISCOVER..DB", "Empty Segment", "Some intent")
        with pytest.raises(InvalidUIDError):
            ig.attach("ROOT", "DISCOVER..DB")
