"""
Converts FedRAMP's consolidated rules JSON to an OSCAL catalog and writes it
in JSON, XML, and YAML formats. Progress and a summary are printed while the
catalog is built; pass --silent to suppress those messages. Pass --refresh to
force a fresh download of the source JSON even when a local copy exists.

The source JSON is cached locally in ./data on first download and reused on
subsequent runs to avoid repeated network requests.

Source: https://github.com/FedRAMP/rules
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

# Locate the oscal-class library relative to this repo (../class from repo root)
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_oscal_lib  = os.path.join(_repo_root, "..", "class")
if os.path.isdir(_oscal_lib) and _oscal_lib not in sys.path:
    sys.path.insert(0, os.path.normpath(_oscal_lib))

from oscal import Catalog

SOURCE_URL = "https://raw.githubusercontent.com/FedRAMP/rules/main/fedramp-consolidated-rules.json"
SOURCE_LOCAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "fedramp-consolidated-rules.json",
)


def load_rules(
    url: str = SOURCE_URL,
    local_path: str = SOURCE_LOCAL,
    refresh: bool = False,
) -> dict | None:
    """Load FedRAMP consolidated rules, downloading to local_path if not cached.

    When refresh is True a fresh download is attempted regardless of whether a
    local copy exists. The download is written to a temporary file first so that
    a failed refresh never corrupts an existing local copy.

    Args:
        url (str, optional): Remote URL to fetch the rules JSON from.
            Defaults to SOURCE_URL.
        local_path (str, optional): Local file path to cache the downloaded JSON.
            Defaults to SOURCE_LOCAL.
        refresh (bool, optional): When True, attempt to download a new copy even
            if a local file is already present. Defaults to False.

    Returns:
        dict: Parsed rules data, or None if the file could not be loaded.
    """
    has_local = os.path.isfile(local_path)

    if refresh or not has_local:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        tmp_path = local_path + ".tmp"
        print(f"Downloading rules from {url} ...")
        try:
            urllib.request.urlretrieve(url, tmp_path)
            os.replace(tmp_path, local_path)
            has_local = True
            print(f"Saved to {local_path}")
        except urllib.error.HTTPError as exc:
            _remove_if_exists(tmp_path)
            print(f"ERROR: HTTP {exc.code} {exc.reason} — {url}")
            _refresh_fallback_hint(refresh, has_local)
            if not has_local:
                return None
        except urllib.error.URLError as exc:
            _remove_if_exists(tmp_path)
            print(f"ERROR: Could not reach {url} — {exc.reason}")
            _refresh_fallback_hint(refresh, has_local)
            if not has_local:
                return None

    with open(local_path, encoding="utf-8") as f:
        return json.load(f)


def _remove_if_exists(path: str) -> None:
    """Remove a file if it exists; silently ignore if it does not."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _refresh_fallback_hint(refresh: bool, has_local: bool) -> None:
    """Print an advisory when a --refresh download fails but a local copy exists."""
    if refresh and has_local:
        print("A local copy is available. Re-run without --refresh to use it.")


_VERBOSE: bool = True
_STATS: dict = {"groups": 0, "controls": 0}


def _emit(msg: str = "", end: str = "\n") -> None:
    """Print msg when verbose mode is active.

    Args:
        msg (str, optional): Text to print. Defaults to empty string.
        end (str, optional): Line terminator passed to print(). Defaults to newline.
    """
    if _VERBOSE:
        print(msg, end=end, flush=True)


def _emit_dot() -> None:
    """Print a single progress dot with no newline when verbose mode is active."""
    if _VERBOSE:
        print(".", end="", flush=True)


def print_metadata(data: dict) -> None:
    """Print the top-level source file info (title, version, last_updated).

    Args:
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.
    """
    info = data.get("info", {})
    _emit(f"Title:        {info.get('title', '')}")
    _emit(f"Version:      {info.get('version', '')}")
    _emit(f"Last Updated: {info.get('last_updated', '')}")

FRR_NS = "http://fedramp.gov/ns/oscal"

UNHANDLED: list = []

UNHANDLED_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "unhandled.json",
)

# Keys consumed by each processing function; anything else is unhandled.
_HANDLED_RULE_KEYS = frozenset({
    "name", "statement", "danger", "notes", "note",
    "related", "force", "affects", "artifacts",
    "corrective_actions", "examples", "schema", "following_information", "updated",
})
_HANDLED_VARIES_RULE_KEYS = frozenset({
    "name", "related", "affects", "varies_by_class",
    "note", "notes",
    "corrective_actions", "examples", "schema", "following_information", "updated",
})
_HANDLED_CLASS_KEYS = frozenset({
    "statement", "force", "related", "note", "notes", "artifacts",
    "following_information", "corrective_actions", "examples", "schema",
})

