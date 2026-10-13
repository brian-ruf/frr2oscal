# FedRAMP CR26 — KSI Information Requirements in the CPO and SDR

**Short answer: none in the CPO, all of it in the SDR.**

## CPO — No KSI-Specific Requirements at All

Checked against the 9 rules that define CPO content (`CPO-CSO-MTD`, `CDS-CSO-PUB`, `CDS-CSO-SVC`, `CDS-CSO-IRP`, `MAS-CSO-IIR`, `MAS-CSO-FLO`, `MAS-CSO-TPR`, `CMU-CSO-CMD`, `IVV-CSO-ICP`) — none of them mention KSIs. The CPO is path-agnostic identification/boundary/policy/third-party content; nothing in it is specific to the 20x path or its assessment mechanism.

## SDR — Two Rules, and They Don't Ask for the Same Things

### `SDR-CSX-KSI` (per applicable KSI) — 5 required items

1. Explanation of the measures/objectives demonstrating the KSI (or the reason/risk if not measured)
2. The cycle for any persistently-implemented measures
3. Verification that the measures demonstrate the KSI
4. Verification that automation in place is accurate/sufficient
5. Validation that the measures are accurate and working as intended

### `SDR-CSX-KMT` (KSI metrics, class-scaled) — historical data, not narrative

| Class | Requirement |
|---|---|
| B | 30-day summary + up-to-1-year summary, per KSI |
| C | Same as B, plus **all daily metric data** up to 1 year |
| D | Exceeds B/C, specifics still pending the 20x Phase 4 pilot |

## Where the Schema Diverges from What the Rule Text Actually Asks For

This is the part worth keeping front of mind — it's the biggest finding from the spreadsheet mapping work:

- **`SDR-CSX-KSI`'s 5 items don't include independent verification/validation** — unlike `SDR-CSO-FRR` (base layer) and `SDR-CSF-CTF` (Rev5 controls), which both explicitly require it. Independent assessment of KSIs happens as an *event* (`IVV-CSX-AIA`, 100% of KSIs assessed annually) rather than a *field* in the KSI record.
- **The schema adds three fields the rule text never asked for:** `ksiTests`, `ksiEvidence` (a fully structured evidence object — type, description, location, text, last-updated), and `ksiAssessment`. None of these three are named anywhere in `SDR-CSX-KSI`'s actual 5-item list.
- **`SDR-CSX-KMT`'s entire requirement — the historical/time-series metrics — has zero representation in the schema.** No metrics array, no summary-period field, nothing class-scaled. This is the single largest gap in the SDR schema overall.
- Working out, from the actual Phase 2 authorization timeline (ChatGPT Enterprise, certified January 9, 2026, ~52 days after the finalized Moderate KSI standard), that this "up to a year of daily data" requirement couldn't plausibly have been demonstrated by any real pilot-era authorization — it's a forward-looking aspiration formalized in CR26, not something validated against real pilot evidence.

**Net effect:** the KSI portion of the SDR is the least evidentially rigorous of the three content types in one dimension (no explicit independent-V&V fields in its own rule text) while simultaneously being the most schema-enforced in another (required evidence/tests structure that Rev5 controls entirely lack) — an asymmetry that runs in opposite directions depending on which axis you're measuring.
