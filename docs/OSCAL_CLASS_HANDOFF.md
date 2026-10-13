# OSCAL Class Library — Handoff: Issues Found in `package2oscal.py`

This document describes issues found in the `oscal` library (version 3.2.2) while
building `src/package2oscal.py`. Each issue is concrete and blocking (or was worked
around with fragile in-place mutation). The priority column indicates impact on
`package2oscal`.

---

## Issue 1 — `new()` fails for SSP, AssessmentResults, AssessmentPlan, POAM (BUG — HIGH)

**Symptom:** Calling `SSP.new(title)`, `AssessmentResults.new(title)`,
`AssessmentPlan.new(title)`, or `POAM.new(title)` returns an empty, non-editable
instance. `is_editable` is `False`, `is_well_formed` is `False`, `_dict` is `None`,
and all mutation methods (`append_child`, `put`, `append_component`, etc.) silently
do nothing.

**Root cause:** `OSCAL.new()` derives the template filename as
`cls.__name__.lower()`. The class names (`SSP`, `AssessmentResults`,
`AssessmentPlan`, `POAM`) do not match the canonical OSCAL model names
(`system-security-plan`, `assessment-results`, `assessment-plan`,
`plan-of-action-and-milestones`). The lookup fails; `create_new_oscal_content()`
returns `None`; the fallback branch creates an empty uninitialised instance.
`Catalog` and `Profile` are unaffected because their class names match their
model names.

**Observed mapping mismatch:**

| Class | `cls.__name__.lower()` (wrong) | Correct model name |
|---|---|---|
| `SSP` | `ssp` | `system-security-plan` |
| `AssessmentResults` | `assessmentresults` | `assessment-results` |
| `AssessmentPlan` | `assessmentplan` | `assessment-plan` |
| `POAM` | `poam` | `plan-of-action-and-milestones` |

**Fix options (either):**
1. Add a `_MODEL_NAME: ClassVar[str]` attribute to each affected class and have
   `new()` use `cls._MODEL_NAME` instead of `cls.__name__.lower()`.
2. Override `new()` in each affected class to pass the correct model name to
   `create_new_oscal_content()`.

**Workaround in `package2oscal.py`:** `_new_model(cls, model_name, title, version)`
calls `get_support().load_file(f"{model_name}.xml")` directly, constructs the
instance via `OSCAL.__new__` / `__init_common__` / `initial_validation`, patches
`__class__`, and manually sets `is_read_only = False`. Mutations then work despite
`is_editable` still reporting `False` (a secondary symptom of the same root cause).

---

## Issue 2 — `SSP.add_by_component()` `implementation_status` kwarg not in signature (MINOR)

**Symptom:** `add_by_component()` accepts `implementation_status` as a parameter
name in the API docs but the actual signature in the installed 3.2.2 package uses
a different internal parameter name or positional order. Calling with
`implementation_status=` raises `TypeError: unexpected keyword argument`.

**Observed signature (3.2.2):**
```python
def add_by_component(
    self,
    implemented_requirement_uuid: str,
    component_uuid: str,
    description: str,
    by_component_uuid: str = "",
    implementation_status: str = "implemented",
    remarks: str = "",
) -> Optional[dict]
```

The keyword argument works correctly when `implementation_status` is passed
positionally (4th positional after description). The keyword form fails if the
internal name differs.

**Fix:** Verify that `implementation_status` is the correct keyword name.
`package2oscal.py` currently passes it as a keyword; if the name is wrong,
either fix the parameter name in the implementation or update the call sites.

**Workaround:** Call without the keyword (`add_by_component(req_uuid, comp_uuid,
description)`) and rely on the default `"implemented"` status; explicit non-default
status is not currently set via this call path.

---

## Issue 3 — No `SSP.add_set_parameter()` method (ENHANCEMENT — MEDIUM)

**Symptom:** After creating an `implemented-requirement` via
`SSP.append_impl_requirement()`, there is no method to add `set-parameters` to it.
The returned dict is a deep copy — mutating it does not modify the document.

**Impact:** Rev5 SDR controls require `set-parameters` per control. Without this
method, callers must either (a) build the full requirement dict manually and use
`append_child()` directly — bypassing `append_impl_requirement()` — or (b) accept
that parameter values are lost.

**Requested method:**
```python
def add_set_parameter(
    self,
    implemented_req_uuid: str,
    param_id: str,
    values: list[str],
) -> Optional[dict]:
    """Add a set-parameter to an existing implemented-requirement.

    Args:
        implemented_req_uuid (str, required): UUID of the target
            implemented-requirement.
        param_id (str, required): OSCAL parameter ID (e.g. ``"ac-02_prm_1"``).
        values (list[str], required): One or more parameter value strings.

    Returns:
        Optional[dict]: The created set-parameter dict, or None on failure.
    """
```

**Workaround in `package2oscal.py`:** `_build_control_requirements()` bypasses
`append_impl_requirement()` entirely; it builds the complete requirement dict
(including `set-parameters`) and uses `ssp.append_child(
"control-implementation/implemented-requirements", req_dict)` directly, then
calls `add_by_component()` with the pre-assigned UUID.

