"""
tests/unit/test_package2oscal.py — Unit tests for src/package2oscal.py.

Tests cover the module-level helpers, each public build function, and the
convert() orchestrator using the scenario CPO/SDR files as integration inputs.
"""
import json
import pathlib
import pytest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "src"))

from package2oscal import (
    FEDRAMP_NS,
    CYBERCRAFT_NS,
    CR26_CATALOG_PLACEHOLDER,
    PROFILE_BASE_URL,
    _prop,
    _link,
    _paragraphs,
    _new_model,
    _contact_role_id,
    build_ssp,
    build_ar,
    build_ap,
    convert,
)
from oscal.oscal_implementation import SSP
from oscal.oscal_assessment import AssessmentResults, AssessmentPlan

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCENARIOS_DIR = pathlib.Path(__file__).parent.parent.parent / "data" / "scenarios"


@pytest.fixture
def cpo_20x() -> dict:
    return json.loads((SCENARIOS_DIR / "cpo_20x.json").read_text())


@pytest.fixture
def cpo_rev5() -> dict:
    return json.loads((SCENARIOS_DIR / "cpo_rev5.json").read_text())


@pytest.fixture
def sdr_20x() -> dict:
    return json.loads((SCENARIOS_DIR / "sdr_20x.json").read_text())


@pytest.fixture
def sdr_rev5() -> dict:
    return json.loads((SCENARIOS_DIR / "sdr_rev5.json").read_text())


@pytest.fixture
def minimal_cpo() -> dict:
    return {
        "serviceIdentification": {
            "fedRampPackageId": "FR9999999999",
            "providerName": "Test Corp",
            "serviceName": "Test Service",
            "serviceAcronym": "TS",
            "serviceDescription": "A test cloud service.",
            "certificationType": "20x",
        },
        "serviceProperties": {
            "serviceType": ["SaaS"],
            "deploymentModel": "Government Community Cloud",
            "businessCategory": ["Collaboration"],
            "nextOngoingCertificationReportDate": "2027-01-01",
        },
        "contactInformation": [
            {
                "contactType": "Security",
                "contactName": "Jane Doe",
                "contactEmail": "security@test.example.com",
                "contactPhone": "703-555-0100",
            },
        ],
        "assessor": {"name": "Ironclad LLC", "assessorID": "A001"},
        "certifiedServices": [
            {
                "serviceName": "Core API",
                "serviceDescription": "REST API for all features.",
                "dateAvailable": "2025-01-01",
            }
        ],
        "thirdPartyInformationResources": {
            "certified": [
                {
                    "fedRampCertifiedThirdPartyInformationResource": "FR1111111111",
                    "useCase": "Underlying compute platform.",
                }
            ],
            "nonCertified": [
                {
                    "name": "SendGrid",
                    "provider": "Twilio",
                    "website": "https://sendgrid.com",
                    "useCase": "Outbound email only.",
                }
            ],
        },
    }


