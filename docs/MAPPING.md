# FRR → OSCAL Mapping

This document maps every field defined in the `FRR` portion of
`fedramp-consolidated-rules.schema.json` to its corresponding location in the
OSCAL catalog produced by `src/frr2oscal.py`. Fields with no current mapping
are marked **NOT MAPPED** and noted with a brief description of the data they
contain.

---

## 1. Schema Hierarchy Overview

```
FRR                                  (object, keyed by frr_document_key)
└── {FRR-key}                        e.g. "AFC", "AGU"
    ├── info                         frr_document_info
    └── data                         data_container_frr
        ├── all                      frr_requirements_map  ← processed
        ├── 20x                      frr_requirements_map  ← processed
        └── rev5                     frr_requirements_map  ← processed
            └── {subset-key}         frr_requirements_subset_group
                └── {rule-id}        frr_requirement
                    └── varies_by_class.{a|b|c|d}   frr_requirement_level
```

All three data scopes (`all`, `20x`, `rev5`) are now converted. Rules from
each scope carry a `path` prop (FedRAMP namespace) identifying which scope
they belong to. Child group IDs include a scope qualifier for `20x` and `rev5`
to prevent collisions with `all` groups whose subset keys overlap (e.g. VDR/TFR
appears in all three scopes).

---

## 2. FRR Document → OSCAL Top-Level Group

Each top-level key in `FRR` (pattern `^[A-Z]{3}$`) becomes a top-level
`group` in the catalog.

### 2.1 `FRR.{key}` → `group`

| OSCAL field | Value |
|---|---|
| `group.id` | `"FRR-{key}"` |
| `group.title` | `info.name` |
| `group.props[name=label].value` | `"FRR-{key}"` |
| `group.parts[name=overview].prose` | `info.purpose` |
| `group.parts[name=overview].title` | `"Purpose"` (set via dict workaround; see `MISSING_FROM_OSCAL_LIBRARY.md` §1) |

### 2.2 `FRR.{key}.info` fields (`frr_document_info`)

| Schema field | Required | Type | OSCAL mapping |
|---|---|---|---|
| `name` | ✓ | string | → `group.title` |
| `purpose` | ✓ | string | → `group.parts[name=overview].prose` |
| `short_name` | ✓ | string `^[A-Z]{3}$` | → `group.props[name=label].value` |
| `web_name` | ✓ | string | **NOT MAPPED** — human-friendly display name |
| `status` | ✓ | `"stable"` \| `"placeholder"` \| `"empty"` | → `group.props[name=status, ns=FRR_NS].value` (FedRAMP extension) |
| `tag` | — | string | **NOT MAPPED** — optional short tag |
| `effective` | ✓ (or `20x`+`rev5`) | `effective_entry` | **NOT MAPPED** — effective date and status for the ruleset |
| `subsets` | — | `frr_info_subsets` | **NOT MAPPED** — subset metadata (names, descriptions, applicability); see §2.3 |
| `flows` | — | array | **NOT MAPPED** — process-flow relationships |
| `20x` | ✓ (when no top-level `effective`) | `frr_document_info_certification` | **NOT MAPPED** — 20x-specific effective dates and subset overrides |
| `rev5` | ✓ (when no top-level `effective`) | `frr_document_info_certification` | **NOT MAPPED** — Rev5-specific effective dates and subset overrides |

### 2.3 `FRR.{key}.info.subsets` (`frr_info_subsets`)

Subset metadata describes each named group of rules within a ruleset. It is
present in the `info` block but is not present in the current data for any
ruleset. No subset has an `info` block in any scope.

| Schema field | Required | Type | OSCAL mapping |
|---|---|---|---|
| `{subset-key}.name` | ✓ | string | **NOT MAPPED** |
| `{subset-key}.description` | ✓ | string | **NOT MAPPED** |
| `{subset-key}.applicability.types` | ✓ | `["20x"` \| `"Rev5"]` | **NOT MAPPED** — which certification types the subset applies to |
| `{subset-key}.applicability.paths` | ✓ | `["Program"` \| `"Agency"]` | **NOT MAPPED** — which certification paths apply |
| `{subset-key}.applicability.classes` | ✓ | `["A"…"D"]` | **NOT MAPPED** — which certification classes apply |
| `{subset-key}.applicability.affects` | ✓ | `affected_party[]` | **NOT MAPPED** — which parties the subset targets |

