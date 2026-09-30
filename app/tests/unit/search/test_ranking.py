import uuid

import pytest

from modules.search.engine import CriteriaValidationError, evaluate_candidate, validate_criteria


def criterion(group, field, operator, value):
    return {
        "id": str(uuid.uuid4()),
        "group_id": group["id"],
        "field": field,
        "operator": operator,
        "value": value,
    }


def test_group_any_all_exclusion_and_stable_score():
    required = {"id": str(uuid.uuid4()), "purpose": "REQUIREMENT", "operator": "ALL"}
    preferred = {"id": str(uuid.uuid4()), "purpose": "PREFERENCE", "operator": "ANY"}
    excluded = {"id": str(uuid.uuid4()), "purpose": "EXCLUSION", "operator": "ANY"}
    criteria = [
        criterion(required, "skill", "CONTAINS", "Python"),
        criterion(required, "location", "EQ", "Bengaluru"),
        criterion(preferred, "work_arrangement", "EQ", "REMOTE"),
        criterion(excluded, "skill", "CONTAINS", "COBOL"),
    ]
    validated = validate_criteria([required, preferred, excluded], criteria)
    result = evaluate_candidate(
        {
            "skills": ["Python"],
            "location": "Bengaluru",
            "work_arrangements": ["REMOTE"],
            "experience_years": 5,
        },
        validated,
    )
    assert result.eligible and result.score == 1
    assert result.evidence


def test_duplicate_missing_and_protected_fields_rejected():
    group = {"id": str(uuid.uuid4()), "purpose": "REQUIREMENT", "operator": "ANY"}
    item = criterion(group, "religion", "EQ", "anything")
    with pytest.raises(CriteriaValidationError):
        validate_criteria([group], [item])


def test_any_all_unknowns_stable_evidence_and_protected_proxies():
    any_group = {"id": str(uuid.uuid4()), "purpose": "REQUIREMENT", "operator": "ANY"}
    all_group = {"id": str(uuid.uuid4()), "purpose": "PREFERENCE", "operator": "ALL"}
    criteria = [
        criterion(any_group, "skill", "EQ", "Python"),
        criterion(any_group, "skill", "EQ", "Rust"),
        criterion(all_group, "availability_date", "LTE", "2026-10-01"),
        criterion(all_group, "experience_years", "GTE", 3),
    ]
    result = evaluate_candidate(
        {
            "skills": ["Python"],
            "availability_date": "2026-09-30",
            "experience_years": 5,
        },
        validate_criteria([any_group, all_group], criteria),
    )
    assert result.eligible and result.score == 1
    assert all(set(item) == {"evidence_id", "label", "provenance"} for item in result.evidence)
    assert result.unknowns == []

    for protected in ("age", "gender", "religion", "caste", "name", "email"):
        protected_item = criterion(any_group, protected, "EQ", "x")
        with pytest.raises(CriteriaValidationError):
            validate_criteria([any_group], [protected_item])


def test_duplicate_group_and_criterion_ids_and_empty_groups_are_rejected():
    group = {"id": str(uuid.uuid4()), "purpose": "REQUIREMENT", "operator": "ALL"}
    item = criterion(group, "skill", "EQ", "Python")
    with pytest.raises(CriteriaValidationError):
        validate_criteria([group, group], [item])
    with pytest.raises(CriteriaValidationError):
        validate_criteria([group], [item, item])
    with pytest.raises(CriteriaValidationError):
        validate_criteria([group], [])
    item["field"] = "skill"
    item["group_id"] = str(uuid.uuid4())
    with pytest.raises(CriteriaValidationError):
        validate_criteria([group], [item])
