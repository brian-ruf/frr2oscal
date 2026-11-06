# VDR/VER Requirements and Comparison to KSI Telemetry

## Basis

- **Source:** `fedramp-consolidated-rules.json`, rules version `2026.10.08.01` (FedRAMP/rules, commit `6eb3767`). Every rule ID and quotation below comes from that file.
- **Rulesets covered:** VDR (Vulnerability Detection and Response, 18 rules) and VER (Vulnerability Evaluation and Reporting, 23 rules).
- **Taxonomy used for the mapping:** the revised KSI taxonomy (Requirement, Definition, Acquisition and Analysis, Evidence, Confirmation).
- **Labels:** "Rule text" means FedRAMP says it. "Mapping" means our reading of how the rule text fits the taxonomy.
- **Not checked:** the JSON Schemas hosted on fedramp.gov were not re-fetched. Statements about what a schema contains rely on the versions examined earlier in this conversation.

---

# Part 1: Revised summary of VDR/VER requirements

## 1.1 Structure and force profile

VDR defines the activities of detecting and responding. VER defines evaluating, reporting, and what agencies do with the reports.

| Ruleset and subset | Rules | Force |
|---|---|---|
| VDR, general (`CSO`) | `DET` Vulnerability Detection, `RES` Vulnerability Response, `FAV` Failures Are Vulnerabilities | MUST |
| | `DFR` Design For Resilience, `ADT` Automate Detection, `DAC` Detect After Changes | SHOULD |
| | `MSP` Maintain Security, `AKE` Avoid KEVs | SHOULD NOT |
| | `SIR` Sampling | MAY |
| VDR, timeframes (`TFR`) | `NMV` non-machine verification and validation | MUST |
| | `MVX` machine verification and validation, 20x (Class B and C) | MUST |
| | `MVF` machine verification and validation, Rev5 (Class C and D) | MUST |
| | `PDD`, `PCD`, `PSD` detection cadences, `PVR` mitigation timeframes, `RMN`, `KEV` | SHOULD |
| VER, evaluation (`EVA`) | `ELX` exploitability, `EIR` internet-reachability, `EPA` potential agency impact, `AIA` assume it is automatable | MUST |
| | `GRV` group vulnerabilities, `EFP` false positives, `EFA` evaluation factors | SHOULD |
| VER, reporting (`RPT`) | `PER` persistent reporting, `VDT` vulnerability details, `AVI` accepted vulnerability info | MUST |
| | `NID` responsible disclosure | MUST NOT |
| | `HLO` high-level overviews | SHOULD |
| | `RPD` responsible public disclosure | MAY |
| VER, timeframes (`TFR`) | `MHR` monthly report, `MAV` mark accepted vulnerabilities | MUST |
| | `MRH` historical activity (Class A MAY, B to D SHOULD), `EVU` evaluate quickly, `IRI` and `NRI` incident treatment (Class A and B MAY, higher classes SHOULD, with exceptions) | SHOULD or MAY, varies by class |
| VER, agency guidance (`AGM`) | `RVR` review vulnerability reports, `MAP` maintain agency POA&Ms | SHOULD |
| VER, FedRAMP (`FRP`) | `ARP` additional requirements, `ADV` sensitive details | MAY |

**The class-scaled detection cadences are SHOULD, not MUST.** The firm requirements are that detection and response happen at all (`DET`, `RES`), that failures in them are vulnerabilities (`FAV`), that resource status is verified and validated on the cadences in `NMV`, `MVX`, and `MVF`, and that evaluation and reporting happen as described below.

Under the glossary's force definitions (`FRD-SHD`, `FRD-MAY`, added September 13), a provider is expected to explain, in its security documentation, its decisions about how it handles SHOULD and MAY rules.

## 1.2 Mapped to the KSI taxonomy

