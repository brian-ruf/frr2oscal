"""
package2oscal — Convert FedRAMP CR26 CPO/SDR JSON files to OSCAL SSP/AP/AR.

Reads a FedRAMP Certification Package Overview (CPO) JSON file and an optional
Security Decision Record (SDR) JSON file and produces a set of OSCAL documents:

* **SSP** (system-security-plan) — assembled from CPO content plus SDR
  control-implementation statements.
* **AR** (assessment-results) — assembled from SDR assessment and evidence
  content; produced only when an SDR is supplied.
* **AP** (assessment-plan) — a minimal shell that imports the SSP and lists
  the reviewed controls; produced only when an SDR is supplied.

Both 20x (KSI-based) and Rev5 (NIST 800-53 control-based) SDRs are supported;
the path is auto-detected from the SDR content.

Constants:
    FEDRAMP_NS (str): FedRAMP OSCAL namespace URI for extension props.
    CYBERCRAFT_NS (str): Cybercraft OSCAL namespace URI for presentation props.
    CR26_CATALOG_PLACEHOLDER (str): Placeholder href used in ``import-ap`` /
        ``import-ssp`` links when no resolved file URI is available.
    OSCAL_VERSION (str): OSCAL version recorded in generated documents.
    PROFILE_BASE_URL (str): GitHub raw-content URL template for the FedRAMP
        2026 OSCAL class profiles. Contains ``{path}`` (``"20X"`` or
        ``"Rev5"``) and ``{cls}`` (``"A"``–``"D"``) format placeholders.
"""
from __future__ import annotations

import json
import re
import uuid as _uuid_mod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from oscal.oscal_assessment import AssessmentPlan, AssessmentResults
from oscal.oscal_content import OSCAL, get_support
from oscal.oscal_helpers import new_uuid
from oscal.oscal_implementation import SSP

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

FEDRAMP_NS = "https://fedramp.gov/ns/oscal"
CYBERCRAFT_NS = "http://cybercraft.app/ns/oscal"
CR26_CATALOG_PLACEHOLDER = "#"
OSCAL_VERSION = "1.2.3"
PROFILE_BASE_URL = (
    "https://raw.githubusercontent.com/brian-ruf/frr2oscal"
    "/refs/heads/main/data/OSCAL/FedRAMP_2026_OSCAL_profile_{path}-{cls}.json"
)

# Stable party UUID for FedRAMP PMO — same value used in frr2oscal.py catalog.
_PARTY_UUID_FEDRAMP = "77e0e2c8-2560-4b3f-a3a7-a5a19f645f7f"

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format with Z suffix.

    Returns:
        str: Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ``.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _prop(name: str, value: str, ns: str = FEDRAMP_NS, remarks: str = "") -> dict:
    """Build a minimal OSCAL prop dict.

    Args:
        name (str, required): Property name.
        value (str, required): Property value.
        ns (str, optional): Property namespace URI. Defaults to FEDRAMP_NS.
        remarks (str, optional): Remarks text. Defaults to empty string.

    Returns:
        dict: OSCAL prop dict.
    """
    p: dict = {"name": name, "ns": ns, "value": value}
    if remarks:
        p["remarks"] = remarks
    return p


def _link(href: str, rel: str = "", text: str = "") -> dict:
    """Build a minimal OSCAL link dict.

    Args:
        href (str, required): Link href (URI or ``#uuid``).
        rel (str, optional): Link relation. Defaults to empty string.
        text (str, optional): Link display text. Defaults to empty string.

    Returns:
        dict: OSCAL link dict.
    """
    lnk: dict = {"href": href}
    if rel:
        lnk["rel"] = rel
    if text:
        lnk["text"] = text
    return lnk


def _to_datetime(date_str: str) -> str:
    """Normalize a bare date or datetime string to OSCAL date-time-with-timezone.

    Bare dates (``YYYY-MM-DD``) are expanded to midnight UTC
    (``YYYY-MM-DDTHH:MM:SSZ``). Strings that already contain ``T`` are
    returned unchanged.

    Args:
        date_str (str, required): Date or datetime string to normalize.

    Returns:
        str: OSCAL ``date-time-with-timezone`` string.
    """
    if date_str and len(date_str) == 10 and "T" not in date_str:
        return f"{date_str}T00:00:00Z"
    return date_str


def _paragraphs(items: list) -> str:
    """Join a list of strings as OSCAL markdown paragraphs.

    Args:
        items (list, required): String items to join.

    Returns:
        str: Items joined with double newlines (OSCAL paragraph separator).
    """
    return "\n\n".join(s for s in items if s)


def _new_model(cls, model_name: str, title: str, version: str = "1.0"):
    """Create a new editable OSCAL model instance.

    Works around a bug in ``OSCAL.new()`` where ``cls.__name__.lower()`` is
    used as the model name (e.g. ``"ssp"``) instead of the correct OSCAL model
    identifier (e.g. ``"system-security-plan"``). The bug affects SSP,
    AssessmentResults, AssessmentPlan, and POAM.

    See ``docs/OSCAL_CLASS_HANDOFF.md`` §1 for the fix request.

    Args:
        cls (type, required): The OSCAL model class (e.g. ``SSP``).
        model_name (str, required): Canonical OSCAL model name matching the
            template filename (e.g. ``"system-security-plan"``).
        title (str, required): Document title written to metadata.
        version (str, optional): Document version written to metadata.
            Defaults to ``"1.0"``.

    Returns:
        OSCAL: A new editable instance of *cls*, or None if the template
            cannot be loaded.
    """
    support = get_support()
    raw = support.load_file(f"{model_name}.xml", as_bytes=False)
    if not raw:
        return None
    obj = OSCAL.__new__(OSCAL)
    obj.__init_common__()
    if not obj.initial_validation(raw):
        return None
    obj.__class__ = cls
    obj._init_common()
    obj._origin = "new"
    obj.is_read_only = False
    root = obj._dict.get(model_name, {})
    if isinstance(root.get("metadata"), dict):
        root["metadata"]["title"] = title
        if version:
            root["metadata"]["version"] = version
    root["uuid"] = str(_uuid_mod.uuid4())
    return obj


