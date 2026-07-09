"""
Unit tests for frr2oscal module.

Tests cover pure helper functions (no I/O), the class-variant dict builder,
and integration-level control creation using a real Catalog object.
"""

import json
import sys
import os

import pytest

# Path setup: resolve the oscal library and the module under test.
_tests_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root  = os.path.dirname(_tests_dir)
sys.path.insert(0, os.path.join(_repo_root, "src"))
sys.path.insert(0, os.path.join(_repo_root, "..", "class"))

import frr2oscal
from frr2oscal import (
    FRR_NS,
    _append_artifact_parts,
    _append_extra_parts,
    _assessment_method_part,
    _build_class_control_dict,
    _date_to_datetime,
    _guidance_part,
    _notes_text,
    _track_unhandled,
    _updated_props,
)
from oscal import Catalog


# ── Helpers ──────────────────────────────────────────────────────────────────

def _catalog_with_group(group_id: str = "grp") -> Catalog:
    """Return a minimal catalog with one root group ready for control insertion."""
    cat = Catalog.new(title="Test Catalog", version="0.1")
    cat.create_control_group(parent_id="[root]", id=group_id, title="Test Group")
    return cat


def _find_control(cat: Catalog, ctrl_id: str) -> dict:
    """Return the first control in the catalog JSON whose id matches ctrl_id."""
    data = json.loads(cat.dumps("json"))
    for group in data.get("catalog", {}).get("groups", []):
        for ctrl in group.get("controls", []):
            if ctrl.get("id") == ctrl_id:
                return ctrl
    return {}


def _prop_value(props: list, name: str, *, ns: str = "") -> str | None:
    """Find a prop by name (and optional ns) and return its value."""
    for p in props:
        if p.get("name") == name and (not ns or p.get("ns") == ns):
            return p.get("value")
    return None


# ── _date_to_datetime ─────────────────────────────────────────────────────────

class TestDateToDatetime:
    def test_bare_date_gets_midnight_utc(self):
        assert _date_to_datetime("2025-01-15") == "2025-01-15T00:00:00Z"

    def test_datetime_string_passthrough(self):
        ts = "2025-01-15T12:30:00Z"
        assert _date_to_datetime(ts) == ts

    def test_empty_string_passthrough(self):
        assert _date_to_datetime("") == ""


# ── _notes_text ───────────────────────────────────────────────────────────────

class TestNotesText:
    def test_single_note_string(self):
        assert _notes_text({"note": "hello"}) == "hello"

    def test_notes_list_joined_with_blank_line(self):
        assert _notes_text({"notes": ["a", "b"]}) == "a\n\nb"

    def test_empty_rule_returns_empty_string(self):
        assert _notes_text({}) == ""

    def test_notes_list_takes_precedence_over_note(self):
        result = _notes_text({"notes": ["x", "y"], "note": "z"})
        assert result == "x\n\ny"


# ── _track_unhandled ──────────────────────────────────────────────────────────

class TestTrackUnhandled:
    def setup_method(self):
        frr2oscal.UNHANDLED.clear()

    def test_unknown_key_added(self):
        _track_unhandled({"foo": 1}, frozenset())
        assert "foo" in frr2oscal.UNHANDLED

    def test_handled_key_not_added(self):
        _track_unhandled({"foo": 1}, frozenset({"foo"}))
        assert frr2oscal.UNHANDLED == []

    def test_duplicate_not_inserted_twice(self):
        _track_unhandled({"foo": 1}, frozenset())
        _track_unhandled({"foo": 1}, frozenset())
        assert frr2oscal.UNHANDLED.count("foo") == 1

    def test_multiple_unknown_keys(self):
        _track_unhandled({"a": 1, "b": 2}, frozenset())
        assert "a" in frr2oscal.UNHANDLED
        assert "b" in frr2oscal.UNHANDLED


# ── _guidance_part ────────────────────────────────────────────────────────────

