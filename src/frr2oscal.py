"""
Converts FedRAMP's consolidated rules JSON to an OSCAL catalog and seven
supporting OSCAL profiles (20X-A/B/C/D and Rev5-B/C/D). Progress and a
summary are printed while the catalog is built; pass --silent to suppress
those messages. Pass --refresh to force a fresh download of the source JSON
even when a local copy exists.

The source JSON is cached locally in data/raw/ on first download and reused
on subsequent runs to avoid repeated network requests.  A companion
``fedramp-consolidated-rules_details.json`` file is written alongside the
cached JSON on every successful download, recording the GitHub Last-Modified
timestamp and the local acquisition time; it is loaded on subsequent runs so
that provenance data is always available regardless of whether a fresh
download was performed.

Source: https://github.com/FedRAMP/rules

Constants:
    SOURCE_URL (str): Remote URL for the FedRAMP consolidated-rules JSON.
    ALTERNATE_URL (str): Alternate (human-facing) FedRAMP URL added to metadata links.
    SOURCE_LOCAL (str): Local cache path for the downloaded JSON.
    SOURCE_DETAILS (str): Local cache path for the companion provenance JSON.
    FRR_NS (str): FedRAMP namespace URI used in OSCAL props.
    MERMAID_INK_URL (str): mermaid.ink API URL template used to render Mermaid diagrams
        as SVG. The placeholder ``{encoded}`` is replaced with the base64url-encoded
        Mermaid source text at call time.
    NIST_800_53_REV5_URL (str): NIST SP 800-53 Rev 5 OSCAL catalog URL (GitHub raw).
    NIST_800_53_REV5_DOI_URL (str): NIST SP 800-53 Rev 5 canonical DOI URL.
    CATALOG_HREF (str): Relative filename for the FedRAMP OSCAL catalog,
        used as the href in profile import statements.
    TAILORING_PROFILE_NAME (str): Key and filename stem for the Rev5 tailoring profile.
    TAILORING_HREF (str): Relative filename for the Rev5 tailoring profile,
        used as the href in Rev5 class-profile import statements.
    NIST_LOCAL (str): Local cache path for the downloaded NIST SP 800-53 Rev 5 catalog.
    CATALOG_OUTPUT_STEM (str): Output path stem for the OSCAL catalog
        (extension added per format).
    CATALOG_FORMATS (tuple): Supported output formats for the catalog.
    PROFILE_NAMES (tuple): Ordered class-based profile identifiers (7 total).
        The Rev5 tailoring profile is produced alongside these but not listed here.
    PROFILE_OUTPUT_STEM (str): Output path stem prefix for profile files.
    PROFILE_FORMATS (tuple): Supported output formats for profiles.
    UNHANDLED_OUTPUT (str): Path to write any unrecognized rule keys.
    CYBERCRAFT_NAMESPACE (str): Cybercraft extension namespace URI used in OSCAL props.
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from oscal import Catalog, Profile

SOURCE_URL = "https://raw.githubusercontent.com/FedRAMP/rules/main/fedramp-consolidated-rules.json"
ALTERNATE_URL = "https://www.fedramp.gov/2026/"

# Stable UUIDs for the four catalog parties.
_PARTY_UUID_FEDRAMP = "aaaaaaaa-0000-4000-a000-000000000001"
_PARTY_UUID_CSP     = "aaaaaaaa-0000-4000-a000-000000000002"
_PARTY_UUID_AO      = "aaaaaaaa-0000-4000-a000-000000000003"
_PARTY_UUID_AGENCY  = "aaaaaaaa-0000-4000-a000-000000000004"
SOURCE_LOCAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "fedramp-consolidated-rules.json",
)
SOURCE_DETAILS = os.path.splitext(SOURCE_LOCAL)[0] + "_details.json"

FRR_NS = "http://fedramp.gov/ns/oscal"
CYBERCRAFT_NAMESPACE = "http://cybercraft.app/ns/oscal"

MERMAID_INK_URL = "https://mermaid.ink/svg/{encoded}"

# Stable UUID namespace for deterministic flow-diagram resource UUIDs.
_FLOW_UUID_NAMESPACE = uuid.UUID("a89f0000-0000-4000-a000-000000000001")

NIST_800_53_REV5_URL = (
    "https://raw.githubusercontent.com/usnistgov/oscal-content"
    "/refs/heads/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
)
NIST_800_53_REV5_DOI_URL = "https://doi.org/10.6028/NIST.SP.800-53r5"

# Stable UUID for the catalog back-matter resource referencing NIST SP 800-53 Rev 5.
_NIST_800_53_REV5_RESOURCE_UUID = "ffffffff-0000-4000-a000-000000000001"

CATALOG_HREF = "FedRAMP_2026_OSCAL_catalog.json"

TAILORING_PROFILE_NAME = "Rev5-Tailoring"
TAILORING_HREF = "FedRAMP_2026_OSCAL_profile_Rev5-Tailoring.json"

NIST_LOCAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "NIST_SP-800-53_rev5_catalog.json",
)

CATALOG_OUTPUT_STEM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "OSCAL", "FedRAMP_2026_OSCAL_catalog",
)
CATALOG_FORMATS = ("json", "xml", "yaml")

# PROFILE_NAMES lists the seven class-based profiles tracked in _PROFILE_FRR/_PROFILE_NIST.
# The eighth profile (Rev5-Tailoring) is derived from the union of the Rev5 NIST sets and
# is not tracked separately.
PROFILE_NAMES = ("20X-A", "20X-B", "20X-C", "20X-D", "Rev5-B", "Rev5-C", "Rev5-D")

PROFILE_OUTPUT_STEM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "OSCAL", "FedRAMP_2026_OSCAL_profile_",
)
PROFILE_FORMATS = ("json", "xml", "yaml")

UNHANDLED: list = []

UNHANDLED_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "interim", "unhandled.json",
)

# Keys consumed by each processing function; anything else is unhandled.
_HANDLED_RULE_KEYS = frozenset({
    "name", "statement", "danger", "notes", "note",
    "related", "force", "affects", "artifacts",
    "corrective_actions", "examples", "schema", "following_information", "updated",
    "following_information_bullets", "reference", "reference_url",
    "effective_date", "timeframe_type", "timeframe_num",
    "controls",
})
_HANDLED_VARIES_RULE_KEYS = frozenset({
    "name", "related", "affects", "varies_by_class",
    "note", "notes",
    "corrective_actions", "examples", "schema", "following_information", "updated",
    "following_information_bullets", "reference", "reference_url",
    "effective_date", "timeframe_type", "timeframe_num",
    "controls",
})
_HANDLED_CLASS_KEYS = frozenset({
    "statement", "force", "related", "note", "notes", "artifacts",
    "following_information", "corrective_actions", "examples", "schema",
    "rev5_controls_list",
    "following_information_bullets",
    "effective_date", "timeframe_type", "timeframe_num",
})

_VERBOSE: bool = True
_STATS: dict = {"groups": 0, "controls": 0}

# Profile control-selection tracking — reset by _reset_profile_tracking().
# _PROFILE_FRR: profile_key → set of FedRAMP catalog control IDs to include.
# _PROFILE_NIST: profile_key → set of NIST OSCAL control IDs to include (Rev5 only).
_PROFILE_FRR: dict = {}
_PROFILE_NIST: dict = {}


# =============================================================================
# I/O helpers
# =============================================================================

def load_rules(
    url: str = SOURCE_URL,
    local_path: str = SOURCE_LOCAL,
    refresh: bool = False,
) -> tuple[dict, dict] | None:
    """Load FedRAMP consolidated rules, downloading to local_path if not cached.

    When refresh is True a fresh download is attempted regardless of whether a
    local copy exists. The download is written to a temporary file first so that
    a failed refresh never corrupts an existing local copy.

    On a successful download the GitHub ``Last-Modified`` response header and
    the local acquisition timestamp are saved to a companion ``_details.json``
    file alongside *local_path*.  On subsequent runs the companion file is
    loaded so that provenance data is always available without re-downloading.

    Args:
        url (str, optional): Remote URL to fetch the rules JSON from.
            Defaults to SOURCE_URL.
        local_path (str, optional): Local file path to cache the downloaded JSON.
            Defaults to SOURCE_LOCAL.
        refresh (bool, optional): When True, attempt to download a new copy even
            if a local file is already present. Defaults to False.

    Returns:
        tuple[dict, dict]: A ``(data, details)`` pair where *data* is the parsed
            rules and *details* contains ``github_last_modified`` and ``acquired``
            keys; or None if the file could not be loaded.
    """
    details_path = os.path.splitext(local_path)[0] + "_details.json"
    has_local = os.path.isfile(local_path)
    has_details = os.path.isfile(details_path)
    details: dict = {}

    if refresh or not has_local or not has_details:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        tmp_path = local_path + ".tmp"
        print(f"Downloading rules from {url} ...")
        try:
            _tmp_file, headers = urllib.request.urlretrieve(url, tmp_path)
            acquired = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            github_last_modified = headers.get("Last-Modified", "")
            os.replace(tmp_path, local_path)
            has_local = True
            details = {
                "github_last_modified": github_last_modified,
                "acquired": acquired,
            }
            with open(details_path, "w", encoding="utf-8") as fh:
                json.dump(details, fh, indent=2)
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

    if not details and os.path.isfile(details_path):
        with open(details_path, encoding="utf-8") as fh:
            details = json.load(fh)

    with open(local_path, encoding="utf-8") as f:
        return json.load(f), details


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


# =============================================================================
# Shared rule-processing helpers
# =============================================================================

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
    """Build a guidance part data dict for examples or schema.

    Returns a plain dict with name, class, title, and prose fields. Callers
    pass these values to catalog.add_part() rather than embedding the dict directly.

    Args:
        key (str, required): Field name ('examples' or 'schema').
        content (required): Field value from the rule dict.

    Returns:
        dict: Dict with keys 'name', 'class', 'title', 'prose'.
    """
    title = key.replace("_", " ").title()
    if key == "schema":
        prose = f"{content.get('name', '')}\n{content.get('url', '')}"
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


def _add_following_information(catalog: Catalog, ctrl_id: str, content) -> None:
    """Add following_information as a numbered-list item child of the statement part.

    The item part is added directly under the control's statement part
    (id={ctrl_id}_smt) with no title. Each string in the content list
    becomes one numbered entry. If no statement part exists the call is a no-op.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        ctrl_id (str, required): ID of the control whose statement receives the item.
        content (list | str, required): The following_information value from the rule dict.
    """
    items = content if isinstance(content, list) else [str(content)]
    if not items:
        return
    prose = "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    catalog.add_part(f"{ctrl_id}_smt", "item", prose=prose)


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


def _add_artifact_parts(catalog: Catalog, ctrl_id: str, artifacts_dict: dict) -> None:
    """Add assessment-method parts for each scope present in artifacts_dict.

    Uses catalog.add_part() to ensure changes persist in the catalog's internal state.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        ctrl_id (str, required): ID of the control to add parts to.
        artifacts_dict (dict, required): Artifacts dict with optional 'all', '20x', 'rev5' keys.
    """
    for scope in ("all", "20x", "rev5"):
        items = artifacts_dict.get(scope) or []
        if items:
            catalog.add_part(
                ctrl_id,
                "assessment-method",
                props=[
                    {"name": "method", "value": "EXAMINE"},
                    {"name": "path", "value": scope, "ns": FRR_NS},
                ],
                parts=[{"name": "assessment-objects", "prose": a} for a in items],
            )


def _add_following_information_bullets(catalog: Catalog, ctrl_id: str, content) -> None:
    """Add following_information_bullets as an unordered-list item child of the statement part.

    Each string in the content list becomes one bullet entry. The part is added
    under the control's statement part (id={ctrl_id}_smt). If no statement part
    exists the call is a no-op.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        ctrl_id (str, required): ID of the control whose statement receives the item.
        content (list | str, required): The following_information_bullets value from the rule dict.
    """
    items = content if isinstance(content, list) else [str(content)]
    if not items:
        return
    prose = "\n".join(f"- {item}" for item in items)
    catalog.add_part(f"{ctrl_id}_smt", "item", prose=prose)


def _reference_link(rule: dict) -> list:
    """Return a list containing a reference link if reference_url is present.

    The link uses rel='reference'. If a 'reference' text field is also present
    in the same rule dict it is used as the link's text.

    Args:
        rule (dict, required): Rule or class-variant dict from the FRR JSON source.

    Returns:
        list: A one-element list with the link dict, or an empty list.
    """
    url = (rule.get("reference_url") or "").strip()
    if not url:
        return []
    link: dict = {"rel": "reference", "href": url}
    ref_text = (rule.get("reference") or "").strip()
    if ref_text:
        link["text"] = ref_text
    return [link]


def _nist_control_links(rule: dict) -> list:
    """Return links for each NIST SP 800-53 control ID cited in the rule's 'controls' array.

    Each link references the catalog back-matter resource for NIST SP 800-53 Rev 5
    via a UUID fragment href, with the control ID stored in 'resource-fragment'.

    Args:
        rule (dict, required): Rule dict from the FRR JSON source.

    Returns:
        list: List of OSCAL link dicts (may be empty).
    """
    result = []
    for ctrl_id in (rule.get("controls") or []):
        result.append({
            "rel": "related",
            "href": f"#{_NIST_800_53_REV5_RESOURCE_UUID}",
            "resource-fragment": ctrl_id,
            "text": f"NIST SP 800-53 Rev 5 {ctrl_id.upper()}",
        })
    return result


def _extension_props(rule: dict) -> list:
    """Return FedRAMP-namespace props for extension fields in a rule or class-variant dict.

    Handles: effective_date (serialised as JSON when it is an object),
    timeframe_type (string), timeframe_num (number converted to string).
    Only fields present and non-None in rule are included.

    Args:
        rule (dict, required): Rule or class-variant dict from the FRR JSON source.

    Returns:
        list: List of OSCAL prop dicts in the FedRAMP namespace (may be empty).
    """
    result = []
    for key in ("effective_date", "timeframe_type", "timeframe_num"):
        val = rule.get(key)
        if val is not None:
            str_val = json.dumps(val, ensure_ascii=False) if isinstance(val, dict) else str(val)
            result.append({"name": key, "ns": FRR_NS, "value": str_val})
    return result


def _effective_entry_props(entry: dict, scope: str = "all") -> list:
    """Return FedRAMP-namespace props for an effective_entry dict on an FRR ruleset group.

    All props use the name prefix 'effective-'; the OSCAL 'class' attribute
    distinguishes which cert scope the entry belongs to: 'all' for the top-level
    info.effective block, '20x' for info.20x.effective, and 'rev5' for
    info.rev5.effective.

    Scalar fields map to a single prop each. Boolean fields are serialised as
    'true' or 'false'. Array fields (comments, warnings) are JSON-serialised so
    the entire array is stored in one prop value. Date fields under 'date' are
    converted to OSCAL dateTime format. The nested grace period object produces
    two props ('effective-date-grace-default' and
    'effective-date-grace-until_next_assessment').

    Prop name mapping (class='all' example):
      is                               → effective-is                          (class=all)
      current_status                   → effective-current_status              (class=all)
      signup_url                       → effective-signup_url                  (class=all)
      comments                         → effective-comments  (JSON array)      (class=all)
      warnings                         → effective-warnings  (JSON array)      (class=all)
      date.obtain                      → effective-date-obtain                 (class=all)
      date.maintain                    → effective-date-maintain               (class=all)
      date.optional_adoption           → effective-date-optional_adoption      (class=all)
      date.grace.default               → effective-date-grace-default          (class=all)
      date.grace.until_next_assessment → effective-date-grace-until_next_assessment (class=all)

    Args:
        entry (dict, required): effective_entry dict from an FRR info block.
            Pass an empty dict (or {}) when the entry is absent.
        scope (str, optional): OSCAL prop class value identifying the cert scope.
            One of 'all' (top-level info.effective), '20x', or 'rev5'. Defaults
            to 'all'.

    Returns:
        list: List of OSCAL prop dicts in the FedRAMP namespace (may be empty).
    """
    if not entry:
        return []
    result = []

    for field in ("is", "current_status", "signup_url"):
        val = entry.get(field)
        if val is not None:
            result.append({"name": f"effective-{field}", "ns": FRR_NS, "class": scope, "value": str(val)})

    for field in ("comments", "warnings"):
        val = entry.get(field)
        if val is not None:
            result.append({
                "name": f"effective-{field}",
                "ns": FRR_NS,
                "class": scope,
                "value": json.dumps(val, ensure_ascii=False),
            })

    date = entry.get("date") or {}
    for field in ("obtain", "maintain", "optional_adoption"):
        val = date.get(field)
        if val is not None:
            result.append({
                "name": f"effective-date-{field}",
                "ns": FRR_NS,
                "class": scope,
                "value": _date_to_datetime(val),
            })

    grace = date.get("grace") or {}
    val = grace.get("default")
    if val is not None:
        result.append({
            "name": "effective-date-grace-default",
            "ns": FRR_NS,
            "class": scope,
            "value": _date_to_datetime(val),
        })
    val = grace.get("until_next_assessment")
    if val is not None:
        result.append({
            "name": "effective-date-grace-until_next_assessment",
            "ns": FRR_NS,
            "class": scope,
            "value": str(val).lower(),
        })

    return result


def _add_extra_parts(catalog: Catalog, ctrl_id: str, rule: dict) -> None:
    """Add remediation and supplemental guidance parts for known extra fields.

    Handles: corrective_actions → remediation part (FedRAMP namespace);
    examples, schema → guidance parts with class and title.
    following_information is handled separately by _add_following_information.

    Uses catalog.add_part() to ensure changes persist in the catalog's internal state.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        ctrl_id (str, required): ID of the control to add parts to.
        rule (dict, required): Rule or class-variant dict from the FRR JSON source.
    """
    ca = rule.get("corrective_actions") or []
    if ca:
        catalog.add_part(ctrl_id, "remediation", ns=FRR_NS, prose="\n\n".join(ca))
    for key in ("examples", "schema"):
        content = rule.get(key)
        if content:
            gp = _guidance_part(key, content)
            catalog.add_part(
                ctrl_id, "guidance",
                title=gp["title"],
                prose=gp["prose"],
                part_class=gp["class"],
            )


# =============================================================================
# Profile tracking helpers
# =============================================================================

def _reset_profile_tracking() -> None:
    """Reset profile control-selection tracking for a fresh catalog build.

    Clears and re-initialises the module-level _PROFILE_FRR and _PROFILE_NIST
    dicts so that repeated calls to build_catalog() start from a clean state.
    """
    global _PROFILE_FRR, _PROFILE_NIST
    _PROFILE_FRR = {name: set() for name in PROFILE_NAMES}
    _PROFILE_NIST = {"Rev5-B": set(), "Rev5-C": set(), "Rev5-D": set()}


def _rev5_ctrl_to_oscal(ctrl_id: str) -> str:
    """Convert a rev5_controls_list entry to a NIST OSCAL control ID.

    Conversion rules applied in order:
    1. Lowercase.
    2. Replace ' (' with '.' (enhancement notation).
    3. Replace bare '(' with '.' (defensive).
    4. Remove ')'.
    5. Remove remaining spaces.
    6. Strip leading zeros from each numeric segment (split on '-' then '.').

    Examples:
        AC-01        → ac-1
        AC-02 (01)   → ac-2.1
        AC-06 (01)   → ac-6.1
        AU-03 (01)   → au-3.1
        AC-17 (01)   → ac-17.1

    Args:
        ctrl_id (str, required): Raw control ID from a rev5_controls_list array.

    Returns:
        str: NIST OSCAL control ID (lowercase, no leading zeros, dot-enhanced).
    """
    s = ctrl_id.lower()
    s = s.replace(" (", ".")
    s = s.replace("(", ".")
    s = s.replace(")", "")
    s = s.replace(" ", "")
    parts = s.split("-")
    result = []
    for part in parts:
        subs = part.split(".")
        stripped = []
        for sp in subs:
            try:
                stripped.append(str(int(sp)))
            except ValueError:
                stripped.append(sp)
        result.append(".".join(stripped))
    return "-".join(result)


def _ctl_id_to_oscal(ctl_id: str) -> str:
    """Convert a CTL section control ID to its NIST OSCAL counterpart.

    Conversion rules applied in order:
    1. Lowercase.
    2. Strip leading zeros from each numeric segment (split on '-').
    3. If a second '-' is present, replace it with '.' (the first dash stays).

    Examples:
        AC-06-01  → ac-6.1
        AC-20     → ac-20
        IA-05     → ia-5
        SA-09-05  → sa-9.5
        CM-12-01  → cm-12.1

    Args:
        ctl_id (str, required): Control ID as it appears in the CTL section
            (e.g. 'AC-06-01').

    Returns:
        str: NIST OSCAL control ID (lowercase, no leading zeros, dot for enhancement).
    """
    parts = ctl_id.lower().split("-")
    result = [parts[0]]
    for p in parts[1:]:
        try:
            result.append(str(int(p)))
        except ValueError:
            result.append(p)
    if len(result) == 3:
        return f"{result[0]}-{result[1]}.{result[2]}"
    return "-".join(result)


def _profile_keys_for(path: str, class_key: str = None) -> list:
    """Return the profile keys that should receive a control given path and class.

    For simple controls (no class_key):
    - path 'all'  → all seven profiles
    - path '20x'  → the four 20X profiles
    - path 'rev5' → the three Rev5 profiles

    For class-variant controls (class_key provided):
    - path 'all'  → matching 20X-{class} and Rev5-{class} (if they exist)
    - path '20x'  → matching 20X-{class} only
    - path 'rev5' → matching Rev5-{class} only

    Args:
        path (str, required): Data scope: 'all', '20x', or 'rev5'.
        class_key (str, optional): Class letter (e.g. 'a', 'b', 'c', 'd').
            When None the control is treated as class-agnostic. Defaults to None.

    Returns:
        list: Profile key strings from PROFILE_NAMES that match the criteria.
    """
    if class_key is None:
        if path == "all":
            return list(PROFILE_NAMES)
        if path == "20x":
            return ["20X-A", "20X-B", "20X-C", "20X-D"]
        return ["Rev5-B", "Rev5-C", "Rev5-D"]

    cls = class_key.upper()
    result = []
    if path in ("all", "20x"):
        key = f"20X-{cls}"
        if key in PROFILE_NAMES:
            result.append(key)
    if path in ("all", "rev5"):
        key = f"Rev5-{cls}"
        if key in PROFILE_NAMES:
            result.append(key)
    return result


def _add_frr_to_profiles(ctrl_id: str, path: str, class_key: str = None) -> None:
    """Register a FedRAMP catalog control ID in the appropriate profiles.

    Adds ctrl_id to the _PROFILE_FRR set for each profile determined by
    _profile_keys_for(path, class_key).

    Args:
        ctrl_id (str, required): OSCAL control identifier from the FedRAMP catalog.
        path (str, required): Data scope: 'all', '20x', or 'rev5'.
        class_key (str, optional): Class letter for a varies_by_class variant.
            Defaults to None (class-agnostic).
    """
    for profile_key in _profile_keys_for(path, class_key):
        _PROFILE_FRR[profile_key].add(ctrl_id)


def _add_nist_to_profiles(ctrl_id: str, path: str, class_key: str = None) -> None:
    """Register a NIST OSCAL control ID in the appropriate Rev5 profiles.

    Converts ctrl_id with _rev5_ctrl_to_oscal(), then adds it to each
    _PROFILE_NIST set determined by _profile_keys_for(path, class_key) that is
    also a Rev5 profile.

    Args:
        ctrl_id (str, required): Raw control ID from a rev5_controls_list entry
            (e.g. 'AC-02 (01)').
        path (str, required): Data scope: 'all', '20x', or 'rev5'.
        class_key (str, optional): Class letter for a varies_by_class variant.
            Defaults to None (class-agnostic).
    """
    oscal_id = _rev5_ctrl_to_oscal(ctrl_id)
    for profile_key in _profile_keys_for(path, class_key):
        if profile_key in _PROFILE_NIST:
            _PROFILE_NIST[profile_key].add(oscal_id)


# =============================================================================
# CTL modify helpers (set-parameters and alter-adds for Rev5 profiles)
# =============================================================================

def _apply_ctl_params(profile: Profile, ctrl_id: str, data: dict) -> None:
    """Apply CTL parameters as set-parameter entries in an OSCAL profile.

    Each entry in data['parameters'] produces one profile.set_parameter() call
    using the parameterId as the OSCAL param-id and value as a single-element
    values list. Entries with a blank parameterId are silently skipped.

    Args:
        profile (Profile, required): The OSCAL profile to mutate.
        ctrl_id (str, required): NIST OSCAL control ID (used for logging only).
        data (dict, required): A CTL control dict or class-variant dict.
    """
    for param in (data.get("parameters") or []):
        pid = (param.get("parameterId") or "").strip()
        val = (param.get("value") or "").strip()
        if pid:
            profile.set_parameter(pid, values=[val] if val else None)


def _apply_ctl_guidance(profile: Profile, ctrl_id: str, data: dict) -> None:
    """Apply CTL guidance strings as an alter.add guidance part in an OSCAL profile.

    Each item in data['guidance'] becomes a line of prose. Lines are joined with
    double newlines. If the list is empty the call is a no-op.

    Args:
        profile (Profile, required): The OSCAL profile to mutate.
        ctrl_id (str, required): NIST OSCAL control ID that the alter targets.
        data (dict, required): A CTL control dict or class-variant dict.
    """
    lines = data.get("guidance") or []
    if not lines:
        return
    prose = "\n\n".join(str(g) for g in lines)
    profile.add_alter_adds(
        ctrl_id,
        position="ending",
        parts=[{"name": "guidance", "prose": prose}],
    )


def _apply_ctl_to_profiles(
    data: dict, tailoring: Profile, rev5_class: dict
) -> list:
    """Process the CTL section and apply modify directives to the right profiles.

    Non-varies controls write set-parameters and guidance alters to the tailoring
    profile. varies_by_class controls write to the matching Rev5 class profile
    (Rev5-B, Rev5-C, or Rev5-D). Returns a sorted list of all parameterId values
    encountered for external validation.

    Args:
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.
        tailoring (Profile, required): The Rev5 tailoring profile to receive
            non-varies CTL modifications.
        rev5_class (dict, required): Mapping of profile key → Profile for the
            three Rev5 class profiles (Rev5-B, Rev5-C, Rev5-D).

    Returns:
        list: Sorted list of unique parameterId strings used across all CTL entries.
    """
    param_ids: set = set()
    ctl = data.get("CTL", {})
    for _fam, controls in ctl.items():
        for ctl_id, ctrl_data in controls.items():
            if not isinstance(ctrl_data, dict):
                continue
            oscal_id = _ctl_id_to_oscal(ctl_id)
            vbc = ctrl_data.get("varies_by_class")
            if vbc:
                for class_key, class_data in vbc.items():
                    target = rev5_class.get(f"Rev5-{class_key.upper()}")
                    if target is None:
                        continue
                    for param in (class_data.get("parameters") or []):
                        pid = (param.get("parameterId") or "").strip()
                        if pid:
                            param_ids.add(pid)
                    _apply_ctl_params(target, oscal_id, class_data)
                    _apply_ctl_guidance(target, oscal_id, class_data)
            else:
                for param in (ctrl_data.get("parameters") or []):
                    pid = (param.get("parameterId") or "").strip()
                    if pid:
                        param_ids.add(pid)
                _apply_ctl_params(tailoring, oscal_id, ctrl_data)
                _apply_ctl_guidance(tailoring, oscal_id, ctrl_data)
    return sorted(param_ids)


def _collect_ctl_param_ids(data: dict) -> list:
    """Return sorted list of parameterId values from the CTL section without modifying any profile.

    Args:
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.

    Returns:
        list: Sorted list of unique parameterId strings found in all CTL entries.
    """
    param_ids: set = set()
    ctl = data.get("CTL", {})
    for _fam, controls in ctl.items():
        for _ctl_id, ctrl_data in controls.items():
            if not isinstance(ctrl_data, dict):
                continue
            vbc = ctrl_data.get("varies_by_class")
            if vbc:
                for class_data in vbc.values():
                    for param in (class_data.get("parameters") or []):
                        pid = (param.get("parameterId") or "").strip()
                        if pid:
                            param_ids.add(pid)
            else:
                for param in (ctrl_data.get("parameters") or []):
                    pid = (param.get("parameterId") or "").strip()
                    if pid:
                        param_ids.add(pid)
    return sorted(param_ids)


def _load_nist_param_ids(refresh: bool = False) -> frozenset:
    """Return the set of parameter IDs present in the NIST SP 800-53 Rev 5 catalog.

    Downloads the catalog on first call (or when refresh=True) and caches it
    locally at NIST_LOCAL. Returns an empty frozenset on any I/O or parse error
    so that callers can still run without aborting.

    Args:
        refresh (bool, optional): Force a fresh download even if a local copy
            exists. Defaults to False.

    Returns:
        frozenset: All 'id' values found on 'param' elements within the catalog.
    """
    has_local = os.path.isfile(NIST_LOCAL)
    if refresh or not has_local:
        os.makedirs(os.path.dirname(NIST_LOCAL), exist_ok=True)
        tmp = NIST_LOCAL + ".tmp"
        _emit(f"Downloading NIST catalog from {NIST_800_53_REV5_URL} ...")
        try:
            urllib.request.urlretrieve(NIST_800_53_REV5_URL, tmp)
            os.replace(tmp, NIST_LOCAL)
            has_local = True
            _emit(f"Saved to {NIST_LOCAL}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            _remove_if_exists(tmp)
            print(f"WARNING: Could not download NIST catalog — {exc}")
            if not has_local:
                return frozenset()

    try:
        with open(NIST_LOCAL, encoding="utf-8") as f:
            nist = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: Could not read NIST catalog — {exc}")
        return frozenset()

    ids: set = set()

    def _collect(obj):
        if isinstance(obj, dict):
            if obj.get("name") == "param" and "id" in obj:
                ids.add(obj["id"])
            # OSCAL JSON: params are under control.params[]
            for param in obj.get("params", []) if isinstance(obj.get("params"), list) else []:
                if isinstance(param, dict) and "id" in param:
                    ids.add(param["id"])
            for v in obj.values():
                _collect(v)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(nist)
    return frozenset(ids)


# =============================================================================
# FRR section builders
# =============================================================================

def _build_frr_simple_control(
    catalog: Catalog, parent_id: str, ctrl_id: str,
    rule: dict, label: str = "", path: str = "all"
) -> None:
    """Create a single OSCAL control from a rule dict.

    All props and links are passed at creation time. Parts (danger, notes,
    assessment-method, remediation, supplemental guidance) are added afterward
    via catalog.add_part() so they persist in the catalog's internal state.
    Registers the control in the appropriate profiles via _add_frr_to_profiles.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent group for this control.
        ctrl_id (str, required): Identifier for the new control (used as id).
        rule (dict, required): Rule data dict from the FRR JSON source.
        label (str, optional): Label prop value. Defaults to ctrl_id.
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.
    """
    label = label or ctrl_id

    props = [{"name": "path", "value": path, "ns": FRR_NS}]
    if rule.get("force"):
        props.append({"name": "force", "value": rule["force"], "ns": FRR_NS})
    for affect in (rule.get("affects") or []):
        props.append({"name": "affects", "value": affect, "ns": FRR_NS})
    props.extend(_updated_props(rule))
    props.extend(_extension_props(rule))

    links = [
        {"rel": "related", "href": f"#{rid}"}
        for rid in (rule.get("related") or [])
    ]
    links.extend(_reference_link(rule))
    links.extend(_nist_control_links(rule))

    danger = rule.get("danger", "")
    statement = rule.get("statement", "")
    title = rule.get("name") or label

    control = catalog.create_control(
        parent_id=parent_id,
        id=ctrl_id,
        title=title,
        label=label,
        statements=[statement] if statement else [],
        props=props,
        links=links,
    )
    if control is None:
        return

    _STATS["controls"] += 1
    _emit_dot()
    _add_frr_to_profiles(ctrl_id, path)

    if danger:
        catalog.add_part(ctrl_id, "guidance", title="Danger", prose=danger)

    notes = _notes_text(rule)
    if notes:
        catalog.add_part(ctrl_id, "guidance", title="Notes", prose=notes)

    fi = rule.get("following_information")
    if fi:
        _add_following_information(catalog, ctrl_id, fi)

    fib = rule.get("following_information_bullets")
    if fib:
        _add_following_information_bullets(catalog, ctrl_id, fib)

    _add_artifact_parts(catalog, ctrl_id, rule.get("artifacts") or {})
    _add_extra_parts(catalog, ctrl_id, rule)

    _track_unhandled(rule, _HANDLED_RULE_KEYS)


def _build_frr_varies_control(
    catalog: Catalog, parent_id: str, rule_id: str, rule: dict, path: str = "all"
) -> None:
    """Create a parent control for a varies_by_class rule with class-variant child controls.

    The parent control carries 'Varies by Class' as its statement prose. Each
    class variant is created as a nested child control via catalog.create_control()
    with parent_id=rule_id, so all mutations persist in the catalog's internal state.
    Each successfully created class-variant child is registered in the appropriate
    profiles via _add_frr_to_profiles.

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
    links.extend(_reference_link(rule))
    links.extend(_nist_control_links(rule))
    props = [{"name": "path", "value": path, "ns": FRR_NS}]
    for affect in (rule.get("affects") or []):
        props.append({"name": "affects", "value": affect, "ns": FRR_NS})
    props.extend(_updated_props(rule))
    props.extend(_extension_props(rule))

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
        catalog.add_part(rule_id, "guidance", title="Notes", prose=notes)

    fi = rule.get("following_information")
    if fi:
        _add_following_information(catalog, rule_id, fi)

    fib = rule.get("following_information_bullets")
    if fib:
        _add_following_information_bullets(catalog, rule_id, fib)

    _add_extra_parts(catalog, rule_id, rule)

    for class_key, class_data in rule["varies_by_class"].items():
        child_id = f"{rule_id}-{class_key}"
        class_label = f"Class {class_key.upper()}"

        child_props = [{"name": "path", "value": path, "ns": FRR_NS}]
        if class_data.get("force"):
            child_props.append({"name": "force", "value": class_data["force"], "ns": FRR_NS})
        child_props.extend(_extension_props(class_data))
        child_links = [
            {"rel": "related", "href": f"#{rid}"}
            for rid in (class_data.get("related") or [])
        ]

        child_ctrl = catalog.create_control(
            parent_id=rule_id,
            id=child_id,
            title=class_label,
            label=class_label,
            statements=[class_data["statement"]] if class_data.get("statement") else [],
            props=child_props,
            links=child_links,
        )
        if child_ctrl is None:
            continue

        _STATS["controls"] += 1
        _emit_dot()
        _add_frr_to_profiles(child_id, path, class_key)

        child_notes = _notes_text(class_data)
        if child_notes:
            catalog.add_part(child_id, "guidance", title="Notes", prose=child_notes)

        child_fi = class_data.get("following_information")
        if child_fi:
            _add_following_information(catalog, child_id, child_fi)

        child_fib = class_data.get("following_information_bullets")
        if child_fib:
            _add_following_information_bullets(catalog, child_id, child_fib)

        _add_artifact_parts(catalog, child_id, class_data.get("artifacts") or {})
        _add_extra_parts(catalog, child_id, class_data)

        for fam_ids in (class_data.get("rev5_controls_list") or {}).values():
            for raw_id in fam_ids:
                _add_nist_to_profiles(raw_id, path, class_key)

        _track_unhandled(class_data, _HANDLED_CLASS_KEYS)

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
    subset_key: str, subset_val: dict, path: str = "all",
    existing_groups: set | None = None,
) -> None:
    """Populate a subset group with controls from one FRR data scope entry.

    Controls from all scopes ('all', '20x', 'rev5') are added to the same group
    (id 'FRR-{frr_key}-{subset_key}'). The scope is recorded as a 'path' prop on
    each control. The target group is expected to exist already, having been created
    by _build_frr_subset_groups(). If it was not pre-created (i.e., subset_key was
    absent from info.subsets), a minimal fallback group is created and its ID is
    added to existing_groups to prevent duplicate creation on subsequent scope passes.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent FRR ruleset group.
        frr_key (str, required): Top-level FRR key (e.g. 'AFC').
        subset_key (str, required): Subset key within the scope (e.g. 'FRP').
        subset_val (dict, required): Subset data dict (keyed by rule ID or 'info').
        path (str, optional): Data scope ('all', '20x', or 'rev5'). Defaults to 'all'.
        existing_groups (set | None, optional): Group IDs already created by
            _build_frr_subset_groups(). Updated in-place when a fallback group is
            created so subsequent scope passes for the same key skip re-creation.
            Defaults to None (treated as empty set).
    """
    if existing_groups is None:
        existing_groups = set()

    base_id = f"FRR-{frr_key}-{subset_key}"

    if base_id not in existing_groups:
        info = subset_val.get("info", {})
        purpose = info.get("purpose", "")
        new_group = catalog.create_control_group(
            parent_id=parent_id,
            id=base_id,
            title=base_id,
            overview=purpose,
        )
        if new_group is None:
            return
        _STATS["groups"] += 1
        existing_groups.add(base_id)

    _emit(f"  {base_id} ", end="")
    for rule_id, rule in subset_val.items():
        if rule_id == "info" or not isinstance(rule, dict):
            continue
        _build_frr_control(catalog, base_id, rule_id, rule, path=path)
    _emit()


