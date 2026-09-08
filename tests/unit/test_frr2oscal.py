"""
Unit tests for frr2oscal module.

Tests cover pure helper functions (no I/O), catalog-integrated part/prop helpers,
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

import frr2oscal
from frr2oscal import (
    CYBERCRAFT_NAMESPACE,
    FRR_NS,
    NIST_800_53_REV5_DOI_URL,
    NIST_800_53_REV5_URL,
    PROFILE_NAMES,
    TAILORING_HREF,
    TAILORING_PROFILE_NAME,
    _NIST_800_53_REV5_RESOURCE_UUID,
    _PARTY_UUID_FEDRAMP,
    _PARTY_UUID_CSP,
    _PARTY_UUID_AO,
    _PARTY_UUID_AGENCY,
    _add_artifact_parts,
    _add_catalog_contacts,
    _add_extra_parts,
    _add_following_information,
    _add_following_information_bullets,
    _add_frr_to_profiles,
    _add_nist_to_profiles,
    _apply_ctl_guidance,
    _assert_single_status_prop,
    _apply_ctl_params,
    _apply_ctl_to_profiles,
    _build_frr_subset_groups,
    _collect_ctl_param_ids,
    _ctl_id_to_oscal,
    _date_to_datetime,
    _extension_props,
    _guidance_part,
    _nist_control_links,
    _notes_text,
    _profile_keys_for,
    _reference_link,
    _reset_profile_tracking,
    _rev5_ctrl_to_oscal,
    _track_unhandled,
    _updated_props,
)
from oscal import Catalog, Profile


# ── Helpers ──────────────────────────────────────────────────────────────────

def _catalog_with_group(group_id: str = "grp") -> Catalog:
    """Return a minimal catalog with one root group ready for control insertion."""
    cat = Catalog.new(title="Test Catalog", version="0.1")
    cat.create_control_group(parent_id="[root]", id=group_id, title="Test Group")
    return cat


def _catalog_with_control(group_id: str = "grp", ctrl_id: str = "R-001") -> Catalog:
    """Return a minimal catalog with one group and one control."""
    cat = _catalog_with_group(group_id)
    cat.create_control(parent_id=group_id, id=ctrl_id, title="Test Control")
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
        part = _guidance_part("examples", [{"id": "E1", "key_tests": [], "examples": []}])
        assert "_" not in part["title"]


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


# ── _add_artifact_parts ───────────────────────────────────────────────────────

class TestAddArtifactParts:
    def _ctrl_parts(self, cat: Catalog, ctrl_id: str = "R-001") -> list:
        ctrl = _find_control(cat, ctrl_id)
        return ctrl.get("parts", [])

    def test_all_scope_produces_one_assessment_method(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {"all": ["artifact-one"]})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        assert len(am) == 1

    def test_path_prop_value_and_ns(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {"20x": ["a-20x"]})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        assert _prop_value(am[0]["props"], "path", ns=FRR_NS) == "20x"

    def test_three_scopes_in_order(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {"all": ["a"], "20x": ["b"], "rev5": ["c"]})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        assert len(am) == 3
        scopes = [_prop_value(p["props"], "path", ns=FRR_NS) for p in am]
        assert scopes == ["all", "20x", "rev5"]

    def test_missing_scope_skipped(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {"rev5": ["r"]})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        assert len(am) == 1
        assert _prop_value(am[0]["props"], "path", ns=FRR_NS) == "rev5"

    def test_empty_dict_produces_no_parts(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        assert am == []

    def test_method_prop_is_examine(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {"all": ["x"]})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        assert _prop_value(am[0]["props"], "method") == "EXAMINE"

    def test_assessment_objects_nested_parts(self):
        cat = _catalog_with_control()
        _add_artifact_parts(cat, "R-001", {"all": ["art one", "art two"]})
        am = [p for p in self._ctrl_parts(cat) if p["name"] == "assessment-method"]
        obj_parts = am[0].get("parts", [])
        assert len(obj_parts) == 2
        assert obj_parts[0]["name"] == "assessment-objects"
        assert obj_parts[0]["prose"] == "art one"


# ── _add_extra_parts ──────────────────────────────────────────────────────────

class TestAddExtraParts:
    def _ctrl_parts(self, cat: Catalog, ctrl_id: str = "R-001") -> list:
        ctrl = _find_control(cat, ctrl_id)
        return ctrl.get("parts", [])

    def test_corrective_actions_becomes_remediation(self):
        cat = _catalog_with_control()
        _add_extra_parts(cat, "R-001", {"corrective_actions": ["Fix this", "Do that"]})
        parts = self._ctrl_parts(cat)
        rem = next((p for p in parts if p["name"] == "remediation"), None)
        assert rem is not None
        assert rem.get("ns") == FRR_NS
        assert "Fix this" in rem["prose"]

    def test_corrective_actions_items_joined(self):
        cat = _catalog_with_control()
        _add_extra_parts(cat, "R-001", {"corrective_actions": ["a", "b"]})
        parts = self._ctrl_parts(cat)
        rem = next(p for p in parts if p["name"] == "remediation")
        assert rem["prose"] == "a\n\nb"

    def test_schema_guidance(self):
        cat = _catalog_with_control()
        _add_extra_parts(cat, "R-001", {"schema": {"name": "S", "url": "http://s"}})
        parts = self._ctrl_parts(cat)
        s = next((p for p in parts if p.get("class") == "schema"), None)
        assert s is not None

    def test_examples_guidance(self):
        cat = _catalog_with_control()
        _add_extra_parts(cat, "R-001", {"examples": [{"id": "E1", "key_tests": [], "examples": []}]})
        parts = self._ctrl_parts(cat)
        ex = next((p for p in parts if p.get("class") == "examples"), None)
        assert ex is not None

    def test_empty_rule_produces_no_parts(self):
        cat = _catalog_with_control()
        _add_extra_parts(cat, "R-001", {})
        assert self._ctrl_parts(cat) == []


# ── _add_following_information ────────────────────────────────────────────────

class TestAddFollowingInformation:
    def _statement_item_parts(self, cat: Catalog, ctrl_id: str = "R-001") -> list:
        ctrl = _find_control(cat, ctrl_id)
        for part in ctrl.get("parts", []):
            if part["name"] == "statement":
                return part.get("parts", [])
        return []

    def _make_control_with_statement(self, ctrl_id: str = "R-001") -> Catalog:
        cat = _catalog_with_group()
        cat.create_control(
            parent_id="grp", id=ctrl_id, title="T", statements=["Do this."]
        )
        return cat

    def test_item_nested_under_statement(self):
        cat = self._make_control_with_statement()
        _add_following_information(cat, "R-001", ["Step one.", "Step two."])
        items = self._statement_item_parts(cat)
        assert len(items) == 1
        assert items[0]["name"] == "item"

    def test_numbered_list_format(self):
        cat = self._make_control_with_statement()
        _add_following_information(cat, "R-001", ["Alpha", "Beta", "Gamma"])
        items = self._statement_item_parts(cat)
        prose = items[0]["prose"]
        assert "1. Alpha" in prose
        assert "2. Beta" in prose
        assert "3. Gamma" in prose

    def test_single_string_wrapped_in_list(self):
        cat = self._make_control_with_statement()
        _add_following_information(cat, "R-001", "Just one thing.")
        items = self._statement_item_parts(cat)
        assert "1. Just one thing." in items[0]["prose"]

    def test_no_title_on_item_part(self):
        cat = self._make_control_with_statement()
        _add_following_information(cat, "R-001", ["Info."])
        items = self._statement_item_parts(cat)
        assert "title" not in items[0]

    def test_no_statement_is_noop(self):
        cat = _catalog_with_control()  # control created without a statement
        _add_following_information(cat, "R-001", ["Info."])
        ctrl = _find_control(cat, "R-001")
        assert ctrl.get("parts", []) == []

    def test_empty_list_is_noop(self):
        cat = self._make_control_with_statement()
        _add_following_information(cat, "R-001", [])
        items = self._statement_item_parts(cat)
        assert items == []


class TestAddFollowingInformationBullets:
    def _make_control_with_statement(self):
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="GRP", title="G")
        cat.create_control(parent_id="GRP", id="R-001", title="R",
                           statements=["The statement."])
        return cat

    def _statement_item_parts(self, cat):
        data = json.loads(cat.dumps("json"))
        ctrl = data["catalog"]["groups"][0]["controls"][0]
        smt = next(p for p in ctrl.get("parts", []) if p["name"] == "statement")
        return [p for p in smt.get("parts", []) if p["name"] == "item"]

    def test_single_bullet(self):
        cat = self._make_control_with_statement()
        _add_following_information_bullets(cat, "R-001", ["Do this."])
        items = self._statement_item_parts(cat)
        assert len(items) == 1
        assert "- Do this." in items[0]["prose"]

    def test_multiple_bullets(self):
        cat = self._make_control_with_statement()
        _add_following_information_bullets(cat, "R-001", ["A", "B", "C"])
        items = self._statement_item_parts(cat)
        prose = items[0]["prose"]
        assert "- A" in prose
        assert "- B" in prose
        assert "- C" in prose

    def test_uses_unordered_not_numbered(self):
        cat = self._make_control_with_statement()
        _add_following_information_bullets(cat, "R-001", ["item"])
        items = self._statement_item_parts(cat)
        assert items[0]["prose"].startswith("- ")
        assert "1." not in items[0]["prose"]

    def test_empty_list_is_noop(self):
        cat = self._make_control_with_statement()
        _add_following_information_bullets(cat, "R-001", [])
        assert self._statement_item_parts(cat) == []


class TestReferenceLink:
    def test_returns_empty_when_no_url(self):
        assert _reference_link({}) == []
        assert _reference_link({"reference": "Some doc"}) == []

    def test_rel_is_reference(self):
        link = _reference_link({"reference_url": "https://example.com"})[0]
        assert link["rel"] == "reference"

    def test_href_is_url(self):
        link = _reference_link({"reference_url": "https://example.com"})[0]
        assert link["href"] == "https://example.com"

    def test_text_set_when_reference_present(self):
        link = _reference_link({
            "reference_url": "https://example.com",
            "reference": "Example Doc",
        })[0]
        assert link["text"] == "Example Doc"

    def test_no_text_key_when_reference_absent(self):
        link = _reference_link({"reference_url": "https://example.com"})[0]
        assert "text" not in link

    def test_blank_url_returns_empty(self):
        assert _reference_link({"reference_url": ""}) == []


class TestExtensionProps:
    def _names(self, props):
        return [p["name"] for p in props]

    def test_empty_rule_returns_empty(self):
        assert _extension_props({}) == []

    def test_timeframe_type_string(self):
        props = _extension_props({"timeframe_type": "bizdays"})
        assert len(props) == 1
        p = props[0]
        assert p["name"] == "timeframe_type"
        assert p["value"] == "bizdays"
        assert p["ns"] == FRR_NS

    def test_timeframe_num_converted_to_string(self):
        props = _extension_props({"timeframe_num": 10})
        assert props[0]["value"] == "10"

    def test_both_timeframe_fields(self):
        props = _extension_props({"timeframe_type": "days", "timeframe_num": 30})
        names = self._names(props)
        assert "timeframe_type" in names
        assert "timeframe_num" in names

    def test_effective_date_dict_serialised_as_json(self):
        ed = {"obtain": "2026-01-01", "maintain": None}
        props = _extension_props({"effective_date": ed})
        assert props[0]["name"] == "effective_date"
        import json as _json
        assert _json.loads(props[0]["value"]) == ed

    def test_all_props_use_frr_ns(self):
        props = _extension_props({"timeframe_type": "hours", "timeframe_num": 4})
        assert all(p["ns"] == FRR_NS for p in props)

    def test_absent_fields_not_included(self):
        props = _extension_props({"timeframe_num": 5})
        names = self._names(props)
        assert "timeframe_type" not in names
        assert "effective_date" not in names


# ── Catalog-integrated: _build_frr_simple_control ────────────────────────────

class TestBuildFrrSimpleControl:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        _reset_profile_tracking()

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
        assert rem.get("ns") == FRR_NS
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

    def test_danger_guidance_part_with_title(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "statement": "S.", "danger": "Watch out!"}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-007", rule)
        ctrl = _find_control(cat, "R-007")
        gdn = next((p for p in ctrl.get("parts", []) if p["name"] == "guidance"), None)
        assert gdn is not None
        assert gdn.get("title") == "Danger"
        assert "Watch out!" in gdn.get("prose", "")

    def test_following_information_as_statement_item(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule", "statement": "Do the thing.",
            "following_information": ["Point one.", "Point two.", "Point three."],
        }
        frr2oscal._build_frr_simple_control(cat, "grp", "R-FI", rule)
        ctrl = _find_control(cat, "R-FI")
        smt = next(p for p in ctrl.get("parts", []) if p["name"] == "statement")
        items = [p for p in smt.get("parts", []) if p["name"] == "item"]
        assert len(items) == 1
        prose = items[0]["prose"]
        assert "1. Point one." in prose
        assert "2. Point two." in prose
        assert "3. Point three." in prose
        assert "title" not in items[0]

    def test_notes_guidance_part(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "statement": "S.", "note": "Be careful."}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-008", rule)
        ctrl = _find_control(cat, "R-008")
        gdn_parts = [p for p in ctrl.get("parts", []) if p["name"] == "guidance"]
        notes_part = next((p for p in gdn_parts if p.get("title") == "Notes"), None)
        assert notes_part is not None
        assert "Be careful." in notes_part["prose"]

    def test_following_information_bullets_unordered(self):
        cat = _catalog_with_group()
        rule = {"name": "R", "statement": "S.", "following_information_bullets": ["X", "Y"]}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-FIB", rule)
        ctrl = _find_control(cat, "R-FIB")
        smt = next(p for p in ctrl["parts"] if p["name"] == "statement")
        item = next(p for p in smt.get("parts", []) if p["name"] == "item")
        assert "- X" in item["prose"]
        assert "- Y" in item["prose"]
        assert "1." not in item["prose"]

    def test_reference_url_link_written(self):
        cat = _catalog_with_group()
        rule = {"name": "R", "statement": "S.", "reference_url": "https://example.com"}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-REF", rule)
        ctrl = _find_control(cat, "R-REF")
        ref_links = [lk for lk in ctrl.get("links", []) if lk.get("rel") == "reference"]
        assert ref_links
        assert ref_links[0]["href"] == "https://example.com"

    def test_reference_text_when_reference_present(self):
        cat = _catalog_with_group()
        rule = {"name": "R", "statement": "S.",
                "reference_url": "https://example.com", "reference": "My Doc"}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-REFT", rule)
        ctrl = _find_control(cat, "R-REFT")
        ref_link = next(lk for lk in ctrl["links"] if lk.get("rel") == "reference")
        assert ref_link.get("text") == "My Doc"

    def test_timeframe_props_written(self):
        cat = _catalog_with_group()
        rule = {"name": "R", "statement": "S.", "timeframe_type": "bizdays", "timeframe_num": 10}
        frr2oscal._build_frr_simple_control(cat, "grp", "R-TF", rule)
        ctrl = _find_control(cat, "R-TF")
        assert _prop_value(ctrl["props"], "timeframe_type", ns=FRR_NS) == "bizdays"
        assert _prop_value(ctrl["props"], "timeframe_num", ns=FRR_NS) == "10"


# ── Catalog-integrated: _build_frr_varies_control ────────────────────────────

class TestBuildFrrVariesControl:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()

    def _get_catalog_json(self, cat: Catalog) -> dict:
        return json.loads(cat.dumps("json"))

    def test_parent_control_created(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule", "varies_by_class": {
                "a": {"statement": "Class A does this."},
            },
        }
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-01", rule)
        data = self._get_catalog_json(cat)
        ctrl_ids = [c["id"] for c in data["catalog"]["groups"][0].get("controls", [])]
        assert "RULE-01" in ctrl_ids

    def test_parent_statement_is_varies_by_class(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "varies_by_class": {"a": {"statement": "S."}}}
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-02", rule)
        data = self._get_catalog_json(cat)
        parent = next(c for c in data["catalog"]["groups"][0]["controls"] if c["id"] == "RULE-02")
        smt = next((p for p in parent.get("parts", []) if p["name"] == "statement"), None)
        assert smt is not None
        assert "Varies by Class" in smt["prose"]

    def test_class_variant_controls_nested(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule",
            "varies_by_class": {
                "a": {"statement": "Class A."},
                "b": {"statement": "Class B."},
            },
        }
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-03", rule)
        data = self._get_catalog_json(cat)
        parent = next(c for c in data["catalog"]["groups"][0]["controls"] if c["id"] == "RULE-03")
        child_ids = [c["id"] for c in parent.get("controls", [])]
        assert "RULE-03-a" in child_ids
        assert "RULE-03-b" in child_ids

    def test_class_variant_label(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "varies_by_class": {"a": {"statement": "S."}}}
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-04", rule)
        data = self._get_catalog_json(cat)
        parent = next(c for c in data["catalog"]["groups"][0]["controls"] if c["id"] == "RULE-04")
        child = parent["controls"][0]
        assert _prop_value(child.get("props", []), "label") == "Class A"

    def test_path_prop_on_parent_and_variants(self):
        cat = _catalog_with_group()
        rule = {"name": "Rule", "varies_by_class": {"a": {"statement": "S."}}}
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-05", rule, path="20x")
        data = self._get_catalog_json(cat)
        parent = next(c for c in data["catalog"]["groups"][0]["controls"] if c["id"] == "RULE-05")
        assert _prop_value(parent.get("props", []), "path", ns=FRR_NS) == "20x"
        child = parent["controls"][0]
        assert _prop_value(child.get("props", []), "path", ns=FRR_NS) == "20x"

    def test_stats_count_parent_and_variants(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule",
            "varies_by_class": {"a": {"statement": "A."}, "b": {"statement": "B."}},
        }
        frr2oscal._STATS["controls"] = 0
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-06", rule)
        assert frr2oscal._STATS["controls"] == 3  # 1 parent + 2 variants

    def test_parent_notes_part(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule",
            "note": "Important note.",
            "varies_by_class": {"a": {"statement": "S."}},
        }
        frr2oscal._build_frr_varies_control(cat, "grp", "RULE-07", rule)
        data = self._get_catalog_json(cat)
        parent = next(c for c in data["catalog"]["groups"][0]["controls"] if c["id"] == "RULE-07")
        notes = next((p for p in parent.get("parts", []) if p.get("title") == "Notes"), None)
        assert notes is not None
        assert "Important note." in notes["prose"]


# ── Catalog-integrated: _build_frr_subset + _build_frr_ruleset ───────────────

class TestBuildFrrSubset:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        _reset_profile_tracking()

    def _parent_with_subset_group(self, subset_id="FRR-TST-SUB"):
        """Return a catalog with FRR-TST and a pre-created subset group."""
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        cat.create_control_group(parent_id="FRR-TST", id=subset_id, title=subset_id)
        return cat

    def test_fallback_creates_subset_group(self):
        """Controls for an undeclared subset key trigger fallback group creation."""
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        subset_val = {"TST-001": {"name": "R", "statement": "S.", "force": "MUST"}}
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB", subset_val, path="all")
        data = json.loads(cat.dumps("json"))
        groups = data["catalog"]["groups"][0].get("groups", [])
        assert any(g["id"] == "FRR-TST-SUB" for g in groups)

    def test_all_scopes_add_to_same_group(self):
        """Controls from all/20x/rev5 scopes land in the same FRR-{key}-{subset} group."""
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        existing = set()
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB",
                                    {"TST-ALL": {"name": "R", "statement": "S."}},
                                    path="all", existing_groups=existing)
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB",
                                    {"TST-20X": {"name": "R", "statement": "S."}},
                                    path="20x", existing_groups=existing)
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB",
                                    {"TST-REV5": {"name": "R", "statement": "S."}},
                                    path="rev5", existing_groups=existing)
        data = json.loads(cat.dumps("json"))
        # Only one subset group should exist (no path-suffixed duplicates).
        groups = data["catalog"]["groups"][0].get("groups", [])
        assert len(groups) == 1
        assert groups[0]["id"] == "FRR-TST-SUB"
        ctrl_ids = {c["id"] for c in groups[0].get("controls", [])}
        assert {"TST-ALL", "TST-20X", "TST-REV5"} == ctrl_ids

    def test_existing_group_not_duplicated(self):
        """When existing_groups contains the subset ID, no second group is created."""
        cat = self._parent_with_subset_group()
        existing = {"FRR-TST-SUB"}
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB",
                                    {"TST-001": {"name": "R", "statement": "S."}},
                                    path="all", existing_groups=existing)
        data = json.loads(cat.dumps("json"))
        groups = data["catalog"]["groups"][0].get("groups", [])
        assert len(groups) == 1  # No duplicate

    def test_controls_added_to_pre_existing_group(self):
        """Controls are inserted into the pre-existing subset group."""
        cat = self._parent_with_subset_group()
        existing = {"FRR-TST-SUB"}
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB",
                                    {"TST-001": {"name": "R", "statement": "S."}},
                                    path="all", existing_groups=existing)
        data = json.loads(cat.dumps("json"))
        sub = data["catalog"]["groups"][0]["groups"][0]
        assert any(c["id"] == "TST-001" for c in sub.get("controls", []))

    def test_fallback_group_uses_purpose_as_overview(self):
        """Fallback group is created with info.purpose as its overview part."""
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        subset_val = {
            "info": {"purpose": "This subset covers X."},
            "TST-001": {"name": "R", "statement": "S."},
        }
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB", subset_val, path="all")
        data = json.loads(cat.dumps("json"))
        sub_group = data["catalog"]["groups"][0]["groups"][0]
        overview = next((p for p in sub_group.get("parts", []) if p["name"] == "overview"), None)
        assert overview is not None
        assert "This subset covers X." in overview["prose"]

    def test_existing_groups_updated_on_fallback(self):
        """The existing_groups set is mutated when a fallback group is created."""
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id="FRR-TST", title="Test")
        existing = set()
        frr2oscal._build_frr_subset(cat, "FRR-TST", "TST", "SUB",
                                    {"TST-001": {"name": "R", "statement": "S."}},
                                    path="all", existing_groups=existing)
        assert "FRR-TST-SUB" in existing


class TestAssertSingleStatusProp:
    def test_empty_props_passes(self):
        _assert_single_status_prop([], "ctrl-1")  # no exception

    def test_one_status_prop_passes(self):
        _assert_single_status_prop([{"name": "status", "value": "stable"}], "ctrl-1")

    def test_two_status_props_raises(self):
        props = [
            {"name": "status", "value": "stable"},
            {"name": "status", "value": "placeholder"},
        ]
        with pytest.raises(RuntimeError, match="ctrl-1"):
            _assert_single_status_prop(props, "ctrl-1")

    def test_non_status_props_ignored(self):
        props = [{"name": "label", "value": "X"}, {"name": "force", "value": "MUST"}]
        _assert_single_status_prop(props, "ctrl-1")  # no exception

    def test_error_message_includes_count(self):
        props = [{"name": "status"}, {"name": "status"}, {"name": "status"}]
        with pytest.raises(RuntimeError, match="3"):
            _assert_single_status_prop(props, "any-id")


class TestBuildFrrRuleset:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()

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
        ctrl_ids = set()
        for top_group in data["catalog"]["groups"]:
            for sub_group in top_group.get("groups", []):
                for ctrl in sub_group.get("controls", []):
                    ctrl_ids.add(ctrl["id"])
        assert "TST-ALL" in ctrl_ids
        assert "TST-20X" in ctrl_ids
        assert "TST-REV5" in ctrl_ids

    def test_multiple_scope_controls_land_in_same_subset_group(self):
        """Controls from all/20x scopes for the same subset key share one group."""
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
        # Only one subset group exists; no path-suffixed duplicate.
        assert group_ids == ["FRR-TST-SAME"]
        subset_grp = data["catalog"]["groups"][0]["groups"][0]
        ctrl_ids = {c["id"] for c in subset_grp.get("controls", [])}
        assert "R1" in ctrl_ids
        assert "R2" in ctrl_ids

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

    def test_ruleset_purpose_overview_with_title(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "purpose": "Covers automated checks."},
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        overview = next((p for p in top_group.get("parts", []) if p["name"] == "overview"), None)
        assert overview is not None
        assert overview.get("title") == "Purpose"
        assert "Covers automated checks." in overview["prose"]

    def test_label_prop_uses_short_name(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "short_name": "TST", "purpose": ""},
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        label = _prop_value(top_group.get("props", []), "label")
        assert label == "TST"

    def test_label_falls_back_to_frr_key_when_short_name_absent(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {"info": {"name": "Test Ruleset", "purpose": ""}, "data": {}}
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        label = _prop_value(top_group.get("props", []), "label")
        assert label == "TST"

    def test_status_prop_written_to_group(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "short_name": "TST", "status": "stable", "purpose": ""},
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        status = _prop_value(top_group.get("props", []), "status", ns=FRR_NS)
        assert status == "stable"

    def test_status_prop_uses_frr_namespace(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "short_name": "TST", "status": "stable", "purpose": ""},
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        props = top_group.get("props", [])
        status_prop = next((p for p in props if p.get("name") == "status"), None)
        assert status_prop is not None
        assert status_prop.get("ns") == FRR_NS

    def test_placeholder_status_written(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "short_name": "TST", "status": "placeholder", "purpose": ""},
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        assert _prop_value(top_group.get("props", []), "status", ns=FRR_NS) == "placeholder"

    def test_no_status_when_absent(self):
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {"info": {"name": "Test Ruleset", "purpose": ""}, "data": {}}
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        top_group = data["catalog"]["groups"][0]
        props = top_group.get("props", [])
        assert not any(p.get("name") == "status" for p in props)


# ── _rev5_ctrl_to_oscal ───────────────────────────────────────────────────────

class TestRev5CtrlToOscal:
    def test_simple_two_part_strips_leading_zero(self):
        assert _rev5_ctrl_to_oscal("AC-01") == "ac-1"

    def test_two_part_double_digit_unchanged(self):
        assert _rev5_ctrl_to_oscal("AC-17") == "ac-17"

    def test_enhancement_parenthesis_becomes_dot(self):
        assert _rev5_ctrl_to_oscal("AC-02 (01)") == "ac-2.1"

    def test_enhancement_strips_zeros_both_segments(self):
        assert _rev5_ctrl_to_oscal("AC-06 (01)") == "ac-6.1"

    def test_enhancement_double_digit_base(self):
        assert _rev5_ctrl_to_oscal("AC-17 (01)") == "ac-17.1"

    def test_lowercase_output(self):
        assert _rev5_ctrl_to_oscal("AU-03 (01)") == "au-3.1"


# ── _profile_keys_for ─────────────────────────────────────────────────────────

class TestProfileKeysFor:
    def test_all_path_no_class_returns_all_seven(self):
        keys = _profile_keys_for("all")
        assert sorted(keys) == sorted(PROFILE_NAMES)

    def test_20x_path_no_class_returns_four(self):
        keys = _profile_keys_for("20x")
        assert set(keys) == {"20X-A", "20X-B", "20X-C", "20X-D"}

    def test_rev5_path_no_class_returns_three(self):
        keys = _profile_keys_for("rev5")
        assert set(keys) == {"Rev5-B", "Rev5-C", "Rev5-D"}

    def test_class_a_all_path_returns_20x_a_only(self):
        # No Rev5-A profile exists.
        keys = _profile_keys_for("all", "a")
        assert keys == ["20X-A"]

    def test_class_b_all_path_returns_20x_b_and_rev5_b(self):
        keys = _profile_keys_for("all", "b")
        assert set(keys) == {"20X-B", "Rev5-B"}

    def test_class_c_20x_path_returns_only_20x_c(self):
        keys = _profile_keys_for("20x", "c")
        assert keys == ["20X-C"]

    def test_class_d_rev5_path_returns_only_rev5_d(self):
        keys = _profile_keys_for("rev5", "d")
        assert keys == ["Rev5-D"]

    def test_unknown_class_yields_empty_if_no_matching_profile(self):
        keys = _profile_keys_for("rev5", "a")
        assert keys == []


# ── _reset_profile_tracking / _add_frr_to_profiles / _add_nist_to_profiles ───

class TestProfileTracking:
    def setup_method(self):
        _reset_profile_tracking()

    def test_reset_clears_all_frr_sets(self):
        for name in PROFILE_NAMES:
            assert frr2oscal._PROFILE_FRR[name] == set()

    def test_reset_clears_all_nist_sets(self):
        for name in ("Rev5-B", "Rev5-C", "Rev5-D"):
            assert frr2oscal._PROFILE_NIST[name] == set()

    def test_add_frr_all_path_populates_seven_profiles(self):
        _add_frr_to_profiles("CTRL-1", "all")
        for name in PROFILE_NAMES:
            assert "CTRL-1" in frr2oscal._PROFILE_FRR[name]

    def test_add_frr_20x_path_skips_rev5_profiles(self):
        _add_frr_to_profiles("CTRL-2", "20x")
        for name in ("Rev5-B", "Rev5-C", "Rev5-D"):
            assert "CTRL-2" not in frr2oscal._PROFILE_FRR[name]

    def test_add_frr_rev5_path_skips_20x_profiles(self):
        _add_frr_to_profiles("CTRL-3", "rev5")
        for name in ("20X-A", "20X-B", "20X-C", "20X-D"):
            assert "CTRL-3" not in frr2oscal._PROFILE_FRR[name]

    def test_add_frr_with_class_b_all_path(self):
        _add_frr_to_profiles("CTRL-4", "all", "b")
        assert "CTRL-4" in frr2oscal._PROFILE_FRR["20X-B"]
        assert "CTRL-4" in frr2oscal._PROFILE_FRR["Rev5-B"]
        assert "CTRL-4" not in frr2oscal._PROFILE_FRR["20X-A"]
        assert "CTRL-4" not in frr2oscal._PROFILE_FRR["20X-C"]

    def test_add_nist_rev5_no_class_populates_three_rev5_profiles(self):
        _add_nist_to_profiles("AC-06 (01)", "rev5")
        for name in ("Rev5-B", "Rev5-C", "Rev5-D"):
            assert "ac-6.1" in frr2oscal._PROFILE_NIST[name]

    def test_add_nist_rev5_class_c_only_rev5_c(self):
        _add_nist_to_profiles("SA-09", "rev5", "c")
        assert "sa-9" in frr2oscal._PROFILE_NIST["Rev5-C"]
        assert "sa-9" not in frr2oscal._PROFILE_NIST["Rev5-B"]
        assert "sa-9" not in frr2oscal._PROFILE_NIST["Rev5-D"]

    def test_add_nist_does_not_affect_20x_profiles(self):
        _add_nist_to_profiles("AC-20", "all")
        for name in ("20X-A", "20X-B", "20X-C", "20X-D"):
            assert "ac-20" not in frr2oscal._PROFILE_FRR.get(name, set())


# ── _build_ksi ────────────────────────────────────────────────────────────────

class TestBuildKsi:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()

    def _make_data(self, *, varies=False):
        ind = {
            "KSI-TST-IND": {
                "name": "Test Indicator",
                "statement": "This is the indicator statement.",
                "controls": ["ac-2"],
                "updated": [],
            }
        }
        if varies:
            ind["KSI-TST-VBC"] = {
                "name": "Varying Indicator",
                "statement": "Base statement.",
                "controls": [],
                "updated": [],
                "varies_by_class": {
                    "b": {"statement": "Class B statement."},
                    "c": {"statement": "Class C statement."},
                },
            }
        return {
            "KSI": {
                "TST": {
                    "id": "KSI-TST",
                    "name": "Test Category",
                    "indicators": ind,
                }
            }
        }

    def test_root_ksi_group_created(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data())
        data = json.loads(cat.dumps("json"))
        group_ids = [g["id"] for g in data["catalog"].get("groups", [])]
        assert "KSI" in group_ids

    def test_subgroup_created(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data())
        data = json.loads(cat.dumps("json"))
        ksi_group = next(g for g in data["catalog"]["groups"] if g["id"] == "KSI")
        sub_ids = [g["id"] for g in ksi_group.get("groups", [])]
        assert "KSI-TST" in sub_ids

    def test_simple_indicator_control_created(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data())
        data = json.loads(cat.dumps("json"))
        ksi_group = next(g for g in data["catalog"]["groups"] if g["id"] == "KSI")
        tst_group = next(g for g in ksi_group["groups"] if g["id"] == "KSI-TST")
        ctrl_ids = [c["id"] for c in tst_group.get("controls", [])]
        assert "KSI-TST-IND" in ctrl_ids

    def test_simple_indicator_added_to_all_20x_profiles(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data())
        for name in ("20X-A", "20X-B", "20X-C", "20X-D"):
            assert "KSI-TST-IND" in frr2oscal._PROFILE_FRR[name]

    def test_simple_indicator_not_in_rev5_profiles(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data())
        for name in ("Rev5-B", "Rev5-C", "Rev5-D"):
            assert "KSI-TST-IND" not in frr2oscal._PROFILE_FRR[name]

    def test_varies_parent_in_all_20x(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data(varies=True))
        for name in ("20X-A", "20X-B", "20X-C", "20X-D"):
            assert "KSI-TST-VBC" in frr2oscal._PROFILE_FRR[name]

    def test_varies_class_b_child_only_in_20x_b(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, self._make_data(varies=True))
        assert "KSI-TST-VBC-b" in frr2oscal._PROFILE_FRR["20X-B"]
        assert "KSI-TST-VBC-b" not in frr2oscal._PROFILE_FRR["20X-A"]
        assert "KSI-TST-VBC-b" not in frr2oscal._PROFILE_FRR["20X-C"]

    def test_empty_ksi_section_does_not_crash(self):
        cat = Catalog.new(title="T", version="0.1")
        frr2oscal._build_ksi(cat, {})  # no KSI key


# ── rev5_controls_list inline processing ─────────────────────────────────────

class TestRev5ControlsList:
    """Tests for rev5_controls_list processing inside _build_frr_varies_control."""

    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()

    def _rule_with_rcl(self, *, path="rev5"):
        return {
            "name": "Rule",
            "varies_by_class": {
                "b": {
                    "statement": "Class B.",
                    "rev5_controls_list": {
                        "AC": ["AC-01", "AC-02 (01)"],
                        "AU": ["AU-03"],
                    },
                },
                "c": {
                    "statement": "Class C.",
                    "rev5_controls_list": {
                        "AC": ["AC-01", "AC-02 (01)", "AC-06 (01)"],
                        "AU": ["AU-03"],
                    },
                },
            },
        }

    def test_rev5_controls_registered_for_class_b(self):
        cat = _catalog_with_group()
        frr2oscal._build_frr_varies_control(cat, "grp", "RCL-01", self._rule_with_rcl())
        assert "ac-1" in frr2oscal._PROFILE_NIST["Rev5-B"]
        assert "ac-2.1" in frr2oscal._PROFILE_NIST["Rev5-B"]
        assert "au-3" in frr2oscal._PROFILE_NIST["Rev5-B"]

    def test_rev5_controls_not_in_rev5_c_from_b_list(self):
        cat = _catalog_with_group()
        frr2oscal._build_frr_varies_control(cat, "grp", "RCL-02", self._rule_with_rcl())
        # ac-6.1 is only in class c
        assert "ac-6.1" not in frr2oscal._PROFILE_NIST["Rev5-B"]
        assert "ac-6.1" in frr2oscal._PROFILE_NIST["Rev5-C"]

    def test_rev5_controls_not_in_20x_profiles(self):
        cat = _catalog_with_group()
        frr2oscal._build_frr_varies_control(cat, "grp", "RCL-03", self._rule_with_rcl())
        for name in ("20X-A", "20X-B", "20X-C", "20X-D"):
            assert "ac-1" not in frr2oscal._PROFILE_NIST.get(name, set())

    def test_all_path_class_b_goes_to_both_20x_b_and_rev5_b(self):
        cat = _catalog_with_group()
        rule = {
            "name": "Rule",
            "varies_by_class": {
                "b": {
                    "statement": "B.",
                    "rev5_controls_list": {"AC": ["AC-01"]},
                },
            },
        }
        frr2oscal._build_frr_varies_control(cat, "grp", "RCL-04", rule, path="all")
        assert "ac-1" in frr2oscal._PROFILE_NIST["Rev5-B"]
        # FedRAMP catalog child also registered for both 20X-B and Rev5-B
        assert "RCL-04-b" in frr2oscal._PROFILE_FRR["20X-B"]


# ── build_profiles ────────────────────────────────────────────────────────────

class TestCtlIdToOscal:
    def test_two_part_strips_leading_zeros(self):
        assert _ctl_id_to_oscal("IA-05") == "ia-5"

    def test_two_part_no_leading_zeros(self):
        assert _ctl_id_to_oscal("AC-20") == "ac-20"

    def test_three_part_becomes_dot_notation(self):
        assert _ctl_id_to_oscal("AC-06-01") == "ac-6.1"

    def test_three_part_strips_zeros_both_segments(self):
        assert _ctl_id_to_oscal("SA-09-05") == "sa-9.5"

    def test_lowercase_output(self):
        assert _ctl_id_to_oscal("CM-12-01") == "cm-12.1"


class TestApplyCtlParams:
    def setup_method(self):
        _reset_profile_tracking()

    def _minimal_profile(self):
        _add_nist_to_profiles("AC-01", "rev5")
        p = Profile.new(title="T", version="0.1")
        import frr2oscal as _f
        p.add_import(_f.NIST_800_53_REV5_URL, title="NIST")
        p.set_import_selection(_f.NIST_800_53_REV5_URL, include_all={})
        return p

    def test_set_parameter_written(self):
        p = self._minimal_profile()
        _apply_ctl_params(p, "ac-1", {
            "parameters": [{"parameterId": "ac-01_odp", "value": "daily"}]
        })
        raw = json.loads(p.dumps("json"))
        setps = raw.get("profile", {}).get("modify", {}).get("set-parameters", [])
        assert any(sp.get("param-id") == "ac-01_odp" for sp in setps)

    def test_set_parameter_value(self):
        p = self._minimal_profile()
        _apply_ctl_params(p, "ac-1", {
            "parameters": [{"parameterId": "ac-01_odp", "value": "annually"}]
        })
        raw = json.loads(p.dumps("json"))
        setps = raw.get("profile", {}).get("modify", {}).get("set-parameters", [])
        sp = next(s for s in setps if s.get("param-id") == "ac-01_odp")
        assert sp.get("values") == ["annually"]

    def test_empty_parameters_is_noop(self):
        p = self._minimal_profile()
        _apply_ctl_params(p, "ac-1", {})
        raw = json.loads(p.dumps("json"))
        assert "modify" not in raw.get("profile", {})

    def test_multiple_parameters(self):
        p = self._minimal_profile()
        _apply_ctl_params(p, "ac-1", {
            "parameters": [
                {"parameterId": "ac-01_odp.01", "value": "v1"},
                {"parameterId": "ac-01_odp.02", "value": "v2"},
            ]
        })
        raw = json.loads(p.dumps("json"))
        setps = raw.get("profile", {}).get("modify", {}).get("set-parameters", [])
        ids = {sp["param-id"] for sp in setps}
        assert "ac-01_odp.01" in ids
        assert "ac-01_odp.02" in ids


class TestApplyCtlGuidance:
    def setup_method(self):
        _reset_profile_tracking()

    def _minimal_profile(self):
        _add_nist_to_profiles("AC-01", "rev5")
        p = Profile.new(title="T", version="0.1")
        import frr2oscal as _f
        p.add_import(_f.NIST_800_53_REV5_URL, title="NIST")
        p.set_import_selection(_f.NIST_800_53_REV5_URL, include_all={})
        return p

    def test_guidance_alter_add_created(self):
        p = self._minimal_profile()
        _apply_ctl_guidance(p, "ac-1", {"guidance": ["Follow the rules."]})
        raw = json.loads(p.dumps("json"))
        alters = raw.get("profile", {}).get("modify", {}).get("alters", [])
        assert any(a.get("control-id") == "ac-1" for a in alters)

    def test_guidance_prose_joined(self):
        p = self._minimal_profile()
        _apply_ctl_guidance(p, "ac-1", {"guidance": ["Line one.", "Line two."]})
        raw = json.loads(p.dumps("json"))
        alters = raw.get("profile", {}).get("modify", {}).get("alters", [])
        alter = next(a for a in alters if a.get("control-id") == "ac-1")
        add = alter["adds"][0]
        part = add["parts"][0]
        assert "Line one." in part["prose"]
        assert "Line two." in part["prose"]

    def test_guidance_part_name_is_guidance(self):
        p = self._minimal_profile()
        _apply_ctl_guidance(p, "ac-2", {"guidance": ["Do this."]})
        raw = json.loads(p.dumps("json"))
        alter = raw["profile"]["modify"]["alters"][0]
        assert alter["adds"][0]["parts"][0]["name"] == "guidance"

    def test_empty_guidance_is_noop(self):
        p = self._minimal_profile()
        _apply_ctl_guidance(p, "ac-1", {})
        raw = json.loads(p.dumps("json"))
        assert "modify" not in raw.get("profile", {})


class TestApplyCtlToProfiles:
    def setup_method(self):
        _reset_profile_tracking()

    def _make_profiles(self):
        import frr2oscal as _f
        _add_nist_to_profiles("AC-01", "rev5")
        tailoring = Profile.new(title="Tailoring", version="0.1")
        tailoring.add_import(_f.NIST_800_53_REV5_URL, title="NIST")
        tailoring.set_import_selection(_f.NIST_800_53_REV5_URL, include_all={})

        rev5 = {}
        for cls in ("B", "C", "D"):
            p = Profile.new(title=f"Rev5-{cls}", version="0.1")
            p.add_import(_f.NIST_800_53_REV5_URL, title="NIST")
            p.set_import_selection(_f.NIST_800_53_REV5_URL, include_all={})
            rev5[f"Rev5-{cls}"] = p
        return tailoring, rev5

    def _make_data(self, *, vbc=False):
        if vbc:
            return {
                "CTL": {
                    "IA": {
                        "IA-05": {
                            "varies_by_class": {
                                "b": {"guidance": ["Class B guidance."]},
                                "c": {"parameters": [{"parameterId": "ia-05_odp", "value": "v2"}]},
                            }
                        }
                    }
                }
            }
        return {
            "CTL": {
                "AC": {
                    "AC-20": {"guidance": ["Differentiate AC-20 from CA-3."]},
                    "AC-06-01": {
                        "parameters": [{"parameterId": "ac-06.01_odp.02", "value": "all funcs"}]
                    },
                }
            }
        }

    def test_non_varies_param_goes_to_tailoring(self):
        tailoring, rev5 = self._make_profiles()
        _apply_ctl_to_profiles(self._make_data(), tailoring, rev5)
        raw = json.loads(tailoring.dumps("json"))
        setps = raw.get("profile", {}).get("modify", {}).get("set-parameters", [])
        assert any(sp["param-id"] == "ac-06.01_odp.02" for sp in setps)

    def test_non_varies_guidance_goes_to_tailoring(self):
        tailoring, rev5 = self._make_profiles()
        _apply_ctl_to_profiles(self._make_data(), tailoring, rev5)
        raw = json.loads(tailoring.dumps("json"))
        alters = raw.get("profile", {}).get("modify", {}).get("alters", [])
        assert any(a.get("control-id") == "ac-20" for a in alters)

    def test_varies_guidance_goes_to_class_profile(self):
        tailoring, rev5 = self._make_profiles()
        _apply_ctl_to_profiles(self._make_data(vbc=True), tailoring, rev5)
        raw = json.loads(rev5["Rev5-B"].dumps("json"))
        alters = raw.get("profile", {}).get("modify", {}).get("alters", [])
        assert any(a.get("control-id") == "ia-5" for a in alters)

    def test_varies_param_goes_to_class_profile(self):
        tailoring, rev5 = self._make_profiles()
        _apply_ctl_to_profiles(self._make_data(vbc=True), tailoring, rev5)
        raw = json.loads(rev5["Rev5-C"].dumps("json"))
        setps = raw.get("profile", {}).get("modify", {}).get("set-parameters", [])
        assert any(sp["param-id"] == "ia-05_odp" for sp in setps)

    def test_varies_guidance_not_in_tailoring(self):
        tailoring, rev5 = self._make_profiles()
        _apply_ctl_to_profiles(self._make_data(vbc=True), tailoring, rev5)
        raw = json.loads(tailoring.dumps("json"))
        modify = raw.get("profile", {}).get("modify", {})
        alters = modify.get("alters", [])
        assert not any(a.get("control-id") == "ia-5" for a in alters)

    def test_returns_sorted_param_id_list(self):
        tailoring, rev5 = self._make_profiles()
        ids = _apply_ctl_to_profiles(self._make_data(), tailoring, rev5)
        assert isinstance(ids, list)
        assert "ac-06.01_odp.02" in ids


class TestCollectCtlParamIds:
    def _make_data(self):
        return {
            "CTL": {
                "AC": {
                    "AC-20": {
                        "parameters": [{"parameterId": "ac-20_odp", "value": "v1"}],
                        "guidance": ["Guidance text."],
                    }
                },
                "IA": {
                    "IA-05": {
                        "varies_by_class": {
                            "b": {"parameters": [{"parameterId": "ia-05_odp.b", "value": "vb"}]},
                            "c": {"guidance": ["Class C guidance."]},
                        }
                    }
                },
            }
        }

    def test_returns_list(self):
        ids = _collect_ctl_param_ids(self._make_data())
        assert isinstance(ids, list)

    def test_collects_non_varies_params(self):
        ids = _collect_ctl_param_ids(self._make_data())
        assert "ac-20_odp" in ids

    def test_collects_varies_params(self):
        ids = _collect_ctl_param_ids(self._make_data())
        assert "ia-05_odp.b" in ids

    def test_sorted_output(self):
        ids = _collect_ctl_param_ids(self._make_data())
        assert ids == sorted(ids)

    def test_no_duplicates(self):
        ids = _collect_ctl_param_ids(self._make_data())
        assert len(ids) == len(set(ids))

    def test_empty_ctl(self):
        assert _collect_ctl_param_ids({}) == []

    def test_guidance_only_entry_not_counted(self):
        data = {"CTL": {"AC": {"AC-01": {"guidance": ["Some text."]}}}}
        ids = _collect_ctl_param_ids(data)
        assert ids == []


class TestBuildProfiles:
    def setup_method(self):
        _reset_profile_tracking()
        # Seed minimal profile tracking state.
        _add_frr_to_profiles("CTRL-1", "all")
        _add_frr_to_profiles("KSI-X", "20x")
        _add_nist_to_profiles("AC-20", "rev5")

    def _make_data(self):
        return {
            "info": {"version": "2026.1", "last_updated": "2026-01-01"},
            "CTL": {},
        }

    def test_returns_eight_profiles(self):
        profiles = frr2oscal.build_profiles(self._make_data())
        assert len(profiles) == 8

    def test_contains_all_seven_class_profiles_and_tailoring(self):
        profiles = frr2oscal.build_profiles(self._make_data())
        assert set(PROFILE_NAMES) | {TAILORING_PROFILE_NAME} == set(profiles.keys())

    def test_each_value_is_profile_instance(self):
        profiles = frr2oscal.build_profiles(self._make_data())
        for p in profiles.values():
            assert isinstance(p, Profile)

    def test_20x_profile_has_only_fedramp_catalog_import(self):
        # Profile imports use UUID anchors; actual URIs live in back-matter rlinks.
        profiles = frr2oscal.build_profiles(self._make_data())
        raw = json.loads(profiles["20X-A"].dumps("json"))
        bm_hrefs = self._back_matter_hrefs(raw)
        assert not any(frr2oscal.NIST_800_53_REV5_URL in h for h in bm_hrefs)
        assert not any(TAILORING_HREF in h for h in bm_hrefs)

    def _back_matter_hrefs(self, raw: dict) -> list:
        """Return all rlink hrefs from a profile's back-matter resources."""
        resources = raw.get("profile", {}).get("back-matter", {}).get("resources", [])
        return [
            rlink.get("href", "")
            for res in resources
            for rlink in res.get("rlinks", [])
        ]

    def test_tailoring_profile_imports_nist_catalog(self):
        profiles = frr2oscal.build_profiles(self._make_data())
        raw = json.loads(profiles[TAILORING_PROFILE_NAME].dumps("json"))
        bm_hrefs = self._back_matter_hrefs(raw)
        assert any(frr2oscal.NIST_800_53_REV5_URL in h for h in bm_hrefs)

    def test_rev5_class_profile_imports_tailoring_not_nist_url(self):
        # Profile imports use UUID anchors (#uuid); actual URIs are in back-matter rlinks.
        profiles = frr2oscal.build_profiles(self._make_data())
        raw = json.loads(profiles["Rev5-B"].dumps("json"))
        bm_hrefs = self._back_matter_hrefs(raw)
        assert any(TAILORING_HREF in h for h in bm_hrefs)
        assert not any(frr2oscal.NIST_800_53_REV5_URL in h for h in bm_hrefs)

    def _uuid_for_href(self, raw: dict, href_fragment: str) -> str | None:
        """Return the UUID anchor for a back-matter resource whose rlink matches href_fragment."""
        for res in raw.get("profile", {}).get("back-matter", {}).get("resources", []):
            for rlink in res.get("rlinks", []):
                if href_fragment in rlink.get("href", ""):
                    return res.get("uuid")
        return None

    def test_tailoring_contains_nist_union(self):
        _add_nist_to_profiles("AC-01", "rev5")
        profiles = frr2oscal.build_profiles(self._make_data())
        raw = json.loads(profiles[TAILORING_PROFILE_NAME].dumps("json"))
        # Imports use UUID anchors — resolve back to the NIST resource via back-matter.
        nist_uuid = self._uuid_for_href(raw, frr2oscal.NIST_800_53_REV5_URL)
        assert nist_uuid is not None, "NIST catalog not found in back-matter"
        imports = raw.get("profile", {}).get("imports", [])
        nist_import = next(
            imp for imp in imports if imp.get("href") == f"#{nist_uuid}"
        )
        all_ids = [
            i
            for block in nist_import.get("include-controls", [])
            for i in block.get("with-ids", [])
        ]
        assert "ac-1" in all_ids
        assert "ac-20" in all_ids

    def _metadata_links(self, raw: dict) -> list:
        return raw.get("profile", {}).get("metadata", {}).get("links", [])

    def test_profile_has_canonical_link(self):
        profiles = frr2oscal.build_profiles(self._make_data())
        for name, profile in profiles.items():
            raw = json.loads(profile.dumps("json"))
            links = self._metadata_links(raw)
            canonical = [lk for lk in links if lk.get("rel") == "canonical"]
            assert canonical, f"No canonical link in metadata of profile '{name}'"
            assert canonical[0]["href"] == frr2oscal.SOURCE_URL

    def test_profile_has_alternate_link(self):
        profiles = frr2oscal.build_profiles(self._make_data())
        for name, profile in profiles.items():
            raw = json.loads(profile.dumps("json"))
            links = self._metadata_links(raw)
            alternate = [lk for lk in links if lk.get("rel") == "alternate"]
            assert alternate, f"No alternate link in metadata of profile '{name}'"
            assert alternate[0]["href"] == frr2oscal.ALTERNATE_URL