class TestGuidancePart:
    def test_following_information_list(self):
        part = _guidance_part("following_information", ["line one", "line two"])
        assert part["name"] == "guidance"
        assert part["class"] == "following_information"
        assert part["title"] == "Following Information"
        assert "line one" in part["prose"]
        assert "line two" in part["prose"]

    def test_following_information_items_separated_by_blank_line(self):
        part = _guidance_part("following_information", ["a", "b"])
        assert part["prose"] == "a\n\nb"

    def test_schema_name_and_url(self):
        part = _guidance_part("schema", {"name": "My Schema", "url": "https://example.com"})
        assert part["class"] == "schema"
        assert part["title"] == "Schema"
        assert "My Schema" in part["prose"]
        assert "https://example.com" in part["prose"]

    def test_examples_renders_id_tests_and_examples(self):
        ex = [{"id": "EX-1", "key_tests": ["test a"], "examples": ["ex a"]}]
        part = _guidance_part("examples", ex)
        assert part["class"] == "examples"
        assert part["title"] == "Examples"
        assert "EX-1" in part["prose"]
        assert "test a" in part["prose"]
        assert "ex a" in part["prose"]

    def test_examples_multiple_entries_separated(self):
        exs = [
            {"id": "A", "key_tests": [], "examples": []},
            {"id": "B", "key_tests": [], "examples": []},
        ]
        part = _guidance_part("examples", exs)
        assert "A" in part["prose"]
        assert "B" in part["prose"]

    def test_title_converts_underscores_to_spaces(self):
        part = _guidance_part("following_information", ["x"])
        assert "_" not in part["title"]


# ── _assessment_method_part ───────────────────────────────────────────────────

class TestAssessmentMethodPart:
    def test_name_is_assessment_method(self):
        part = _assessment_method_part(["a1"], "all")
        assert part["name"] == "assessment-method"

    def test_method_prop_is_examine(self):
        part = _assessment_method_part(["a1"], "all")
        assert _prop_value(part["props"], "method") == "EXAMINE"

    def test_path_prop_ns_and_value(self):
        part = _assessment_method_part(["a1"], "20x")
        assert _prop_value(part["props"], "path", ns=FRR_NS) == "20x"

    def test_assessment_objects_parts(self):
        part = _assessment_method_part(["art one", "art two"], "rev5")
        assert len(part["parts"]) == 2
        assert part["parts"][0]["name"] == "assessment-objects"
        assert part["parts"][0]["prose"] == "art one"

    def test_empty_artifacts_produces_empty_parts(self):
        part = _assessment_method_part([], "all")
        assert part["parts"] == []


# ── _append_artifact_parts ────────────────────────────────────────────────────

class TestAppendArtifactParts:
    def test_all_scope_only(self):
        parts: list = []
        _append_artifact_parts(parts, {"all": ["a1"]})
        assert len(parts) == 1
        assert _prop_value(parts[0]["props"], "path", ns=FRR_NS) == "all"

    def test_three_scopes_in_order(self):
        parts: list = []
        _append_artifact_parts(parts, {"all": ["a"], "20x": ["b"], "rev5": ["c"]})
        assert len(parts) == 3
        scopes = [_prop_value(p["props"], "path", ns=FRR_NS) for p in parts]
        assert scopes == ["all", "20x", "rev5"]

    def test_missing_scope_skipped(self):
        parts: list = []
        _append_artifact_parts(parts, {"20x": ["b"]})
        assert len(parts) == 1
        assert _prop_value(parts[0]["props"], "path", ns=FRR_NS) == "20x"

    def test_empty_dict_produces_no_parts(self):
        parts: list = []
        _append_artifact_parts(parts, {})
        assert parts == []


# ── _append_extra_parts ───────────────────────────────────────────────────────

class TestAppendExtraParts:
    def test_corrective_actions_becomes_remediation(self):
        parts: list = []
        _append_extra_parts(parts, {"corrective_actions": ["Fix this", "Do that"]})
        assert len(parts) == 1
        assert parts[0]["name"] == "remediation"
        assert parts[0]["ns"] == FRR_NS
        assert "Fix this" in parts[0]["prose"]
        assert "Do that" in parts[0]["prose"]

    def test_corrective_actions_items_joined(self):
        parts: list = []
        _append_extra_parts(parts, {"corrective_actions": ["a", "b"]})
        assert parts[0]["prose"] == "a\n\nb"

    def test_following_information_guidance(self):
        parts: list = []
        _append_extra_parts(parts, {"following_information": ["info one"]})
        assert len(parts) == 1
        assert parts[0]["class"] == "following_information"

    def test_schema_guidance(self):
        parts: list = []
        _append_extra_parts(parts, {"schema": {"name": "S", "url": "http://s"}})
        assert len(parts) == 1
        assert parts[0]["class"] == "schema"

    def test_examples_guidance(self):
        parts: list = []
        _append_extra_parts(parts, {"examples": [{"id": "E1", "key_tests": [], "examples": []}]})
        assert len(parts) == 1
        assert parts[0]["class"] == "examples"

    def test_order_remediation_then_guidance_fields(self):
        parts: list = []
        _append_extra_parts(parts, {
            "corrective_actions": ["fix"],
            "following_information": ["info"],
        })
        assert parts[0]["name"] == "remediation"
        assert parts[1]["class"] == "following_information"

    def test_empty_rule_produces_no_parts(self):
        parts: list = []
        _append_extra_parts(parts, {})
        assert parts == []