def _build_frr_subset_groups(
    catalog: Catalog, group_id: str, info: dict
) -> set:
    """Create a child group for each entry in info['subsets'].

    Each subset entry becomes an OSCAL group whose title is 'SUBSET: {name}'.
    The optional 'description' field populates an 'overview' part. Applicability
    fields (types, paths, classes, affects) are stored as FedRAMP-namespace props.
    These groups establish the container structure that _build_frr_subset() later
    fills with controls.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        group_id (str, required): ID of the parent ruleset group (e.g. 'FRR-AFC').
        info (dict, required): The 'info' block from an FRR ruleset dict.

    Returns:
        set: IDs of the subset groups successfully created.
    """
    subsets = info.get("subsets") or {}
    created: set = set()
    for subset_key, subset_meta in subsets.items():
        if not isinstance(subset_meta, dict):
            continue
        child_id = f"{group_id}-{subset_key}"
        title = subset_meta.get('name', subset_key)
        description = subset_meta.get("description", "")
        applicability = subset_meta.get("applicability") or {}

        props: list = []
        for atype in (applicability.get("types") or []):
            props.append({"name": "applicability-type", "value": atype, "ns": FRR_NS})
        for apath in (applicability.get("paths") or []):
            props.append({"name": "applicability-path", "value": apath, "ns": FRR_NS})
        for aclass in (applicability.get("classes") or []):
            props.append({"name": "applicability-class", "value": aclass, "ns": FRR_NS})
        for affect in (applicability.get("affects") or []):
            props.append({"name": "affects", "value": affect, "ns": FRR_NS})

        child_group = catalog.create_control_group(
            parent_id=group_id,
            id=child_id,
            title=title,
            props=props,
            overview=description,
        )
        if child_group is None:
            continue
        _STATS["groups"] += 1
        created.add(child_id)

    return created