---

## 3. `FRR.{key}.data` → Data Scope Selection

All three scopes are processed. Child group and control IDs reflect the scope
they originate from.

| Schema key | Type | OSCAL mapping |
|---|---|---|
| `data.all` | `frr_requirements_map` | → processed; child groups use `FRR-{key}-{subset}` ID |
| `data.20x` | `frr_requirements_map` | → processed; child groups use `FRR-{key}-{subset}-20x` ID |
| `data.rev5` | `frr_requirements_map` | → processed; child groups use `FRR-{key}-{subset}-rev5` ID |

---

## 4. `FRR.{key}.data.{scope}.{subset}` → OSCAL Child Group

Each subset key within a scope becomes a child `group` nested under the parent
ruleset group.

| OSCAL field | Value |
|---|---|
| `group.id` | `"FRR-{key}-{subset}"` (scope=all) or `"FRR-{key}-{subset}-{scope}"` (scope=20x/rev5) |
| `group.title` | Same as `group.id` for scope=all; `"FRR-{key}-{subset} 20X Path"` or `"FRR-{key}-{subset} Rev 5 Path"` for scoped groups |
| `group.parts[name=overview]` | Omitted (no `info` block present in current data) |

> The `frr_requirements_subset_group` schema allows any `frr_requirement_id`
> as a property key alongside an optional `info` entry. When `info` is
> present, its `title` and `purpose` fields map to `group.title` and
> `group.parts[name=overview].prose` respectively.

---

## 5. `FRR.{key}.data.{scope}.{subset}.{rule-id}` → OSCAL Control

Each rule entry (`frr_requirement`) maps to one OSCAL `control`. The schema
enforces a mutual exclusion: a rule has either `statement` + `force`
(simple rule) or `varies_by_class` (class-conditional rule), never both.

### 5.1 Simple Rule (has `statement` and `force`, no `varies_by_class`)

| Schema field | Required | Type | OSCAL mapping |
|---|---|---|---|
| *(key)* | — | `frr_requirement_id` | → `control.id`, `props[name=label].value` |
| `name` | ✓ | string | → `control.title` |
| `statement` | ✓ | string | → `parts[name=statement, id={id}_smt].prose` |
| `force` | ✓ | `force_enum` | → `props[name=force, ns=FRR_NS].value` |
| *(scope)* | — | — | → `props[name=path, ns=FRR_NS].value` = `"all"` \| `"20x"` \| `"rev5"` |
| `affects` | ✓ | `affected_party[]` | → one `props[name=affects, ns=FRR_NS]` per item |
| `danger` | — | string | → `parts[name=guidance, title=Danger].prose` (title set via workaround; see `MISSING_FROM_OSCAL_LIBRARY.md` §1) |
| `note` | — | string | → `parts[name=guidance, title=Notes].prose` |
| `notes` | — | string[] (min 2) | → `parts[name=guidance, title=Notes].prose` (items joined with blank lines) |
| `related` | — | string[] | → one `links[rel=related, href=#{id}]` per item |
| `artifacts.all` | — | string[] | → `parts[name=assessment-method, props=[method=EXAMINE, path=all]].parts[name=assessment-objects].prose` (one per item; see `MISSING_FROM_OSCAL_LIBRARY.md` §3) |
| `artifacts.20x` | — | string[] | → `parts[name=assessment-method, props=[method=EXAMINE, path=20x]].parts[name=assessment-objects].prose` |
| `artifacts.rev5` | — | string[] | → `parts[name=assessment-method, props=[method=EXAMINE, path=rev5]].parts[name=assessment-objects].prose` |
| `corrective_actions` | — | string[] | → `parts[name=remediation, ns=FRR_NS].prose` (items joined with blank lines) |
| `examples` | — | object[] (`id`, `key_tests`, `examples`) | → `parts[name=guidance, class=examples, title=Examples].prose` |
| `schema` | — | `rule_schema` (`name`+`url`) | → `parts[name=guidance, class=schema, title=Schema].prose` |
| `following_information` | — | string[] | → `parts[name=guidance, class=following_information, title=Following Information].prose` |
| `updated` | ✓ | `updated_list` | → one `props[name=updated, ns=FRR_NS, value=date, remarks=comment]` per entry |
| `following_information_bullets` | — | string[] | → `parts[name=statement, id={id}_smt].parts[name=item].prose` (each item prefixed with `- `; appended after `statement`) |
| `reference` | — | string | → `links[rel=reference].text` (used as link text when `reference_url` is also present) |
| `reference_url` | — | URI | → `links[rel=reference, href={url}]`; `.text` set to `reference` value when present |
| `effective_date` | — | `effective_dates` | → `props[name=effective_date, ns=FRR_NS].value` (JSON-serialised when value is an object) |
| `timeframe_type` | — | enum (`bizdays`\|`days`\|`hours`\|`weeks`\|`months`\|`years`) | → `props[name=timeframe_type, ns=FRR_NS].value` |
| `timeframe_num` | — | positive number | → `props[name=timeframe_num, ns=FRR_NS].value` (number converted to string) |
| `notification` | — | object[] (`party`, `method`, `target`, `name`, `url`) | **NOT MAPPED** — structured notification requirements |
| `controls` | — | `control_id[]` | **NOT MAPPED** — NIST SP 800-53 control identifiers related to this rule |
| `terms` | — | string[] | **NOT MAPPED** — FRD term references |

