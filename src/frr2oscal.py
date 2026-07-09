"""
Converts FedRAMP's consolidated rules JSON to an OSCAL catalog and prints
metadata followed by every section (in the order they appear in the file),
listing each entry's ID and title. Entries whose statement text is
conditioned on Certification Class (via a `varies_by_class` block) or on
Certification Path (an entry that only exists under the 20x-only or
Rev5-only side of an FRR ruleset, rather than the shared "all" side) are
annotated with which classes/paths have conditions. Statement/guidance
text itself is intentionally not printed.

The source JSON is cached locally in ./data on first download and reused on
subsequent runs to avoid repeated network requests. Pass --refresh to attempt
a fresh download even when a local copy exists.

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


def class_conditions(entry: dict) -> list[str]:
    """Classes (A/B/C/D) that have distinct conditional text, if any."""
    vbc = entry.get("varies_by_class") if isinstance(entry, dict) else None
    if not vbc:
        return []
    return sorted(k.upper() for k in vbc.keys())


def path_conditions_for_rule(scope: str, subset_types: list | None) -> list[str]:
    """
    Which certification path(s) this FRR rule instance's text applies to.
    scope is the top-level data bucket the rule was found under: 'all',
    '20x', or 'rev5'. subset_types is the applicability.types list declared
    on the rule's subset (None if that metadata wasn't found).
    """
    if scope == "20x":
        return ["20x"]
    if scope == "rev5":
        return ["Rev5"]
    if subset_types is None:
        return ["20x", "Rev5"]  # no restriction found -> treat as universal
    return [p for p in ("20x", "Rev5") if p in subset_types]


def format_conditions(classes: list[str], paths: list[str],
                       universal_paths=("20x", "Rev5")) -> str:
    parts = []
    if classes:
        parts.append(f"classes: {', '.join(classes)}")
    if paths and set(paths) != set(universal_paths):
        parts.append(f"path: {', '.join(paths)}")
    return f"  [{'; '.join(parts)}]" if parts else ""


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def print_metadata(data: dict) -> None:
    print_header("METADATA")
    for k, v in data.get("info", {}).items():
        print(f"{k}: {v}")


def print_frd(data: dict) -> None:
    print_header("FRD — FedRAMP Definitions")
    for fid, entry in data.get("FRD", {}).get("data", {}).get("all", {}).items():
        cond = format_conditions(class_conditions(entry), [])
        print(f"{fid}: {entry.get('term', '')}{cond}")


def print_frr(data: dict) -> None:
    print_header("FRR — FedRAMP Rules")
    for rsk, rsv in data.get("FRR", {}).items():
        rsinfo = rsv.get("info", {})
        print(f"\n--- {rsk}: {rsinfo.get('name', '')} ---")
        subset_meta = rsinfo.get("subsets", {})
        for scope, subsets in rsv.get("data", {}).items():
            for subk, rules in subsets.items():
                subset_types = subset_meta.get(subk, {}).get("applicability", {}).get("types")
                for rid, rule in rules.items():
                    classes = class_conditions(rule)
                    paths = path_conditions_for_rule(scope, subset_types)
                    cond = format_conditions(classes, paths)
                    print(f"{rid}: {rule.get('name', '')}{cond}")


def print_ksi(data: dict) -> None:
    print_header("KSI — Key Security Indicators")
    for tk, tv in data.get("KSI", {}).items():
        print(f"\n--- {tv.get('id', tk)}: {tv.get('name', '')} ---")
        for iid, iv in tv.get("indicators", {}).items():
            cond = format_conditions(class_conditions(iv), [])
            print(f"{iid}: {iv.get('name', '')}{cond}")


def print_ctl(data: dict) -> None:
    # CTL (FedRAMP parameter/guidance overlays on specific NIST 800-53
    # controls) has no title field per entry -- it's keyed as
    # family -> control_id -> {parameters, guidance, varies_by_class}.
    # There's no "title" to print, so we list the control IDs themselves.
    print_header("CTL — Control Overlay Guidance (FedRAMP-added parameters/guidance)")
    for fam, controls in data.get("CTL", {}).items():
        print(f"\n--- {fam} ---")
        for cid, entry in controls.items():
            cond = format_conditions(class_conditions(entry), [])
            print(f"{cid}{cond}")


SECTION_PRINTERS = {
    "FRD": print_frd,
    "FRR": print_frr,
    "KSI": print_ksi,
    "CTL": print_ctl,
}

FRR_NS = "http://fedramp.gov/ns/oscal"

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


def _build_frr_simple_control(
    catalog: Catalog, parent_id: str, ctrl_id: str,
    rule: dict, label: str = ""
) -> None:
    """Create a single OSCAL control from a rule or class-variant dict.

    Handles statement, danger/guidance, notes/guidance, related links,
    force/affects props, and assessment-method/objects parts.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent group for this control.
        ctrl_id (str, required): Identifier for the new control (used as id).
        rule (dict, required): Rule or class-variant data dict.
        label (str, optional): Label prop value. Defaults to ctrl_id.
    """
    label = label or ctrl_id

    links = [
        {"rel": "related", "href": f"#{rid}"}
        for rid in (rule.get("related") or [])
    ]

    props = []
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

    # Library gap: create_control does not support a title on the guidance part.
    # Set it directly on the returned dict until the library adds this support.
    if danger:
        _set_part_title(control, "guidance", "Danger")

    # Notes become a separate guidance part rather than remarks.
    notes = _notes_text(rule)
    if notes:
        control.setdefault("parts", []).append(
            {"name": "guidance", "title": "Notes", "prose": notes}
        )

    # Library gap: create_control's 'objects' parameter is not yet implemented.
    # assessment-objects parts are wrapped in an assessment-method parent part.
    artifacts = (rule.get("artifacts") or {}).get("all") or []
    if artifacts:
        control.setdefault("parts", []).append({
            "name": "assessment-method",
            "props": [{"name": "method", "value": "EXAMINE"}],
            "parts": [{"name": "assessment-objects", "prose": a} for a in artifacts],
        })


def _build_class_control_dict(
    ctrl_id: str, class_data: dict, label: str
) -> dict:
    """Build a class-variant child control dict without inserting it into the catalog.

    Used for varies_by_class children, which must be appended directly to a
    parent control's 'controls' list because create_control only supports
    groups as parents (library gap).

    Args:
        ctrl_id (str, required): ID for the new control (e.g. 'CCM-QTR-MTG-a').
        class_data (dict, required): Class-variant data from varies_by_class[key].
        label (str, required): Label prop value (e.g. 'Class A').

    Returns:
        dict: A fully formed OSCAL control dict.
    """
    ctrl: dict = {"id": ctrl_id, "title": label}

    props = [{"name": "label", "value": label}]
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

    artifacts = (class_data.get("artifacts") or {}).get("all") or []
    if artifacts:
        parts.append({
            "name": "assessment-method",
            "props": [{"name": "method", "value": "EXAMINE"}],
            "parts": [{"name": "assessment-objects", "prose": a} for a in artifacts],
        })

    if parts:
        ctrl["parts"] = parts

    return ctrl


def _build_frr_varies_control(
    catalog: Catalog, parent_id: str, rule_id: str, rule: dict
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
    """
    links = [
        {"rel": "related", "href": f"#{rid}"}
        for rid in (rule.get("related") or [])
    ]
    props = []
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

    for class_key, class_data in rule["varies_by_class"].items():
        child = _build_class_control_dict(
            ctrl_id=f"{rule_id}-{class_key}",
            class_data=class_data,
            label=f"Class {class_key.upper()}",
        )
        parent_ctrl.setdefault("controls", []).append(child)