# ---------------------------------------------------------------------------
# SSP — metadata helpers
# ---------------------------------------------------------------------------

def _contact_role_id(contact_type: str) -> str:
    """Map a CPO contactType string to an OSCAL role-id.

    Args:
        contact_type (str, required): CPO contact type value.

    Returns:
        str: Corresponding OSCAL role-id.
    """
    mapping = {
        "Security": "security-poc",
        "Sales": "sales-poc",
        "Primary": "system-owner",
    }
    return mapping.get(contact_type, contact_type.lower().replace(" ", "-"))


def _build_ssp_metadata(ssp: SSP, cpo: dict) -> dict:
    """Populate SSP metadata from CPO contact, assessor, and service information.

    Adds roles, parties, and responsible-parties to the SSP metadata.
    Returns a dict mapping role-id strings to their party UUIDs so that
    downstream sections can reference them.

    Args:
        ssp (SSP, required): Target SSP instance to populate.
        cpo (dict, required): Parsed CPO JSON dict.

    Returns:
        dict: Mapping of role-id → party UUID for all parties created.
    """
    role_to_party: dict = {}

    svc = cpo.get("serviceIdentification", {})
    provider_name = svc.get("providerName", "Cloud Service Provider")
    fedramp_id = svc.get("fedRampPackageId", "")
    uei = svc.get("ueiNumber", "")

    # --- Roles ---------------------------------------------------------------
    roles = [
        {"id": "system-owner",   "title": "System Owner"},
        {"id": "prepared-by",    "title": "Prepared By"},
        {"id": "security-poc",   "title": "Security Point of Contact"},
        {"id": "sales-poc",      "title": "Sales Point of Contact"},
        {"id": "assessor",       "title": "Independent Assessor"},
        {"id": "fedramp",        "title": "FedRAMP"},
        {"id": "provider",       "title": "Service Provider"},
    ]
    for role in roles:
        ssp.append_child("metadata/roles", role)

    # --- CSP party -----------------------------------------------------------
    csp_uuid = new_uuid()
    csp_party: dict = {
        "uuid": csp_uuid,
        "type": "organization",
        "name": provider_name,
    }
    if fedramp_id:
        csp_party["external-ids"] = [
            {"scheme": "https://fedramp.gov", "id": fedramp_id}
        ]
    if uei:
        csp_party.setdefault("external-ids", []).append(
            {"scheme": "https://www.sam.gov", "id": uei}
        )
    ssp.append_child("metadata/parties", csp_party)
    role_to_party["system-owner"] = csp_uuid
    role_to_party["prepared-by"] = csp_uuid

    # --- Contact parties -----------------------------------------------------
    for contact in cpo.get("contactInformation", []):
        ctype = contact.get("contactType", "")
        rid = _contact_role_id(ctype)
        contact_uuid = new_uuid()
        party: dict = {
            "uuid": contact_uuid,
            "type": "person",
            "name": contact.get("contactName", ""),
            "member-of-organizations": [csp_uuid],
        }
        email = contact.get("contactEmail", "")
        phone = contact.get("contactPhone", "")
        if email:
            party["email-addresses"] = [email]
        if phone:
            party["telephone-numbers"] = [{"number": re.sub(r"\D", "", phone)}]
        ssp.append_child("metadata/parties", party)
        role_to_party[rid] = contact_uuid

    # --- Assessor party ------------------------------------------------------
    assessor_info = cpo.get("assessor", {})
    if assessor_info:
        assessor_uuid = new_uuid()
        assessor_party: dict = {
            "uuid": assessor_uuid,
            "type": "organization",
            "name": assessor_info.get("name", "Assessing Organization"),
        }
        aid = assessor_info.get("assessorID", "")
        if aid:
            assessor_party["external-ids"] = [
                {"scheme": "https://fedramp.gov/assessor", "id": aid}
            ]
        ssp.append_child("metadata/parties", assessor_party)
        role_to_party["assessor"] = assessor_uuid

    # --- FedRAMP PMO party ---------------------------------------------------
    fedramp_party: dict = {
        "uuid": _PARTY_UUID_FEDRAMP,
        "type": "organization",
        "name": "FedRAMP PMO",
        "email-addresses": ["info@fedramp.gov"],
        "links": [_link("https://www.fedramp.gov", "website")],
    }
    ssp.append_child("metadata/parties", fedramp_party)
    role_to_party["fedramp"] = _PARTY_UUID_FEDRAMP

    # --- Responsible-parties -------------------------------------------------
    for rid, puuid in role_to_party.items():
        ssp.append_child(
            "metadata/responsible-parties",
            {"role-id": rid, "party-uuids": [puuid]},
        )

    return role_to_party


# ---------------------------------------------------------------------------
# SSP — system-characteristics helpers
# ---------------------------------------------------------------------------