CATALOG_OUTPUT_STEM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "FedRAMP_2026_OSCAL_catalog",
)

CATALOG_FORMATS = ("json", "xml", "yaml")


def _date_to_datetime(date_str: str) -> str:
    """Convert a bare date (YYYY-MM-DD) to an OSCAL dateTime-with-timezone string."""
    if date_str and "T" not in date_str:
        return f"{date_str}T00:00:00Z"
    return date_str


def _track_unhandled(obj: dict, handled: frozenset) -> None:
    """Record any keys in obj that are not in handled into the global UNHANDLED list.

    Preserves insertion order and avoids duplicates.

    Args:
        obj (dict, required): Rule or class-variant dict to inspect.
        handled (frozenset, required): Set of key names already processed by the caller.
    """
    for key in obj:
        if key not in handled and key not in UNHANDLED:
            UNHANDLED.append(key)


def _set_part_title(obj: dict, part_name: str, title: str) -> None:
    """Set a title on a named part within an OSCAL object's parts list.

    The oscal library does not yet support titles on overview/guidance parts
    via its creation APIs. This function sets the title directly on the
    returned dict, which is the live object already inserted into the catalog.

    Args:
        obj (dict, required): OSCAL group or control dict containing a 'parts' list.
        part_name (str, required): The 'name' attribute of the target part.
        title (str, required): Title string to assign.
    """
    for part in obj.get("parts", []):
        if part.get("name") == part_name:
            part["title"] = title
            return


def _notes_text(rule: dict) -> str:
    """Extract and normalise the notes/note field from a rule dict.

    Both 'note' (str, 58 rules) and 'notes' (list, 24 rules) appear in the
    source data. Returns a single string with entries joined by blank lines,
    or an empty string when neither field is present.

    Args:
        rule (dict, required): Rule or class-variant dict from the FRR JSON source.

    Returns:
        str: Joined notes text, or empty string.
    """
    raw = rule.get("notes") or rule.get("note") or []
    if isinstance(raw, str):
        raw = [raw]
    return "\n\n".join(raw)


def _guidance_part(key: str, content) -> dict:
    """Build a guidance part dict for examples, schema, or following_information.

    Args:
        key (str, required): Field name ('examples', 'schema', 'following_information').
        content (required): Field value from the rule dict.

    Returns:
        dict: OSCAL part dict with name='guidance', class=key, title=Title Case, prose.
    """
    title = key.replace("_", " ").title()
    if key == "schema":
        prose = f"{content.get('name', '')}\n{content.get('url', '')}"
    elif key == "following_information":
        prose = "\n\n".join(content) if isinstance(content, list) else str(content)
    elif key == "examples":
        blocks = []
        for ex in content:
            lines = []
            if ex.get("id"):
                lines.append(f"**{ex['id']}**")
            if ex.get("key_tests"):
                lines.append("Key tests:")
                lines.extend(f"- {t}" for t in ex["key_tests"])
            if ex.get("examples"):
                lines.append("Examples:")
                lines.extend(f"- {e}" for e in ex["examples"])
            blocks.append("\n".join(lines))
        prose = "\n\n".join(blocks)
    else:
        prose = str(content)
    return {"name": "guidance", "class": key, "title": title, "prose": prose}


def _assessment_method_part(artifacts: list, path: str) -> dict:
    """Build an assessment-method part with a path prop for one artifact scope.

    Args:
        artifacts (list, required): List of artifact description strings.
        path (str, required): Scope name ('all', '20x', or 'rev5').

    Returns:
        dict: OSCAL assessment-method part dict.
    """
    return {
        "name": "assessment-method",
        "props": [
            {"name": "method", "value": "EXAMINE"},
            {"name": "path", "value": path, "ns": FRR_NS},
        ],
        "parts": [{"name": "assessment-objects", "prose": a} for a in artifacts],
    }


def _append_artifact_parts(parts: list, artifacts_dict: dict) -> None:
    """Append assessment-method parts for each scope present in artifacts_dict.

    Args:
        parts (list, required): Mutable parts list to append to.
        artifacts_dict (dict, required): Artifacts dict with optional 'all', '20x', 'rev5' keys.
    """
    for scope in ("all", "20x", "rev5"):
        items = artifacts_dict.get(scope) or []
        if items:
            parts.append(_assessment_method_part(items, scope))