class TestBuildCatalogCanonicalLink:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        _reset_profile_tracking()

    def _make_data(self):
        return {
            "info": {
                "title": "Test Catalog",
                "version": "0.1",
                "description": "",
                "last_updated": "2026-01-01",
            },
            "FRR": {},
            "KSI": {},
        }

    def test_catalog_has_canonical_link(self):
        catalog = frr2oscal.build_catalog(self._make_data())
        raw = json.loads(catalog.dumps("json"))
        links = raw.get("catalog", {}).get("metadata", {}).get("links", [])
        canonical = [lk for lk in links if lk.get("rel") == "canonical"]
        assert canonical, "No canonical link in catalog metadata"
        assert canonical[0]["href"] == frr2oscal.SOURCE_URL

    def test_catalog_has_alternate_link(self):
        catalog = frr2oscal.build_catalog(self._make_data())
        raw = json.loads(catalog.dumps("json"))
        links = raw.get("catalog", {}).get("metadata", {}).get("links", [])
        alternate = [lk for lk in links if lk.get("rel") == "alternate"]
        assert alternate, "No alternate link in catalog metadata"
        assert alternate[0]["href"] == frr2oscal.ALTERNATE_URL


# ── _build_frr_ruleset: web_name / tag props ──────────────────────────────────

