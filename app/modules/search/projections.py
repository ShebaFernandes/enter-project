from modules.candidate.models import CandidateFinding


def project_finding(finding: CandidateFinding) -> dict:
    if (
        finding.code != "SHORT_TENURE"
        or finding.severity != "INFORMATIONAL"
        or finding.result != "FOUND"
        or finding.superseded_at is not None
    ):
        raise ValueError("Finding is not eligible for recruiter presentation.")
    evidence = dict(finding.evidence)
    months = evidence["calculated_duration"]["calendar_months"]
    company = evidence["company"]
    return {
        "id": str(finding.id),
        "code": "SHORT_TENURE",
        "severity": "INFORMATIONAL",
        "informational_only": True,
        "message": f"Candidate left {company} after approximately {months} months.",
        "evidence": evidence,
        "calculation_version": finding.calculation_version,
        "evaluated_at": finding.evaluated_at.isoformat().replace("+00:00", "Z"),
    }


def authorized_findings(profile, *, allow: bool) -> list[dict]:
    if not allow:
        return []
    findings = profile.findings.filter(
        code="SHORT_TENURE", result="FOUND", superseded_at__isnull=True
    ).order_by("evaluated_at", "id")
    return [project_finding(finding) for finding in findings]