# ── _updated_props ────────────────────────────────────────────────────────────

class TestUpdatedProps:
    def test_single_entry(self):
        props = _updated_props({"updated": [{"date": "2025-01-01", "comment": "Initial"}]})
        assert len(props) == 1
        assert props[0]["name"] == "updated"
        assert props[0]["ns"] == FRR_NS
        assert props[0]["value"] == "2025-01-01T00:00:00Z"
        assert props[0]["remarks"] == "Initial"

    def test_multiple_entries(self):
        props = _updated_props({"updated": [
            {"date": "2025-01-01", "comment": "v1"},
            {"date": "2025-06-01", "comment": "v2"},
        ]})
        assert len(props) == 2

    def test_no_updated_key(self):
        assert _updated_props({}) == []

    def test_empty_updated_list(self):
        assert _updated_props({"updated": []}) == []


# ── _build_class_control_dict ─────────────────────────────────────────────────

class TestBuildClassControlDict:
    def test_id_and_title(self):
        ctrl = _build_class_control_dict("RULE-a", {}, "Class A")
        assert ctrl["id"] == "RULE-a"
        assert ctrl["title"] == "Class A"

    def test_label_prop_present(self):
        ctrl = _build_class_control_dict("RULE-a", {}, "Class A")
        assert _prop_value(ctrl["props"], "label") == "Class A"

    def test_path_prop_default_all(self):
        ctrl = _build_class_control_dict("RULE-a", {}, "Class A")
        assert _prop_value(ctrl["props"], "path", ns=FRR_NS) == "all"

    def test_path_prop_custom(self):
        ctrl = _build_class_control_dict("RULE-a", {}, "Class A", path="20x")
        assert _prop_value(ctrl["props"], "path", ns=FRR_NS) == "20x"

    def test_force_prop(self):
        ctrl = _build_class_control_dict("RULE-a", {"force": "MUST"}, "Class A")
        assert _prop_value(ctrl["props"], "force", ns=FRR_NS) == "MUST"

    def test_statement_part(self):
        ctrl = _build_class_control_dict("RULE-a", {"statement": "Do this."}, "Class A")
        smt = next((p for p in ctrl["parts"] if p["name"] == "statement"), None)
        assert smt is not None
        assert smt["prose"] == "Do this."
        assert smt["id"] == "RULE-a_smt"

    def test_notes_guidance_part(self):
        ctrl = _build_class_control_dict("RULE-a", {"note": "Be careful."}, "Class A")
        guidance = next((p for p in ctrl["parts"] if p["name"] == "guidance"), None)
        assert guidance is not None
        assert guidance["title"] == "Notes"
        assert "Be careful." in guidance["prose"]

    def test_artifacts_multiple_scopes(self):
        data = {"artifacts": {"all": ["a-all"], "20x": ["a-20x"]}}
        ctrl = _build_class_control_dict("RULE-a", data, "Class A")
        am_parts = [p for p in ctrl["parts"] if p["name"] == "assessment-method"]
        assert len(am_parts) == 2

    def test_following_information(self):
        data = {"following_information": ["info line"]}
        ctrl = _build_class_control_dict("RULE-a", data, "Class A")
        fi = next((p for p in ctrl["parts"] if p.get("class") == "following_information"), None)
        assert fi is not None

    def test_no_parts_key_when_empty(self):
        ctrl = _build_class_control_dict("RULE-a", {}, "Class A")
        assert "parts" not in ctrl


# ── Catalog-integrated: _build_frr_simple_control ────────────────────────────

