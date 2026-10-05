from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class CriteriaValidationError(ValueError):
    pass


ALLOWED_FIELDS = {
    "skill",
    "experience_years",
    "location",
    "work_arrangement",
    "availability_date",
    "role_category",
    "resume_keyword",
    "notice_period",
}
ALLOWED_OPERATORS = {"EQ", "NE", "LT", "LTE", "GT", "GTE", "IN", "NOT_IN", "CONTAINS", "EXISTS"}


@dataclass(frozen=True)
class MatchResult:
    eligible: bool
    score: Decimal
    evidence: list[dict]
    unknowns: list[str]


def validate_criteria(groups, criteria):
    group_ids = [str(g.get("id", "")) for g in groups]
    criterion_ids = [str(c.get("id", "")) for c in criteria]
    if (
        not groups
        or not criteria
        or any(not value for value in group_ids + criterion_ids)
        or len(set(group_ids)) != len(group_ids)
        or len(set(criterion_ids)) != len(criterion_ids)
    ):
        raise CriteriaValidationError("Group and criterion IDs must be present and unique.")
    indexed = {}
    for group in groups:
        if group.get("purpose") not in {"REQUIREMENT", "PREFERENCE", "EXCLUSION"} or group.get(
            "operator"
        ) not in {"ANY", "ALL"}:
            raise CriteriaValidationError("Unsupported group.")
        indexed[str(group["id"])] = {**group, "criteria": []}
    for item in criteria:
        if str(item.get("group_id")) not in indexed:
            raise CriteriaValidationError("Criterion references a missing group.")
        if item.get("field") not in ALLOWED_FIELDS or item.get("operator") not in ALLOWED_OPERATORS:
            raise CriteriaValidationError("Unsupported or protected criterion.")
        indexed[str(item["group_id"])]["criteria"].append(item)
    if any(not group["criteria"] for group in indexed.values()):
        raise CriteriaValidationError("Every group requires a criterion.")
    return list(indexed.values())


def _value(candidate, field):
    return candidate.get(
        {
            "skill": "skills",
            "work_arrangement": "work_arrangements",
            "role_category": "role_categories",
        }.get(field, field)
    )


def _matches(candidate, item):
    actual = _value(candidate, item["field"])
    expected, op = item.get("value"), item["operator"]
    if actual is None:
        return False, True
    values = actual if isinstance(actual, list) else [actual]
    normalized = [str(v).casefold() for v in values]
    target = str(expected).casefold()
    if item["field"] == "resume_keyword" and op == "CONTAINS":
        result = bool(target.strip()) and any(target in value for value in normalized)
    elif op in {"EQ", "CONTAINS"}:
        result = target in normalized
    elif op == "NE":
        result = target not in normalized
    elif op == "IN":
        result = any(str(v).casefold() in {str(x).casefold() for x in expected} for v in values)
    elif op == "NOT_IN":
        result = all(str(v).casefold() not in {str(x).casefold() for x in expected} for v in values)
    elif op == "EXISTS":
        result = bool(actual) is bool(expected)
    else:
        if item["field"] == "availability_date":
            try:
                left_date = actual if isinstance(actual, date) else date.fromisoformat(str(actual))
                right_date = date.fromisoformat(str(expected))
            except (TypeError, ValueError) as exc:
                raise CriteriaValidationError("Availability values must be ISO dates.") from exc
            result = {
                "LT": left_date < right_date,
                "LTE": left_date <= right_date,
                "GT": left_date > right_date,
                "GTE": left_date >= right_date,
            }[op]
        else:
            try:
                left_number = Decimal(str(actual))
                right_number = Decimal(str(expected))
            except Exception as exc:
                raise CriteriaValidationError("Numeric criterion value is invalid.") from exc
            result = {
                "LT": left_number < right_number,
                "LTE": left_number <= right_number,
                "GT": left_number > right_number,
                "GTE": left_number >= right_number,
            }[op]
    return result, False


def evaluate_candidate(candidate, groups):
    score = Decimal("0")
    evidence = []
    unknowns = []
    for group in groups:
        outcomes = []
        for item in group["criteria"]:
            matched, unknown = _matches(candidate, item)
            outcomes.append(matched)
            if unknown:
                unknowns.append(item["field"])
            elif matched:
                evidence.append(
                    {
                        "evidence_id": str(item["id"]),
                        "label": item["field"],
                        "provenance": "CANDIDATE_REPORTED",
                    }
                )
        group_match = all(outcomes) if group["operator"] == "ALL" else any(outcomes)
        if group["purpose"] == "REQUIREMENT" and not group_match:
            return MatchResult(False, score, evidence, sorted(set(unknowns)))
        if group["purpose"] == "EXCLUSION" and group_match:
            return MatchResult(False, score, evidence, sorted(set(unknowns)))
        if group["purpose"] == "PREFERENCE" and group_match:
            score += 1
    return MatchResult(True, score, evidence, sorted(set(unknowns)))
