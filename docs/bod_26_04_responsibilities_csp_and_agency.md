# Responsibilities under CISA BOD 26-04 and FedRAMP VDR/VER

Revised against the text of the directive. This version replaces the earlier summaries, which relied on secondary sources for the BOD. Part 5 lists what changed.

## Basis and verification status

- **BOD (verified).** A saved copy of CISA's web page for BOD 26-04 (June 10, 2026), read in full. Rows labeled "BOD" come from it.
- **BOD (not verified).** Table 1 (Remediation Timelines) is an image that was not in the upload, so the deadline tiers beyond three days with forensic triage and fix on system upgrade are not confirmed. CISA's Implementation Guidance was not provided.
- **FedRAMP.** `fedramp-consolidated-rules.json`, rules version `2026.10.13.01`, and Public Notice NTC-0014 (June 16, 2026). VDR, VER, and the agency rules are unchanged in substance since version `2026.10.08.01`.
- **Source labels.** BOD rows give the BOD section. FedRAMP rows give the rule ID and its force. "Inference" marks my reading, not a statement in either source.

## How the two sources reach each audience

- The BOD binds Federal Civilian Executive Branch agencies. It reaches providers only through contracts: "Unless directed by the governing procurement contract, this Directive does not apply to contractors," but agencies "must review all contracts to determine what modifications are necessary."
- For FedRAMP certified services, the BOD says agencies "must work through the FedRAMP PMO to ensure compliance," and must keep an inventory of third-party-hosted systems and obtain status updates "through collaborative continuous monitoring."
- FedRAMP's rules bind providers directly. VDR and VER become mandatory to obtain and maintain certification on December 7, 2026. FedRAMP's agency rules bind agencies. Most of the agency rules relevant to vulnerabilities are SHOULD.

---

# Part 1: Cloud service providers and system owners

## 1.1 Binding under FedRAMP rules

| Responsibility | Source | Force |
|---|---|---|
| Detect and respond to vulnerabilities systematically, persistently, and promptly | `VDR-CSO-DET`, `VDR-CSO-RES` | MUST |
| Treat failures of your own detection and response process as vulnerabilities | `VDR-CSO-FAV` | MUST |
| Verify and validate resource status: non-machine resources every 3 months; machine resources every 7 days (20x Class B) or 3 days (20x Class C); monthly (Rev5 Classes C and D) | `VDR-TFR-NMV`, `VDR-TFR-MVX`, `VDR-TFR-MVF` | MUST |
| Evaluate each detected vulnerability: likely exploitable, internet-reachable, and PAIN rating N0 to N5. Assume exploitation can be automated unless you have evidence otherwise | `VER-EVA-ELX`, `EIR`, `EPA`, `AIA` | MUST |
| Consider the evaluation factors, check for false positives, group affected resources, and evaluate within 14, 7, 5, or 2 days of detection (Classes A to D) | `VER-EVA-EFA`, `EFP`, `GRV`, `VER-TFR-EVU` | SHOULD |
| Mitigate or remediate within the class timeframes set by PAIN, reachability, and exploitability | `VDR-TFR-PVR` | SHOULD |
| Remediate KEVs by their due dates even if fully mitigated. Do not deploy new machine-based resources with KEVs | `VDR-TFR-KEV`, `VDR-CSO-AKE` | SHOULD, SHOULD NOT |
| Detect on schedule: drift-prone resources, non-drift resources, and samples, at the class cadences | `VDR-TFR-PDD`, `PCD`, `PSD` | SHOULD |
| Categorize any vulnerability not fully mitigated or remediated within 192 days as accepted | `VER-TFR-MAV` | MUST |
| Report at least monthly in a human-readable format, persistently summarizing all activity since the last report | `VER-TFR-MHR`, `VER-RPT-PER` | MUST |
| Provide the 11-item record for active vulnerabilities and the 8-item record for accepted ones | `VER-RPT-VDT`, `VER-RPT-AVI` | MUST |
| Do not disclose exploitation-enabling detail, but disclose enough for risk-based decisions | `VER-RPT-NID` | MUST NOT, MUST |
| Offer historical activity as JSON for automated retrieval, give high-level program overviews | `VER-TFR-MRH` (MAY at Class A), `VER-RPT-HLO` | SHOULD |
| Treat internet-reachable, likely exploitable vulnerabilities above N3 as reportable incidents | `VER-TFR-IRI` | SHOULD at Classes C and D, MAY at A and B |
| Explain, in security documentation, decisions about SHOULD and MAY rules | `FRD-SHD`, `FRD-MAY` | MUST for SHOULD rules, SHOULD for MAY rules |
| Follow VDR and VER to obtain and maintain certification | NTC-0014, `effective` blocks | Mandatory from 2026-12-07 |