def _infer_group_label(rule_ids: list) -> str | None:
    """Infer a group label from control IDs by stripping their trailing sequence segment.

    Expects each rule ID to have the form ``PREFIX-NNN`` (e.g. ``CDM-AGM-001``).
    Returns the common prefix if every ID in the list agrees; returns None if the
    list is empty, if any ID has no hyphen, or if IDs disagree on the prefix.

    Args:
        rule_ids (list, required): Control IDs from the group's controls.

    Returns:
        str | None: The inferred label prefix, or None if it cannot be determined.
    """
    if not rule_ids:
        return None
    prefixes = set()
    for rid in rule_ids:
        if "-" not in rid:
            return None
        prefixes.add(rid.rsplit("-", 1)[0])
    return prefixes.pop() if len(prefixes) == 1 else None


def _set_group_label(catalog: Catalog, group_id: str, label: str) -> None:
    """Add or update the label prop on an existing catalog group.

    Navigates ``catalog._dict`` directly because no public API exists for
    post-creation prop updates on groups.  Inserts the label prop at position 0
    so it appears first in the props list, consistent with how
    ``create_control_group`` builds new groups with labels.

    Args:
        catalog (Catalog, required): The OSCAL catalog containing the group.
        group_id (str, required): ID of the group to update.
        label (str, required): Label value to set.
    """
    root_groups = catalog._dict.get("catalog", {}).get("groups", [])

    def _find(groups: list) -> dict | None:
        for g in groups:
            if g.get("id") == group_id:
                return g
            found = _find(g.get("groups", []))
            if found is not None:
                return found
        return None

    group = _find(root_groups)
    if group is None:
        return
    props = group.setdefault("props", [])
    for p in props:
        if p.get("name") == "label":
            p["value"] = label
            return
    props.insert(0, {"name": "label", "value": label})