def _build_ssp_characteristics(ssp: SSP, cpo: dict) -> None:
    """Populate SSP system-characteristics from CPO service and property data.

    Replaces the template placeholder system-id and information-type with
    values derived from the CPO, then adds props and links for service
    metadata, deployment model, trust center, and other CPO fields.

    Args:
        ssp (SSP, required): Target SSP instance to populate.
        cpo (dict, required): Parsed CPO JSON dict.
    """
    svc = cpo.get("serviceIdentification", {})
    props = cpo.get("serviceProperties", {})

    # Scalar fields via put()
    system_name = svc.get("serviceName", "")
    if system_name:
        ssp.put("system-characteristics/system-name", system_name)

    desc = svc.get("serviceDescription", "")
    if desc:
        ssp.put("system-characteristics/description", desc)

    # Replace placeholder system-id
    fedramp_id = svc.get("fedRampPackageId", "")
    if fedramp_id:
        ssp.put(
            "system-characteristics/system-ids",
            [{"identifier-type": "https://fedramp.gov", "id": fedramp_id}],
        )

    # Status — default to operational
    ssp.put("system-characteristics/status", {"state": "operational"})

    # Replace placeholder information-type with a minimal entry
    ssp.put(
        "system-characteristics/system-information/information-types",
        [
            {
                "uuid": new_uuid(),
                "title": system_name or "System Information",
                "description": desc or "General system information.",
                "categorizations": [
                    {
                        "system": "https://doi.org/10.6028/NIST.SP.800-60v2r1",
                        "information-type-ids": ["C.3.5.8"],
                    }
                ],
                "confidentiality-impact": {"base": "moderate"},
                "integrity-impact": {"base": "moderate"},
                "availability-impact": {"base": "moderate"},
            }
        ],
    )

    # Security sensitivity level (Class C = Moderate)
    ssp.put("system-characteristics/security-sensitivity-level", "moderate")

    # Security impact level
    ssp.put(
        "system-characteristics/security-impact-level",
        {
            "security-objective-confidentiality": "moderate",
            "security-objective-integrity": "moderate",
            "security-objective-availability": "moderate",
        },
    )

    # Authorization boundary description
    ssp.put(
        "system-characteristics/authorization-boundary/description",
        (
            f"{system_name or 'This system'} operates within the boundary "
            "described in the CPO. See the trust center for a complete boundary "
            "and data-flow diagram."
        ),
    )

    # --- Props ---------------------------------------------------------------
    cert_type = svc.get("certificationType", "")
    if cert_type:
        ssp.append_child(
            "system-characteristics/props",
            _prop("certification-type", cert_type),
        )

    for stype in props.get("serviceType") or []:
        ssp.append_child(
            "system-characteristics/props",
            _prop("service-type", stype),
        )

    deploy = props.get("deploymentModel", "")
    if deploy:
        ssp.append_child(
            "system-characteristics/props",
            _prop("deployment-model", deploy),
        )

    for bcat in props.get("businessCategory") or []:
        ssp.append_child(
            "system-characteristics/props",
            _prop("business-category", bcat),
        )

    ocr_date = props.get("nextOngoingCertificationReportDate", "")
    if ocr_date:
        ssp.append_child(
            "system-characteristics/props",
            _prop("next-ongoing-certification-report-date", ocr_date),
        )

    # --- Links ---------------------------------------------------------------
    website = svc.get("website", "")
    if website:
        ssp.append_child(
            "system-characteristics/links",
            _link(website, "website"),
        )

    logo = svc.get("logo", "")
    if logo:
        ssp.append_child(
            "system-characteristics/links",
            _link(logo, "logo"),
        )

    tc = props.get("trustCenter", {})
    tc_url = tc.get("url", "") if isinstance(tc, dict) else ""
    if tc_url:
        ssp.append_child(
            "system-characteristics/links",
            _link(tc_url, "trust-center"),
        )

    scg = props.get("secureConfigurationGuidance", {})
    scg_url = scg.get("url", "") if isinstance(scg, dict) else ""
    if scg_url:
        ssp.append_child(
            "system-characteristics/links",
            _link(scg_url, "secure-configuration-guidance"),
        )

    # Additional repositories → back-matter (linked from characteristics)
    for repo in props.get("additionalRepositories") or []:
        repo_url = repo.get("url", "")
        repo_types = repo.get("repositoryType") or []
        if repo_url:
            rel = "-".join(t.lower().replace(" ", "-") for t in repo_types) or "alternate"
            ssp.append_child(
                "system-characteristics/links",
                _link(repo_url, rel, repo.get("repositoryDescription", "")),
            )


# ---------------------------------------------------------------------------
# SSP — system-implementation helpers
# ---------------------------------------------------------------------------