def _build_frr_control(
    catalog: Catalog, parent_id: str, rule_id: str, rule: dict
) -> None:
    """Dispatch to the appropriate builder for a single FRR rule entry.

    Rules with a 'varies_by_class' key become a control whose class variants
    are nested as child controls. All other rules become a single control.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent group.
        rule_id (str, required): Identifier for this rule.
        rule (dict, required): Rule data dict from the FRR JSON source.
    """
    if rule.get("varies_by_class"):
        _build_frr_varies_control(catalog, parent_id, rule_id, rule)
    else:
        _build_frr_simple_control(catalog, parent_id, rule_id, rule)


def _build_frr_subset(
    catalog: Catalog, parent_id: str, frr_key: str,
    subset_key: str, subset_val: dict
) -> None:
    """Create a child group for one FRR subset and populate its controls.

    The subset ID is used as the group title (no label prop). Title and overview
    are only added when an 'info' block is present in the source data.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent FRR ruleset group.
        frr_key (str, required): Top-level FRR key (e.g. 'AFC').
        subset_key (str, required): Subset key within FRR data.all (e.g. 'FRP').
        subset_val (dict, required): Subset data dict.
    """
    child_id = f"FRR-{frr_key}-{subset_key}"
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

    if purpose:
        _set_part_title(child_group, "overview", "Purpose")

    for rule_id, rule in subset_val.items():
        if rule_id == "info" or not isinstance(rule, dict):
            continue
        _build_frr_control(catalog, child_id, rule_id, rule)


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

    if purpose:
        _set_part_title(group, "overview", "Purpose")

    for subset_key, subset_val in frr_val.get("data", {}).get("all", {}).items():
        _build_frr_subset(catalog, group_id, frr_key, subset_key, subset_val)


def _build_frr(catalog: Catalog, data: dict) -> None:
    """Populate the catalog with groups and controls from the top-level FRR section.

    Args:
        catalog (Catalog, required): The OSCAL catalog to populate.
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.
    """
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
    parser = argparse.ArgumentParser(
        description="Convert FedRAMP consolidated rules to an OSCAL catalog."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Download a fresh copy of the source JSON even if a local copy exists.",
    )
    args = parser.parse_args()

    data = load_rules(refresh=args.refresh)
    if data is None:
        sys.exit(1)
    print_metadata(data)

    catalog = build_catalog(data)
    print()
    for fmt in CATALOG_FORMATS:
        path = f"{CATALOG_OUTPUT_STEM}.{fmt}"
        if catalog.dump(path, format=fmt, pretty_print=True):
            print(f"Catalog written to: {path}")
        else:
            print(f"ERROR: Failed to write catalog to: {path}")

    # Iterate in the order keys actually appear in the source JSON
    # (Python dicts preserve insertion order; json.load preserves file order).
    for key in data.keys():
        if key == "info":
            continue
        printer = SECTION_PRINTERS.get(key)
        if printer:
            printer(data)
        else:
            print_header(f"{key} — (unrecognized top-level section, raw dump)")
            print(json.dumps(data[key], indent=2)[:2000])


if __name__ == "__main__":
    main()