### 5.2 Varies-by-Class Rule (has `varies_by_class`, no `statement` or `force`)

The rule becomes a parent `control` with a fixed statement, and each class
variant becomes a child `control` nested in the parent's `controls` list
(see `MISSING_FROM_OSCAL_LIBRARY.md` §4 for the library workaround).

**Parent control:**

| Schema field | Required | Type | OSCAL mapping |
|---|---|---|---|
| *(key)* | — | `frr_requirement_id` | → `control.id`, `props[name=label].value` |
| `name` | ✓ | string | → `control.title` |
| *(hardcoded)* | — | — | → `parts[name=statement].prose = "Varies by Class"` |
| *(scope)* | — | — | → `props[name=path, ns=FRR_NS].value` = `"all"` \| `"20x"` \| `"rev5"` |
| `related` | — | string[] | → one `links[rel=related, href=#{id}]` per item |
| `affects` | ✓ | `affected_party[]` | → one `props[name=affects, ns=FRR_NS]` per item |
| `note` | — | string | → `parts[name=guidance, title=Notes].prose` |
| `notes` | — | string[] | → `parts[name=guidance, title=Notes].prose` (items joined with blank lines) |
| `corrective_actions` | — | string[] | → `parts[name=remediation, ns=FRR_NS].prose` |
| `examples` | — | object[] | → `parts[name=guidance, class=examples, title=Examples].prose` |
| `schema` | — | `rule_schema` | → `parts[name=guidance, class=schema, title=Schema].prose` |
| `following_information` | — | string[] | → `parts[name=guidance, class=following_information, title=Following Information].prose` |
| `updated` | ✓ | `updated_list` | → one `props[name=updated, ns=FRR_NS, value=date, remarks=comment]` per entry |
| `following_information_bullets` | — | string[] | → `parts[name=statement, id={id}_smt].parts[name=item].prose` (each item prefixed with `- `) |
| `reference` | — | string | → `links[rel=reference].text` (used as link text when `reference_url` is also present) |
| `reference_url` | — | URI | → `links[rel=reference, href={url}]`; `.text` set to `reference` value when present |
| `effective_date` | — | `effective_dates` | → `props[name=effective_date, ns=FRR_NS].value` (JSON-serialised when value is an object) |
| `timeframe_type` | — | enum | → `props[name=timeframe_type, ns=FRR_NS].value` |
| `timeframe_num` | — | positive number | → `props[name=timeframe_num, ns=FRR_NS].value` (number converted to string) |
| `notification` | — | object[] | **NOT MAPPED** |
| `controls` | — | `control_id[]` | **NOT MAPPED** |
| `terms` | — | string[] | **NOT MAPPED** |

---

## 6. `varies_by_class.{a|b|c|d}` → OSCAL Child Control (`frr_requirement_level`)

Each class key (`a`, `b`, `c`, `d`) becomes a child `control` appended
directly to the parent control's `controls` list.