def _build_ssp_implementation(ssp: SSP, cpo: dict) -> tuple:
    """Populate SSP system-implementation from CPO service and third-party data.

    Replaces the template placeholder user and component with entries derived
    from the CPO. For non-certified third-party resources, adds an
    ``interconnection`` component. For FedRAMP-certified third-party resources,
    adds a ``leveraged-authorization`` entry (title and party-uuid only) plus a
    ``system`` component whose ``leveraged-authorization-uuid`` prop links back
    to the authorization; the use-case description lives on the component, not
    on the authorization entry.

    Args:
        ssp (SSP, required): Target SSP instance to populate.
        cpo (dict, required): Parsed CPO JSON dict.

    Returns:
        tuple: A 2-tuple of (this_system_uuid: str, leveraged_auth_uuids: dict)
            where ``this_system_uuid`` is the UUID of the ``this-system``
            component, and ``leveraged_auth_uuids`` maps FedRAMP package IDs
            to their leveraged-authorization UUIDs.
    """
    svc = cpo.get("serviceIdentification", {})
    system_name = svc.get("serviceName", "This System")

    # --- Replace placeholder user --------------------------------------------
    # The template ships a generic "System Owner" user; replace the whole array.
    primary_contact = next(
        (c for c in cpo.get("contactInformation", []) if c.get("contactType") == "Primary"),
        None,
    )
    user_title = primary_contact.get("contactName", "System Owner") if primary_contact else "System Owner"
    ssp.put(
        "system-implementation/users",
        [
            {
                "uuid": new_uuid(),
                "title": user_title,
                "props": [{"name": "type", "value": "internal"}],
                "role-ids": ["system-owner"],
            }
        ],
    )

    # --- This-system component -----------------------------------------------
    this_system_uuid = new_uuid()
    desc = svc.get("serviceDescription", "")
    components = [
        {
            "uuid": this_system_uuid,
            "type": "this-system",
            "title": system_name,
            "description": desc or f"The {system_name} cloud service offering.",
            "status": {"state": "operational"},
        }
    ]

    # --- Certified services → software components ----------------------------
    for svc_entry in cpo.get("certifiedServices") or []:
        comp_uuid = new_uuid()
        avail = svc_entry.get("dateAvailable", "")
        comp: dict = {
            "uuid": comp_uuid,
            "type": "software",
            "title": svc_entry.get("serviceName", "Service"),
            "description": svc_entry.get("serviceDescription", ""),
            "status": {"state": "operational"},
        }
        if avail:
            comp.setdefault("props", []).append(
                {"name": "date-available", "ns": FEDRAMP_NS, "value": avail}
            )
        components.append(comp)

    # --- Non-certified third parties → external-system components -----------
    third_party = cpo.get("thirdPartyInformationResources", {})
    for nc in third_party.get("nonCertified") or []:
        comp: dict = {
            "uuid": new_uuid(),
            "type": "interconnection",
            "title": nc.get("name", "External Service"),
            "description": nc.get("useCase", ""),
            "status": {"state": "operational"},
        }
        provider = nc.get("provider", "")
        if provider:
            provider_uuid = new_uuid()
            ssp.append_child(
                "metadata/parties",
                {"uuid": provider_uuid, "type": "organization", "name": provider},
            )
            comp["responsible-roles"] = [
                {"role-id": "provider", "party-uuids": [provider_uuid]}
            ]
        website = nc.get("website", "")
        if website:
            comp["links"] = [_link(website, "website")]
        components.append(comp)

    ssp.put("system-implementation/components", components)

    # --- Leveraged authorizations for certified third parties ----------------
    leveraged_uuids: dict = {}
    for certified in third_party.get("certified") or []:
        pkg_id = certified.get("fedRampCertifiedThirdPartyInformationResource", "")
        if not pkg_id:
            continue
        la_uuid = new_uuid()
        la_party_uuid = new_uuid()

        # Party for the leveraged system's CSP — CPO carries no org name,
        # so the FedRAMP package ID serves as the name and external identifier.
        ssp.append_child(
            "metadata/parties",
            {
                "uuid": la_party_uuid,
                "type": "organization",
                "name": pkg_id,
                "external-ids": [{"scheme": "https://fedramp.gov", "id": pkg_id}],
                "links": [_link(
                    f"https://marketplace.fedramp.gov/products/{pkg_id}",
                    "authorization",
                )],
            },
        )

        # Leveraged-authorization entry. date-authorized is required by OSCAL;
        # the CPO carries no authorization date so today's date is used as the
        # closest available approximation.
        la: dict = {
            "uuid": la_uuid,
            "title": pkg_id,
            "party-uuid": la_party_uuid,
            "date-authorized": _now_iso()[:10],
        }
        ssp.append_child("system-implementation/leveraged-authorizations", la)

        # System component that references this leveraged authorization.
        # The use-case description belongs here, not on the LA entry.
        ssp.append_child(
            "system-implementation/components",
            {
                "uuid": new_uuid(),
                "type": "system",
                "title": pkg_id,
                "description": certified.get("useCase", ""),
                "status": {"state": "operational"},
                "props": [{"name": "leveraged-authorization-uuid", "value": la_uuid}],
            },
        )
        leveraged_uuids[pkg_id] = la_uuid

    return this_system_uuid, leveraged_uuids


# ---------------------------------------------------------------------------
# SSP — control-implementation helpers
# ---------------------------------------------------------------------------

def _build_frr_requirements(ssp: SSP, sdr: dict, this_system_uuid: str) -> None:
    """Add implemented-requirements for FRR rules from the SDR.

    One ``implemented-requirement`` is created per ``fedRampRequirements``
    entry. The ``frrImplementation`` statements become the by-component
    description; ``frrValidation`` is appended to the remarks; status is
    derived from ``frrImplementationStatus``.

    Args:
        ssp (SSP, required): Target SSP instance to populate.
        sdr (dict, required): Parsed SDR JSON dict.
        this_system_uuid (str, required): UUID of the ``this-system`` component.
    """
    status_map = {
        "Implemented": "implemented",
        "Planned": "planned",
        "Not Applicable": "not-applicable",
        "Partial": "partial",
    }
    for frr in sdr.get("fedRampRequirements") or []:
        frr_id = frr.get("frrID", "")
        if not frr_id:
            continue
        impl_status = status_map.get(
            frr.get("frrImplementationStatus", "Implemented"), "implemented"
        )
        impl_text = _paragraphs(frr.get("frrImplementation") or [])
        validation_text = _paragraphs(frr.get("frrValidation") or [])

        remarks = validation_text if validation_text else ""
        req_uuid = new_uuid()
        req: dict = {
            "uuid": req_uuid,
            "control-id": frr_id,
            "props": [_prop("implementation-status", impl_status)],
        }
        if remarks:
            req["remarks"] = remarks
        ssp.append_child("control-implementation/implemented-requirements", req)
        if impl_text:
            ssp.add_by_component(
                req_uuid,
                this_system_uuid,
                impl_text,
                implementation_status=impl_status,
            )