@pytest.fixture
def minimal_sdr_20x() -> dict:
    return {
        "certificationPackageOverviewUri": "https://example.com/cpo.json",
        "fedRampRequirements": [
            {
                "frrID": "MAS-CSO-IIR",
                "frrImplementationStatus": "Implemented",
                "frrImplementation": ["Automated inventory pipeline."],
                "frrValidation": ["Weekly reconciliation."],
                "frrAssessment": ["Assessor confirmed no discrepancies."],
            }
        ],
        "keySecurityIndicators": [
            {
                "ksiId": "KSI-IAM-APM",
                "ksiImplementationStatus": "Implemented",
                "ksiImplementation": ["All accounts use WebAuthn."],
                "ksiValidation": ["Monthly coverage review."],
                "ksiAssessment": ["97% passwordless coverage confirmed."],
                "ksiTests": ["Monthly IdP query"],
                "ksiEvidence": [
                    {
                        "evidenceType": "Report",
                        "evidenceDescription": "IdP authenticator report July 2026",
                        "evidenceLocation": "https://trust.example/iam-apm.pdf",
                        "lastUpdated": "2026-07-15",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def minimal_sdr_rev5() -> dict:
    return {
        "certificationPackageOverviewUri": "https://example.com/cpo.json",
        "fedRampRequirements": [
            {
                "frrID": "MAS-CSO-IIR",
                "frrImplementationStatus": "Implemented",
                "frrImplementation": ["Inventory is automated."],
                "frrValidation": ["Weekly cross-check."],
                "frrAssessment": ["Assessor confirmed coverage."],
            }
        ],
        "securityControls": [
            {
                "controlId": "AC-02",
                "controlImplementationStatus": "Implemented",
                "controlImplementationDescription": "Accounts managed via IdP.",
                "parameterValues": [
                    {"parameterId": "ac-02_odp.01", "parameterValue": "Privileged accounts"},
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests: module helpers
# ---------------------------------------------------------------------------


class TestProp:
    def test_required_fields(self):
        p = _prop("foo", "bar")
        assert p["name"] == "foo"
        assert p["value"] == "bar"
        assert p["ns"] == FEDRAMP_NS

    def test_custom_ns(self):
        p = _prop("x", "y", ns=CYBERCRAFT_NS)
        assert p["ns"] == CYBERCRAFT_NS

    def test_remarks_included_when_set(self):
        p = _prop("x", "y", remarks="note")
        assert p["remarks"] == "note"

    def test_remarks_absent_when_empty(self):
        p = _prop("x", "y")
        assert "remarks" not in p


class TestLink:
    def test_required_href(self):
        lnk = _link("https://example.com")
        assert lnk["href"] == "https://example.com"

    def test_rel_included_when_set(self):
        lnk = _link("https://example.com", rel="canonical")
        assert lnk["rel"] == "canonical"

    def test_rel_absent_when_empty(self):
        lnk = _link("https://example.com")
        assert "rel" not in lnk

    def test_text_included_when_set(self):
        lnk = _link("https://example.com", text="Click here")
        assert lnk["text"] == "Click here"


class TestParagraphs:
    def test_joins_with_double_newline(self):
        result = _paragraphs(["A", "B", "C"])
        assert result == "A\n\nB\n\nC"

    def test_single_item_no_separator(self):
        assert _paragraphs(["A"]) == "A"

    def test_empty_list(self):
        assert _paragraphs([]) == ""

    def test_filters_empty_strings(self):
        assert _paragraphs(["A", "", "B"]) == "A\n\nB"


class TestContactRoleId:
    def test_security_maps_to_security_poc(self):
        assert _contact_role_id("Security") == "security-poc"

    def test_sales_maps_to_sales_poc(self):
        assert _contact_role_id("Sales") == "sales-poc"

    def test_primary_maps_to_system_owner(self):
        assert _contact_role_id("Primary") == "system-owner"

    def test_unknown_lowercased_and_hyphenated(self):
        assert _contact_role_id("Compliance Officer") == "compliance-officer"


class TestNewModel:
    def test_ssp_new_model_succeeds(self):
        obj = _new_model(SSP, "system-security-plan", "Test")
        assert obj is not None

    def test_ar_new_model_succeeds(self):
        obj = _new_model(AssessmentResults, "assessment-results", "Test")
        assert obj is not None

    def test_ap_new_model_succeeds(self):
        obj = _new_model(AssessmentPlan, "assessment-plan", "Test")
        assert obj is not None

    def test_returns_correct_class(self):
        obj = _new_model(SSP, "system-security-plan", "Test")
        assert isinstance(obj, SSP)

    def test_title_is_set(self):
        obj = _new_model(SSP, "system-security-plan", "My Title")
        data = json.loads(obj.dumps(format="json"))
        assert data["system-security-plan"]["metadata"]["title"] == "My Title"

    def test_version_is_set(self):
        obj = _new_model(SSP, "system-security-plan", "T", version="2.0")
        data = json.loads(obj.dumps(format="json"))
        assert data["system-security-plan"]["metadata"]["version"] == "2.0"

    def test_uuid_is_fresh(self):
        a = _new_model(SSP, "system-security-plan", "T")
        b = _new_model(SSP, "system-security-plan", "T")
        uuid_a = json.loads(a.dumps(format="json"))["system-security-plan"]["uuid"]
        uuid_b = json.loads(b.dumps(format="json"))["system-security-plan"]["uuid"]
        assert uuid_a != uuid_b

    def test_append_child_works_after_creation(self):
        obj = _new_model(SSP, "system-security-plan", "T")
        result = obj.append_child("metadata/roles", {"id": "test-role", "title": "Test"})
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: build_ssp
# ---------------------------------------------------------------------------


class TestBuildSsp:
    def test_returns_ssp_instance(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        assert isinstance(ssp, SSP)

    def test_title_contains_service_name(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        title = data["system-security-plan"]["metadata"]["title"]
        assert "Test Service" in title

    def test_system_name_set(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        assert data["system-security-plan"]["system-characteristics"]["system-name"] == "Test Service"

    def test_fedramp_system_id_present(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        ids = data["system-security-plan"]["system-characteristics"]["system-ids"]
        fedramp_ids = [i["id"] for i in ids if "fedramp" in i.get("identifier-type", "")]
        assert "FR9999999999" in fedramp_ids

    def test_roles_include_security_poc(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        role_ids = [r["id"] for r in data["system-security-plan"]["metadata"].get("roles", [])]
        assert "security-poc" in role_ids

    def test_roles_include_provider(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        role_ids = [r["id"] for r in data["system-security-plan"]["metadata"].get("roles", [])]
        assert "provider" in role_ids

    def test_parties_include_csp(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        names = [p["name"] for p in data["system-security-plan"]["metadata"].get("parties", [])]
        assert "Test Corp" in names

    def test_non_certified_provider_is_metadata_party(self, minimal_cpo):
        # "Twilio" is the provider for the SendGrid nonCertified entry
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        names = [p["name"] for p in data["system-security-plan"]["metadata"].get("parties", [])]
        assert "Twilio" in names

    def test_non_certified_component_uses_responsible_roles_not_props(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        components = data["system-security-plan"]["system-implementation"].get("components", [])
        interconnections = [c for c in components if c.get("type") == "interconnection"]
        assert interconnections
        for comp in interconnections:
            # provider must not appear as a prop
            provider_props = [
                p for p in comp.get("props", []) if p.get("name") == "provider"
            ]
            assert not provider_props, "provider must not be a prop on interconnection components"
            # provider party-uuid must be referenced via responsible-roles
            rr_ids = [r["role-id"] for r in comp.get("responsible-roles", [])]
            assert "provider" in rr_ids

    def test_parties_include_assessor(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        names = [p["name"] for p in data["system-security-plan"]["metadata"].get("parties", [])]
        assert "Ironclad LLC" in names

    def test_leveraged_authorization_added_for_certified_third_party(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        las = data["system-security-plan"]["system-implementation"].get("leveraged-authorizations", [])
        assert any("FR1111111111" in la.get("title", "") for la in las)

    def test_phone_number_stored_as_digits_only(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        parties = data["system-security-plan"]["metadata"].get("parties", [])
        for party in parties:
            for tel in party.get("telephone-numbers", []):
                number = tel.get("number", "")
                assert number.isdigit(), f"Non-digit characters in telephone number: {number!r}"

    def test_leveraged_authorization_has_date_authorized(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        las = data["system-security-plan"]["system-implementation"].get("leveraged-authorizations", [])
        for la in las:
            assert "date-authorized" in la
            # must be a bare date (YYYY-MM-DD)
            assert len(la["date-authorized"]) == 10
            assert la["date-authorized"][4] == "-" and la["date-authorized"][7] == "-"

    def test_date_available_prop_is_fedramp_extension(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        components = data["system-security-plan"]["system-implementation"].get("components", [])
        for comp in components:
            for prop in comp.get("props", []):
                if prop.get("name") == "date-available":
                    assert prop.get("ns") == FEDRAMP_NS, (
                        f"date-available prop missing FedRAMP ns, got: {prop.get('ns')!r}"
                    )

    def test_leveraged_authorization_has_no_href(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        las = data["system-security-plan"]["system-implementation"].get("leveraged-authorizations", [])
        for la in las:
            assert "href" not in la

    def test_leveraged_authorization_has_no_description(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        las = data["system-security-plan"]["system-implementation"].get("leveraged-authorizations", [])
        for la in las:
            assert "description" not in la

    def test_leveraged_auth_system_component_present(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        impl = data["system-security-plan"]["system-implementation"]
        las = impl.get("leveraged-authorizations", [])
        la_uuids = {la["uuid"] for la in las}
        components = impl.get("components", [])
        system_comps = [c for c in components if c.get("type") == "system"]
        la_uuid_props = {
            p["value"]
            for c in system_comps
            for p in c.get("props", [])
            if p.get("name") == "leveraged-authorization-uuid"
        }
        assert la_uuid_props == la_uuids

    def test_leveraged_auth_system_component_has_use_case_description(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        impl = data["system-security-plan"]["system-implementation"]
        components = impl.get("components", [])
        system_comps = [c for c in components if c.get("type") == "system"]
        la_comps = [
            c for c in system_comps
            if any(p.get("name") == "leveraged-authorization-uuid" for p in c.get("props", []))
        ]
        assert la_comps
        assert any("compute platform" in c.get("description", "") for c in la_comps)

    def test_certification_type_prop_present(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        props = data["system-security-plan"]["system-characteristics"].get("props", [])
        cert_props = [p for p in props if p.get("name") == "certification-type"]
        assert cert_props
        assert cert_props[0]["value"] == "20x"

    def test_no_placeholder_requirement_in_output(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        reqs = (
            data["system-security-plan"]
            .get("control-implementation", {})
            .get("implemented-requirements", [])
        )
        assert all(r.get("control-id") != "_" for r in reqs)

    def test_presentation_id_prop_present(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        props = data["system-security-plan"]["metadata"].get("props", [])
        pid_props = [p for p in props if p.get("name") == "presentation-id" and p.get("ns") == CYBERCRAFT_NS]
        assert pid_props
        assert pid_props[0]["value"] == "fedramp-cr26"

    def test_import_profile_href_points_to_back_matter_resource(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        doc = data["system-security-plan"]
        href = doc.get("import-profile", {}).get("href", "")
        assert href.startswith("#"), f"import-profile href should be a fragment ref, got: {href!r}"
        resource_uuid = href[1:]
        resources = doc.get("back-matter", {}).get("resources", [])
        matching = [r for r in resources if r.get("uuid") == resource_uuid]
        assert matching, "No back-matter resource found matching import-profile href"

    def test_import_profile_resource_url_uses_correct_path_and_class(self, minimal_cpo):
        # minimal_cpo has certificationType "20x"; default class is "C"
        ssp = build_ssp(minimal_cpo, certification_class="C")
        data = json.loads(ssp.dumps(format="json"))
        doc = data["system-security-plan"]
        resource_uuid = doc["import-profile"]["href"][1:]
        resources = doc.get("back-matter", {}).get("resources", [])
        resource = next(r for r in resources if r.get("uuid") == resource_uuid)
        rlinks = resource.get("rlinks", [])
        assert rlinks
        url = rlinks[0]["href"]
        assert "20X-C" in url, f"Expected '20X-C' in profile URL, got: {url!r}"
        assert url == PROFILE_BASE_URL.format(path="20X", cls="C")

    def test_import_profile_resource_url_respects_class_parameter(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo, certification_class="B")
        data = json.loads(ssp.dumps(format="json"))
        doc = data["system-security-plan"]
        resource_uuid = doc["import-profile"]["href"][1:]
        resources = doc.get("back-matter", {}).get("resources", [])
        resource = next(r for r in resources if r.get("uuid") == resource_uuid)
        url = resource["rlinks"][0]["href"]
        assert "20X-B" in url

    def test_ssp_without_sdr_has_no_frr_requirements(self, minimal_cpo):
        ssp = build_ssp(minimal_cpo)
        data = json.loads(ssp.dumps(format="json"))
        reqs = (
            data["system-security-plan"]
            .get("control-implementation", {})
            .get("implemented-requirements", [])
        )
        assert reqs == []

    def test_ssp_with_20x_sdr_adds_frr_requirement(self, minimal_cpo, minimal_sdr_20x):
        ssp = build_ssp(minimal_cpo, minimal_sdr_20x)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        ctrl_ids = [r["control-id"] for r in reqs]
        assert "MAS-CSO-IIR" in ctrl_ids

    def test_ssp_with_20x_sdr_adds_ksi_requirement(self, minimal_cpo, minimal_sdr_20x):
        ssp = build_ssp(minimal_cpo, minimal_sdr_20x)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        ctrl_ids = [r["control-id"] for r in reqs]
        assert "KSI-IAM-APM" in ctrl_ids

    def test_ssp_with_rev5_sdr_adds_nist_control(self, minimal_cpo, minimal_sdr_rev5):
        ssp = build_ssp(minimal_cpo, minimal_sdr_rev5)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        ctrl_ids = [r["control-id"] for r in reqs]
        assert "ac-02" in ctrl_ids

    def test_ssp_with_rev5_sdr_includes_set_parameters(self, minimal_cpo, minimal_sdr_rev5):
        ssp = build_ssp(minimal_cpo, minimal_sdr_rev5)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        ac2_reqs = [r for r in reqs if r["control-id"] == "ac-02"]
        assert ac2_reqs
        set_params = ac2_reqs[0].get("set-parameters", [])
        assert any(sp["param-id"] == "ac-02_odp.01" for sp in set_params)

    def test_ssp_with_rev5_sdr_by_component_description(self, minimal_cpo, minimal_sdr_rev5):
        ssp = build_ssp(minimal_cpo, minimal_sdr_rev5)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        ac2_reqs = [r for r in reqs if r["control-id"] == "ac-02"]
        assert ac2_reqs
        by_comps = ac2_reqs[0].get("by-components", [])
        assert by_comps
        assert "IdP" in by_comps[0].get("description", "")


class TestBuildSspWithScenarios:
    def test_20x_cpo_sdr_produces_ssp(self, cpo_20x, sdr_20x):
        ssp = build_ssp(cpo_20x, sdr_20x)
        assert ssp is not None

    def test_rev5_cpo_sdr_produces_ssp(self, cpo_rev5, sdr_rev5):
        ssp = build_ssp(cpo_rev5, sdr_rev5)
        assert ssp is not None

    def test_20x_ssp_has_ksi_requirements(self, cpo_20x, sdr_20x):
        ssp = build_ssp(cpo_20x, sdr_20x)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        ksi_ids = [r["control-id"] for r in reqs if r["control-id"].startswith("KSI-")]
        assert len(ksi_ids) == 7  # 7 KSIs in sdr_20x

    def test_rev5_ssp_has_nist_controls(self, cpo_rev5, sdr_rev5):
        ssp = build_ssp(cpo_rev5, sdr_rev5)
        data = json.loads(ssp.dumps(format="json"))
        reqs = data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        nist_ids = [r["control-id"] for r in reqs if "-" in r["control-id"] and not r["control-id"].startswith("KSI")]
        # 6 FRRs + 6 NIST controls in sdr_rev5
        frr_ids = [r["control-id"] for r in reqs if r["control-id"].startswith(tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))]
        nist_only = [r["control-id"] for r in reqs if r["control-id"][0].islower()]
        assert len(nist_only) == 6

    def test_20x_ssp_has_second_leveraged_auth(self, cpo_20x, sdr_20x):
        ssp = build_ssp(cpo_20x, sdr_20x)
        data = json.loads(ssp.dumps(format="json"))
        las = data["system-security-plan"]["system-implementation"].get("leveraged-authorizations", [])
        titles = [la.get("title", "") for la in las]
        assert "FR3084716259" in titles

    def test_rev5_ssp_import_profile_uses_rev5_path(self, cpo_rev5):
        ssp = build_ssp(cpo_rev5, certification_class="C")
        data = json.loads(ssp.dumps(format="json"))
        doc = data["system-security-plan"]
        resource_uuid = doc["import-profile"]["href"][1:]
        resources = doc.get("back-matter", {}).get("resources", [])
        resource = next(r for r in resources if r.get("uuid") == resource_uuid)
        url = resource["rlinks"][0]["href"]
        assert "Rev5-C" in url


# ---------------------------------------------------------------------------
# Tests: build_ar
# ---------------------------------------------------------------------------


class TestBuildAr:
    def test_returns_ar_instance(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        assert isinstance(ar, AssessmentResults)

    def test_ar_has_one_result(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        results = data["assessment-results"]["results"]
        assert len(results) == 1

    def test_result_has_frr_finding(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        findings = data["assessment-results"]["results"][0].get("findings", [])
        titles = [f["title"] for f in findings]
        assert any("MAS-CSO-IIR" in t for t in titles)

    def test_result_has_ksi_finding(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        findings = data["assessment-results"]["results"][0].get("findings", [])
        titles = [f["title"] for f in findings]
        assert any("KSI-IAM-APM" in t for t in titles)

    def test_ksi_observation_has_relevant_evidence(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        observations = data["assessment-results"]["results"][0].get("observations", [])
        ksi_obs = [o for o in observations if "KSI-IAM-APM" in o.get("title", "")]
        assert ksi_obs
        evidence = ksi_obs[0].get("relevant-evidence", [])
        assert evidence
        assert any("iam-apm.pdf" in ev.get("href", "") for ev in evidence)

    def test_all_observations_have_collected(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        observations = data["assessment-results"]["results"][0].get("observations", [])
        assert observations
        for obs in observations:
            assert "collected" in obs, f"observation {obs.get('uuid')} missing 'collected'"

    def test_ksi_observation_collected_matches_evidence_date(self, minimal_sdr_20x):
        # KSI-IAM-APM has evidence with lastUpdated "2026-07-15"
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        observations = data["assessment-results"]["results"][0].get("observations", [])
        ksi_obs = [o for o in observations if "KSI-IAM-APM" in o.get("title", "")]
        assert ksi_obs
        assert ksi_obs[0]["collected"] == "2026-07-15T00:00:00Z"

    def test_frr_observation_collected_falls_back_to_sdr_date(self, minimal_sdr_20x):
        # FRR entry has no date; should match the SDR reference date (most recent evidence)
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        observations = data["assessment-results"]["results"][0].get("observations", [])
        frr_obs = [o for o in observations if "MAS-CSO-IIR" in o.get("title", "")]
        assert frr_obs
        assert frr_obs[0]["collected"] == "2026-07-15T00:00:00Z"

    def test_no_placeholder_result_in_output(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        results = data["assessment-results"]["results"]
        # The template placeholder result should not be present
        assert all(r.get("title") != "[Results Title]" for r in results)

    def test_presentation_id_prop_present(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        props = data["assessment-results"]["metadata"].get("props", [])
        pid_props = [p for p in props if p.get("name") == "presentation-id" and p.get("ns") == CYBERCRAFT_NS]
        assert pid_props
        assert pid_props[0]["value"] == "fedramp-cr26"

    def test_ssp_href_set_in_import_ap(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x, ssp_href="my-ssp.json")
        data = json.loads(ar.dumps(format="json"))
        assert data["assessment-results"]["import-ap"]["href"] == "my-ssp.json"

    def test_related_observations_link_to_observations(self, minimal_sdr_20x):
        ar = build_ar(minimal_sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        result = data["assessment-results"]["results"][0]
        obs_uuids = {o["uuid"] for o in result.get("observations", [])}
        for finding in result.get("findings", []):
            for rel_obs in finding.get("related-observations", []):
                assert rel_obs["observation-uuid"] in obs_uuids


class TestBuildArWithScenarios:
    def test_20x_sdr_produces_ar(self, sdr_20x):
        ar = build_ar(sdr_20x)
        assert ar is not None

    def test_20x_ar_has_7_ksi_findings(self, sdr_20x):
        ar = build_ar(sdr_20x)
        data = json.loads(ar.dumps(format="json"))
        findings = data["assessment-results"]["results"][0].get("findings", [])
        ksi_findings = [f for f in findings if "KSI-" in f["title"]]
        assert len(ksi_findings) == 7


# ---------------------------------------------------------------------------
# Tests: build_ap
# ---------------------------------------------------------------------------


class TestBuildAp:
    def test_returns_ap_instance(self, minimal_sdr_20x):
        ap = build_ap(minimal_sdr_20x)
        assert isinstance(ap, AssessmentPlan)

    def test_import_ssp_href_set(self, minimal_sdr_20x):
        ap = build_ap(minimal_sdr_20x, ssp_href="my-ssp.json")
        data = json.loads(ap.dumps(format="json"))
        assert data["assessment-plan"]["import-ssp"]["href"] == "my-ssp.json"

    def test_reviewed_controls_includes_frr_ids(self, minimal_sdr_20x):
        ap = build_ap(minimal_sdr_20x)
        data = json.loads(ap.dumps(format="json"))
        selections = (
            data["assessment-plan"]
            .get("reviewed-controls", {})
            .get("control-selections", [])
        )
        all_ids = [
            c["control-id"]
            for sel in selections
            for c in sel.get("include-controls", [])
        ]
        assert "MAS-CSO-IIR" in all_ids

    def test_reviewed_controls_includes_ksi_ids(self, minimal_sdr_20x):
        ap = build_ap(minimal_sdr_20x)
        data = json.loads(ap.dumps(format="json"))
        selections = (
            data["assessment-plan"]
            .get("reviewed-controls", {})
            .get("control-selections", [])
        )
        all_ids = [
            c["control-id"]
            for sel in selections
            for c in sel.get("include-controls", [])
        ]
        assert "KSI-IAM-APM" in all_ids

    def test_presentation_id_prop_present(self, minimal_sdr_20x):
        ap = build_ap(minimal_sdr_20x)
        data = json.loads(ap.dumps(format="json"))
        props = data["assessment-plan"]["metadata"].get("props", [])
        pid_props = [p for p in props if p.get("name") == "presentation-id" and p.get("ns") == CYBERCRAFT_NS]
        assert pid_props

    def test_rev5_ap_includes_nist_control_ids(self, minimal_sdr_rev5):
        ap = build_ap(minimal_sdr_rev5)
        data = json.loads(ap.dumps(format="json"))
        selections = (
            data["assessment-plan"]
            .get("reviewed-controls", {})
            .get("control-selections", [])
        )
        all_ids = [
            c["control-id"]
            for sel in selections
            for c in sel.get("include-controls", [])
        ]
        assert "ac-02" in all_ids


# ---------------------------------------------------------------------------
# Tests: convert (integration)
# ---------------------------------------------------------------------------


class TestConvert:
    def test_convert_20x_produces_three_files(self, tmp_path, cpo_20x, sdr_20x):
        cpo_file = tmp_path / "cpo.json"
        sdr_file = tmp_path / "sdr.json"
        cpo_file.write_text(json.dumps(cpo_20x))
        sdr_file.write_text(json.dumps(sdr_20x))

        output = convert(cpo_file, sdr_file, tmp_path)

        assert "ssp" in output
        assert "ar" in output
        assert "ap" in output
        assert output["ssp"].exists()
        assert output["ar"].exists()
        assert output["ap"].exists()

    def test_convert_cpo_only_produces_one_file(self, tmp_path, cpo_20x):
        cpo_file = tmp_path / "cpo.json"
        cpo_file.write_text(json.dumps(cpo_20x))

        output = convert(cpo_file, output_dir=tmp_path)

        assert "ssp" in output
        assert "ar" not in output
        assert "ap" not in output

    def test_output_files_are_valid_json(self, tmp_path, cpo_20x, sdr_20x):
        cpo_file = tmp_path / "cpo.json"
        sdr_file = tmp_path / "sdr.json"
        cpo_file.write_text(json.dumps(cpo_20x))
        sdr_file.write_text(json.dumps(sdr_20x))

        output = convert(cpo_file, sdr_file, tmp_path)

        for doc_type, path in output.items():
            content = path.read_text(encoding="utf-8")
            parsed = json.loads(content)  # must not raise
            assert isinstance(parsed, dict), f"{doc_type} output is not a JSON object"

    def test_output_filenames_contain_package_id(self, tmp_path, cpo_20x, sdr_20x):
        cpo_file = tmp_path / "cpo.json"
        sdr_file = tmp_path / "sdr.json"
        cpo_file.write_text(json.dumps(cpo_20x))
        sdr_file.write_text(json.dumps(sdr_20x))

        output = convert(cpo_file, sdr_file, tmp_path)

        pkg_id = cpo_20x["serviceIdentification"]["fedRampPackageId"].lower()
        for path in output.values():
            assert pkg_id in path.name.lower()

    def test_convert_rev5_produces_ssp_with_nist_controls(self, tmp_path, cpo_rev5, sdr_rev5):
        cpo_file = tmp_path / "cpo.json"
        sdr_file = tmp_path / "sdr.json"
        cpo_file.write_text(json.dumps(cpo_rev5))
        sdr_file.write_text(json.dumps(sdr_rev5))

        output = convert(cpo_file, sdr_file, tmp_path)
        ssp_data = json.loads(output["ssp"].read_text())
        reqs = ssp_data["system-security-plan"]["control-implementation"]["implemented-requirements"]
        nist_ids = {r["control-id"] for r in reqs}
        assert "ac-02" in nist_ids
