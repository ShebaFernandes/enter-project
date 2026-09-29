from pathlib import Path

import yaml

CONTRACT = (
    Path(__file__).parents[3] / "specs/001-recruiter-candidate-workflows/contracts/openapi.yaml"
)


def _resolve(document, reference):
    assert reference.startswith("#/")
    value = document
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def _walk_references(document, value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for nested in value.values():
            yield from _walk_references(document, nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_references(document, nested)


def test_every_local_reference_resolves_and_operation_declares_responses():
    document = yaml.safe_load(CONTRACT.read_text())
    assert document["openapi"].startswith("3.")
    for reference in _walk_references(document, document):
        assert _resolve(document, reference) is not None
    for path_item in document["paths"].values():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                assert operation.get("operationId")
                assert operation.get("responses")


def test_foundation_paths_and_conditional_types_are_declared():
    document = yaml.safe_load(CONTRACT.read_text())
    paths = document["paths"]
    assert "/platform/tenants" in paths
    assert "/tenants/{tenantId}/business-units" in paths
    assert "/tenants/{tenantId}/openings" in paths
    assert "/tenants/{tenantId}/recruiter-entered-candidates" in paths
    assert "/administration/emergency-access-requests" in paths
    schemas = document["components"]["schemas"]
    assert set(schemas["CandidateFacingStatus"]["enum"]) == {
        "APPLIED",
        "PROFILE_VIEWED",
        "SHORTLISTED",
        "RECRUITER_INTERESTED",
        "INTERVIEW_REQUESTED",
        "OFFER_MADE",
        "NOT_SELECTED",
        "WITHDRAWN",
    }
    assert "opening_id" not in schemas["SavedSearch"].get("properties", {})


def test_search_context_groups_and_saved_search_have_one_authoritative_shape():
    document = yaml.safe_load(CONTRACT.read_text())
    schemas = document["components"]["schemas"]
    contexts = schemas["SearchContext"]["oneOf"]
    ad_hoc, opening = contexts
    assert ad_hoc["properties"]["type"]["const"] == "AD_HOC"
    assert "opening_id" not in ad_hoc["properties"]
    assert ad_hoc["additionalProperties"] is False
    assert opening["properties"]["type"]["const"] == "OPENING"
    assert opening["required"] == ["type", "opening_id"]
    assert opening["additionalProperties"] is False
    assert schemas["CriteriaGroup"]["properties"]["operator"]["enum"] == ["ANY", "ALL"]
    assert "group_id" in schemas["Criterion"]["required"]
    assert "opening_id" not in schemas["SavedSearch"]["properties"]
    example = schemas["SearchCriteria"]["example"]
    group_ids = {group["id"] for group in example["groups"]}
    assert all(criterion["group_id"] in group_ids for criterion in example["criteria"])


def test_status_preview_publication_notification_and_emergency_types_are_separated():
    document = yaml.safe_load(CONTRACT.read_text())
    paths = document["paths"]
    schemas = document["components"]["schemas"]
    preview_schema = paths["/tenants/{tenantId}/applications/{applicationId}/status-preview"][
        "post"
    ]["requestBody"]["content"]["application/json"]["schema"]
    assert preview_schema["properties"]["internal_status"]["$ref"].endswith(
        "/InternalRecruitingStatus"
    )
    publication_schema = paths["/tenants/{tenantId}/applications/{applicationId}/status-publish"][
        "post"
    ]["requestBody"]["content"]["application/json"]["schema"]
    assert publication_schema["properties"]["candidate_status"]["$ref"].endswith(
        "/CandidateFacingStatus"
    )
    suggestion = schemas["StatusPreview"]["properties"]["suggested_candidate_status"]
    assert {item.get("type") for item in suggestion["oneOf"] if "type" in item} == {"null"}
    assert schemas["InternalNotificationDelivery"]["properties"]["state"]["enum"] == [
        "QUEUED",
        "SENDING",
        "SENT",
        "FAILED",
        "CANCELLED",
    ]
    assert schemas["CandidateNotificationState"]["properties"]["state"]["enum"] == [
        "PENDING",
        "SENT",
        "FAILED",
        "CANCELLED",
    ]
    assert schemas["EmergencyAccessRequest"]["properties"]["field_scope"]["minItems"] == 1


def test_foundation_operations_declare_standard_error_contracts_and_examples():
    document = yaml.safe_load(CONTRACT.read_text())
    components = document["components"]
    assert set(components["responses"]) >= {
        "Unauthorized",
        "Forbidden",
        "NotFound",
        "ValidationFailed",
        "RateLimited",
        "Conflict",
        "SafeDegradation",
    }
    recruiter_create = document["paths"]["/tenants/{tenantId}/recruiter-entered-candidates"]["post"]
    assert set(recruiter_create["responses"]) >= {"201", "401", "403", "422"}
    schema = components["schemas"]["RecruiterEnteredCandidateCreate"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["confirm_synthetic"]["const"] is True
    assert components["schemas"]["SearchCriteria"].get("example")
