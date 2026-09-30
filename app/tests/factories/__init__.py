import uuid
from datetime import timedelta
from typing import cast

import factory
from django.utils import timezone

from modules.candidate.models import (
    CandidateProfile,
    ConsentRecord,
    EmploymentRecord,
    ResumeAsset,
    VisibilityRule,
)
from modules.communications.models import Notification
from modules.identity.models import Identity, IdentityCapability
from modules.operations.crypto import encrypt
from modules.recruiting.models import (
    Application,
    CandidateFacingStatus,
    CandidateWorkRecord,
    DisclosureRequest,
    Opening,
    RecruiterEnteredCandidate,
    RecruiterNote,
)
from modules.search.models import SearchDefinition
from modules.tenancy.models import AccessGrant, BusinessUnit, Tenant, TenantMembership


class IdentityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Identity

    cognito_subject = factory.Sequence(lambda n: f"synthetic-subject-{n}")
    email_lookup_hmac = factory.Sequence(lambda n: f"hmac-{n}".encode())
    email_ciphertext = factory.LazyAttribute(
        lambda obj: encrypt(f"{obj.cognito_subject}@synthetic.invalid")
    )
    email_verified_at = factory.LazyFunction(timezone.now)


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"Synthetic Company {n}")
    slug = factory.Sequence(lambda n: f"synthetic-company-{n}")
    legal_boundary_reference = factory.Sequence(lambda n: f"contract-{n}")
    status = Tenant.Status.ACTIVE

    class Params:
        provisioning = factory.Trait(status=Tenant.Status.PROVISIONING)
        active = factory.Trait(status=Tenant.Status.ACTIVE)
        suspended = factory.Trait(status=Tenant.Status.SUSPENDED)
        closed = factory.Trait(status=Tenant.Status.CLOSED)


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TenantMembership

    tenant = factory.SubFactory(TenantFactory)
    identity = factory.SubFactory(IdentityFactory)
    role = TenantMembership.Role.RECRUITER
    status = TenantMembership.Status.ACTIVE

    class Params:
        recruiter = factory.Trait(role=TenantMembership.Role.RECRUITER)
        hiring_manager = factory.Trait(role=TenantMembership.Role.HIRING_MANAGER)
        tenant_admin = factory.Trait(role=TenantMembership.Role.TENANT_ADMIN)
        stale = factory.Trait(version=2, status=TenantMembership.Status.SUSPENDED)


class BusinessUnitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BusinessUnit

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f"Synthetic Unit {n}")
    created_by = factory.SubFactory(IdentityFactory)


class OpeningFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Opening

    tenant = factory.SelfAttribute("business_unit.tenant")
    business_unit = factory.SubFactory(BusinessUnitFactory)
    title = factory.Sequence(lambda n: f"Synthetic Role {n}")
    location = {"city": "Bengaluru", "country": "IN"}
    work_mode = Opening.WorkMode.HYBRID
    employment_type = "FULL_TIME"
    created_by = factory.SubFactory(IdentityFactory)

    class Params:
        draft = factory.Trait(state=Opening.State.DRAFT)
        open = factory.Trait(state=Opening.State.OPEN)
        paused = factory.Trait(state=Opening.State.PAUSED)
        closed = factory.Trait(state=Opening.State.CLOSED)


class CandidateCapabilityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IdentityCapability

    identity = factory.SubFactory(IdentityFactory)
    role = IdentityCapability.Role.CANDIDATE
    assigned_by = factory.SubFactory(IdentityFactory)


class PlatformSecurityCapabilityFactory(CandidateCapabilityFactory):
    role = IdentityCapability.Role.PLATFORM_SECURITY_ADMIN


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application

    opening = factory.SubFactory(OpeningFactory)
    tenant = factory.SelfAttribute("opening.tenant")
    candidate_profile_id = factory.LazyFunction(lambda: CandidateProfileFactory().id)
    consent_context_id = factory.LazyAttribute(
        lambda obj: ConsentRecordFactory(
            profile_id=obj.candidate_profile_id,
            purpose="APPLICATION_SUBMISSION",
            field_scope=["application", "resume", "notifications"],
            audience_scope={
                "opening_id": str(obj.opening.id),
                "tenant_id": str(obj.tenant.id),
            },
        ).id
    )
    state = Application.State.DRAFT

    class Params:
        submitted = factory.Trait(
            state=Application.State.SUBMITTED, submitted_at=factory.LazyFunction(timezone.now)
        )
        active = factory.Trait(
            state=Application.State.ACTIVE, submitted_at=factory.LazyFunction(timezone.now)
        )
        closed = factory.Trait(
            state=Application.State.CLOSED,
            submitted_at=factory.LazyFunction(timezone.now),
            closed_at=factory.LazyFunction(timezone.now),
        )
        withdrawn = factory.Trait(
            state=Application.State.WITHDRAWN,
            submitted_at=factory.LazyFunction(timezone.now),
            withdrawn_at=factory.LazyFunction(timezone.now),
            candidate_status=CandidateFacingStatus.WITHDRAWN,
        )
        unmapped_status = factory.Trait(suggested_candidate_status=None)
        stale = factory.Trait(version=2)


class RecruiterEnteredCandidateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RecruiterEnteredCandidate

    tenant = factory.SubFactory(TenantFactory)
    created_by = factory.SubFactory(IdentityFactory)
    display_name = factory.Sequence(lambda n: f"Synthetic Candidate {n}")
    location = {"city": "Bengaluru", "country": "IN"}
    experience_years = "4.50"
    skills = ["Python", "Django"]

    class Params:
        long_content = factory.Trait(display_name="S" * 200, skills=["X" * 200])
        stale = factory.Trait(version=2)


class SearchDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SearchDefinition

    tenant = factory.SubFactory(TenantFactory)
    actor = factory.SubFactory(IdentityFactory)
    context_type = SearchDefinition.ContextType.AD_HOC
    criteria_context = {"type": "AD_HOC"}


class CandidateWorkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CandidateWorkRecord

    originating_search = factory.SubFactory(SearchDefinitionFactory)
    tenant = factory.SelfAttribute("originating_search.tenant")
    candidate_profile = factory.SubFactory("tests.factories.CandidateProfileFactory")
    created_by = factory.SelfAttribute("originating_search.actor")
    updated_by = factory.SelfAttribute("originating_search.actor")

    class Params:
        on_shortlist = factory.Trait(internal_status="SHORTLISTED", shortlisted=True)
        not_relevant = factory.Trait(
            internal_status="NOT_RELEVANT", structured_reasons=["SYNTHETIC_REASON"]
        )
        stale = factory.Trait(version=2)


class RecruiterNoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RecruiterNote

    candidate_work = factory.SubFactory(CandidateWorkFactory)
    tenant = factory.SelfAttribute("candidate_work.tenant")
    application = None
    author = factory.SelfAttribute("candidate_work.created_by")
    body_ciphertext = factory.LazyFunction(lambda: encrypt("Synthetic private note"))


class DisclosureRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DisclosureRequest

    application = factory.SubFactory(ApplicationFactory)
    candidate_work = None
    tenant = factory.SelfAttribute("application.tenant")
    candidate_profile_id = factory.SelfAttribute("application.candidate_profile_id")
    purpose = "HIRING_TEAM_SHARE"
    destination_type = "HIRING_TEAM"
    destination_identifier_ciphertext = factory.LazyFunction(lambda: encrypt("synthetic-team"))
    destination_preview = "Synthetic team"
    requested_fields = ["name"]
    permitted_fields = ["name"]
    consent_record_id = factory.SelfAttribute("application.consent_context_id")
    preview_hash = "a" * 64
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=10))
    idempotency_key = factory.Sequence(lambda n: f"synthetic-disclosure-{n}")


class AccessGrantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AccessGrant

    tenant = factory.SubFactory(TenantFactory)
    grantee = factory.SubFactory(IdentityFactory)
    purpose_code = "RECRUITING_REVIEW"
    field_scope = ["profile_state"]
    object_scope = factory.LazyFunction(lambda: {"ids": [str(uuid.uuid4())]})
    valid_from = factory.LazyFunction(timezone.now)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=1))


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    tenant_id = factory.LazyFunction(uuid.uuid4)
    channel = Notification.Channel.EMAIL
    template_key = "synthetic-template"
    template_version = "v1"
    destination_ciphertext = factory.LazyFunction(lambda: encrypt("synthetic@example.invalid"))
    consent_basis = "SECURITY_REQUIRED"
    idempotency_key = factory.Sequence(lambda n: f"synthetic-notification-{n}")

    class Params:
        queued = factory.Trait(state=Notification.State.QUEUED)
        sending = factory.Trait(state=Notification.State.SENDING, attempts=1)
        sent = factory.Trait(
            state=Notification.State.SENT,
            attempts=1,
            provider_reference="synthetic-provider-reference",
        )
        retrying = factory.Trait(state=Notification.State.QUEUED, attempts=2)
        failed = factory.Trait(
            state=Notification.State.FAILED,
            attempts=5,
            terminal_error_category="SYNTHETIC_FAILURE",
        )
        cancelled = factory.Trait(state=Notification.State.CANCELLED)


