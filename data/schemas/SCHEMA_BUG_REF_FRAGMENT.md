# Schema Bug: Missing Fragment Separator in Cross-Schema `$ref` URIs

**Schemas version:** 2026-06-24  
**Draft:** JSON Schema 2020-12  
**Discovered:** 2026-09-14

## Summary

Five of the eleven FedRAMP schema files contain malformed `$ref` URIs that reference
definitions in `fedramp-common-definitions-schema-2026-06-24.json`. The URIs are missing
the `#` fragment separator required by RFC 3986 and the JSON Schema specification. As a
result, any compliant JSON Schema validator that performs URI-based reference resolution
will fail to resolve these references and report an error, even for otherwise-valid
documents.

## Root Cause

JSON Schema uses URI fragments (the portion after `#`) to express JSON Pointer paths
within a document. A cross-document `$ref` pointing to a named definition must take the
form:

```
<base-URI>#/<JSON-Pointer-path>
```

The affected `$ref` values omit the `#`, causing the `/$defs/<name>` portion to be
interpreted as a URI path segment rather than a fragment. No document exists at those
constructed URIs, so resolution fails.

### Incorrect (as written in the schemas)

```json
"$ref": "https://fedramp.gov/schemas/fedramp-common-definitions-schema-2026-06-24.json/$defs/certificationPackageOverviewUri"
```

### Correct

```json
"$ref": "https://fedramp.gov/schemas/fedramp-common-definitions-schema-2026-06-24.json#/$defs/certificationPackageOverviewUri"
```

## Affected Files and References

| Schema file | Broken `$ref` target |
|---|---|
| `fedramp-accepted-vulnerability-info-schema-2026-06-24.json` | `.../$defs/certificationPackageOverviewUri` |
| `fedramp-accepted-vulnerability-info-schema-2026-06-24.json` | `.../$defs/reportPeriodDateTime` |
| `fedramp-accepted-vulnerability-info-schema-2026-06-24.json` | `.../$defs/acceptedVulnerabilityInfo` |
| `fedramp-incident-report-schema-2026-06-24.json` | `.../$defs/certificationPackageOverviewUri` |
| `fedramp-incident-report-schema-2026-06-24.json` | `.../$defs/nRating` (appears twice) |
| `fedramp-ongoing-certification-report-schema-2026-06-24.json` | `.../$defs/certificationPackageOverviewUri` |
| `fedramp-ongoing-certification-report-schema-2026-06-24.json` | `.../$defs/reportPeriodDate` |
| `fedramp-security-decision-record-schema-2026-06-24.json` | `.../$defs/certificationPackageOverviewUri` |
| `fedramp-significant-change-notifications-schema-2026-06-24.json` | `.../$defs/certificationPackageOverviewUri` |
| `fedramp-vulnerability-detail-report-schema-2026-06-24.json` | `.../$defs/certificationPackageOverviewUri` |
| `fedramp-vulnerability-detail-report-schema-2026-06-24.json` | `.../$defs/reportPeriodDateTime` |
| `fedramp-vulnerability-detail-report-schema-2026-06-24.json` | `.../$defs/vulnerabilityDetail` |

All broken references point into `fedramp-common-definitions-schema-2026-06-24.json`,
which is the only file that defines shared `$defs`. That file itself is not affected.

The two files that validate against these schemas without triggering the bug —
`fedramp-certification-package-overview-schema-2026-06-24.json` and
`fedramp-assessor-information-schema-2026-06-24.json` — contain no cross-schema `$ref`
values and are unaffected.

## Fix

In each affected schema file, insert `#` between the `.json` filename and the `/$defs/`
path in every broken `$ref`. This is a mechanical find-and-replace:

```
fedramp-common-definitions-schema-2026-06-24.json/$defs/
                                                 ^
                                          insert # here
```

No changes to the definitions themselves, and no changes to `fedramp-common-definitions-schema-2026-06-24.json`, are required.

## Workaround for Local Validation

When validating locally against these schemas before an upstream fix is available, patch
the `$ref` strings in memory before building the validator registry:

```python
import re

def fix_refs(schema_text: str) -> str:
    return re.sub(
        r'(https://fedramp\.gov/schemas/[^"#]+\.json)(/\$defs/)',
        r'\1#\2',
        schema_text,
    )
```

Apply `fix_refs()` to the raw text of each schema file before parsing it as JSON.
