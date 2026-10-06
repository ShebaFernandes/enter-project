from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Literal["search-intent.v1"] = "search-intent.v1"
INTENT_NAMESPACE = uuid.UUID("86becd39-1203-44a0-af9f-083a721def5b")
PROTECTED_TERMS = {
    "age",
    "caste",
    "disability",
    "ethnicity",
    "gender",
    "marital_status",
    "pregnancy",
    "race",
    "religion",
    "sex",
}
SUPPORTED_FIELDS = {
    "skill",
    "experience_years",
    "location",
    "work_arrangement",
    "availability_date",
    "role_category",
    "current_role",
    "current_company",
    "education",
    "resume_keyword",
    "notice_period",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClarificationQuestion(StrictModel):
    id: Literal["skills", "location", "work_arrangement", "experience_rule"]
    question: str
    kind: Literal["TEXT", "CHOICE"]
    options: list[str] = Field(default_factory=list)
    allow_any: bool = True


class AdHocContext(StrictModel):
    type: Literal["AD_HOC"]


class OpeningContext(StrictModel):
    type: Literal["OPENING"]
    opening_id: uuid.UUID


SearchContextInput = Annotated[AdHocContext | OpeningContext, Field(discriminator="type")]


class CriteriaGroupInput(StrictModel):
    id: uuid.UUID
    purpose: Literal["REQUIREMENT", "PREFERENCE", "EXCLUSION"]
    operator: Literal["ANY", "ALL"]
    label: str | None = Field(default=None, max_length=200)


class CriterionInput(StrictModel):
    id: uuid.UUID
    group_id: uuid.UUID
    field: Literal[
        "skill",
        "experience_years",
        "location",
        "work_arrangement",
        "availability_date",
        "role_category",
        "current_role",
        "current_company",
        "education",
        "resume_keyword",
        "notice_period",
    ]
    operator: Literal["EQ", "NE", "LT", "LTE", "GT", "GTE", "IN", "NOT_IN", "CONTAINS", "EXISTS"]
    value: str | int | float | bool | list[str]


class SearchCriteriaInput(StrictModel):
    context: SearchContextInput
    groups: list[CriteriaGroupInput] = Field(min_length=1)
    criteria: list[CriterionInput] = Field(min_length=1)
    cursor: str | None = None
    limit: int = Field(default=25, ge=1, le=100)

    @model_validator(mode="after")
    def validate_references(self) -> SearchCriteriaInput:
        group_ids = [item.id for item in self.groups]
        criterion_ids = [item.id for item in self.criteria]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("Group IDs must be unique.")
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("Criterion IDs must be unique.")
        known = set(group_ids)
        referenced = {item.group_id for item in self.criteria}
        if not referenced <= known:
            raise ValueError("Every criterion must reference one submitted group.")
        if known != referenced:
            raise ValueError("Every group requires at least one criterion.")
        return self


class SearchIntent(StrictModel):
    schema_version: Literal["search-intent.v1"] = SCHEMA_VERSION
    criteria: SearchCriteriaInput
    requires_review: bool
    ambiguities: list[str] = Field(default_factory=list)
    clarifications: list[ClarificationQuestion] = Field(default_factory=list)
    ai_status: Literal["USED", "NOT_NEEDED", "UNAVAILABLE", "INVALID_OUTPUT"]


def _stable_id(prompt: str, context: dict[str, object], label: str) -> uuid.UUID:
    context_key = f"{context.get('type')}:{context.get('opening_id', '')}"
    return uuid.uuid5(
        INTENT_NAMESPACE, f"{SCHEMA_VERSION}:{context_key}:{prompt.casefold()}:{label}"
    )


def deterministic_fallback(prompt: str, context: dict[str, object]) -> SearchIntent:
    """Create visible, editable criteria without treating free text as authority."""
    normalized = " ".join(prompt.split())
    folded = normalized.casefold()
    protected = sorted(
        term for term in PROTECTED_TERMS if re.search(rf"\b{re.escape(term)}\b", folded)
    )
    injection = any(
        phrase in folded
        for phrase in ("ignore all", "ignore policy", "system prompt", "grant access", "tool call")
    )
    specs: list[dict[str, object]] = []
    for skill in ("python", "django", "java", "javascript", "react", "sql"):
        if re.search(rf"\b{skill}\b", folded):
            specs.append({"field": "skill", "operator": "CONTAINS", "value": skill.title()})
    for location in ("bengaluru", "bangalore", "mumbai", "delhi", "hyderabad", "pune", "chennai"):
        if re.search(rf"\b{location}\b", folded):
            specs.append(
                {
                    "field": "location",
                    "operator": "EQ",
                    "value": "Bengaluru" if location == "bangalore" else location.title(),
                }
            )
    experience = re.search(r"\b(\d{1,2})\s*(\+)?\s*(?:years?|yrs?|exp(?:erience)?)\b", folded)
    experience_rule_is_explicit = bool(
        experience
        and (
            experience.group(2)
            or re.search(r"\b(?:at least|minimum|min\.?|exactly|exact)\b", folded)
        )
    )
    if experience:
        operator = "EQ" if re.search(r"\b(?:exactly|exact)\b", folded) else "GTE"
        specs.append(
            {
                "field": "experience_years",
                "operator": operator,
                "value": int(experience.group(1)),
            }
        )
    arrangement = next((item for item in ("remote", "hybrid", "onsite") if item in folded), None)
    if arrangement:
        specs.append({"field": "work_arrangement", "operator": "EQ", "value": arrangement.upper()})
    role = next(
        (
            item
            for item in ("engineer", "developer", "designer", "recruiter", "manager", "analyst")
            if item in folded
        ),
        None,
    )
    if role:
        specs.append({"field": "role_category", "operator": "CONTAINS", "value": role})
    specialty = next(
        (
            item
            for item in (
                "backend",
                "frontend",
                "full stack",
                "fullstack",
                "platform",
                "mobile",
                "data",
                "machine learning",
                "devops",
            )
            if item in folded
        ),
        None,
    )
    if specialty:
        specs.append({"field": "resume_keyword", "operator": "CONTAINS", "value": specialty})
    if not specs:
        specs.append(
            {
                "field": "role_category",
                "operator": "CONTAINS",
                "value": normalized[:200] or "Unspecified role",
            }
        )

    group_id = _stable_id(normalized, context, "requirements")
    group = CriteriaGroupInput(
        id=group_id,
        purpose="REQUIREMENT",
        operator="ALL",
        label="Interpreted requirements",
    )
    criteria = [
        CriterionInput.model_validate(
            {
                "id": _stable_id(normalized, context, f"criterion:{index}:{spec}"),
                "group_id": group_id,
                **spec,
            }
        )
        for index, spec in enumerate(specs)
    ]
    fields = {str(spec["field"]) for spec in specs}
    clarifications: list[ClarificationQuestion] = []
    if "skill" not in fields:
        clarifications.append(
            ClarificationQuestion(
                id="skills",
                question="Which skills or technologies are essential?",
                kind="TEXT",
            )
        )
    if "location" not in fields:
        clarifications.append(
            ClarificationQuestion(
                id="location",
                question="Where can this person be based?",
                kind="TEXT",
            )
        )
    if "work_arrangement" not in fields:
        clarifications.append(
            ClarificationQuestion(
                id="work_arrangement",
                question="What work arrangement should the search use?",
                kind="CHOICE",
                options=["REMOTE", "HYBRID", "ON_SITE", "FLEXIBLE"],
            )
        )
    if "experience_years" in fields and not experience_rule_is_explicit:
        clarifications.append(
            ClarificationQuestion(
                id="experience_rule",
                question="Should the experience number be a minimum or an exact match?",
                kind="CHOICE",
                options=["AT_LEAST", "EXACT"],
                allow_any=False,
            )
        )
    ambiguities: list[str] = []
    if len(specs) < 2 or any(term in folded for term in ("maybe", "suitable", "good fit", "etc")):
        ambiguities.append("The hiring need is materially incomplete; review the visible criteria.")
    if protected:
        ambiguities.append("Protected attributes were rejected and were not added as criteria.")
    if injection:
        ambiguities.append("Instruction-like text was treated only as untrusted recruiter input.")
    return SearchIntent(
        criteria=SearchCriteriaInput.model_validate(
            {"context": context, "groups": [group], "criteria": criteria, "limit": 25}
        ),
        requires_review=bool(ambiguities or clarifications),
        ambiguities=ambiguities,
        clarifications=clarifications,
        ai_status="NOT_NEEDED",
    )