def _append_extra_parts(parts: list, rule: dict) -> None:
    """Append remediation and supplemental guidance parts for known extra fields.

    Handles: corrective_actions → remediation part (FedRAMP namespace);
    examples, schema, following_information → guidance parts with class and title.

    Args:
        parts (list, required): Mutable parts list to append to.
        rule (dict, required): Rule or class-variant dict from the FRR JSON source.
    """
    ca = rule.get("corrective_actions") or []
    if ca:
        parts.append({"name": "remediation", "ns": FRR_NS, "prose": "\n\n".join(ca)})
    for key in ("examples", "schema", "following_information"):
        content = rule.get(key)
        if content:
            parts.append(_guidance_part(key, content))


def _updated_props(rule: dict) -> list:
    """Return a list of 'updated' props from a rule's updated array.

    Each entry in the updated list becomes one prop in the FedRAMP namespace
    with name='updated', value=date-as-datetime, and remarks=comment.

    Args:
        rule (dict, required): Rule or class-variant dict from the FRR JSON source.

    Returns:
        list: List of OSCAL prop dicts (may be empty).
    """
    result = []
    for entry in (rule.get("updated") or []):
        result.append({
            "name": "updated",
            "ns": FRR_NS,
            "value": _date_to_datetime(entry.get("date", "")),
            "remarks": entry.get("comment", ""),
        })
    return result


def _build_frr_simple_control(
    catalog: Catalog, parent_id: str, ctrl_id: str,
    rule: dict, label: str = "", path: str = "all"
) -> None:
    """Create a single OSCAL control from a rule dict.

    Handles statement, danger/guidance, notes/guidance, related links,
    force/affects/path props, assessment-method/objects parts for each artifact
    scope, remediation, supplemental guidance, and updated props.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent group for this control.
        ctrl_id (str, required): Identifier for the new control (used as id).
        rule (dict, required): Rule data dict from the FRR JSON source.
        label (str, optional): Label prop value. Defaults to ctrl_id.
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.
    """
    label = label or ctrl_id

    links = [
        {"rel": "related", "href": f"#{rid}"}
        for rid in (rule.get("related") or [])
    ]

    props = [{"name": "path", "value": path, "ns": FRR_NS}]
    if rule.get("force"):
        props.append({"name": "force", "value": rule["force"], "ns": FRR_NS})
    for affect in (rule.get("affects") or []):
        props.append({"name": "affects", "value": affect, "ns": FRR_NS})

    danger = rule.get("danger", "")
    statement = rule.get("statement", "")
    title = rule.get("name") or label

    control = catalog.create_control(
        parent_id=parent_id,
        id=ctrl_id,
        title=title,
        label=label,
        statements=[statement] if statement else [],
        guidance=danger,
        links=links,
        props=props,
    )
    if control is None:
        return

    _STATS["controls"] += 1
    _emit_dot()

    # Library gap: create_control does not support a title on the guidance part.
    # Set it directly on the returned dict until the library adds this support.
    if danger:
        _set_part_title(control, "guidance", "Danger")

    notes = _notes_text(rule)
    if notes:
        control.setdefault("parts", []).append(
            {"name": "guidance", "title": "Notes", "prose": notes}
        )

    # Library gap: create_control's 'objects' parameter is not yet implemented.
    # Assessment-method/objects structure is built directly on the returned dict.
    ctrl_parts = control.setdefault("parts", [])
    _append_artifact_parts(ctrl_parts, rule.get("artifacts") or {})
    _append_extra_parts(ctrl_parts, rule)

    for prop in _updated_props(rule):
        control.setdefault("props", []).append(prop)

    _track_unhandled(rule, _HANDLED_RULE_KEYS)