class TestBuildFrrSimpleControl:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()

    def test_path_prop_value_and_ns(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "statement": "S.", "force": "MUST"}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-001", rule, path="20x")
        ctrl = _find_control(cat, "R-001")
        assert _prop_value(ctrl.get("props", []), "path", ns=FRR_NS) == "20x"

    def test_default_path_is_all(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "statement": "S.", "force": "MUST"}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-002", rule)
        ctrl = _find_control(cat, "R-002")
        assert _prop_value(ctrl.get("props", []), "path", ns=FRR_NS) == "all"

    def test_corrective_actions_remediation_part(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule", "statement": "S.", "force": "MUST",
            "corrective_actions": ["Fix A", "Fix B"],
        }
        frr2oscal._build_frr_simple_control(cat, "grp", "R-003", rule)
        ctrl = _find_control(cat, "R-003")
        rem = next((p for p in ctrl.get("parts", []) if p["name"] == "remediation"), None)
        assert rem is not None
        assert rem["ns"] == FRR_NS
        assert "Fix A" in rem["prose"]

    def test_updated_props_appended(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule", "statement": "S.", "force": "MUST",
            "updated": [{"date": "2025-03-01", "comment": "rev"}],
        }
        frr2oscal._build_frr_simple_control(cat, "grp", "R-004", rule)
        ctrl = _find_control(cat, "R-004")
        upd = [p for p in ctrl.get("props", []) if p["name"] == "updated"]
        assert len(upd) == 1
        assert upd[0]["value"] == "2025-03-01T00:00:00Z"
        assert upd[0]["remarks"] == "rev"

    def test_artifacts_all_three_scopes(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule", "statement": "S.", "force": "MUST",
            "artifacts": {"all": ["a-all"], "20x": ["a-20x"], "rev5": ["a-rev5"]},
        }
        frr2oscal._build_frr_simple_control(cat, "grp", "R-005", rule)
        ctrl = _find_control(cat, "R-005")
        am = [p for p in ctrl.get("parts", []) if p["name"] == "assessment-method"]
        assert len(am) == 3
        paths = [_prop_value(p["props"], "path", ns=FRR_NS) for p in am]
        assert sorted(paths) == ["20x", "all", "rev5"]

    def test_stats_incremented(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "statement": "S.", "force": "MUST"}
        before = frr2oscal._STATS["controls"]
        frr2oscal._build_frr_simple_control(cat, "grp", "R-006", rule)
        assert frr2oscal._STATS["controls"] == before + 1


# ── Catalog-integrated: _build_frr_subset + _build_frr_ruleset ───────────────

class TestBuildFrrSubset:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()

    def test_all_scope_id_has_no_path_prefix(self):
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        subset_val = {
            "TST-001": {"name": "R", "statement": "S.", "force": "MUST"},
        }
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB", subset_val, path="all")
        data = json.loads(cat.dumps("json"))
        groups = data["catalog"]["groups"][0].get("groups", [])
        assert any(g["id"] == "FRR-TST-SUB" for g in groups)

    def test_20x_scope_id_has_path_prefix(self):
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        subset_val = {
            "TST-001": {"name": "R", "statement": "S.", "force": "MUST"},
        }
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB", subset_val, path="20x")
        data = json.loads(cat.dumps("json"))
        groups = data["catalog"]["groups"][0].get("groups", [])
        assert any(g["id"] == "FRR-TST-20x-SUB" for g in groups)


class TestBuildFrrRuleset:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        frr2oscal._VERBOSE = False

    def test_processes_all_three_scopes(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "purpose": ""},
            "data": {
                "all":  {"GRP": {"TST-ALL":  {"name": "All Rule",  "statement": "S.", "force": "MUST"}}},
                "20x":  {"GRP": {"TST-20X":  {"name": "20x Rule",  "statement": "S.", "force": "MUST"}}},
                "rev5": {"GRP": {"TST-REV5": {"name": "Rev5 Rule", "statement": "S.", "force": "MUST"}}},
            },
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        # Collect all control IDs recursively
        ctrl_ids = set()
        for top_group in data["catalog"]["groups"]:
            for sub_group in top_group.get("groups", []):
                for ctrl in sub_group.get("controls", []):
                    ctrl_ids.add(ctrl["id"])
        assert "TST-ALL" in ctrl_ids
        assert "TST-20X" in ctrl_ids
        assert "TST-REV5" in ctrl_ids

    def test_scope_conflict_produces_unique_group_ids(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "purpose": ""},
            "data": {
                "all":  {"SAME": {"R1": {"name": "R1", "statement": "S.", "force": "MUST"}}},
                "20x":  {"SAME": {"R2": {"name": "R2", "statement": "S.", "force": "MUST"}}},
            },
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        group_ids = [g["id"] for g in data["catalog"]["groups"][0].get("groups", [])]
        assert "FRR-TST-SAME" in group_ids
        assert "FRR-TST-20x-SAME" in group_ids

    def test_controls_inherit_scope_path_prop(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "purpose": ""},
            "data": {
                "20x": {"GRP": {"R-20X": {"name": "Rule", "statement": "S.", "force": "MUST"}}},
            },
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        ctrl = None
        for top_group in data["catalog"]["groups"]:
            for sub_group in top_group.get("groups", []):
                for c in sub_group.get("controls", []):
                    if c["id"] == "R-20X":
                        ctrl = c
        assert ctrl is not None
        assert _prop_value(ctrl.get("props", []), "path", ns=FRR_NS) == "20x"
