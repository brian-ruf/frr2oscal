# SCENARIOS.md — CR26 20x vs. Rev5, Illustrated with a Single Fictitious CSP

## The Scenario

**Cloud Service Provider:** Meridian Cloud Solutions, Inc.
**Cloud Service Offering:** Meridian Secure Workspace (MSW) — a SaaS document co-authoring, secure messaging, and workflow-automation platform for federal agency teams, built on a separately FedRAMP Certified underlying IaaS platform.

**Target certification: Class C (Moderate).**

Meridian is evaluating both available routes to a Class C Certification under CR26. This scenario documents the same CSP and the same CSO pursuing **both** paths side by side, so the actual package differences are visible in the artifacts themselves rather than only in prose.

**Files in this scenario:**

| File | Path | Content |
|---|---|---|
| `cpo_20x.json` | 20x | Certification Package Overview |
| `sdr_20x.json` | 20x | Security Decision Record (KSIs) |
| `cpo_rev5.json` | Rev5 | Certification Package Overview |
| `sdr_rev5.json` | Rev5 | Security Decision Record (800-53 controls) |

All four files validate cleanly against FedRAMP's published JSON Schemas (`fedramp-certification-package-overview-schema-2026-06-24.json` and `fedramp-security-decision-record-schema-2026-06-24.json`, schema version `1.0.0`).

**Important scope caveat:** these are illustrative samples, not complete compliant packages. A real Class C submission would need to address the full applicable set — all ~322 Rev5 Class C controls or all 46 KSIs, plus every applicable FRR across the shared rulesets (roughly 200+ entries), not the 6-item samples shown here. The point of this scenario is to make the *structural* differences between the two paths concrete, not to model package completeness.

---

## Path 1: FedRAMP 20x, Class C

**`cpo_20x.json`** — Certification Package Overview, `certificationType: "20x"`.

**`sdr_20x.json`** — Security Decision Record containing:
- **`fedRampRequirements`** — 6 sample entries against shared FRR rules (`MAS-CSO-IIR`, `MAS-CSO-FLO`, `MAS-CSO-TPR`, `VDR-CSO-DET`, `CCM-OCR-AVL`, `SCN-CSO-INF`)
- **`keySecurityIndicators`** — 6 sample KSIs (`KSI-IAM-APM`, `KSI-IAM-JIT`, `KSI-SVC-SIN`, `KSI-MLA-OSM`, `KSI-CNA-RNT`, `KSI-INR-RIR`), each with implementation, validation, assessment, tests, and evidence

Note the `VDR-CSO-DET` and `CCM-OCR-AVL` entries reflect 20x's tighter cadence — continuous authenticated scanning, and an Ongoing Certification Report every 2 weeks (the Class C `CPO-CSX-CPM` maintenance requirement).

---

## Path 2: FedRAMP Rev5, Class C

**`cpo_rev5.json`** — Certification Package Overview, `certificationType: "Rev5"`, otherwise identical content to `cpo_20x.json`.

**`sdr_rev5.json`** — Security Decision Record containing:
- **`fedRampRequirements`** — the **same 6 FRR entries** as the 20x SDR, since these rules are shared across both paths. The `VDR-CSO-DET` and `CCM-OCR-AVL` entries differ in *content* (monthly scanning, quarterly reporting) to reflect Rev5's slower standing cadence, even though the underlying rule IDs are identical.
- **`securityControls`** — 6 sample NIST 800-53 controls chosen to parallel the 20x KSIs by topic (`AC-02`, `IA-02`, `SC-13`, `SI-04`, `IR-04`, `CA-07`), each with parameter values, implementation status, and a implementation description.

No `keySecurityIndicators` array — not applicable to this path.

---

## What the Comparison Actually Shows

**The CPO is nearly identical across both paths.** The only difference between `cpo_20x.json` and `cpo_rev5.json` is the `certificationType` field and the `nextOngoingCertificationReportDate` (reflecting each path's different maintenance cadence). Everything else — service identification, contacts, third-party resources, certified services — is the same content, because it describes the CSO itself, not the certification methodology.

**The SDR is where the paths genuinely diverge, and it diverges in three ways, not one:**

1. **The content type itself.** 20x's SDR has a `keySecurityIndicators` array; Rev5's has a `securityControls` array. This is the headline difference and the one most people expect.
2. **The shared `fedRampRequirements` are the same rule IDs on both paths, but not always the same content.** `VDR-CSO-DET` and `CCM-OCR-AVL` are present in both SDRs with the same `frrID`, but the actual implementation statements differ — because the underlying FRR rules themselves are class-scaled by path (see `VDR` and `CCM-OCR-AVL`'s cadence differences documented elsewhere in this analysis). A shared FRR ID does not guarantee shared substance.
3. **What each content type's schema actually enforces differs, independent of anything about the CSO itself.** The `keySecurityIndicators` schema requires `ksiTests` and `ksiEvidence` — both populated in `sdr_20x.json`. The `securityControls` schema has no equivalent required field, and in fact requires nothing at all beyond an object existing in the array (not even `controlId` is mandatory by schema). Both sample files here include full narrative detail for every entry, but a package that validated against the schema with far less content in `securityControls` than in `keySecurityIndicators` would still pass — the two content types are not held to the same evidentiary bar by the schema itself, regardless of what the corresponding rule text (`SDR-CSF-CTF` vs. `SDR-CSX-KSI`) says should be there.

**One thing this scenario deliberately does not show:** neither SDR includes anything for KSI historical metrics (`SDR-CSX-KMT`) or the FRR-level "responses to assessor comments" and "rule-specific artifacts" fields required by `SDR-CSO-FRR` — because, as established in this conversation's earlier schema analysis, **the schema has no fields for any of these**, on either path. These sample files are schema-valid precisely because that content isn't enforceable in the first place.