def _add_catalog_contacts(catalog: Catalog) -> None:
    """Add roles, parties, and responsible-parties to the catalog metadata.

    Creates four roles (fedramp, system-owner, assessor, agency), four matching
    parties (FedRAMP PMO, Cloud Service Provider, Assessing Organization,
    Federal Agency), and four responsible-party entries linking each role to its
    party.  Party UUIDs are stable module-level constants.

    Args:
        catalog (Catalog, required): The OSCAL catalog to annotate.
    """
    roles = [
        {"id": "fedramp",      "title": "FedRAMP"},
        {"id": "system-owner", "title": "System Owner"},
        {"id": "assessor",     "title": "Assessor"},
        {"id": "agency",       "title": "Agency"},
    ]
    for role in roles:
        catalog.append_child("metadata/roles", role)

    parties = [
        {
            "uuid": _PARTY_UUID_FEDRAMP,
            "type": "organization",
            "name": "FedRAMP PMO",
            "email-addresses": ["info@fedramp.gov"],
            "links": [{"rel": "website", "href": "https://www.fedramp.gov"}],
        },
        {"uuid": _PARTY_UUID_CSP,    "type": "organization", "name": "Cloud Service Provider"},
        {"uuid": _PARTY_UUID_AO,     "type": "organization", "name": "Assessing Organization"},
        {"uuid": _PARTY_UUID_AGENCY, "type": "organization", "name": "Federal Agency"},
    ]
    for party in parties:
        catalog.append_child("metadata/parties", party)

    resp_parties = [
        {"role-id": "fedramp",      "party-uuids": [_PARTY_UUID_FEDRAMP]},
        {"role-id": "system-owner", "party-uuids": [_PARTY_UUID_CSP]},
        {"role-id": "assessor",     "party-uuids": [_PARTY_UUID_AO]},
        {"role-id": "agency",       "party-uuids": [_PARTY_UUID_AGENCY]},
    ]
    for rp in resp_parties:
        catalog.append_child("metadata/responsible-parties", rp)