| Taxonomy element | VDR/VER content | Rule IDs | Basis |
|---|---|---|---|
| **Requirement** | Detect and respond to vulnerabilities in the cloud service offering, systematically, persistently, and promptly. Evaluate them. Report on them. | `VDR-CSO-DET`, `VDR-CSO-RES`, `VER-RPT-PER` | Rule text |
| **Subject** | The **information resource** (`FRD-IRS`): machine-based (hardware, software, services, code) or non-machine-based (policies, procedures, people). The rules partition the population: resources likely to drift, resources not likely to drift, representative samples of similar machine-based resources, non-machine-based resources. Affected resources may be grouped for response. | `VDR-TFR-PDD`, `PCD`, `PSD`, `NMV`, `VER-EVA-GRV`, `FRD-IRS`, `FRD-VLD` | Rule text |
| **Attribute** | The **vulnerability**. `FRD-VUL` defines it as "any attribute of hardware, software, process, or procedure that could enable or facilitate the defeat of" controls. The evaluated attributes of a vulnerability are internet-reachability, likely exploitability, Potential Agency Impact N-rating, overdue status, and disposition. | `FRD-VUL`, `VER-EVA-EIR`, `ELX`, `EPA`, `VER-RPT-VDT` | Rule text |
| **Cycle** | Multiple, set by FedRAMP, and tied to the Subject class and Certification Class (see 1.3). Also a time-to-evaluate, a time-to-mitigate by PAIN rating (see 1.5), and monthly reporting. | `VDR-TFR-*`, `VER-TFR-EVU`, `MHR`, `MRH` | Rule text |
| **Rationale** | Not a per-instance required item. Rationale appears in rule notes (for example the notes on `VDR-CSO-DET` and `VER-EVA-ELX`) and in two required explanations: why a vulnerability is overdue, and why it is accepted. | `VER-RPT-VDT`, `VER-RPT-AVI` | Rule text, with the taxonomy item interpreted |
| **Data Source** | The detection techniques: assessment, scanning, threat intelligence, vulnerability disclosure mechanisms, bug bounties, penetration testing, incident response, automated control testing, supply chain monitoring. Several sources feed one determination. | `VDR-CSO-DET`, `FRD-VLD` | Rule text |
| **Acquisition Basis** | Varies by technique. A scanner result is a direct observation, while threat intelligence and a human penetration-test finding involve inference or judgment. FedRAMP does not classify the techniques this way. | `VDR-CSO-DET` | Mapping |
| **Data Analysis** | A required evaluation of each detected vulnerability in context: is it likely exploitable, is it internet-reachable, what is the PAIN rating. Providers must assume exploitation can be automated unless they have evidence otherwise. Evaluation factors, false-positive checks, and grouping are SHOULD. | `VER-EVA-ELX`, `EIR`, `EPA`, `AIA`, `EFA`, `EFP`, `GRV` | Rule text |
| **Analysis Basis and Analysis Agent** | The central determinations are provider **estimates** ("estimate the likely potential agency impact", "likely exploitable"). Under the taxonomy's own definitions that places them in the Inferential Tier, with Human or Statistical Model analysts. | `VER-EVA-ELX`, `EPA` | Mapping |
| **Collection Mechanism, Analysis Mechanism** | Automation is encouraged (SHOULD): use automated services, and automatically detect on new or significantly changed resources. The rules do not require a description of the mechanism. The `VDR-CSO-DET` note discourages a separate compliance-only detection process unless it consumes data directly from the areas that maintain the service. | `VDR-CSO-ADT`, `DAC`, `DET` (notes) | Rule text |
| **Telemetry** | Detection events (time and source of detection) and the results of resource-status verification and validation. | `VER-RPT-VDT`, `VDR-TFR-NMV`, `MVX`, `MVF` | Mapping |
| **Automated Determination** | The evaluation outcomes: likely exploitable (yes or no), internet-reachable (yes or no), PAIN N0 to N5, overdue flag, accepted status, final disposition. | `VER-EVA-*`, `VER-TFR-MAV`, `VER-RPT-VDT` | Mapping |
| **Metric** | A monthly human-readable report of all activity since the previous report, plus historical activity in JSON for automated retrieval. | `VER-TFR-MHR`, `VER-RPT-PER`, `VER-TFR-MRH` | Rule text, with the taxonomy item mapped |
| **Confirmation** | Verification and validation are applied to the **status of the Subject** (see 2.2). The reliability of the detection and response process itself is handled differently: a failure in it is a vulnerability. | `VDR-CSO-DET`, `VDR-CSO-FAV`, `VDR-TFR-NMV`, `MVX`, `MVF` | Rule text |

## 1.3 Detection and verification cadences

Detection cadences are SHOULD. Verification and validation cadences are MUST where noted.