def _build_ksi_requirements(ssp: SSP, sdr: dict, this_system_uuid: str) -> None:
    """Add implemented-requirements for KSIs from a 20x SDR.

    One ``implemented-requirement`` is created per ``keySecurityIndicators``
    entry, using the KSI ID as the control-id. The ``ksiImplementation``
    statements become the by-component description.

    Args:
        ssp (SSP, required): Target SSP instance to populate.
        sdr (dict, required): Parsed SDR JSON dict (20x path).
        this_system_uuid (str, required): UUID of the ``this-system`` component.
    """
    status_map = {
        "Implemented": "implemented",
        "Planned": "planned",
        "Not Applicable": "not-applicable",
        "Partial": "partial",
    }
    for ksi in sdr.get("keySecurityIndicators") or []:
        ksi_id = ksi.get("ksiId", "")
        if not ksi_id:
            continue
        impl_status = status_map.get(
            ksi.get("ksiImplementationStatus", "Implemented"), "implemented"
        )
        impl_text = _paragraphs(ksi.get("ksiImplementation") or [])
        validation_text = _paragraphs(ksi.get("ksiValidation") or [])

        req_uuid = new_uuid()
        req: dict = {
            "uuid": req_uuid,
            "control-id": ksi_id,
            "props": [_prop("implementation-status", impl_status)],
        }
        if validation_text:
            req["remarks"] = validation_text
        ssp.append_child("control-implementation/implemented-requirements", req)
        if impl_text:
            ssp.add_by_component(
                req_uuid,
                this_system_uuid,
                impl_text,
                implementation_status=impl_status,
            )


def _build_control_requirements(ssp: SSP, sdr: dict, this_system_uuid: str) -> None:
    """Add implemented-requirements for NIST 800-53 controls from a Rev5 SDR.

    One ``implemented-requirement`` is created per ``securityControls`` entry.
    Parameter values are embedded in the requirement as ``set-parameters``.
    The ``controlImplementationDescription`` becomes the by-component description.

    Args:
        ssp (SSP, required): Target SSP instance to populate.
        sdr (dict, required): Parsed SDR JSON dict (Rev5 path).
        this_system_uuid (str, required): UUID of the ``this-system`` component.
    """
    status_map = {
        "Implemented": "implemented",
        "Planned": "planned",
        "Not Applicable": "not-applicable",
        "Partial": "partial",
        "Alternative Implementation": "alternative",
        "Inherited": "inherited",
    }
    for ctrl in sdr.get("securityControls") or []:
        ctrl_id = ctrl.get("controlId", "")
        if not ctrl_id:
            continue
        # OSCAL control IDs use lowercase with hyphens (e.g. ac-2 not AC-2)
        oscal_ctrl_id = ctrl_id.lower().replace("_", "-")
        impl_status = status_map.get(
            ctrl.get("controlImplementationStatus", "Implemented"), "implemented"
        )
        impl_text = ctrl.get("controlImplementationDescription", "")

        req_uuid = new_uuid()
        req: dict = {
            "uuid": req_uuid,
            "control-id": oscal_ctrl_id,
            "props": [_prop("implementation-status", impl_status)],
        }

        # Set-parameters — schema uses an array of {parameterId, parameterValue}
        # objects; also accept a legacy dict form used in tests.
        param_values = ctrl.get("parameterValues") or {}
        set_params: list = []
        if isinstance(param_values, list):
            for pv in param_values:
                pid = pv.get("parameterId", "")
                pval = pv.get("parameterValue", "")
                if pid:
                    set_params.append({
                        "param-id": pid,
                        "values": pval if isinstance(pval, list) else [str(pval)],
                    })
        elif isinstance(param_values, dict):
            for pid, pval in param_values.items():
                set_params.append({
                    "param-id": pid,
                    "values": pval if isinstance(pval, list) else [str(pval)],
                })
        if set_params:
            req["set-parameters"] = set_params

        ssp.append_child("control-implementation/implemented-requirements", req)
        if impl_text:
            ssp.add_by_component(
                req_uuid,
                this_system_uuid,
                impl_text,
                implementation_status=impl_status,
            )


# ---------------------------------------------------------------------------
# Public: build_ssp
# ---------------------------------------------------------------------------