def _assert_single_status_prop(props: list, control_id: str) -> None:
    """Raise RuntimeError if a control's props list contains more than one 'status' entry.

    This guard is intended for OSCAL controls only. Multiple status props on a
    single control indicate a logic error where two separate code paths both
    attempted to set status.

    Args:
        props (list, required): The props list of the OSCAL control to inspect.
        control_id (str, required): ID of the control, used in the error message.

    Returns:
        None

    Raises:
        RuntimeError: If more than one prop with name='status' is found.
    """
    count = sum(1 for p in props if p.get("name") == "status")
    if count > 1:
        raise RuntimeError(
            f"Control '{control_id}' has {count} 'status' props; expected at most 1."
        )


def _flow_to_mermaid(flow: dict) -> str:
    """Convert a single flow dict to a Mermaid flowchart string.

    The ``nodes`` dict maps node names to types ('start', 'end', 'decision',
    'process'). Each type is translated to the corresponding Mermaid node shape.
    The ``steps`` list provides directed edges; the optional ``description``
    field on each step becomes an edge label. Nodes referenced in steps but
    absent from ``nodes`` are emitted as unlabelled rectangles. Node names are
    mapped to short safe IDs (N0, N1, …) so that spaces and punctuation in the
    original names do not break the Mermaid syntax.

    Args:
        flow (dict, required): A single flow object from an FRR info.flows array.

    Returns:
        str: Mermaid flowchart source text (``flowchart TD`` direction).
    """
    _shape = {
        "start":    ("([", "])"),
        "end":      ("([", "])"),
        "decision": ("{",  "}"),
        "process":  ("[",  "]"),
    }

    nodes: dict = flow.get("nodes") or {}
    steps: list = flow.get("steps") or []

    node_ids: dict[str, str] = {}
    for i, name in enumerate(nodes):
        node_ids[name] = f"N{i}"
    idx = len(node_ids)
    for step in steps:
        for key in ("from", "to"):
            name = (step.get(key) or "").strip()
            if name and name not in node_ids:
                node_ids[name] = f"N{idx}"
                idx += 1

    lines = ["flowchart TD"]

    declared: set = set()
    for node_name, node_type in nodes.items():
        sid = node_ids[node_name]
        ob, cb = _shape.get(node_type, ("[", "]"))
        label = node_name.replace('"', "#quot;")
        lines.append(f'    {sid}{ob}"{label}"{cb}')
        declared.add(node_name)

    for step in steps:
        for key in ("from", "to"):
            name = (step.get(key) or "").strip()
            if name and name not in declared:
                sid = node_ids[name]
                label = name.replace('"', "#quot;")
                lines.append(f'    {sid}["{label}"]')
                declared.add(name)

    seen: set = set()
    for step in steps:
        from_name = (step.get("from") or "").strip()
        to_name   = (step.get("to")   or "").strip()
        if not from_name or not to_name:
            continue
        desc = (step.get("description") or "").strip()
        from_id = node_ids.get(from_name, "")
        to_id   = node_ids.get(to_name,   "")
        if not from_id or not to_id:
            continue
        if desc:
            escaped = desc.replace('"', "#quot;")
            edge = f'    {from_id} -->|"{escaped}"| {to_id}'
        else:
            edge = f'    {from_id} --> {to_id}'
        if edge not in seen:
            lines.append(edge)
            seen.add(edge)

    return "\n".join(lines)