Dates: grace runs to 2027-03-07 under a corrective action plan, with notice to all agencies. NTC-0014 says certification is revoked after that date.

## 1.2 What reaches providers through the BOD

| Item | Source | Effect on the provider |
|---|---|---|
| Agencies review all contracts, in consultation with the Contracting Officer | BOD, Scope | Contract modifications may import BOD obligations. The directive does not bind contractors unless the contract says so |
| Agencies obtain status updates on BOD compliance from third-party hosts through collaborative continuous monitoring | BOD, Scope | VER reports and Ongoing Certification Reports are the FedRAMP-side source of those updates |
| For FedRAMP certified offerings, agencies work through the PMO | BOD, Scope | The PMO, not the provider, is the agency's stated route |
| For offerings that are not FedRAMP certified, the supporting provider infrastructure must follow the same requirements, and deviations must be documented and communicated to the customer agency | BOD, Scope | Applies to non-certified offerings only |

## 1.3 What an agency applying the BOD would need (inference from the rule text)

- **Each vulnerability record.** `VER-RPT-VDT` requires the provider's internal tracking identifier, detection and evaluation times, the internet-reachable and likely exploitable flags, PAIN history, overdue status, and disposition. It does not require a CVE ID or the affected asset. The BOD's Table 1 is evaluated per asset instance of a CVE ID.
- **KEV status, automation, and technical impact.** The BOD says CISA publishes these for every CVE ID, so an agency could derive them if it had the CVE ID. VER requires none of them.
- **Existing channel.** `VER-RPT-VDT` includes supplementary information the provider "responsibly determines will help federal agencies assess or mitigate the risk." That is the place for a CVE ID or asset reference.
- **Forensic triage.** The BOD requires the agency to carry out forensic triage of the asset in the top tier. VDR/VER has no forensic triage requirement. Neither document says how that applies to a provider-operated asset.

---

# Part 2: Leveraging agencies and authorizing officials

## 2.1 Binding under the BOD

| Responsibility | Source | Force |
|---|---|---|
| Update vulnerability management policy: ongoing KEV remediation, roles, response actions, internal validation and enforcement, tracking and reporting. Provide it to CISA on request | BOD, Phase I | Binding, effective June 10, 2026 |
| Monitor KEV Catalog updates and aggressively mitigate in line with the KEV remediation timelines | BOD, Phase I | Binding |
| Report KEV status through the CDM Dashboard, or manually every two weeks | BOD, Phase I | Binding |
| Continue Cyber Hygiene scanning, remove its source IPs from blocklists, attest publicly exposed IPs and domains each quarter or on request, submit acceptance letters on request | BOD, Phase I | Binding |
| Update processes to support ongoing remediation based on the CVE database and the KEV Catalog | BOD, Phase II | Binding, within 60 days of issuance (about August 9) |
| Remediate each vulnerability as quickly as possible and no later than Table 1. The clock starts at the earlier of KEV addition or the agency identifying the vulnerability and updating CDM. In the top tier, also carry out forensic triage of the asset | BOD, Phase III and Table 1 notes | Binding, within 180 days (December 7, 2026) |
| Re-evaluate as facts change. Removing exposure shifts the timeline, and a new KEV listing shortens it | BOD, Table 1 notes | Binding |
| Continuously identify and tag agency-owned assets reachable from outside via a routable IP, with organization, environment, exposure, and asset type. Report every seven days in machine-readable form if not automated through CDM | BOD, Phase III | Binding |
| Keep an inventory of systems hosted in third-party environments, including FedRAMP certified ones. Obtain status updates and ensure compliance through collaborative continuous monitoring | BOD, Scope | Binding |
| For FedRAMP certified offerings, work through the FedRAMP PMO | BOD, Scope | Binding |
| Review all contracts with the Contracting Officer to determine needed modifications | BOD, Scope | Binding |

## 2.2 Under FedRAMP rules