def build_ssp(
    cpo: dict,
    sdr: Optional[dict] = None,
    certification_class: str = "C",
) -> Optional[SSP]:
    """Build an OSCAL SSP from a CPO and optional SDR.

    The SSP is populated in four stages:
    1. Metadata (roles, parties, responsible-parties) from CPO contacts.
    2. System-characteristics (IDs, name, description, props, links) from CPO.
    3. System-implementation (components, leveraged authorizations) from CPO.
    4. Control-implementation (implemented requirements) from SDR, if provided.

    When an SDR is provided, its certification path is auto-detected:
    - 20x path: ``keySecurityIndicators`` array present → KSI requirements.
    - Rev5 path: ``securityControls`` array present → NIST control requirements.
    - ``fedRampRequirements`` are always added regardless of path.

    The ``import-profile`` element is resolved to a back-matter resource that
    links to the appropriate FedRAMP 2026 OSCAL class profile on GitHub, keyed
    by the CPO's ``certificationType`` and the supplied *certification_class*.

    Args:
        cpo (dict, required): Parsed CPO JSON dict (top-level object from the
            FedRAMP CPO JSON file).
        sdr (dict, optional): Parsed SDR JSON dict. Defaults to None.
        certification_class (str, optional): FedRAMP certification class letter
            — ``"A"``, ``"B"``, ``"C"``, or ``"D"``. Case-insensitive.
            Defaults to ``"C"``.

    Returns:
        Optional[SSP]: A populated OSCAL SSP instance, or None on failure.
    """
    svc = cpo.get("serviceIdentification", {})
    service_name = svc.get("serviceName", "System Security Plan")
    cert_type = svc.get("certificationType", "")
    title = f"{service_name} — System Security Plan"
    if cert_type:
        title += f" ({cert_type})"

    ssp = _new_model(SSP, "system-security-plan", title)
    if ssp is None:
        return None

    # Metadata
    _build_ssp_metadata(ssp, cpo)

    # Import-profile → back-matter resource → GitHub-hosted class profile
    path = "20X" if cert_type.lower() == "20x" else "Rev5"
    cls = certification_class.upper()
    profile_url = PROFILE_BASE_URL.format(path=path, cls=cls)
    profile_resource_uuid = new_uuid()
    ssp.append_resource(
        uuid=profile_resource_uuid,
        title=f"FedRAMP {path} — Class {cls} Profile",
        rlinks=[{"href": profile_url}],
    )
    ssp.put("import-profile/href", f"#{profile_resource_uuid}")

    # System characteristics
    _build_ssp_characteristics(ssp, cpo)

    # System implementation
    this_system_uuid, _ = _build_ssp_implementation(ssp, cpo)

    # Control implementation description
    ssp.put(
        "control-implementation/description",
        (
            f"{service_name} implements the applicable FedRAMP CR26 rules "
            "and security requirements as described in the Security Decision Record."
        ),
    )

    # Remove the template's placeholder requirement (control-id="_")
    root_dict = ssp._dict.get("system-security-plan", {})
    ctrl_impl = root_dict.get("control-implementation", {})
    existing = ctrl_impl.get("implemented-requirements", [])
    ctrl_impl["implemented-requirements"] = [
        r for r in existing if r.get("control-id", "") != "_"
    ]

    # SDR-based requirements
    if sdr:
        _build_frr_requirements(ssp, sdr, this_system_uuid)
        if sdr.get("keySecurityIndicators"):
            _build_ksi_requirements(ssp, sdr, this_system_uuid)
        if sdr.get("securityControls"):
            _build_control_requirements(ssp, sdr, this_system_uuid)

    # Cybercraft presentation-id extension
    ssp.append_child(
        "metadata/props",
        {"name": "presentation-id", "ns": CYBERCRAFT_NS, "value": "fedramp-cr26"},
    )

    return ssp


# ---------------------------------------------------------------------------
# Private: AR result builder
# ---------------------------------------------------------------------------