class TestBuildFrrRulesetExtensionProps:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()

    def _top_group_props(self, info_extra: dict) -> list:
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {"name": "Test Ruleset", "short_name": "TST", **info_extra},
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        return data["catalog"]["groups"][0].get("props", [])

    def test_web_name_becomes_frr_prop(self):
        props = self._top_group_props({"web_name": "Test Full Name"})
        assert _prop_value(props, "web_name", ns=FRR_NS) == "Test Full Name"

    def test_tag_becomes_frr_prop(self):
        props = self._top_group_props({"tag": "tst-tag"})
        assert _prop_value(props, "tag", ns=FRR_NS) == "tst-tag"

    def test_absent_web_name_not_in_props(self):
        props = self._top_group_props({})
        assert not any(p.get("name") == "web_name" for p in props)

    def test_absent_tag_not_in_props(self):
        props = self._top_group_props({})
        assert not any(p.get("name") == "tag" for p in props)

    def test_web_name_and_tag_both_present(self):
        props = self._top_group_props({"web_name": "Full Name", "tag": "fn"})
        assert _prop_value(props, "web_name", ns=FRR_NS) == "Full Name"
        assert _prop_value(props, "tag", ns=FRR_NS) == "fn"

    def test_web_name_uses_frr_namespace(self):
        props = self._top_group_props({"web_name": "Name"})
        prop = next((p for p in props if p.get("name") == "web_name"), None)
        assert prop is not None
        assert prop.get("ns") == FRR_NS

    def test_tag_uses_frr_namespace(self):
        props = self._top_group_props({"tag": "t"})
        prop = next((p for p in props if p.get("name") == "tag"), None)
        assert prop is not None
        assert prop.get("ns") == FRR_NS