---

## Issue 4 — No `AssessmentResults` high-level mutation methods (ENHANCEMENT — HIGH)

**Symptom:** `AssessmentResults` has no methods for adding results, observations,
findings, or relevant evidence. All AR structure must be constructed as raw OSCAL
JSON dicts and appended via `append_child("results", full_result_dict)`.

**Impact:** Building an AR requires constructing deeply nested OSCAL structures
in Python dicts with no library validation of the structure. This is verbose,
error-prone, and bypasses any schema enforcement the library could provide.

**Requested methods:**

```python
def add_result(
    self,
    title: str,
    description: str,
    start: str,
    end: str = "",
    result_uuid: str = "",
) -> Optional[dict]:
    """Add a result to the assessment-results document.
    Returns the result dict (with generated uuid) or None on failure.
    """

def add_observation(
    self,
    result_uuid: str,
    title: str,
    description: str,
    methods: list[str] = None,
    obs_uuid: str = "",
) -> Optional[dict]:
    """Add an observation to the result identified by result_uuid.
    Returns the observation dict or None on failure.
    """

def add_finding(
    self,
    result_uuid: str,
    title: str,
    description: str,
    target_id: str,
    target_type: str = "objective-id",
    status: str = "satisfied",
    related_observation_uuids: list[str] = None,
    finding_uuid: str = "",
) -> Optional[dict]:
    """Add a finding to the result identified by result_uuid.
    Returns the finding dict or None on failure.
    """

def add_relevant_evidence(
    self,
    result_uuid: str,
    observation_uuid: str,
    description: str,
    href: str = "",
) -> Optional[dict]:
    """Add a relevant-evidence entry to an existing observation.
    Returns the evidence dict or None on failure.
    """
```

**Workaround in `package2oscal.py`:** `_build_ar_result()` builds the entire result
dict (with all nested observations and findings) in Python and appends it in one
`append_child("results", ...)` call. The workaround works but loses the ability to
navigate UUID-based paths within the result after insertion.

---

## Issue 5 — No `AssessmentPlan` high-level mutation methods (ENHANCEMENT — LOW)

**Symptom:** Same structural gap as Issue 4, but for `AssessmentPlan`. No methods
to add tasks, reviewed-controls entries, or assessment assets.

**Impact:** Low for `package2oscal.py` because the AP generated is intentionally
minimal. Higher impact for any future code that builds detailed assessment plans.

**Requested minimum:**
```python
def set_reviewed_controls(
    self,
    control_ids: list[str],
) -> bool:
    """Set the reviewed-controls/control-selections to include the given control IDs."""

def add_task(
    self,
    title: str,
    description: str,
    task_type: str = "action",
    task_uuid: str = "",
) -> Optional[dict]:
    """Add a task entry to the assessment-plan."""
```

**Workaround in `package2oscal.py`:** `build_ap()` uses `ap.put(
"reviewed-controls/control-selections", [...])` directly.

---

## Issue 6 — `bool(ssp)` returns `False` for instances created via the `_new_model` workaround (BUG — HIGH)

**Symptom:** An SSP (or AR, AP) instance created via the `_new_model` workaround
evaluates as falsy in boolean context. `bool(ssp)` → `False`. A plain `if ssp:`
guard silently skips all downstream processing even though the object is fully
populated and `dump()` succeeds.

**Root cause:** `OSCAL.__bool__` (or `__len__`, `is_valid`, or similar property)
returns `False` when the instance was created via the workaround path. The flag is
likely `is_valid = False` because `is_read_only = False` is assigned as an instance
attribute but the validity check uses an internal flag that was never set by the
normal `new()` path.

**Fix:** Add `is_valid = True` (or its internal equivalent) to the `new()` path's
clean-up after template loading, and verify the same for `_new_model` callers once
Issue 1 is resolved.

**Workaround in `package2oscal.py`:** Use `if ssp is not None:` instead of `if ssp:`
throughout `convert()`. Confirmed that `ssp.dump()` returns `True` and produces
correct output even when `bool(ssp)` is `False`.

---

## Summary

| # | Issue | Type | Priority | Status in 3.2.2 |
|---|---|---|---|---|
| 1 | `new()` broken for SSP/AR/AP/POAM | Bug | High | Workaround implemented |
| 2 | `add_by_component` kwarg name | Minor | Low | Avoiding keyword usage |
| 3 | `add_set_parameter` missing | Enhancement | Medium | Workaround via `append_child` |
| 4 | AR mutation methods missing | Enhancement | High | Workaround via raw dict |
| 5 | AP mutation methods missing | Enhancement | Low | Workaround via `put` |
| 6 | `bool(instance)` is `False` after workaround | Bug | High | Use `is not None` guards |

Issue 1 is a regression — `Catalog.new()` and `Profile.new()` work correctly and
the affected classes should behave identically. All other issues are forward-looking
and do not block the current `package2oscal.py` workarounds.