def _build_ar_result(sdr: dict) -> dict:
    """Build a complete OSCAL AR result dict from SDR assessment content.

    The result contains one observation and one finding per FRR requirement
    and per KSI entry. KSI evidence items are added as relevant-evidence on
    the corresponding observation.

    Each observation carries a required ``collected`` timestamp. KSI
    observations use the most recent ``lastUpdated`` value from that KSI's
    evidence items; FRR observations (which carry no date) fall back to the
    SDR reference date — the most recent ``lastUpdated`` found anywhere in
    the SDR, or the current timestamp if the SDR contains no dates.

    Args:
        sdr (dict, required): Parsed SDR JSON dict.

    Returns:
        dict: Complete OSCAL result dict ready for ``append_child("results", ...)``.
    """
    # --- SDR reference date --------------------------------------------------
    # Collect all evidence dates upfront; used for collected fallback and the
    # assessment period end timestamp.
    all_ev_dates: list = [
        ev["lastUpdated"]
        for ksi in (sdr.get("keySecurityIndicators") or [])
        for ev in (ksi.get("ksiEvidence") or [])
        if ev.get("lastUpdated")
    ]
    _max_date: str = max(all_ev_dates) if all_ev_dates else ""
    sdr_date: str = _to_datetime(_max_date) if _max_date else _now_iso()
    end_dt: str = (
        f"{_max_date}T23:59:59Z" if _max_date and len(_max_date) == 10 else sdr_date
    )
    start_dt: str = _now_iso()

    result_uuid = new_uuid()
    observations: list = []
    findings: list = []

    # --- FRR assessments -----------------------------------------------------
    # FRR entries carry no date field; use the SDR reference date for collected.
    for frr in sdr.get("fedRampRequirements") or []:
        frr_id = frr.get("frrID", "")
        if not frr_id:
            continue
        assessment_text = _paragraphs(frr.get("frrAssessment") or [])
        if not assessment_text:
            continue
        obs_uuid = new_uuid()
        obs: dict = {
            "uuid": obs_uuid,
            "title": f"Assessment of {frr_id}",
            "description": assessment_text,
            "collected": sdr_date,
            "methods": ["EXAMINE"],
            "types": ["finding"],
        }
        observations.append(obs)

        finding_uuid = new_uuid()
        finding: dict = {
            "uuid": finding_uuid,
            "title": f"{frr_id} — Assessor Finding",
            "description": assessment_text,
            "target": {
                "type": "objective-id",
                "target-id": frr_id,
                "status": {"state": "satisfied"},
            },
            "related-observations": [{"observation-uuid": obs_uuid}],
        }
        findings.append(finding)

    # --- KSI assessments (20x path) ------------------------------------------
    for ksi in sdr.get("keySecurityIndicators") or []:
        ksi_id = ksi.get("ksiId", "")
        if not ksi_id:
            continue
        assessment_statements = ksi.get("ksiAssessment") or []
        assessment_text = _paragraphs(assessment_statements)
        if not assessment_text:
            continue

        # Use the most recent evidence date for this KSI, falling back to the
        # SDR reference date when no evidence carries a lastUpdated value.
        evidence_list = ksi.get("ksiEvidence") or []
        ksi_dates = [ev["lastUpdated"] for ev in evidence_list if ev.get("lastUpdated")]
        collected: str = _to_datetime(max(ksi_dates)) if ksi_dates else sdr_date

        obs_uuid = new_uuid()
        obs: dict = {
            "uuid": obs_uuid,
            "title": f"Assessment of {ksi_id}",
            "description": assessment_text,
            "collected": collected,
            "methods": ["EXAMINE", "TEST"],
            "types": ["finding"],
        }

        # Evidence items → relevant-evidence
        if evidence_list:
            obs["relevant-evidence"] = []
            for ev in evidence_list:
                ev_href = ev.get("evidenceLocation", "")
                ev_desc = ev.get("evidenceDescription", "")
                ev_type = ev.get("evidenceType", "")
                rel_ev: dict = {"description": ev_desc or ev_type}
                if ev_href:
                    rel_ev["href"] = ev_href
                obs["relevant-evidence"].append(rel_ev)

        observations.append(obs)

        # Tests → one finding
        finding_uuid = new_uuid()
        finding: dict = {
            "uuid": finding_uuid,
            "title": f"{ksi_id} — Assessor Finding",
            "description": assessment_text,
            "target": {
                "type": "objective-id",
                "target-id": ksi_id,
                "status": {"state": "satisfied"},
            },
            "related-observations": [{"observation-uuid": obs_uuid}],
        }
        findings.append(finding)

    # --- Assemble result dict -------------------------------------------------

    result: dict = {
        "uuid": result_uuid,
        "title": "Annual Assessment",
        "description": "Independent assessment results for the FedRAMP certification package.",
        "start": start_dt,
        "end": end_dt,
        "reviewed-controls": {
            "control-selections": [{"include-all": {}}],
        },
    }
    if observations:
        result["observations"] = observations
    if findings:
        result["findings"] = findings

    return result


# ---------------------------------------------------------------------------
# Public: build_ar
# ---------------------------------------------------------------------------

def build_ar(sdr: dict, ssp_href: str = "") -> Optional[AssessmentResults]:
    """Build an OSCAL Assessment Results (AR) from an SDR.

    The AR contains one result with observations and findings derived from
    the ``frrAssessment`` and ``ksiAssessment`` fields in the SDR. KSI
    evidence is attached as relevant-evidence on observations.

    Args:
        sdr (dict, required): Parsed SDR JSON dict.
        ssp_href (str, optional): Href to the corresponding SSP file. Used in
            the AR's ``import-ap`` link. Defaults to ``"#"``.

    Returns:
        Optional[AssessmentResults]: A populated OSCAL AR instance, or None
            on failure.
    """
    title = "FedRAMP Assessment Results"
    ar = _new_model(AssessmentResults, "assessment-results", title)
    if ar is None:
        return None

    # Set import-ap href
    ar.put("import-ap/href", ssp_href or CR26_CATALOG_PLACEHOLDER)

    # Replace template placeholder result
    ar.put("results", [])

    # Add our result
    result_dict = _build_ar_result(sdr)
    ar.append_child("results", result_dict)

    # Metadata roles
    ar.append_child("metadata/roles", {"id": "assessor", "title": "Independent Assessor"})
    ar.append_child("metadata/roles", {"id": "system-owner", "title": "System Owner"})

    # Cybercraft presentation-id
    ar.append_child(
        "metadata/props",
        {"name": "presentation-id", "ns": CYBERCRAFT_NS, "value": "fedramp-cr26"},
    )

    return ar


# ---------------------------------------------------------------------------
# Public: build_ap
# ---------------------------------------------------------------------------

def build_ap(sdr: dict, ssp_href: str = "") -> Optional[AssessmentPlan]:
    """Build a minimal OSCAL Assessment Plan (AP) from an SDR.

    The AP shell imports the SSP and lists the reviewed controls (all FRR
    rule IDs plus KSI or NIST control IDs found in the SDR).

    Args:
        sdr (dict, required): Parsed SDR JSON dict.
        ssp_href (str, optional): Href to the corresponding SSP file. Used in
            the AP's ``import-ssp`` link. Defaults to ``"#"``.

    Returns:
        Optional[AssessmentPlan]: A populated OSCAL AP instance, or None
            on failure.
    """
    title = "FedRAMP Assessment Plan"
    ap = _new_model(AssessmentPlan, "assessment-plan", title)
    if ap is None:
        return None

    # Import-ssp
    ap.put("import-ssp/href", ssp_href or CR26_CATALOG_PLACEHOLDER)

    # Collect all control IDs being reviewed
    control_ids: list = []
    for frr in sdr.get("fedRampRequirements") or []:
        fid = frr.get("frrID", "")
        if fid:
            control_ids.append({"control-id": fid})
    for ksi in sdr.get("keySecurityIndicators") or []:
        kid = ksi.get("ksiId", "")
        if kid:
            control_ids.append({"control-id": kid})
    for ctrl in sdr.get("securityControls") or []:
        cid = ctrl.get("controlId", "")
        if cid:
            control_ids.append({"control-id": cid.lower().replace("_", "-")})

    if control_ids:
        ap.put(
            "reviewed-controls/control-selections",
            [{"include-controls": control_ids}],
        )
    else:
        ap.put(
            "reviewed-controls/control-selections",
            [{"include-all": {}}],
        )

    # Metadata roles
    ap.append_child("metadata/roles", {"id": "assessor", "title": "Independent Assessor"})

    # Cybercraft presentation-id
    ap.append_child(
        "metadata/props",
        {"name": "presentation-id", "ns": CYBERCRAFT_NS, "value": "fedramp-cr26"},
    )

    return ap


