# CISA BOD 26-04 and FedRAMP VDR/VER: Alignment and Overlap

Revised against the text of the directive. This version replaces the earlier one, which relied on secondary sources for the BOD. Section 11 lists what changed.

## Basis and verification status

- **BOD (verified).** A saved copy of CISA's web page for BOD 26-04 (June 10, 2026), supplied by the user and read in full. Everything labeled "BOD text" comes from it.
- **BOD (not verified).**
  - **Table 1 (Remediation Timelines)** is an image in the saved page. The image file was not part of the upload, so I could not read it. The 14-day and 60-day tiers and the combinations that trigger each tier come from secondary sources (Tenable, Patrowl, CSA) and are labeled that way. The page text itself confirms only the three-day tier with forensic triage and the "fix on system upgrade" tier.
  - **CISA's Implementation Guidance** and Internet Exposure Reduction Guidance were not provided.
- **FedRAMP.** `fedramp-consolidated-rules.json`, rules version `2026.10.13.01`. The October 13 release (PR #37) only added 800-53 control mappings to 35 rules. No VDR or VER statement, force, name, or timeframe differs from version `2026.10.08.01`. FedRAMP's own alignment claims come from Public Notice NTC-0014 (June 16, 2026).

## Summary

- FedRAMP built VDR and VER to align with the BOD and says so. `FRD-KEV` is defined by reference to BOD 26-04. The `effective` blocks on both rulesets read `Mandated by CISA BOD 26-04`. NTC-0014 says FedRAMP confirmed with CISA that providers following VDR/VER meet or exceed the BOD's expectations.
- They are different instruments. The BOD binds agencies and sets per-asset, per-CVE deadlines from four binary variables. VDR/VER binds providers and sets per-vulnerability deadlines from a provider-estimated impact rating (PAIN) combined with reachability and exploitability.
- The BOD routes FedRAMP-certified services through the FedRAMP PMO and "collaborative continuous monitoring." Neither document says how responsibility for a given deadline divides between the agency and the provider.
- Neither source gives a provider-to-CISA reporting path. The chain appears to run from the provider to FedRAMP and its agencies, then from each agency to CISA through CDM (section 8).
- The BOD's mitigation rule and its reporting model differ from VDR/VER in ways the secondary sources did not show (section 6).

## 1. What the BOD requires (BOD text)

**Scope**

- The directive applies to agency assets in any federal information system, defined as one "used or operated by an agency or by another entity on behalf of an agency."
- "Unless directed by the governing procurement contract, this Directive does not apply to contractors, but FCEB agencies must review all contracts to determine what modifications are necessary to comply."
- For systems hosted in third-party environments, including FedRAMP certified environments, each agency must maintain an inventory of those systems, obtain status updates, and ensure compliance "through collaborative continuous monitoring."
- "For FedRAMP certified cloud service offerings, agencies must work through the FedRAMP PMO to ensure compliance with this Directive." For offerings that are not FedRAMP certified, agencies work directly with the provider, and all deviations must be documented and communicated to the customer agency.

**Variables.** Four binary variables set urgency.

| Variable | Question | Who answers |
|---|---|---|
| Asset Exposure | Is the vulnerable asset publicly exposed? | The agency, using CISA's Internet Exposure Reduction Guidance |
| KEV Status | Is the CVE ID in CISA's KEV Catalog? | CISA publishes it for every CVE ID |
| Exploit Automation | Can an adversary automate all steps needed to exploit it? | CISA publishes it for every CVE ID (Vulnrichment) |
| Technical Impact | Does exploitation give partial or total control? | CISA publishes it for every CVE ID (Vulnrichment) |

**Definitions**

- **Publicly exposed:** "Any agency-owned or agency-managed IT resource accessible to unauthenticated or untrusted entities via public networks, such as the internet, regardless of its physical or logical location." If any method finds an asset exposed, the value is Yes.
- **Total control:** the exploit gives the adversary total control over the behavior of the software, including if it reliably reveals log-in credentials.
- **Partial control:** limited control or information exposure, or a low stochastic opportunity for total control. A denial-of-service attack is limited control.
- **Remediated:** the vulnerability is eliminated through patching, decommissioning, or another action.

**Required actions**

- **Phase I (effective immediately):**
  - Update vulnerability management policy. At a minimum it must establish ongoing remediation of KEVs, assign roles, define response actions, set up validation and enforcement, and set tracking and reporting.
  - Report KEV status through the CDM Dashboard, or manually every two weeks.
  - Continue Cyber Hygiene scanning, and remove its source IPs from blocklists.
  - Attest publicly exposed IPs and domain names each quarter.
- **Phase II (within 60 days):** update processes to support ongoing remediation based on the CVE database and the KEV Catalog.
- **Phase III (within 180 days):**
  - Remediate each vulnerability by the Table 1 timelines.
  - Continuously identify and tag agency-owned assets reachable from outside via a routable IP.
  - Tags carry organization, environment, exposure, and asset type.
  - Agencies not automated through CDM report every seven days in machine-readable form.

**Table 1 notes**

- **Unit and days:** days are calendar days. Each asset with an instance of a CVE ID is remediated within the Table 1 timeline.
- **Forensic triage:** "& forensic triage" means the agency completes remediation or mitigation within the timeline (three days) and carries out a forensic triage of the asset to assess whether it is compromised.
- **Dynamic timelines:** removing a system from the internet changes Publicly Exposed from Yes to No and shifts the required timeline for further action back. A new KEV listing shortens it.
- **Clock start:** the earlier of CISA adding the vulnerability to the KEV, or the agency identifying it on an asset and updating the CDM dashboard.
- **Fix on system upgrade:** remediate at the next scheduled major upgrade or rebuild.
- **Annual reassessment:** CISA reassesses the timelines each fiscal year.

## 2. BOD variables mapped to VDR/VER

| BOD variable | FedRAMP counterpart | Fit |
|---|---|---|
| **Asset Exposure** | `VER-EVA-EIR` (MUST) evaluates internet-reachability. It appears as a flag in `VER-RPT-VDT` and `VER-RPT-AVI` | Aligned in intent. The BOD asks whether an asset is accessible to untrusted entities and treats any positive method as Yes. FedRAMP asks whether a triggering payload can reach the vulnerable service, and its note says filtering or rejecting such payloads means it should no longer be considered internet-reachable. Whether the BOD would treat a filtered asset as exposed is not stated in the page text |
| **KEV Status** | `FRD-KEV`; `VDR-TFR-KEV` (SHOULD); `VDR-CSO-AKE` (SHOULD NOT deploy new resources with KEVs) | Aligned on remediation. VER has no KEV determination and no KEV field in its reports |
| **Exploit Automation** | `VER-EVA-AIA` (MUST): assume exploitation can be automated unless there is evidence otherwise; `VER-EVA-ELX` (MUST) | FedRAMP defaults to the high case. The BOD takes the answer from CISA's published data |
| **Technical Impact** | `VER-EVA-EFA` "Privilege" factor (SHOULD). `VER-EVA-EPA` (MUST) rates impact on agencies | Partial. No FedRAMP rule asks for a total-or-partial-control determination. PAIN is a different axis |

## 3. Deadline structure

| | BOD 26-04 | VDR/VER |
|---|---|---|
| Binds | Agencies | Providers |
| Unit | Each asset instance of a CVE ID | Each vulnerability, groupable (`VER-EVA-GRV`) |
| Vulnerability scope | Identified by CVE ID | `FRD-VUL`: includes misconfigurations, weak credentials, exposures, and gaps in controls or KSIs |
| Clock start | Earlier of KEV addition or agency identification recorded in CDM | `VDR-TFR-PVR` runs from evaluation. `VER-TFR-EVU` (SHOULD) asks for evaluation within 14, 7, 5, or 2 days of detection (Classes A to D) |
| Inputs | Exposure, KEV, automatable, technical impact | PAIN, internet-reachable, likely exploitable |
| Outputs | Three days with forensic triage, then (per secondary sources) three days, 14 days, 60 days, and fix on system upgrade | `VDR-TFR-PVR` table by class, from 12 hours to 192 days, with no deadline at N1 |
| What satisfies it | Remediation (elimination). Mitigation shifts the timeline | Partial or full mitigation, or remediation, to a lower PAIN rating (`VDR-TFR-PVR`) |
| Force | Binding | SHOULD |

**Boundary comparisons.** These are indicative only, because Table 1 was not available.

- **Fast end.** The BOD's fastest tier is three days. FedRAMP's N5, internet-reachable and likely exploitable cell is 4 days at Classes A and B, 2 days at Class C, and 12 hours at Class D.
- **Slow end.** The BOD's slowest outcome is fix on system upgrade. FedRAMP allows up to 192 days, and anything not fully mitigated or remediated within 192 days must be marked accepted (`VER-TFR-MAV`, MUST).
- **Clock arithmetic.** At Class C the maximums add: up to 5 days to evaluate plus 2 days to mitigate is 7 days from detection for an N5, internet-reachable, likely exploitable vulnerability. At Class D it is 2 days plus 12 hours. The BOD clock starts at identification.

## 4. Where they align

- **Graduated, risk-based deadlines.** Both replace flat deadlines with deadlines driven by exposure and exploitability.
- **The same risk signals.** Exposure, exploitability, and automation drive both.
- **Dynamic.** The BOD re-evaluates as exposure and KEV status change. FedRAMP's detection is persistent (`VDR-CSO-DET`, `VDR-CSO-RES`).
- **Remediation means elimination.** The BOD defines remediation as eliminating the vulnerability. FedRAMP's note on `VDR-CSO-RES` says remediation is entirely eliminating it and does not use "mitigation" and "remediation" interchangeably.
- **Shared vocabulary and dates.** `FRD-KEV` points at the BOD. FedRAMP's December 7, 2026 date matches the BOD's 180-day Phase III date (180 days after June 10 is December 7).

## 5. Where they overlap

These are the places where both cover the same ground, so a cloud service used by an agency can be subject to both.

- **KEV remediation.** `VDR-TFR-KEV` points providers at the KEV due dates "as required by CISA Binding Operational Directive (BOD) 26-04 or any successor guidance." The BOD text sets timelines by Table 1. It does not mention per-entry due dates, so I can't tell from the page whether catalog entries still carry them.
- **Exposure determination.** The agency determines exposure under the BOD. The provider determines and reports internet-reachability under VER.
- **Status updates.** The BOD makes the agency obtain status updates from third-party hosts through collaborative continuous monitoring. VER reports and Ongoing Certification Reports are the FedRAMP-side source for them.
- **Agency use of provider data.** `VER-AGM-RVR` (SHOULD) has agencies review vulnerability reports. `VER-AGM-MAP` (SHOULD) has agencies keep their own POA&Ms from them.

## 6. Where they diverge

- **Mitigation versus remediation.**
  - The BOD treats mitigation, such as removing exposure, as shifting the timeline. Remediation is still required by the shifted timeline, and at the lowest tier at the next scheduled major upgrade or rebuild.
  - FedRAMP accepts partial or full mitigation to a lower PAIN rating as meeting `VDR-TFR-PVR`. `VDR-TFR-RMN` (SHOULD) then leaves remaining vulnerabilities to routine operations "as determined necessary by the provider."
  - For KEVs, `VDR-TFR-KEV` is the stricter one: remediate by the due dates even if fully mitigated.
- **Force.** The BOD binds agencies. `VDR-TFR-KEV` and `VDR-TFR-PVR` are SHOULD. Under `FRD-SHD`, a provider that does not follow a SHOULD rule must explain the decision in its security documentation. NTC-0014 says `VDR-TFR-KEV` "requires" BOD timelines unless there are valid technical reasons. The rule text says SHOULD.
- **Forensic triage.** The BOD requires it for the top tier, following CISA's guidance. The VDR/VER rules contain no "forensic" language. The nearest link is `VER-TFR-IRI`, which treats internet-reachable, likely exploitable vulnerabilities above N3 as FedRAMP Reportable Incidents (SHOULD at Classes C and D, MAY at A and B).
- **Technical impact.** No required determination of total or partial control.
- **Reporting.**
  - The BOD has agencies report to CISA: KEV status through the CDM Dashboard or every two weeks, asset tags every seven days, and a quarterly attestation of publicly exposed IPs and domains.
  - FedRAMP has providers report to all necessary parties at least monthly (`VER-TFR-MHR`).
  - A BOD status update for a cloud-hosted asset needs a CVE ID and an asset. `VER-RPT-VDT` requires neither, only the provider's internal tracking identifier.
  - Neither source has the provider report to CISA (section 8).
- **Unit and scope.** The BOD works per asset instance of a CVE ID. FedRAMP can group affected resources and covers vulnerabilities beyond CVEs.
- **Data sources.** The rules never mention Vulnrichment, SSVC, or CVSS.
- **Ownership of assets.** The BOD's exposure definition and asset tags refer to agency-owned or agency-managed assets. Whether a provider's infrastructure counts is not stated in the page text.

## 7. How the BOD routes FedRAMP-certified services

- Agencies must work through the FedRAMP PMO to ensure compliance.
- Agencies keep an inventory of third-party-hosted systems and obtain status updates through collaborative continuous monitoring.
- FedRAMP's rules and NTC-0014 are the PMO-side mechanism: mandatory VDR and VER, a corrective action plan with notice to all agencies, and revocation after the grace period.
- The BOD does not say how a deadline divides between the agency and the provider, or how an agency performs forensic triage on a provider-operated asset.

## 8. Reporting flow (interpretation)

**What the sources state**

- **BOD.** Every reporting duty is the agency's, and the recipient is CISA: KEV status through the CDM Dashboard or manually every two weeks, asset tags every seven days, a quarterly attestation of publicly exposed IPs and domains, policies on request, and "reporting to CISA, as requested." CISA reports back to agencies, and once a year reports cross-agency status to the Secretary of Homeland Security, the OMB Director, and the National Cyber Director.
- **No provider path in the BOD.** No provision lets a provider or contractor report to CISA, or requires it. The directive names neither authorizing officials nor system owners. Phase I requires agency policy to "assign roles and responsibilities for executing agency actions," so the pass-down is left to the agency.
- **Third-party hosting.** Agencies keep an inventory of third-party-hosted systems, obtain status updates through collaborative continuous monitoring, and work through the FedRAMP PMO for certified offerings.
- **FedRAMP rules.** Providers report to "all necessary parties." `FRD-ANP` says that always includes FedRAMP and agency customers, and may include others by the provider's agreement. Incident reports go to "all affected parties," which `FRD-AAP` says always include FedRAMP and directly impacted agencies. CISA is named only in `FRD-KEV`, `VDR-TFR-KEV`, and the `effective` blocks.

**Interpreted chain.** Neither source states it. It is consistent with every reporting duty being the agency's and with the absence of any provider-to-CISA path.

1. The provider reports to FedRAMP and its leveraging agencies (and others by agreement) through VER reports, Ongoing Certification Reports, and incident reports.
2. Each agency uses that information as the "status updates" input to its BOD compliance. Its policy assigns the roles. The authorizing official's accountability comes from the FISMA and RMF structure, not from the BOD page.
3. The agency reports to CISA through CDM. That this covers provider-hosted systems is inferred from the BOD's reference to cloud assets in the CDM Federal Dashboard and the agency's responsibility for third-party-hosted systems.
4. CISA aggregates across agencies.

The FedRAMP PMO sits beside this chain. Agencies "work through" it, and NTC-0014 says FedRAMP confirmed alignment with CISA. Nothing says the PMO passes provider data to CISA.

**Consequence for the data.** The agency, not the provider, must produce the per-asset CDM status from the provider's data. The missing CVE ID and affected-asset fields in `VER-RPT-VDT` (section 6) therefore fall on the agency.

**Open items**

1. **The PMO's role.** Whether it is only a compliance-assurance route or also aggregates anything for CISA is not stated.
2. **Shared services.** A vulnerability in a service shared by many agencies would appear in each leveraging agency's roll-up. The BOD's per-asset model assumes agency-owned or agency-managed assets, and the page does not say how shared provider infrastructure is counted.
3. **Compromise found by forensic triage.** The BOD lists a CISA contact for indications of compromise. The BOD and FedRAMP's incident rules do not say who reports a compromise found on a provider-operated asset.

## 9. Dates

| Date | Event | Source |
|---|---|---|
| 2026-06-10 | BOD issued, Phase I effective | BOD text |
| 2026-06-16 | NTC-0014 published | FedRAMP |
| 2026-07-04 | Optional adoption of VDR/VER begins | `effective.optional_adoption` in the rules |
| About 2026-08-09 | BOD Phase II (within 60 days). NTC-0014 says August 7 | BOD text; NTC-0014 |
| 2026-12-07 | BOD Phase III (within 180 days). VDR and VER mandatory to obtain and maintain certification | BOD text; `effective.date` in the rules |
| 2027-03-07 | End of grace. During grace, providers may maintain certification under a corrective action plan with notice to all agencies | NTC-0014; `effective.date.grace.default` in the rules |
| After 2027-03-07 | FedRAMP Certification revoked for offerings not following the rules | NTC-0014 only |

## 10. New in the October 13 FedRAMP release: control mappings

PR #37 added 800-53 mappings to 35 rules. Examples among VDR/VER:

- `VDR-CSO-DET` maps to RA-5, RA-5(2) to (4), SI-2, SI-3, CA-8, and others.
- `VDR-CSO-RES` maps to IR-4(11), IR-9(3), RA-7, SI-2, and SI-3.
- `VDR-TFR-PVR` and `VER-RPT-VDT` map to SI-2(3).
- `VER-EVA-EPA` maps to RA-3. `VER-EVA-EFA` maps to RA-9.

The BOD's footnote on remediation says its definition is consistent with NIST SP 800-53 Rev 5, which is the only 800-53 tie in the page text.

## 11. Changes from the previous version

| Earlier statement | Corrected |
|---|---|
| CISA publishes the KEV, automation, and impact answers for most CVEs | CISA publishes them for every CVE ID |
| The BOD's reporting is the agency's own internal governance | The BOD requires agencies to report to CISA: CDM or bi-weekly KEV status, seven-day asset tags, quarterly attestation |
| The BOD's mitigation treatment is unconfirmed (secondary sources) | Confirmed in the BOD text. Mitigation shifts the timeline, and remediation is still required. FedRAMP's KEV rule is stricter. FedRAMP's non-KEV approach leaves remaining vulnerabilities to the provider |
| Where the BOD clock starts is unknown | The earlier of KEV addition or agency identification recorded in CDM. FedRAMP's PVR clock starts at evaluation |
| Who meets BOD timelines for a provider-operated service is unresolved | Partly resolved: agencies stay responsible, maintain an inventory, obtain status updates, and work through the PMO. The split between agency and provider is still unstated |
| The BOD covers CVE-referenced vulnerabilities (secondary source) | Confirmed: CISA identifies a vulnerability by its CVE ID |
| The BOD's exposure definition (secondary source) | Now quoted: agency-owned or agency-managed resource accessible to unauthenticated or untrusted entities, with any positive method counting as Yes |
| The 14-day and 60-day tiers | Still unverified. Table 1 is an image that was not in the upload |
| FedRAMP side | Unchanged in substance. Rules version updated to `2026.10.13.01` |
| Who reports to CISA | Not stated. Earlier text said agencies report to CISA and providers report to necessary parties | Section 8 states that neither source gives a provider-to-CISA path, gives the interpreted chain, and lists three open items |
