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
