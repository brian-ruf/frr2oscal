# Missing Features in the `oscal` Library

This document tracks functionality that `frr2oscal` requires but that is not yet
available in the `oscal` library. Each entry describes the gap, the workaround
currently in use, and the affected code in `src/frr2oscal.py`.

When a gap is resolved in the library the corresponding workaround should be
replaced with the proper API call and the entry removed from this file.

---

## 1. Part titles on `overview` and `guidance` parts

**Affected methods:** `Catalog.create_control_group()`, `Catalog.create_control()`

**Gap:** Both methods accept `overview` and `guidance` string parameters that
create a part with the matching `name`. Neither method supports setting a `title`
attribute on those parts.

**Needed:** An optional `title` keyword argument (or equivalent) for each part
parameter so callers can specify a display title alongside the prose.

**Workaround:** The `_set_part_title()` helper iterates the `parts` list on the
dict returned by the creation method (which is the live object already inserted
into the catalog) and sets `title` in-place.

**Call sites:**
- `_build_frr_ruleset()` — sets `title="Purpose"` on the `overview` part of each
  top-level FRR group.
- `_build_frr_subset()` — sets `title="Purpose"` on the `overview` part of each
  child subset group.
- `_build_frr_simple_control()` — sets `title="Danger"` on the `guidance` part of
  controls that carry a danger warning.

---

## 2. Multiple guidance parts per control

**Affected method:** `Catalog.create_control()`

**Gap:** The `guidance` parameter creates exactly one guidance part. There is no
mechanism to add a second guidance part (e.g. one titled "Danger" and a separate
one titled "Notes") through the API.

**Needed:** Either accept a list of guidance items (each with optional `title` and
`prose`), or provide an `add_part()` method that appends an arbitrary part to an
existing control.

**Workaround:** The "Danger" guidance is passed via the `guidance` parameter as
before. The "Notes" guidance part is constructed as a raw dict and appended
directly to the returned control's `parts` list.

**Call site:** `_build_frr_simple_control()` and `_build_class_control_dict()`.

---

## 3. `objects` parameter not implemented in `create_control()`

**Affected method:** `Catalog.create_control()`

**Gap:** The `objects` parameter appears in the method signature and docstring
("Assessment object items") but the implementation body never processes it —
no parts are written to the control dict.

**Needed:** The `objects` parameter should generate one `assessment-objects` part
per list item. Based on how `frr2oscal` uses these, each item's prose should be
the item value, and all `assessment-objects` parts should be nested inside a
single `assessment-method` parent part that carries a `method` prop (value
`"EXAMINE"`).

**Workaround:** The assessment-method/assessment-objects structure is built as a
raw dict and appended directly to the returned control's `parts` list.

**Call site:** `_build_frr_simple_control()` and `_build_class_control_dict()`.

---

## 4. `create_control()` does not support a control as parent

**Affected method:** `Catalog.create_control()`

**Gap:** The `parent_id` parameter is resolved internally via `_find_group()`,
which only searches the group hierarchy. A control ID passed as `parent_id` is
never found, so child controls cannot be created under a parent control through
the API. OSCAL itself allows controls to nest controls.

**Needed:** `_find_group()` (or a new resolver) should also search the control
hierarchy so that a control ID can serve as a valid `parent_id`.

**Workaround:** `_build_class_control_dict()` constructs a complete control dict
manually (mirroring the structure `create_control()` would produce) and
`_build_frr_varies_control()` appends it directly to the parent control's
`"controls"` list.

**Call site:** `_build_frr_varies_control()` — used for every `varies_by_class`
rule, where each class variant (A, B, C, D) must be a child control under the
parent rule's control.
