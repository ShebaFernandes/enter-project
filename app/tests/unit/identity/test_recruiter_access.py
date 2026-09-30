import pytest
from django.core.exceptions import PermissionDenied

from modules.identity.recruiter_access import validate_work_email
from modules.identity.services import link_identity_with_role


def test_work_email_normalizes_and_personal_or_invalid_email_is_denied():
    assert validate_work_email(" Recruiter@Synthetic.Example ") == "recruiter@synthetic.example"
    for value in ("", "invalid", "person@gmail.com", "person@outlook.com"):
        with pytest.raises(PermissionDenied, match="verified work identity"):
            validate_work_email(value)


@pytest.mark.django_db
def test_workforce_link_requires_verified_mfa_work_email():
    base = {"sub": "workforce-1", "email_verified": True, "amr": ["mfa"]}
    with pytest.raises(PermissionDenied):
        link_identity_with_role({**base, "email": "person@gmail.com"}, workforce=True)
    with pytest.raises(PermissionDenied):
        link_identity_with_role(
            {**base, "email": "recruiter@synthetic.example", "email_verified": False},
            workforce=True,
        )
    identity = link_identity_with_role(
        {**base, "email": "recruiter@synthetic.example"}, workforce=True
    )
    assert identity.email_verified_at is not None
