"""
Fetches FedRAMP's consolidated rules JSON directly from source and prints
metadata followed by every section (in the order they appear in the file),
listing each entry's ID and title. Entries whose statement text is
conditioned on Certification Class (via a `varies_by_class` block) or on
Certification Path (an entry that only exists under the 20x-only or
Rev5-only side of an FRR ruleset, rather than the shared "all" side) are
annotated with which classes/paths have conditions. Statement/guidance
text itself is intentionally not printed.

Source: https://github.com/FedRAMP/rules
"""

import json
import urllib.request

SOURCE_URL = "https://raw.githubusercontent.com/FedRAMP/rules/main/fedramp-consolidated-rules.json"


def load_rules(url: str = SOURCE_URL) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


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


def main() -> None:
    data = load_rules()
    print_metadata(data)
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