| Schema field | Required | Type | OSCAL mapping |
|---|---|---|---|
| *(key, uppercased)* | — | `"a"`…`"d"` | → `control.id` = `"{parent-id}-{key}"`, `props[name=label].value` = `"Class {KEY}"` |
| *(label as title)* | — | — | → `control.title` = `"Class {KEY}"` (class entries have no `name` field) |
| *(scope)* | — | — | → `props[name=path, ns=FRR_NS].value` (inherited from parent rule's scope) |
| `statement` | ✓ | string | → `parts[name=statement, id={id}_smt].prose` |
| `force` | ✓ | `force_enum` | → `props[name=force, ns=FRR_NS].value` |
| `note` | — | string | → `parts[name=guidance, title=Notes].prose` |
| `notes` | — | string[] (min 2) | → `parts[name=guidance, title=Notes].prose` (items joined with blank lines) |
| `artifacts.all` | — | string[] | → `parts[name=assessment-method, props=[method=EXAMINE, path=all]].parts[name=assessment-objects].prose` |
| `artifacts.20x` | — | string[] | → `parts[name=assessment-method, props=[method=EXAMINE, path=20x]].parts[name=assessment-objects].prose` |
| `artifacts.rev5` | — | string[] | → `parts[name=assessment-method, props=[method=EXAMINE, path=rev5]].parts[name=assessment-objects].prose` |
| `following_information` | — | string[] | → `parts[name=guidance, class=following_information, title=Following Information].prose` |
| `following_information_bullets` | — | string[] | → `parts[name=statement, id={id}_smt].parts[name=item].prose` (each item prefixed with `- `) |
| `rev5_controls_list` | — | object (family → `rev5_control_id[]`) | → used for Rev5 profile control selection (not written to the catalog); control IDs are converted to OSCAL format and added to the appropriate Rev5 class profile's include list |
| `effective_date` | — | `effective_dates` | → `props[name=effective_date, ns=FRR_NS].value` (JSON-serialised when value is an object) |
| `timeframe_type` | — | enum | → `props[name=timeframe_type, ns=FRR_NS].value` |
| `timeframe_num` | — | positive number | → `props[name=timeframe_num, ns=FRR_NS].value` (number converted to string) |
| `pain_timeframes` | — | object (PAIN level 1–5 → timeframe) | **NOT MAPPED** — PAIN score-based response timeframe table |

---

## 7. Supporting Types Summary

| Type | Used in | Description |
|---|---|---|
| `force_enum` | rule, class variant | `MUST` \| `MUST NOT` \| `SHOULD` \| `SHOULD NOT` \| `MAY` |
| `affected_party` | rule, subset applicability | `Advisors` \| `Agencies` \| `Assessors` \| `FedRAMP` \| `Providers` \| `Everyone` |
| `certification_type` | subset applicability | `20x` \| `Rev5` |
| `certification_path` | subset applicability | `Program` \| `Agency` |
| `class_name` | subset applicability | `A` \| `B` \| `C` \| `D` |
| `timeframe_type` | rule, class variant | `bizdays` \| `days` \| `hours` \| `weeks` \| `months` \| `years` |
| `updated_list` | rule | Array of `{date, comment}` changelog entries |
| `effective_entry` | document info | `{is, current_status, date, comments, warnings, signup_url}` |
| `effective_dates` | rule, class variant | `{obtain, maintain, optional_adoption, grace}` dates |
| `notification` | rule | `{party, method, target, name, url}` — who to notify, how, and where |
| `rule_schema` | rule | `{name, url}` — machine-readable schema governing artifacts |
| `pain_timeframes` | class variant | PAIN severity 1–5 → response timeframe table |
| `rev5_controls_list` | class variant | NIST SP 800-53 Rev5 family → control ID list |
| `artifact_list` | artifacts | `string[]` — plain-text artifact descriptions |
| `control_id` | rule | `^[a-z]{2}-\d+(\.\d+)?$` — NIST SP 800-53 control ID |

---

## 8. Summary of Unaddressed Fields

The following fields appear in the source data but are not yet mapped to OSCAL
output. They are recorded in `data/unhandled.json` at runtime.

| Field | Appears in | Description |
|---|---|---|
| `notification` | rule | Structured notification requirements (party, method, target, URL) |
| `controls` | rule | NIST SP 800-53 control identifiers related to this rule |
| `terms` | rule | References to defined terms in the FRD |
| `pain_timeframes` | class variant | PAIN severity 1–5 → response timeframe lookup table |