| Responsibility | Source | Force |
|---|---|---|
| Complete the ATO for systems using certified services, notify FedRAMP on authorizing, and keep agency policy aligned with OMB M-24-15 | `AGU-USE-ABU`, `AGU-AGC-NAA`, `AGU-AGC-AIP` | MUST |
| Review each Ongoing Certification Report | `CCM-AGM-ROR` (MUST), `AGU-USE-ROR` (SHOULD) | MUST |
| Review vulnerability reports at intervals matching the ATO risk posture, with automated processing. The note suggests focusing on overdue and accepted vulnerabilities above N2 | `VER-AGM-RVR` | SHOULD |
| Maintain agency POA&Ms from the reported information when relevant | `VER-AGM-MAP` | SHOULD |
| Notify FedRAMP of concerns likely to lead to ATO rescission, and collaborate on certification package conflicts | `AGU-USE-NFC`, `AGU-USE-RCF` | MUST |
| Notify the provider of those concerns, designate a senior official for Ongoing Certification Reports and Quarterly Reviews, and consider third-party resources | `AGU-USE-NPC`, `AGU-USE-DSO`, `AGU-USE-RIR` | SHOULD |
| Let providers follow FedRAMP rules | `AGU-USE-AFR` | MUST |
| Do not require additional information beyond FedRAMP's unless the agency head or delegate finds a demonstrable need and notifies FedRAMP | `AGU-AGC-NAR` | MUST NOT |

## 2.3 What provider data covers for BOD purposes (gap analysis from rule text)

Under the reporting flow in Part 3, the agency produces the CDM status, so these gaps fall on the agency.

| BOD need | FedRAMP-provided data | Gap |
|---|---|---|
| Publicly exposed | The internet-reachable flag in `VER-RPT-VDT` and `VER-RPT-AVI` | Definitions differ. The BOD asks whether an asset is accessible to untrusted entities and treats any positive method as Yes. FedRAMP asks whether a triggering payload can reach the service |
| KEV status | None in VER | No CVE ID in the record to look it up |
| Automatable and technical impact | None as such. FedRAMP assumes automatable by default, and PAIN is a different axis | No CVE ID in the record to look up CISA's answers |
| Remediation status against the timeline | Detection time, evaluation time, PAIN history, overdue flag, next reduction | The affected asset is not in the record. FedRAMP's clock starts at evaluation, the BOD's at KEV addition or identification |
| Forensic triage in the top tier | None | Not addressed by VDR/VER |
| Asset tagging and CDM reporting | None | Agency-owned data. Provider-hosted assets are not addressed in the page text |

## 2.4 Authorizing official focus

- **Accepted and overdue vulnerabilities.** `VER-AGM-RVR` says accepted vulnerabilities generally need review only when added or when the agency's use or authorization changes.
- **ATO risk.** Concerns likely to lead to rescission trigger notification to FedRAMP (MUST) and the provider (SHOULD).
- **POA&M.** Where the agency authorizes continued use with accepted vulnerabilities that put its systems at risk, `VER-AGM-MAP` points to the agency's own POA&M.
- **Corrective action plans.** During the March 7, 2027 grace period, notice goes to all agencies. The notice is the trigger for a risk decision.

---

# Part 3: Reporting flow (interpretation)

**What the sources state**

- **BOD.** Every reporting duty is the agency's, and the recipient is CISA: KEV status through the CDM Dashboard or manually every two weeks, asset tags every seven days, a quarterly attestation of publicly exposed IPs and domains, policies on request, and "reporting to CISA, as requested." CISA reports back to agencies, and once a year reports cross-agency status to the Secretary of Homeland Security, the OMB Director, and the National Cyber Director.
- **No provider path in the BOD.** No provision lets a provider or contractor report to CISA, or requires it. The directive names neither authorizing officials nor system owners. Phase I requires agency policy to "assign roles and responsibilities for executing agency actions," so the pass-down is left to the agency.
- **FedRAMP rules.** Providers report to "all necessary parties." `FRD-ANP` says that always includes FedRAMP and agency customers, and may include others by the provider's agreement. Incident reports go to "all affected parties," which `FRD-AAP` says always include FedRAMP and directly impacted agencies. CISA is named only in `FRD-KEV`, `VDR-TFR-KEV`, and the `effective` blocks.

**Interpreted chain.** Neither source states it. It is consistent with every reporting duty being the agency's and with the absence of any provider-to-CISA path.