| Rule | Applies to | Class A | Class B | Class C | Class D |
|---|---|---|---|---|---|
| `VDR-TFR-PDD` | all resources likely to drift | 3 months | 1 month | 14 days | 7 days |
| `VDR-TFR-PCD` | all resources not likely to drift | 6 months | 6 months | 1 month | 1 month |
| `VDR-TFR-PSD` | representative samples of similar machine-based resources | 14 days | 7 days | 3 days | 1 day |
| `VDR-TFR-NMV` (MUST) | non-machine-based resources, verify and validate status | 3 months | 3 months | 3 months | 3 months |
| `VDR-TFR-MVX` (20x) | machine-based resources, verify and validate status | 1 month (SHOULD) | 7 days (MUST) | 3 days (MUST) | no Class D rule |
| `VDR-TFR-MVF` (Rev5) | machine-based resources, verify and validate status | no Class A rule | 1 month (SHOULD) | 1 month (MUST) | 1 month (MUST) |

At Class C, the 20x machine-resource cadence (3 days) is roughly ten times tighter than Rev5's (1 month). That is a path-based difference, not only a class-based one.

## 1.4 Evaluation and the PAIN scale

`VER-EVA-EPA` (MUST) requires one rating per detected vulnerability. The scale gained N0 in the October 5 release.

| Rating | Meaning (condensed) |
|---|---|
| N0 | Exploitation is extremely unlikely to have any adverse effects on agencies |
| N1 | Minimal customer effects on one or more agencies |
| N2 | Narrow customer effects on one or more agencies |
| N3 | A disruptive customer effect on one agency |
| N4 | A debilitating effect on one agency, or a disruptive effect on more than one |
| N5 | A debilitating effect on more than one agency |

Other firm determinations: `VER-EVA-ELX` (is it likely exploitable) and `VER-EVA-EIR` (is it internet-reachable), both MUST. `VER-EVA-EFA` lists eight factors a provider SHOULD consider: criticality, reachability, exploitability, detectability, prevalence, privilege, proximate vulnerabilities, and known threats. `VER-TFR-EVU` (SHOULD) asks for evaluation within 14 days of detection at Class A, 7 at B, 5 at C, and 2 at D. `VER-TFR-MAV` (MUST) requires any vulnerability not fully mitigated or remediated within **192 days** of evaluation to be categorized as accepted.

## 1.5 Mitigation and remediation timeframes (`VDR-TFR-PVR`, SHOULD)

Maximum time from evaluation to partially mitigate, fully mitigate, or remediate to a lower PAIN rating. Each cell shows three values in days, in this order: internet-reachable and likely exploitable, not internet-reachable and likely exploitable, not likely exploitable.

| PAIN | Class A | Class B | Class C | Class D |
|---|---|---|---|---|
| N1 | no timeframe | no timeframe | no timeframe | no timeframe |
| N2 | 96 / 160 / 192 | 96 / 160 / 192 | 48 / 128 / 192 | 24 / 96 / 192 |
| N3 | 32 / 64 / 192 | 32 / 64 / 192 | 16 / 32 / 128 | 8 / 16 / 64 |
| N4 | 8 / 32 / 64 | 8 / 32 / 64 | 4 / 8 / 64 | 2 / 8 / 32 |
| N5 | 4 / 8 / 32 | 4 / 8 / 32 | 2 / 4 / 16 | 12 hours / 1 day / 8 days |

N0 has no row. Classes A and B are identical. This table is, in effect, a published decision rule that maps a determination (PAIN, reachability, exploitability) to a response deadline.

`VDR-TFR-RMN` (SHOULD) covers the remainder: mitigate or remediate remaining vulnerabilities during routine operations. `VDR-TFR-KEV` (SHOULD) says to remediate Known Exploited Vulnerabilities by the CISA catalog due dates, even if fully mitigated.

## 1.6 Reporting

- **Cadence:** `VER-TFR-MHR` (MUST) requires a consistent, human-readable report to all necessary parties at least monthly. `VER-RPT-PER` (MUST) requires persistent reporting that summarizes all activity since the previous report, including persistent verification and validation. These reports are FedRAMP Certification Data and subject to the data sharing rules.
- **Active vulnerabilities (`VER-RPT-VDT`, MUST, "if applicable"):** eleven items.
  1. The provider's internal tracking identifier
  2. Time and source of detection
  3. Time of completed evaluation
  4. Internet-reachable or not
  5. Likely exploitable or not
  6. Historical and current estimated PAIN rating
  7. Time and PAIN rating of each completed reduction
  8. Estimated time and target of the next reduction
  9. Overdue now or likely to become overdue, with an explanation
  10. Supplementary information
  11. Final disposition