def _build_class_control_dict(
    ctrl_id: str, class_data: dict, label: str, path: str = "all"
) -> dict:
    """Build a class-variant child control dict without inserting it into the catalog.

    Used for varies_by_class children, which must be appended directly to a
    parent control's 'controls' list because create_control only supports
    groups as parents (library gap).

    Args:
        ctrl_id (str, required): ID for the new control (e.g. 'CCM-QTR-MTG-a').
        class_data (dict, required): Class-variant data from varies_by_class[key].
        label (str, required): Label prop value (e.g. 'Class A').
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.

    Returns:
        dict: A fully formed OSCAL control dict.
    """
    ctrl: dict = {"id": ctrl_id, "title": label}

    props = [
        {"name": "label", "value": label},
        {"name": "path", "value": path, "ns": FRR_NS},
    ]
    if class_data.get("force"):
        props.append({"name": "force", "value": class_data["force"], "ns": FRR_NS})
    ctrl["props"] = props

    links = [
        {"rel": "related", "href": f"#{rid}"}
        for rid in (class_data.get("related") or [])
    ]
    if links:
        ctrl["links"] = links

    parts: list = []
    statement = class_data.get("statement", "")
    if statement:
        parts.append({"name": "statement", "id": f"{ctrl_id}_smt", "prose": statement})

    notes = _notes_text(class_data)
    if notes:
        parts.append({"name": "guidance", "title": "Notes", "prose": notes})

    _append_artifact_parts(parts, class_data.get("artifacts") or {})
    _append_extra_parts(parts, class_data)

    if parts:
        ctrl["parts"] = parts

    _track_unhandled(class_data, _HANDLED_CLASS_KEYS)
    return ctrl


def _build_frr_varies_control(
    catalog: Catalog, parent_id: str, rule_id: str, rule: dict, path: str = "all"
) -> None:
    """Create a parent control for a varies_by_class rule with class-variant child controls.

    The parent control carries 'Varies by Class' as its statement prose.
    Each class-variant dict is appended directly to the parent control's
    'controls' list because create_control only supports groups as parents
    (library gap).

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent subset group.
        rule_id (str, required): Identifier used as the parent control's id and label.
        rule (dict, required): Rule dict containing a 'varies_by_class' mapping.
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.
    """
    links = [
        {"rel": "related", "href": f"#{rid}"}
        for rid in (rule.get("related") or [])
    ]
    props = [{"name": "path", "value": path, "ns": FRR_NS}]
    for affect in (rule.get("affects") or []):
        props.append({"name": "affects", "value": affect, "ns": FRR_NS})

    parent_ctrl = catalog.create_control(
        parent_id=parent_id,
        id=rule_id,
        title=rule.get("name", rule_id),
        label=rule_id,
        statements=["Varies by Class"],
        links=links,
        props=props,
    )
    if parent_ctrl is None:
        return

    _STATS["controls"] += 1
    _emit_dot()

    notes = _notes_text(rule)
    if notes:
        parent_ctrl.setdefault("parts", []).append(
            {"name": "guidance", "title": "Notes", "prose": notes}
        )

    ctrl_parts = parent_ctrl.setdefault("parts", [])
    _append_extra_parts(ctrl_parts, rule)

    for prop in _updated_props(rule):
        parent_ctrl.setdefault("props", []).append(prop)

    for class_key, class_data in rule["varies_by_class"].items():
        child = _build_class_control_dict(
            ctrl_id=f"{rule_id}-{class_key}",
            class_data=class_data,
            label=f"Class {class_key.upper()}",
            path=path,
        )
        parent_ctrl.setdefault("controls", []).append(child)
        _STATS["controls"] += 1
        _emit_dot()

    _track_unhandled(rule, _HANDLED_VARIES_RULE_KEYS)


def _build_frr_control(
    catalog: Catalog, parent_id: str, rule_id: str, rule: dict, path: str = "all"
) -> None:
    """Dispatch to the appropriate builder for a single FRR rule entry.

    Rules with a 'varies_by_class' key become a control whose class variants
    are nested as child controls. All other rules become a single control.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent group.
        rule_id (str, required): Identifier for this rule.
        rule (dict, required): Rule data dict from the FRR JSON source.
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.
    """
    if rule.get("varies_by_class"):
        _build_frr_varies_control(catalog, parent_id, rule_id, rule, path=path)
    else:
        _build_frr_simple_control(catalog, parent_id, rule_id, rule, path=path)