class VisibilityPayloadFactory(factory.DictFactory):
    mode = "NOT_LOOKING"
    consent_record_id = factory.LazyFunction(lambda: str(uuid.uuid4()))

    class Params:
        approved_recruiters = factory.Trait(
            mode="APPROVED_RECRUITERS",
            approved_tenant_ids=factory.LazyFunction(lambda: [str(uuid.uuid4())]),
        )
        matching_roles = factory.Trait(
            mode="MATCHING_ROLES",
            matching_preferences={"roles": ["Software Engineer"], "locations": ["Bengaluru"]},
        )
        applied_roles_only = factory.Trait(mode="APPLIED_ROLES_ONLY")
        not_looking = factory.Trait(mode="NOT_LOOKING")


class FailurePayloadFactory(factory.DictFactory):
    category = "SYNTHETIC_FAILURE"
    retryable = True
    detail = "Synthetic failure with no candidate data"


class CandidateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CandidateProfile

    identity = factory.SubFactory(IdentityFactory)
    full_name_ciphertext = factory.LazyFunction(lambda: encrypt("Synthetic Candidate"))
    location = {"city": "Bengaluru", "country": "IN"}
    experience_years = "4.50"


class EmploymentRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmploymentRecord

    profile = factory.SubFactory(CandidateProfileFactory)
    company = factory.Sequence(lambda n: f"Synthetic Employer {n}")
    role_title = "Engineer"
    start_date = factory.LazyFunction(lambda: timezone.now().date() - timedelta(days=730))
    end_date = factory.LazyFunction(lambda: timezone.now().date() - timedelta(days=365))
    start_date_state = EmploymentRecord.ValueState.CONFIRMED
    end_date_state = EmploymentRecord.ValueState.CONFIRMED
    employment_type = EmploymentRecord.EmploymentType.PERMANENT
    employment_type_state = EmploymentRecord.ValueState.CONFIRMED
    provenance = EmploymentRecord.Provenance.CANDIDATE_REPORTED


class ConsentRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConsentRecord

    profile = factory.SubFactory(CandidateProfileFactory)
    purpose = "RECRUITING_DISCOVERY"
    field_scope = ["profile", "employment_history", "skills"]
    audience_scope = {"mode": "NOT_LOOKING"}
    notice_version = "candidate-discovery-v1"
    affirmative_action = "VISIBILITY_SAVE"
    source_request_id = factory.Sequence(lambda n: f"synthetic-consent-{n}")
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=365))


class VisibilityRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VisibilityRule

    profile = factory.SelfAttribute("consent_record.profile")
    consent_record = factory.SubFactory(ConsentRecordFactory)
    mode = VisibilityRule.Mode.NOT_LOOKING
    actor = factory.SelfAttribute("profile.identity")


class ResumeAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ResumeAsset

    profile = factory.SubFactory(CandidateProfileFactory)
    quarantine_key = factory.Sequence(lambda n: f"quarantine/synthetic/{n}")
    original_filename_ciphertext = factory.LazyFunction(lambda: encrypt("synthetic-resume.pdf"))
    declared_mime = "application/pdf"
    detected_mime = "application/pdf"
    size_bytes = 1024
    sha256 = "a" * 64

    class Params:
        clean = factory.Trait(
            scan_status=ResumeAsset.ScanStatus.CLEAN,
            parse_status=ResumeAsset.ParseStatus.READY,
            clean_key=factory.Sequence(lambda n: f"clean/synthetic/{n}"),
        )


# factory-boy exposes declarative factory classes rather than a generic model-return
# signature. Keep that third-party typing boundary in one place so tests receive the
# concrete Django model types that factory-boy creates at runtime.
def make_identity(**kwargs: object) -> Identity:
    return cast(Identity, IdentityFactory(**kwargs))


def make_candidate_profile(**kwargs: object) -> CandidateProfile:
    return cast(CandidateProfile, CandidateProfileFactory(**kwargs))


def make_application(**kwargs: object) -> Application:
    return cast(Application, ApplicationFactory(**kwargs))


def make_employment_record(**kwargs: object) -> EmploymentRecord:
    return cast(EmploymentRecord, EmploymentRecordFactory(**kwargs))