- **Accepted vulnerabilities (`VER-RPT-AVI`, MUST):** eight items. These are the identifier, detection time and source, evaluation time, reachability, exploitability, current PAIN rating, an explanation of why it is accepted, and supplementary information.
- **Not required in either list:** the affected information resource, which is the Subject (see 2.2).
- **Disclosure:** `VER-RPT-NID` (MUST NOT) forbids irresponsible disclosure of exploitation-enabling detail while requiring enough information for risk-based decisions. `VER-RPT-RPD` (MAY) permits public disclosure when it will not likely lead to exploitation.
- **Overviews:** `VER-RPT-HLO` (SHOULD) asks for high-level overviews of all detection and response activity, including disclosure programs, bug bounties, and penetration testing.
- **Schemas:** `VER-RPT-VDT` and `VER-RPT-PER` reference the Vulnerability Detail Report schema. `VER-RPT-AVI` references the Accepted Vulnerability Info schema. `VER-TFR-MRH` references the Historical VER Activity schema.
- **Historical activity (`VER-TFR-MRH`):** Class A MAY and Classes B to D SHOULD make all recent historical activity available as JSON for automated retrieval, updated at least monthly (A and B), every 14 days (C), or every 7 days (D). The rule says "recent" and does not define a retention depth.

## 1.7 Agency-side and FedRAMP-side rules

- `VER-AGM-RVR` (SHOULD): agencies review vulnerability reports at intervals matching their ATO risk posture, using automated processing of machine-readable data. The rule's note recommends reviewing only overdue and accepted vulnerabilities with PAIN above N2, unless the provider recommends mitigations or the service supports a higher-risk system.
- `VER-AGM-MAP` (SHOULD): agencies use the reported information to maintain **their own** Plans of Action and Milestones when relevant. This is where the POA&M concept now lives.
- `VER-FRP-ARP` and `VER-FRP-ADV` (MAY): FedRAMP may require additional or more frequent reporting, or sensitive details, in connection with a corrective action plan or investigation.
- `VDR-CSO-FAV` (MUST): failures in the provider's own detection and response processes are treated as vulnerabilities.

---

# Part 2: Comparison to KSI telemetry

## 2.1 Side by side

| Dimension | KSI (`SDR-CSX-KSI`, `SDR-CSX-KMT`) | VDR/VER |
|---|---|---|
| **Subject** | Defined per KSI by the provider: a capability, process, or resource | A population of information resources, partitioned by the rules into drift-prone, non-drift, sampled, and non-machine-based |
| **Attribute** | Defined per KSI by the provider | Fixed: the vulnerability, with five evaluated attributes (reachability, exploitability, PAIN, overdue, disposition) |
| **Cycle** | Provider explains the cycle "if applicable" (item 2). FedRAMP sets no collection frequency | Set by FedRAMP, varying by Subject class and Certification Class (1.3). Two cadences are also path-specific (`MVX` and `MVF`) |
| **Force of the cadence** | The KSI item itself is MUST | Mostly SHOULD. MUST only for resource-status verification and validation, and for monthly reporting |
| **Analysis rubric** | Abstract; the provider defines it. Pass/fail or degree of health is a taxonomy principle, not FedRAMP text | Enumerated: three MUST determinations, eight SHOULD factors, a six-level ordinal scale (N0 to N5), a 192-day acceptance threshold |
| **Link from determination to action** | None in the KSI rules | `VDR-TFR-PVR` maps PAIN, reachability, and exploitability to a response deadline (1.5) |
| **Mechanism description** | Item 4 asks for verification of "the automation in place," or that it is not necessary | No mechanism description required. Automation is SHOULD |
| **Per-instance record** | `ksiEvidence` in the SDR schema (type, description, location, text, date) | Eleven-item vulnerability record and eight-item accepted record, each with a dedicated schema |
| **Identifies the Subject in each record** | The KSI ID names the KSI, not a resource | Not required by either item list |
| **Historical metrics** | `SDR-CSX-KMT`: class-scaled depth. Class B SHOULD (30-day and one-year summaries), Class C MUST (same plus daily data including persistent-validation status), Class D must exceed. The SDR schema examined earlier has no field for it | `VER-TFR-MRH`: JSON for automated retrieval, class-scaled update cadence, retention depth undefined ("recent"). Has a published schema |
| **Periodic reporting** | No dedicated cadence rule for KSI content | `VER-TFR-MHR`: at least monthly, MUST |
| **Verification and validation object** | The measurement chain (items 3 to 5) | The status of the Subject (`DET`, `NMV`, `MVX`, `MVF`) |
| **Reliability of the chain** | Verify and validate it (items 3 to 5) | Recursive: a failure in detection or response is itself a vulnerability (`FAV`) |
| **Independent assessment, in the SDR** | `SDR-CSX-KSI` items are provider-only. Independent assessment happens as an annual event (`IVV-CSX-AIA`) | VDR and VER are FedRAMP rules, so each provider-applicable rule is documented through `SDR-CSO-FRR`, whose seven items include independent verification and validation |
| **Agency consumption** | No agency-side rule in the KSI rules | `VER-AGM-RVR` and `VER-AGM-MAP` (SHOULD) |

