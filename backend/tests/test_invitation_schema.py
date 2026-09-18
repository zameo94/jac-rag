from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.core import security
from app.core.datetimes import ensure_aware_utc, utcnow
from app.models import Invitation
from app.schemas.invitation import InvitationCreate, InvitationCreated
from app.schemas.membership import MembershipRole


def test_invitation_create_defaults_to_member():
    invitation = InvitationCreate(email="User@Example.com")

    assert str(invitation.email) == "user@example.com"
    assert invitation.role is MembershipRole.MEMBER


def test_invitation_create_normalizes_email():
    invitation = InvitationCreate(email="  Mixed@Case.IT ", role="ADMIN")

    assert str(invitation.email) == "mixed@case.it"
    assert invitation.role is MembershipRole.ADMIN


def test_invitation_create_rejects_owner_role():
    with pytest.raises(ValidationError):
        InvitationCreate(email="user@example.com", role="OWNER")


def test_invitation_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        InvitationCreate(email="not-an-email")


def test_invitation_created_exposes_token():
    invitation = InvitationCreated(
        id=1,
        tenant_id=2,
        email="user@example.com",
        role="MEMBER",
        token="raw-token",
        expires_at=utcnow(),
    )

    assert invitation.token == "raw-token"


def test_generate_invitation_token_is_unique_and_urlsafe():
    first = security.generate_invitation_token()
    second = security.generate_invitation_token()

    assert first != second
    assert len(first) >= 32
    assert set(first) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )


def test_hash_token_is_stable_and_not_reversible():
    token = "raw-token"

    assert security.hash_token(token) == security.hash_token(token)
    assert security.hash_token(token) != token
    assert len(security.hash_token(token)) == 64


def test_hash_token_differs_for_different_tokens():
    assert security.hash_token("a") != security.hash_token("b")


def test_ensure_aware_utc_adds_timezone():
    naive = utcnow().replace(tzinfo=None)

    aware = ensure_aware_utc(naive)

    assert aware.tzinfo is not None


def test_ensure_aware_utc_keeps_aware_value():
    aware = utcnow()

    assert ensure_aware_utc(aware) == aware


def test_utcnow_is_timezone_aware():
    assert utcnow().tzinfo is not None


def test_invitation_model_stores_hash_not_token():
    invitation = Invitation(
        tenant_id=1,
        email="user@example.com",
        role=MembershipRole.MEMBER,
        token_hash=security.hash_token("secret"),
        expires_at=utcnow() + timedelta(days=1),
        created_by=1,
    )

    assert invitation.token_hash == security.hash_token("secret")
    assert not hasattr(invitation, "token")