def _mermaid_to_svg(mermaid_text: str) -> str | None:
    """Render Mermaid diagram source to SVG via the mermaid.ink public API.

    Encodes the source as base64url and calls MERMAID_INK_URL. Returns the
    raw SVG string on success, or None on any network or HTTP error.

    Args:
        mermaid_text (str, required): Mermaid source text (e.g. from _flow_to_mermaid).

    Returns:
        str | None: SVG markup string, or None if rendering failed.
    """
    encoded = base64.urlsafe_b64encode(mermaid_text.encode("utf-8")).decode("ascii")
    url = MERMAID_INK_URL.format(encoded=encoded)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "frr2oscal/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        print(f"WARNING: Could not render Mermaid diagram — {exc}")
        return None


def _add_flow_resources(
    catalog: Catalog, flows: list, frr_key: str, scope: str = ""
) -> list:
    """Convert a flows list to SVG back-matter resources and return diagram link dicts.

    For each flow, the JSON is converted to Mermaid text, rendered to SVG via
    _mermaid_to_svg, and stored as a base64-encoded back-matter resource.  A
    link dict with rel='diagram' is collected for each successfully rendered
    flow and returned for the caller to attach to the parent group.

    Resource UUIDs are derived deterministically from the FRR key, scope, and
    flow index so that repeated runs produce stable catalogs.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        flows (list, required): The flows array from an FRR info (or cert) block.
        frr_key (str, required): Top-level FRR key (e.g. 'AFC'), used in filenames.
        scope (str, optional): Cert scope qualifier ('20x' or 'rev5') used in
            filenames. Empty string for the top-level info block. Defaults to ''.

    Returns:
        list: OSCAL link dicts (rel='diagram', href='#uuid', text=activity) for
            each flow that was successfully rendered; may be empty.
    """
    if not flows:
        return []

    file_prefix = f"FRR-{frr_key}-{scope}-" if scope else f"FRR-{frr_key}-"
    links: list = []

    for i, flow in enumerate(flows):
        activity    = (flow.get("activity") or f"Flow {i + 1}").strip()
        description = (flow.get("description") or "").strip()

        mermaid_text = _flow_to_mermaid(flow)
        svg = _mermaid_to_svg(mermaid_text)
        if svg is None:
            continue

        resource_uuid = str(uuid.uuid5(_FLOW_UUID_NAMESPACE, f"{frr_key}/{scope}/{i}"))
        b64_value     = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        filename      = f"{file_prefix}flow-{i + 1}.svg"

        catalog.append_resource(
            uuid=resource_uuid,
            title=activity,
            description=description,
        )
        # append_resource does not yet support base64 payloads; inject directly.
        catalog._dict[catalog.model]["back-matter"]["resources"][-1]["base64"] = {
            "filename":   filename,
            "media-type": "image/svg+xml",
            "value":      b64_value,
        }

        links.append({
            "rel":  "diagram",
            "href": f"#{resource_uuid}",
            "text": activity,
        })

    return links