## 2.2 What VDR/VER shows about the taxonomy

1. **The Subject definition may be too narrow.** The taxonomy defines Subject as "the capability the KSI's claim is about." In VDR the rules are stated per category of information resource, and a vulnerability is itself defined as an attribute of hardware, software, a process, or a procedure. `FRD-IRS` already covers capabilities and resources in one term, because it includes processes, policies, hardware, and software. One option is to define Subject by reference to the information resource. The alternative reading is that the Subject is the detection and response capability and the resources are the population it is applied to, which parallels the IAM workflow example. The text of the rules favors the resource reading. This is an open decision.
2. **Cycle is multiple, and it follows the Subject class.** The taxonomy already allows more than one instance of any element, so nothing needs to change, but a KSI-only reading would not have predicted five or more Cycles on one requirement.
3. **"Automated Determination" fits poorly here.** The central VDR/VER determinations (likely exploitable, PAIN) are provider judgments. The taxonomy allows a Human Analysis Agent, but the element name reads as excluding them. An unqualified "Determination" would cover both.
4. **PAIN is a Degree of Health scale.** It is an ordinal, consistently quantifiable scale, which fits the "degree of health" option in the Data Analysis principle. FedRAMP also does something the taxonomy only implies: it defines what each grade means and attaches response deadlines to it.
5. **Verification and validation mean two different things across the rule sets.** In `SDR-CSX-KSI` they confirm the measurement chain, which is the taxonomy's Confirmation tier. In `VDR-CSO-DET`, `NMV`, `MVX`, and `MVF` they confirm the status of the Subject, which in taxonomy terms is Evidence about the Subject. A reader moving between the two will see the same words used for different objects. The taxonomy's Confirmation tier does not apply to VDR/VER as a separate layer, because `FAV` handles the chain's reliability recursively.
6. **The affected resource is not a required reported field.** A vulnerability record must say when it was detected and how severe it is, but neither item list requires saying which resource has it. I have not checked whether the published schemas add that field.
7. **Both rule sets have a Metric. Only one has a schema.** KSI's Metric requirement is specific about depth but has no schema field in the SDR schema I examined. VDR/VER's has a schema but leaves depth undefined.
8. **The determination-to-action mapping is unique to VDR/VER.** Nothing in the KSI rules connects a Finding to a required response. If the taxonomy is meant to generalize beyond KSIs, that link (determination, then response obligation) has no element today.

---

# Part 3: Corrections to my earlier comparison

| Earlier statement | Corrected |
|---|---|
| Subject is fixed globally ("a vulnerability") with no equivalent | The Subject is the information resource, partitioned by the rules. A vulnerability is the Attribute |
| The eight evaluation factors MUST inform evaluation | `VER-EVA-EFA` is SHOULD ("at least the following factors") |
| Class-scaled Cycles, stated without force | The detection cadences (`PDD`, `PCD`, `PSD`) are SHOULD. Only the verification and validation cadences and monthly reporting are MUST |
| `MVX` and `MVF` described only as split by path | Each also omits a class: `MVX` has no Class D, `MVF` has no Class A |
| VDR/VER has no Design, Mechanism Verification, or Mechanism Validation structure, only the `FAV` recursion | VDR/VER does verify and validate, but the object is the Subject's status. `FAV` addresses the chain's reliability |
| The PAIN scale is N1 to N5 | N0 to N5 as of the October 5 release |
| Not mentioned | The `VDR-TFR-PVR` PAIN-by-class timeframe tables (1.5) and the 192-day acceptance rule (`VER-TFR-MAV`) |

## Caveats

- Statements about KSI metrics and SDR schema content rely on the SDR schema version I examined earlier (v1.0.0). The current hosted schemas were not re-fetched.
- The Acquisition Basis, Analysis Basis, Telemetry, and Automated Determination rows in 1.2 are mappings, not FedRAMP statements.
- `VDR-TFR-MVX` and `MVF` define the verification and validation cadence for "the status of machine-based information resources." I have not found a rule that spells out what that status check consists of.