def _build_frr_subset(
    catalog: Catalog, parent_id: str, frr_key: str,
    subset_key: str, subset_val: dict, path: str = "all"
) -> None:
    """Create a child group for one FRR subset and populate its controls.

    The subset ID is used as the group title (no label prop). For the 'all'
    scope the ID is 'FRR-{key}-{subset}'; for '20x' and 'rev5' scopes a
    path qualifier is inserted to avoid ID collisions ('FRR-{key}-{path}-{subset}').

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent FRR ruleset group.
        frr_key (str, required): Top-level FRR key (e.g. 'AFC').
        subset_key (str, required): Subset key within the scope (e.g. 'FRP').
        subset_val (dict, required): Subset data dict.
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.
    """
    child_id = (
        f"FRR-{frr_key}-{subset_key}"
        if path == "all"
        else f"FRR-{frr_key}-{path}-{subset_key}"
    )
    info = subset_val.get("info", {})
    purpose = info.get("purpose", "")

    child_group = catalog.create_control_group(
        parent_id=parent_id,
        id=child_id,
        title=child_id,
        overview=purpose,
    )
    if child_group is None:
        return

    _STATS["groups"] += 1
    if purpose:
        _set_part_title(child_group, "overview", "Purpose")

    _emit(f"  {child_id} ", end="")
    for rule_id, rule in subset_val.items():
        if rule_id == "info" or not isinstance(rule, dict):
            continue
        _build_frr_control(catalog, child_id, rule_id, rule, path=path)
    _emit()


def _build_frr_ruleset(
    catalog: Catalog, frr_key: str, frr_val: dict
) -> None:
    """Create a top-level group for one FRR ruleset and populate its children.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        frr_key (str, required): Top-level FRR key (e.g. 'AFC').
        frr_val (dict, required): FRR ruleset dict containing 'info' and 'data'.
    """
    group_id = f"FRR-{frr_key}"
    info = frr_val.get("info", {})
    title = info.get("name", frr_key)
    purpose = info.get("purpose", "")

    group = catalog.create_control_group(
        parent_id="[root]",
        id=group_id,
        title=title,
        label=group_id,
        overview=purpose,
    )
    if group is None:
        return

    _STATS["groups"] += 1
    if purpose:
        _set_part_title(group, "overview", "Purpose")

    _emit(f"\n{title}")
    data_block = frr_val.get("data", {})
    for scope in ("all", "20x", "rev5"):
        for subset_key, subset_val in data_block.get(scope, {}).items():
            _build_frr_subset(catalog, group_id, frr_key, subset_key, subset_val, path=scope)


def _build_frr(catalog: Catalog, data: dict) -> None:
    """Populate the catalog with groups and controls from the top-level FRR section.

    Args:
        catalog (Catalog, required): The OSCAL catalog to populate.
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.
    """
    _emit("\n" + "=" * 72)
    _emit("FRR — FedRAMP Rules")
    _emit("=" * 72)
    for frr_key, frr_val in data.get("FRR", {}).items():
        _build_frr_ruleset(catalog, frr_key, frr_val)


def build_catalog(data: dict) -> Catalog:
    """Create an OSCAL Catalog from the FedRAMP consolidated-rules info block."""
    info = data.get("info", {})
    title        = info.get("title", "FedRAMP Consolidated Rules")
    version      = info.get("version", "")
    description  = info.get("description", "")
    published    = _date_to_datetime(info.get("last_updated", ""))
    now          = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    catalog = Catalog.new(title=title, version=version)

    catalog.set_metadata({
        "title":         title,
        "version":       version,
        "remarks":       description,
        "published":     published,
        "last-modified": now,
    })

    _build_frr(catalog, data)

    return catalog


def main() -> None:
    global _VERBOSE

    parser = argparse.ArgumentParser(
        description="Convert FedRAMP consolidated rules to an OSCAL catalog."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download a fresh copy of the source JSON even if a local copy exists.",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress progress and summary output (errors are always shown).",
    )
    args = parser.parse_args()
    _VERBOSE = not args.silent

    data = load_rules(refresh=args.refresh)
    if data is None:
        sys.exit(1)

    print_metadata(data)

    catalog = build_catalog(data)

    _emit("\n" + "=" * 72)
    _emit("Summary")
    _emit(f"  Groups:   {_STATS['groups']}")
    _emit(f"  Controls: {_STATS['controls']}")
    _emit("=" * 72)

    _emit()
    for fmt in CATALOG_FORMATS:
        path = f"{CATALOG_OUTPUT_STEM}.{fmt}"
        if catalog.dump(path, format=fmt, pretty_print=True):
            _emit(f"Catalog written to: {path}")
        else:
            print(f"ERROR: Failed to write catalog to: {path}")

    if UNHANDLED:
        with open(UNHANDLED_OUTPUT, "w", encoding="utf-8") as fh:
            json.dump(UNHANDLED, fh, indent=2)
        _emit(f"Unhandled keys written to: {UNHANDLED_OUTPUT}")


if __name__ == "__main__":
    main()