# ---------------------------------------------------------------------------
# Public: convert
# ---------------------------------------------------------------------------

def convert(
    cpo_path: "str | Path",
    sdr_path: "Optional[str | Path]" = None,
    output_dir: "str | Path" = ".",
    format: str = "json",
    certification_class: str = "C",
) -> dict:
    """Convert CPO/SDR JSON files to OSCAL SSP/AP/AR files.

    Reads the CPO and (optionally) SDR files, builds OSCAL documents, and
    writes them to *output_dir*. File names are derived from the CPO's
    ``fedRampPackageId`` field when available, otherwise ``"package"``.

    Args:
        cpo_path (str | Path, required): Path to the CPO JSON file.
        sdr_path (str | Path | None, optional): Path to the SDR JSON file.
            When None, only the SSP is produced. Defaults to None.
        output_dir (str | Path, optional): Directory for output files.
            Created if it does not exist. Defaults to current directory.
        format (str, optional): Output format — ``"json"``, ``"xml"``, or
            ``"yaml"``. Defaults to ``"json"``.
        certification_class (str, optional): FedRAMP certification class letter
            — ``"A"``, ``"B"``, ``"C"``, or ``"D"``. Passed to
            :func:`build_ssp` to select the correct profile. Defaults to
            ``"C"``.

    Returns:
        dict: Mapping of document type (``"ssp"``, ``"ap"``, ``"ar"``) to
            the output ``Path`` for each file written. Keys are absent when
            the corresponding document was not produced.

    Raises:
        FileNotFoundError: If *cpo_path* does not exist.
        ValueError: If *cpo_path* content is not valid JSON.
    """
    cpo_path = Path(cpo_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cpo = json.loads(cpo_path.read_text(encoding="utf-8"))
    sdr: Optional[dict] = None
    if sdr_path:
        sdr = json.loads(Path(sdr_path).read_text(encoding="utf-8"))

    # Derive a base filename from the FedRAMP package ID
    pkg_id = (
        cpo.get("serviceIdentification", {}).get("fedRampPackageId", "")
        or "package"
    )
    base = pkg_id.lower().replace(" ", "-")

    ext_map = {"json": ".json", "xml": ".xml", "yaml": ".yaml", "yml": ".yaml"}
    ext = ext_map.get(format, ".json")

    output: dict = {}

    # Build and write SSP
    ssp_path = output_dir / f"{base}-ssp{ext}"
    ssp = build_ssp(cpo, sdr, certification_class=certification_class)
    if ssp is not None:
        ssp.dump(str(ssp_path), format=format, pretty_print=True)
        output["ssp"] = ssp_path

    if sdr:
        ssp_href = ssp_path.name  # relative href from AP/AR perspective

        # Build and write AP
        ap_path = output_dir / f"{base}-ap{ext}"
        ap = build_ap(sdr, ssp_href=ssp_href)
        if ap is not None:
            ap.dump(str(ap_path), format=format, pretty_print=True)
            output["ap"] = ap_path

        # Build and write AR
        ar_path = output_dir / f"{base}-ar{ext}"
        ap_href = ap_path.name
        ar = build_ar(sdr, ssp_href=ap_href)
        if ar is not None:
            ar.dump(str(ar_path), format=format, pretty_print=True)
            output["ar"] = ar_path

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Parse command-line arguments and run the conversion.

    Usage:
        python package2oscal.py CPO_PATH [SDR_PATH] [--output DIR] [--format FMT] [--class CLS]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert FedRAMP CR26 CPO/SDR JSON files to OSCAL SSP/AP/AR."
    )
    parser.add_argument("cpo", metavar="CPO_PATH", help="Path to CPO JSON file.")
    parser.add_argument(
        "sdr",
        metavar="SDR_PATH",
        nargs="?",
        default=None,
        help="Path to SDR JSON file (optional).",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        default=".",
        help="Output directory. Defaults to current directory.",
    )
    parser.add_argument(
        "--format",
        "-f",
        metavar="FMT",
        choices=["json", "xml", "yaml"],
        default="json",
        help="Output format: json, xml, or yaml. Defaults to json.",
    )
    parser.add_argument(
        "--class",
        "-c",
        metavar="CLS",
        choices=["A", "B", "C", "D"],
        default="C",
        dest="certification_class",
        help="FedRAMP certification class: A, B, C, or D. Defaults to C.",
    )
    args = parser.parse_args()

    results = convert(args.cpo, args.sdr, args.output, args.format, args.certification_class)
    for doc_type, path in results.items():
        print(f"{doc_type.upper()}: {path}")


if __name__ == "__main__":
    _cli()