def _build_frr_ruleset(
    catalog: Catalog, frr_key: str, frr_val: dict
) -> None:
    """Create a top-level group for one FRR ruleset and populate its children.

    The purpose overview part is added via catalog.add_part() with its title set
    directly, so it persists in the catalog's internal state.

    The group's label prop is set to info.short_name (the abbreviated ruleset
    code). If status, web_name, or tag values are present in info, each is
    stored as a FedRAMP-namespace prop.  Each entry in info.subsets becomes a
    child group via _build_frr_subset_groups, establishing the container structure
    before data controls are added.

    Flows (info.flows, info.20x.flows, info.rev5.flows) are converted to Mermaid
    diagrams, rendered to SVG via _mermaid_to_svg, and stored as base64-encoded
    back-matter resources.  A link with rel='diagram' for each successfully
    rendered flow is attached to the group.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        frr_key (str, required): Top-level FRR key (e.g. 'AFC').
        frr_val (dict, required): FRR ruleset dict containing 'info' and 'data'.
    """
    group_id = f"FRR-{frr_key}"
    info = frr_val.get("info", {})
    title = info.get("name", frr_key)
    purpose = info.get("purpose", "")
    short_name = info.get("short_name", frr_key)
    status   = info.get("status", "")
    web_name = info.get("web_name", "")
    tag      = info.get("tag", "")

    extra_props: list = []
    if status:
        extra_props.append({"name": "status",   "ns": FRR_NS, "value": status})
    if web_name:
        extra_props.append({"name": "web_name", "ns": FRR_NS, "value": web_name})
    if tag:
        extra_props.append({"name": "tag",      "ns": FRR_NS, "value": tag})

    extra_props.extend(_effective_entry_props(info.get("effective") or {}))
    extra_props.extend(_effective_entry_props(
        (info.get("20x") or {}).get("effective") or {}, scope="twentyx"
    ))
    extra_props.extend(_effective_entry_props(
        (info.get("rev5") or {}).get("effective") or {}, scope="rev5"
    ))

    flow_links: list = []
    flow_links.extend(_add_flow_resources(catalog, info.get("flows") or [], frr_key))
    flow_links.extend(_add_flow_resources(
        catalog, (info.get("20x") or {}).get("flows") or [], frr_key, scope="twentyx"
    ))
    flow_links.extend(_add_flow_resources(
        catalog, (info.get("rev5") or {}).get("flows") or [], frr_key, scope="rev5"
    ))

    group = catalog.create_control_group(
        parent_id="[root]",
        id=group_id,
        title=title,
        label=short_name,
        props=extra_props,
        links=flow_links,
    )
    if group is None:
        return

    _STATS["groups"] += 1
    if purpose:
        catalog.add_part(group_id, "overview", title="Purpose", prose=purpose)

    created_subset_groups = _build_frr_subset_groups(catalog, group_id, info)

    _emit(f"\n{title}")
    data_block = frr_val.get("data", {})
    for scope in ("all", "20x", "rev5"):
        for subset_key, subset_val in data_block.get(scope, {}).items():
            _build_frr_subset(
                catalog, group_id, frr_key, subset_key, subset_val,
                path=scope, existing_groups=created_subset_groups,
            )

    # Infer and assign labels for 2nd-level (subset) groups from control IDs.
    subset_rule_ids: dict = {}
    for scope in ("all", "20x", "rev5"):
        for subset_key, subset_val in data_block.get(scope, {}).items():
            rule_ids = [
                rid for rid, v in subset_val.items()
                if rid != "info" and isinstance(v, dict)
            ]
            subset_rule_ids.setdefault(subset_key, []).extend(rule_ids)

    for subset_key, rule_ids in subset_rule_ids.items():
        base_id = f"FRR-{frr_key}-{subset_key}"
        inferred = _infer_group_label(rule_ids)
        if inferred:
            _set_group_label(catalog, base_id, inferred)
        elif rule_ids:
            print(
                f"WARNING: Cannot infer label for group {base_id} — "
                f"control IDs do not share a common prefix: {rule_ids[:5]!r}"
            )


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


# =============================================================================
# KSI section builders
# =============================================================================

def _build_ksi_indicator(
    catalog: Catalog, parent_id: str, ind_id: str, ind_data: dict
) -> None:
    """Create an OSCAL control for a single KSI indicator.

    Simple indicators become a single control added to all four 20X profiles.
    Indicators with varies_by_class become a parent control (added to all four
    20X profiles) whose class-variant children are added only to the matching
    20X profile (e.g. class 'b' → 20X-B).

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        parent_id (str, required): ID of the parent KSI sub-group.
        ind_id (str, required): Indicator identifier (e.g. 'KSI-CED-RAT').
        ind_data (dict, required): Indicator data dict from the KSI section.
    """
    name = ind_data.get("name", ind_id)
    statement = ind_data.get("statement", "")
    props = _updated_props(ind_data)
    vbc = ind_data.get("varies_by_class")

    if vbc:
        parent_ctrl = catalog.create_control(
            parent_id=parent_id,
            id=ind_id,
            title=name,
            label=ind_id,
            statements=["Varies by Class"],
            props=props,
        )
        if parent_ctrl is None:
            return

        _STATS["controls"] += 1
        _emit_dot()
        _add_frr_to_profiles(ind_id, "20x")

        for class_key, class_data in vbc.items():
            child_id = f"{ind_id}-{class_key}"
            class_label = f"Class {class_key.upper()}"
            child_stmt = class_data.get("statement", "")

            child_ctrl = catalog.create_control(
                parent_id=ind_id,
                id=child_id,
                title=class_label,
                label=class_label,
                statements=[child_stmt] if child_stmt else [],
            )
            if child_ctrl is None:
                continue

            _STATS["controls"] += 1
            _emit_dot()
            _add_frr_to_profiles(child_id, "20x", class_key)
    else:
        ctrl = catalog.create_control(
            parent_id=parent_id,
            id=ind_id,
            title=name,
            label=ind_id,
            statements=[statement] if statement else [],
            props=props,
        )
        if ctrl is None:
            return

        _STATS["controls"] += 1
        _emit_dot()
        _add_frr_to_profiles(ind_id, "20x")


def _build_ksi(catalog: Catalog, data: dict) -> None:
    """Populate the catalog with KSI groups and indicator controls.

    Creates a root-level 'KSI' group, then one sub-group per KSI category
    (e.g. 'KSI-CED'), and finally one control per indicator. All KSI indicators
    are registered in the four 20X profiles and none of the Rev5 profiles.

    Args:
        catalog (Catalog, required): The OSCAL catalog being built.
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.
    """
    ksi = data.get("KSI", {})
    if not ksi:
        return

    _emit("\n" + "=" * 72)
    _emit("KSI — Key Security Indicators")
    _emit("=" * 72)

    root_group = catalog.create_control_group(
        parent_id="[root]",
        id="KSI",
        title="Key Security Indicators",
        label="KSI",
    )
    if root_group is None:
        return
    _STATS["groups"] += 1

    for ksi_key, ksi_val in ksi.items():
        group_id = ksi_val.get("id") or f"KSI-{ksi_key}"
        title = ksi_val.get("name", ksi_key)

        subgroup = catalog.create_control_group(
            parent_id="KSI",
            id=group_id,
            title=title,
            label=group_id,
        )
        if subgroup is None:
            continue
        _STATS["groups"] += 1

        _emit(f"\n{title} ", end="")
        for ind_id, ind_data in ksi_val.get("indicators", {}).items():
            _build_ksi_indicator(catalog, group_id, ind_id, ind_data)
        _emit()


# =============================================================================
# Catalog builder
# =============================================================================

def build_catalog(data: dict, details: dict | None = None) -> Catalog:
    """Create an OSCAL Catalog from the FedRAMP consolidated-rules JSON.

    Resets profile tracking state, then populates the catalog with FRR rules
    (all scopes) and KSI indicators. NIST SP 800-53 Rev 5 control IDs for the
    Rev5 profiles are registered inline during FRR build whenever a class-variant
    rule contains a rev5_controls_list field. Returns the completed catalog.

    Args:
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON.
        details (dict, optional): Provenance dict with ``github_last_modified``
            and ``acquired`` keys as returned by :func:`load_rules`.  When
            provided the values are appended to ``metadata.remarks``.
            Defaults to None.

    Returns:
        Catalog: The populated OSCAL catalog.
    """
    details = details or {}

    global _STATS
    _STATS = {"groups": 0, "controls": 0}
    _reset_profile_tracking()

    info = data.get("info", {})
    title        = info.get("title", "FedRAMP Consolidated Rules")
    version      = info.get("version", "")
    description  = info.get("description", "")
    published    = _date_to_datetime(info.get("last_updated", ""))
    now          = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    provenance_lines = []
    if details.get("github_last_modified"):
        provenance_lines.append(
            f"Last published update from the FedRAMP PMO {details['github_last_modified']}"
        )
    if details.get("acquired"):
        provenance_lines.append(f"Acquired {details['acquired']}")
    provenance = "\n".join(provenance_lines)
    remarks = "\n\n".join(filter(None, [description, provenance]))

    catalog = Catalog.new(title=title, version=version)

    catalog.set_metadata({
        "title":         title,
        "version":       version,
        "remarks":       remarks,
        "published":     published,
        "last-modified": now,
    })
    catalog.append_child("metadata/links", {"href": SOURCE_URL, "rel": "canonical"})
    catalog.append_child("metadata/links", {"href": ALTERNATE_URL, "rel": "alternate"})
    catalog.append_child("metadata/props", {"name": "presentation-id", "ns": CYBERCRAFT_NAMESPACE, "value": "fedramp-cr26"})
    _add_catalog_contacts(catalog)

    catalog.append_resource(
        uuid=_NIST_800_53_REV5_RESOURCE_UUID,
        title="NIST SP 800-53 Rev 5",
        rlinks=[
            {"href": NIST_800_53_REV5_URL},
            {"href": NIST_800_53_REV5_DOI_URL},
        ],
    )

    _build_frr(catalog, data)
    _build_ksi(catalog, data)

    return catalog