# ── _build_frr_subset_info_controls ──────────────────────────────────────────

class TestBuildFrrSubsetGroups:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()

    def _cat_with_group(self, group_id: str = "FRR-TST") -> Catalog:
        cat = Catalog.new(title="T", version="0.1")
        cat.create_control_group(parent_id="[root]", id=group_id, title="Test")
        return cat

    def _subgroups_in(self, cat: Catalog, group_id: str = "FRR-TST") -> list:
        data = json.loads(cat.dumps("json"))
        for grp in data.get("catalog", {}).get("groups", []):
            if grp.get("id") == group_id:
                return grp.get("groups", [])
        return []

    def test_no_subsets_returns_empty_set(self):
        cat = self._cat_with_group()
        created = _build_frr_subset_groups(cat, "FRR-TST", {})
        assert created == set()

    def test_no_subsets_creates_no_groups(self):
        cat = self._cat_with_group()
        _build_frr_subset_groups(cat, "FRR-TST", {})
        assert self._subgroups_in(cat) == []

    def test_single_subset_creates_one_group(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline"}}}
        _build_frr_subset_groups(cat, "FRR-TST", info)
        assert len(self._subgroups_in(cat)) == 1

    def test_returns_set_of_created_ids(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline"}, "EXT": {"name": "Extended"}}}
        created = _build_frr_subset_groups(cat, "FRR-TST", info)
        assert created == {"FRR-TST-BSL", "FRR-TST-EXT"}

    def test_subset_title_is_name(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline"}}}
        _build_frr_subset_groups(cat, "FRR-TST", info)
        grp = self._subgroups_in(cat)[0]
        assert grp["title"] == "Baseline"

    def test_subset_group_id_is_parent_dash_key(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline"}}}
        _build_frr_subset_groups(cat, "FRR-TST", info)
        grp = self._subgroups_in(cat)[0]
        assert grp["id"] == "FRR-TST-BSL"

    def test_description_becomes_overview_part(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline", "description": "The baseline subset."}}}
        _build_frr_subset_groups(cat, "FRR-TST", info)
        grp = self._subgroups_in(cat)[0]
        overview = next((p for p in grp.get("parts", []) if p.get("name") == "overview"), None)
        assert overview is not None
        assert "The baseline subset." in overview.get("prose", "")

    def test_no_statement_part_created(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline", "description": "Desc."}}}
        _build_frr_subset_groups(cat, "FRR-TST", info)
        grp = self._subgroups_in(cat)[0]
        assert not any(p.get("name") == "statement" for p in grp.get("parts", []))

    def test_applicability_types_become_props(self):
        cat = self._cat_with_group()
        info = {
            "subsets": {
                "BSL": {"name": "Baseline", "applicability": {"types": ["20x", "Rev5"]}}
            }
        }
        _build_frr_subset_groups(cat, "FRR-TST", info)
        grp = self._subgroups_in(cat)[0]
        type_vals = [p["value"] for p in grp.get("props", []) if p.get("name") == "applicability-type"]
        assert "20x" in type_vals
        assert "Rev5" in type_vals

    def test_affects_becomes_props(self):
        cat = self._cat_with_group()
        info = {
            "subsets": {
                "BSL": {"name": "Baseline", "applicability": {"affects": ["Providers", "Agencies"]}}
            }
        }
        _build_frr_subset_groups(cat, "FRR-TST", info)
        grp = self._subgroups_in(cat)[0]
        affects_vals = [p["value"] for p in grp.get("props", []) if p.get("name") == "affects"]
        assert "Providers" in affects_vals
        assert "Agencies" in affects_vals

    def test_multiple_subsets_create_multiple_groups(self):
        cat = self._cat_with_group()
        info = {"subsets": {"BSL": {"name": "Baseline"}, "EXT": {"name": "Extended"}}}
        _build_frr_subset_groups(cat, "FRR-TST", info)
        ids = {g["id"] for g in self._subgroups_in(cat)}
        assert "FRR-TST-BSL" in ids
        assert "FRR-TST-EXT" in ids

    def test_via_build_frr_ruleset_creates_subgroups(self):
        """Subsets from info.subsets appear as groups (not controls) under the ruleset group."""
        cat = Catalog.new(title="T", version="0.1")
        frr_val = {
            "info": {
                "name": "Test", "short_name": "TST",
                "subsets": {"BSL": {"name": "Baseline"}},
            },
            "data": {},
        }
        frr2oscal._build_frr_ruleset(cat, "TST", frr_val)
        data = json.loads(cat.dumps("json"))
        group = data["catalog"]["groups"][0]
        sub_ids = [g["id"] for g in group.get("groups", [])]
        assert "FRR-TST-BSL" in sub_ids
        # Must NOT appear as a control.
        ctrl_ids = [c["id"] for c in group.get("controls", [])]
        assert "FRR-TST-BSL" not in ctrl_ids


# ── _add_catalog_contacts ─────────────────────────────────────────────────────

class TestAddCatalogContacts:
    def _catalog_with_contacts(self) -> tuple:
        cat = Catalog.new(title="T", version="0.1")
        _add_catalog_contacts(cat)
        raw = json.loads(cat.dumps("json"))
        meta = raw.get("catalog", {}).get("metadata", {})
        return cat, meta

    def test_four_roles_created(self):
        _, meta = self._catalog_with_contacts()
        roles = meta.get("roles", [])
        assert len(roles) == 4

    def test_role_ids_correct(self):
        _, meta = self._catalog_with_contacts()
        ids = {r["id"] for r in meta.get("roles", [])}
        assert ids == {"fedramp", "system-owner", "assessor", "agency"}

    def test_four_parties_created(self):
        _, meta = self._catalog_with_contacts()
        parties = meta.get("parties", [])
        assert len(parties) == 4

    def test_fedramp_party_has_email(self):
        _, meta = self._catalog_with_contacts()
        fedramp = next(
            (p for p in meta.get("parties", []) if p.get("name") == "FedRAMP PMO"), None
        )
        assert fedramp is not None
        assert "info@fedramp.gov" in fedramp.get("email-addresses", [])

    def test_fedramp_party_has_website_link(self):
        _, meta = self._catalog_with_contacts()
        fedramp = next(
            (p for p in meta.get("parties", []) if p.get("name") == "FedRAMP PMO"), None
        )
        links = fedramp.get("links", [])
        website = next((lk for lk in links if lk.get("rel") == "website"), None)
        assert website is not None
        assert website["href"] == "https://www.fedramp.gov"

    def test_party_uuids_match_constants(self):
        _, meta = self._catalog_with_contacts()
        uuids = {p["uuid"] for p in meta.get("parties", [])}
        assert _PARTY_UUID_FEDRAMP in uuids
        assert _PARTY_UUID_CSP in uuids
        assert _PARTY_UUID_AO in uuids
        assert _PARTY_UUID_AGENCY in uuids

    def test_four_responsible_parties(self):
        _, meta = self._catalog_with_contacts()
        rps = meta.get("responsible-parties", [])
        assert len(rps) == 4

    def test_fedramp_role_linked_to_fedramp_pmo(self):
        _, meta = self._catalog_with_contacts()
        rp = next(
            (r for r in meta.get("responsible-parties", []) if r.get("role-id") == "fedramp"),
            None,
        )
        assert rp is not None
        assert _PARTY_UUID_FEDRAMP in rp.get("party-uuids", [])

    def test_system_owner_role_linked_to_csp(self):
        _, meta = self._catalog_with_contacts()
        rp = next(
            (r for r in meta.get("responsible-parties", []) if r.get("role-id") == "system-owner"),
            None,
        )
        assert rp is not None
        assert _PARTY_UUID_CSP in rp.get("party-uuids", [])

    def test_assessor_role_linked_to_ao(self):
        _, meta = self._catalog_with_contacts()
        rp = next(
            (r for r in meta.get("responsible-parties", []) if r.get("role-id") == "assessor"),
            None,
        )
        assert rp is not None
        assert _PARTY_UUID_AO in rp.get("party-uuids", [])

    def test_agency_role_linked_to_federal_agency(self):
        _, meta = self._catalog_with_contacts()
        rp = next(
            (r for r in meta.get("responsible-parties", []) if r.get("role-id") == "agency"),
            None,
        )
        assert rp is not None
        assert _PARTY_UUID_AGENCY in rp.get("party-uuids", [])

    def test_contacts_present_in_build_catalog_output(self):
        data = {
            "info": {"title": "T", "version": "0.1", "description": "", "last_updated": "2026-01-01"},
            "FRR": {}, "KSI": {},
        }
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        _reset_profile_tracking()
        cat = frr2oscal.build_catalog(data)
        raw = json.loads(cat.dumps("json"))
        meta = raw.get("catalog", {}).get("metadata", {})
        assert len(meta.get("roles", [])) == 4
        assert len(meta.get("parties", [])) == 4
        assert len(meta.get("responsible-parties", [])) == 4


# ── _nist_control_links ───────────────────────────────────────────────────────

class TestNistControlLinks:
    def test_empty_controls_returns_empty_list(self):
        assert _nist_control_links({}) == []

    def test_none_controls_returns_empty_list(self):
        assert _nist_control_links({"controls": None}) == []

    def test_single_control_produces_one_link(self):
        links = _nist_control_links({"controls": ["ac-2"]})
        assert len(links) == 1

    def test_link_rel_is_related(self):
        links = _nist_control_links({"controls": ["ac-2"]})
        assert links[0]["rel"] == "related"

    def test_link_href_references_resource_uuid(self):
        links = _nist_control_links({"controls": ["ac-2"]})
        assert links[0]["href"] == f"#{_NIST_800_53_REV5_RESOURCE_UUID}"

    def test_resource_fragment_is_control_id(self):
        links = _nist_control_links({"controls": ["ac-2"]})
        assert links[0]["resource-fragment"] == "ac-2"

    def test_multiple_controls_produce_multiple_links(self):
        links = _nist_control_links({"controls": ["ac-2", "ia-5", "si-3"]})
        assert len(links) == 3
        fragments = [lk["resource-fragment"] for lk in links]
        assert fragments == ["ac-2", "ia-5", "si-3"]

    def test_all_links_point_to_same_resource(self):
        links = _nist_control_links({"controls": ["ac-2", "ia-5"]})
        hrefs = {lk["href"] for lk in links}
        assert hrefs == {f"#{_NIST_800_53_REV5_RESOURCE_UUID}"}

    def test_link_text_is_uppercase_label(self):
        links = _nist_control_links({"controls": ["ac-2"]})
        assert links[0]["text"] == "NIST SP 800-53 Rev 5 AC-2"

    def test_link_text_uppercases_id(self):
        links = _nist_control_links({"controls": ["ia-5", "si-3.1"]})
        texts = [lk["text"] for lk in links]
        assert "NIST SP 800-53 Rev 5 IA-5" in texts
        assert "NIST SP 800-53 Rev 5 SI-3.1" in texts

    def test_simple_control_builds_nist_links(self):
        cat = _catalog_with_group()
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()
        rule = {
            "name": "Test Rule",
            "statement": "Do this.",
            "force": "MUST",
            "affects": [],
            "updated": [],
            "controls": ["ac-2", "ia-5"],
        }
        frr2oscal._build_frr_simple_control(cat, "grp", "TEST-001", rule)
        raw = json.loads(cat.dumps("json"))
        ctrl = next(
            c for g in raw["catalog"]["groups"]
            for c in g.get("controls", [])
            if c["id"] == "TEST-001"
        )
        nist_links = [
            lk for lk in ctrl.get("links", [])
            if lk.get("href") == f"#{_NIST_800_53_REV5_RESOURCE_UUID}"
        ]
        assert len(nist_links) == 2
        fragments = {lk["resource-fragment"] for lk in nist_links}
        assert fragments == {"ac-2", "ia-5"}
        texts = {lk["text"] for lk in nist_links}
        assert texts == {"NIST SP 800-53 Rev 5 AC-2", "NIST SP 800-53 Rev 5 IA-5"}

    def test_varies_control_parent_builds_nist_links(self):
        cat = _catalog_with_group()
        frr2oscal._VERBOSE = False
        _reset_profile_tracking()
        rule = {
            "name": "Varies Rule",
            "controls": ["si-3"],
            "affects": [],
            "updated": [],
            "varies_by_class": {
                "b": {"statement": "Class B.", "force": "MUST"},
            },
        }
        frr2oscal._build_frr_varies_control(cat, "grp", "VBC-001", rule)
        raw = json.loads(cat.dumps("json"))
        ctrl = next(
            c for g in raw["catalog"]["groups"]
            for c in g.get("controls", [])
            if c["id"] == "VBC-001"
        )
        nist_links = [
            lk for lk in ctrl.get("links", [])
            if lk.get("resource-fragment") == "si-3"
        ]
        assert len(nist_links) == 1


# ── back-matter NIST resource ─────────────────────────────────────────────────

class TestCatalogNistResource:
    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        _reset_profile_tracking()

    def _minimal_data(self):
        return {
            "info": {"title": "T", "version": "0.1", "description": "", "last_updated": "2026-01-01"},
            "FRR": {}, "KSI": {},
        }

    def _back_matter_resources(self) -> list:
        cat = frr2oscal.build_catalog(self._minimal_data())
        raw = json.loads(cat.dumps("json"))
        return raw.get("catalog", {}).get("back-matter", {}).get("resources", [])

    def test_nist_resource_present(self):
        resources = self._back_matter_resources()
        uuids = [r.get("uuid") for r in resources]
        assert _NIST_800_53_REV5_RESOURCE_UUID in uuids

    def test_nist_resource_title(self):
        resources = self._back_matter_resources()
        res = next(r for r in resources if r.get("uuid") == _NIST_800_53_REV5_RESOURCE_UUID)
        assert res["title"] == "NIST SP 800-53 Rev 5"

    def test_nist_resource_has_two_rlinks(self):
        resources = self._back_matter_resources()
        res = next(r for r in resources if r.get("uuid") == _NIST_800_53_REV5_RESOURCE_UUID)
        assert len(res.get("rlinks", [])) == 2

    def test_first_rlink_is_oscal_github_url(self):
        resources = self._back_matter_resources()
        res = next(r for r in resources if r.get("uuid") == _NIST_800_53_REV5_RESOURCE_UUID)
        assert res["rlinks"][0]["href"] == NIST_800_53_REV5_URL

    def test_second_rlink_is_doi_url(self):
        resources = self._back_matter_resources()
        res = next(r for r in resources if r.get("uuid") == _NIST_800_53_REV5_RESOURCE_UUID)
        assert res["rlinks"][1]["href"] == NIST_800_53_REV5_DOI_URL


# ── Cybercraft extension (presentation-id prop) ────────────────────────────────────

class TestCybercraftExtension:
    """Verify the cybercraft presentation-id extension appears in catalog and profile metadata."""

    def setup_method(self):
        frr2oscal._STATS["groups"] = 0
        frr2oscal._STATS["controls"] = 0
        frr2oscal.UNHANDLED.clear()
        _reset_profile_tracking()

    def _minimal_data(self):
        return {
            "info": {"title": "T", "version": "0.1", "description": "", "last_updated": "2026-01-01"},
            "FRR": {}, "KSI": {}, "CTL": {},
        }

    def _catalog_meta_props(self) -> list:
        cat = frr2oscal.build_catalog(self._minimal_data())
        raw = json.loads(cat.dumps("json"))
        return raw.get("catalog", {}).get("metadata", {}).get("props", [])

    def test_catalog_has_content_id_prop(self):
        props = self._catalog_meta_props()
        assert any(p.get("name") == "presentation-id" for p in props)

    def test_catalog_content_id_value_is_fedramp_cr26(self):
        props = self._catalog_meta_props()
        prop = next(p for p in props if p.get("name") == "presentation-id")
        assert prop["value"] == "fedramp-cr26"

    def test_catalog_content_id_uses_cybercraft_namespace(self):
        props = self._catalog_meta_props()
        prop = next(p for p in props if p.get("name") == "presentation-id")
        assert prop["ns"] == CYBERCRAFT_NAMESPACE

    def test_profiles_have_content_id_prop(self):
        _add_frr_to_profiles("CTRL-1", "all")
        _add_nist_to_profiles("AC-20", "rev5")
        profiles = frr2oscal.build_profiles(self._minimal_data())
        for name, profile in profiles.items():
            raw = json.loads(profile.dumps("json"))
            props = raw.get("profile", {}).get("metadata", {}).get("props", [])
            assert any(p.get("name") == "presentation-id" for p in props), (
                f"Profile '{name}' missing presentation-id prop"
            )

    def test_profiles_content_id_value_is_fedramp_cr26(self):
        _add_frr_to_profiles("CTRL-1", "all")
        _add_nist_to_profiles("AC-20", "rev5")
        profiles = frr2oscal.build_profiles(self._minimal_data())
        for name, profile in profiles.items():
            raw = json.loads(profile.dumps("json"))
            props = raw.get("profile", {}).get("metadata", {}).get("props", [])
            prop = next((p for p in props if p.get("name") == "presentation-id"), None)
            assert prop is not None and prop["value"] == "fedramp-cr26", (
                f"Profile '{name}' presentation-id value mismatch"
            )

    def test_profiles_content_id_uses_cybercraft_namespace(self):
        _add_frr_to_profiles("CTRL-1", "all")
        _add_nist_to_profiles("AC-20", "rev5")
        profiles = frr2oscal.build_profiles(self._minimal_data())
        for name, profile in profiles.items():
            raw = json.loads(profile.dumps("json"))
            props = raw.get("profile", {}).get("metadata", {}).get("props", [])
            prop = next((p for p in props if p.get("name") == "presentation-id"), None)
            assert prop is not None and prop["ns"] == CYBERCRAFT_NAMESPACE, (
                f"Profile '{name}' presentation-id namespace mismatch"
            )