| Step | Who | What | Basis |
|---|---|---|---|
| 1 | Provider | Reports to FedRAMP and its leveraging agencies (and others by agreement) through VER reports, Ongoing Certification Reports, and incident reports | `VER-RPT-PER`, `VER-TFR-MHR`, `IEC-*`, `FRD-ANP`, `FRD-AAP` |
| 2 | Agency and AO | Uses that information as the "status updates" input to BOD compliance. Policy assigns the roles. The AO's accountability comes from the FISMA and RMF structure | BOD, Scope and Phase I |
| 3 | Agency | Reports to CISA through CDM. That this covers provider-hosted systems is inferred from the BOD's reference to cloud assets in the CDM Federal Dashboard and the agency's responsibility for third-party-hosted systems | BOD, Scope, Phase I, and Phase III |
| 4 | CISA | Aggregates across agencies and reports annually | BOD, CISA Actions |

The FedRAMP PMO sits beside this chain. Agencies "work through" it, and NTC-0014 says FedRAMP confirmed alignment with CISA. Nothing says the PMO passes provider data to CISA.

**Consequence for each audience**

- **Providers.** Nothing in either source obliges a provider to report to CISA. The provider's reporting obligations run to FedRAMP and agencies.
- **Agencies and AOs.** The agency, not the provider, must produce the per-asset CDM status from the provider's data. The missing CVE ID and affected-asset fields in `VER-RPT-VDT` (sections 1.3 and 2.3) therefore fall on the agency.

**Open items**

1. **The PMO's role.** Whether it is only a compliance-assurance route or also aggregates anything for CISA is not stated.
2. **Shared services.** A vulnerability in a service shared by many agencies would appear in each leveraging agency's roll-up. The BOD's per-asset model assumes agency-owned or agency-managed assets, and the page does not say how shared provider infrastructure is counted.
3. **Compromise found by forensic triage.** The BOD lists a CISA contact for indications of compromise. The BOD and FedRAMP's incident rules do not say who reports a compromise found on a provider-operated asset.

# Part 4: Tensions the sources do not resolve

- **Information the BOD needs versus the limit on asking for it.** An agency may need a CVE ID or asset reference that VER does not require. `AGU-AGC-NAR` restricts requiring information beyond FedRAMP's. Whether BOD compliance is a demonstrable need is not addressed. The BOD's instruction to work through the PMO may be the intended channel, but neither document says so.
- **Who meets the deadline.** The BOD keeps the agency responsible and routes FedRAMP certified services through the PMO. It does not say how a deadline divides between the agency and the provider.
- **Asset ownership.** The BOD's exposure definition and tagging duty refer to agency-owned or agency-managed assets. How that covers provider-hosted assets is unstated.
- **Forensic triage of provider-operated assets.** Unaddressed in both.
- **Report review duty.** Reviewing Ongoing Certification Reports is MUST in `CCM-AGM-ROR` and SHOULD in `AGU-USE-ROR`.
- **Phase II date.** 60 days after June 10 is August 9. NTC-0014 says August 7.

# Part 5: Changes from the earlier summaries

| Earlier statement | Corrected |
|---|---|
| Agency BOD duties came from secondary sources | Now from the BOD text, in three phases (immediate, 60 days, 180 days) |
| BOD reporting was not described | Agencies report KEV status through CDM or every two weeks, asset tags every seven days, and attest exposed IPs and domains quarterly |
| Who meets BOD timelines for a provider-operated service was an open question | Partly answered: agencies stay responsible, keep an inventory, obtain status updates, and work through the PMO. The split of a deadline is still unstated |
| The BOD's contractor scope was inferred | Confirmed in the BOD text, with contract review in consultation with the Contracting Officer |
| Forensic triage wording was from a quotation | Confirmed. The agency completes remediation or mitigation in three days and triages the asset per CISA's guidance |
| Provider-side exposure to the BOD was inferred | Section 1.2 gives it from the BOD text. Section 1.3 remains inference and is labeled |
| Table 1 deadline tiers | Still unverified beyond the three-day and fix-on-upgrade tiers |
| FedRAMP side | Unchanged in substance. Rules version updated to `2026.10.13.01` |
| Who reports to CISA | Not stated. Earlier text said agencies report to CISA and providers report to necessary parties | Part 3 states that neither source gives a provider-to-CISA path, gives the interpreted chain, and lists three open items |