# =============================================================================
# Profile builder
# =============================================================================

def build_profiles(data: dict, details: dict | None = None) -> dict:
    """Create seven OSCAL profiles from the accumulated profile tracking state.

    Must be called after build_catalog() so that _PROFILE_FRR and _PROFILE_NIST
    are populated. Returns a dict mapping profile name → Profile instance.

    Profile layout:
    - 20X-A, 20X-B, 20X-C, 20X-D: import the FedRAMP catalog (CATALOG_HREF)
      with the control IDs registered for that profile.
    - Rev5-B, Rev5-C, Rev5-D: import the FedRAMP catalog AND the NIST SP 800-53
      Rev 5 catalog (NIST_800_53_REV5_URL) with the IDs registered for each.

    Args:
        data (dict, required): The full parsed FedRAMP consolidated-rules JSON,
            used to populate profile metadata (version, published).
        details (dict, optional): Provenance dict with ``github_last_modified``
            and ``acquired`` keys as returned by :func:`load_rules`.  When
            provided the values are written to each profile's ``metadata.remarks``.
            Defaults to None.

    Returns:
        dict: Mapping of profile name (str) to Profile instance.
    """
    details = details or {}

    info = data.get("info", {})
    version   = info.get("version", "")
    published = _date_to_datetime(info.get("last_updated", ""))
    now       = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    provenance_lines = []
    if details.get("github_last_modified"):
        provenance_lines.append(
            f"Last published update from the FedRAMP PMO {details['github_last_modified']}"
        )
    if details.get("acquired"):
        provenance_lines.append(f"Acquired {details['acquired']}")
    provenance = "\n".join(provenance_lines)

    profile_titles = {
        "20X-A":  "FedRAMP 20X — Class A",
        "20X-B":  "FedRAMP 20X — Class B",
        "20X-C":  "FedRAMP 20X — Class C",
        "20X-D":  "FedRAMP 20X — Class D",
        "Rev5-B": "FedRAMP Rev 5 — Class B",
        "Rev5-C": "FedRAMP Rev 5 — Class C",
        "Rev5-D": "FedRAMP Rev 5 — Class D",
    }

    profiles = {}

    def _make_profile(key: str, title: str) -> Profile:
        p = Profile.new(title=title, version=version)
        meta = {
            "title":         title,
            "version":       version,
            "published":     published,
            "last-modified": now,
        }
        if provenance:
            meta["remarks"] = provenance
        p.set_metadata(meta)
        p.append_child("metadata/links", {"href": SOURCE_URL, "rel": "canonical"})
        p.append_child("metadata/links", {"href": ALTERNATE_URL, "rel": "alternate"})
        p.append_child("metadata/props", {"name": "presentation-id", "ns": CYBERCRAFT_NAMESPACE, "value": "fedramp-cr26"})
        return p

    def _set_frr_import(p: Profile, key: str) -> None:
        frr_ids = sorted(_PROFILE_FRR.get(key, set()))
        p.add_import(CATALOG_HREF, title="FedRAMP Consolidated Rules OSCAL Catalog")
        if frr_ids:
            p.set_import_selection(CATALOG_HREF, include_controls=[{"with-ids": frr_ids}])
        else:
            p.set_import_selection(CATALOG_HREF, include_all={})

    # --- 20X profiles: import FedRAMP catalog only ---
    for key in ("20X-A", "20X-B", "20X-C", "20X-D"):
        p = _make_profile(key, profile_titles[key])
        _set_frr_import(p, key)
        profiles[key] = p

    # --- Rev5 Tailoring profile ---
    # Imports the NIST catalog with the union of all Rev5 class control IDs.
    # Carries all non-varies CTL set-parameters and guidance alters.
    nist_union = sorted(
        _PROFILE_NIST.get("Rev5-B", set())
        | _PROFILE_NIST.get("Rev5-C", set())
        | _PROFILE_NIST.get("Rev5-D", set())
    )
    tailoring = _make_profile(TAILORING_PROFILE_NAME, "FedRAMP Rev 5 — Tailoring")
    tailoring.add_import(NIST_800_53_REV5_URL, title="NIST SP 800-53 Revision 5")
    if nist_union:
        tailoring.set_import_selection(
            NIST_800_53_REV5_URL,
            include_controls=[{"with-ids": nist_union}],
        )
    else:
        tailoring.set_import_selection(NIST_800_53_REV5_URL, include_all={})
    profiles[TAILORING_PROFILE_NAME] = tailoring

    # --- Rev5 class profiles: import FedRAMP catalog + tailoring profile ---
    # The tailoring profile replaces the direct NIST catalog import so that
    # FedRAMP's set-parameters and guidance alters are included automatically.
    for key in ("Rev5-B", "Rev5-C", "Rev5-D"):
        p = _make_profile(key, profile_titles[key])
        _set_frr_import(p, key)

        nist_ids = sorted(_PROFILE_NIST.get(key, set()))
        p.add_import(TAILORING_HREF, title="FedRAMP Rev 5 Tailoring Profile")
        if nist_ids:
            p.set_import_selection(TAILORING_HREF, include_controls=[{"with-ids": nist_ids}])
        else:
            p.set_import_selection(TAILORING_HREF, include_all={})

        profiles[key] = p

    # --- Apply CTL modify directives ---
    rev5_class = {k: profiles[k] for k in ("Rev5-B", "Rev5-C", "Rev5-D")}
    _apply_ctl_to_profiles(data, tailoring, rev5_class)

    return profiles


# =============================================================================
# Entry point
# =============================================================================

def main() -> None:
    """Parse CLI arguments, build the catalog and profiles, and write output files."""
    global _VERBOSE

    parser = argparse.ArgumentParser(
        description="Convert FedRAMP consolidated rules to an OSCAL catalog and profiles."
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

    result = load_rules(refresh=args.refresh)
    if result is None:
        sys.exit(1)
    data, details = result

    print_metadata(data)

    catalog = build_catalog(data, details)

    _emit("\n" + "=" * 72)
    _emit("Summary")
    _emit(f"  Groups:   {_STATS['groups']}")
    _emit(f"  Controls: {_STATS['controls']}")
    _emit("=" * 72)

    _emit()
    for fmt in CATALOG_FORMATS:
        path = f"{CATALOG_OUTPUT_STEM}.{fmt}"
        if catalog.dump(path, format=fmt, pretty_print=True):
            _emit(f"Catalog written to:  {path}")
        else:
            print(f"ERROR: Failed to write catalog to: {path}")

    profiles = build_profiles(data, details)
    for profile_key, profile in profiles.items():
        for fmt in PROFILE_FORMATS:
            path = f"{PROFILE_OUTPUT_STEM}{profile_key}.{fmt}"
            if profile.dump(path, format=fmt, pretty_print=True):
                _emit(f"Profile written to:  {path}")
            else:
                print(f"ERROR: Failed to write profile to: {path}")

    # Validate CTL parameter IDs against the NIST SP 800-53 catalog.
    _emit()
    param_ids_used = _collect_ctl_param_ids(data)
    nist_param_ids = _load_nist_param_ids(refresh=args.refresh)
    if nist_param_ids:
        missing = sorted(p for p in param_ids_used if p not in nist_param_ids)
        _emit("=" * 72)
        _emit("CTL Parameter ID Validation")
        _emit(f"  Parameters used:      {len(param_ids_used)}")
        _emit(f"  Not found in catalog: {len(missing)}")
        if missing:
            _emit("  Missing IDs:")
            for pid in missing:
                _emit(f"    {pid}")
        else:
            _emit("  All parameter IDs validated successfully.")
        _emit("=" * 72)
    else:
        _emit("WARNING: NIST catalog unavailable — CTL parameter IDs not validated.")

    if UNHANDLED:
        with open(UNHANDLED_OUTPUT, "w", encoding="utf-8") as fh:
            json.dump(UNHANDLED, fh, indent=2)
        _emit(f"Unhandled keys written to: {UNHANDLED_OUTPUT}")


if __name__ == "__main__":
    main()
