import pytest

from modules.search.engine import evaluate_candidate, validate_criteria


@pytest.mark.parametrize(
    "operator,terms,expected",
    [
        ("ANY", ["python", "ruby"], True),
        ("ALL", ["python", "ruby"], False),
        ("ALL", ["python", "django"], True),
    ],
)
def test_keyword_groups(operator, terms, expected):
    groups = validate_criteria(
        [{"id": "g", "purpose": "REQUIREMENT", "operator": operator}],
        [
            {
                "id": str(i),
                "group_id": "g",
                "field": "resume_keyword",
                "operator": "CONTAINS",
                "value": term,
            }
            for i, term in enumerate(terms)
        ],
    )
    assert (
        evaluate_candidate(
            {"resume_keyword": ["Built Python services using Django"]}, groups
        ).eligible
        is expected
    )


def test_notice_filter_requires_matching_known_value():
    groups = validate_criteria(
        [{"id": "g", "purpose": "REQUIREMENT", "operator": "ALL"}],
        [
            {
                "id": "c",
                "group_id": "g",
                "field": "notice_period",
                "operator": "EQ",
                "value": "30 days",
            }
        ],
    )
    assert evaluate_candidate({"notice_period": "30 days"}, groups).eligible
    assert not evaluate_candidate({"notice_period": None}, groups).eligible


def test_role_company_and_education_filters_use_case_insensitive_contains():
    groups = validate_criteria(
        [{"id": "g", "purpose": "REQUIREMENT", "operator": "ALL"}],
        [
            {
                "id": "role",
                "group_id": "g",
                "field": "current_role",
                "operator": "CONTAINS",
                "value": "backend engineer",
            },
            {
                "id": "company",
                "group_id": "g",
                "field": "current_company",
                "operator": "CONTAINS",
                "value": "zylker",
            },
            {
                "id": "education",
                "group_id": "g",
                "field": "education",
                "operator": "CONTAINS",
                "value": "computer science",
            },
        ],
    )

    candidate = {
        "current_role": "Senior Backend Engineer",
        "current_company": "Zylker Pay",
        "education": ["B.Tech Computer Science Bengaluru Institute of Technology"],
    }
    assert evaluate_candidate(candidate, groups).eligible
