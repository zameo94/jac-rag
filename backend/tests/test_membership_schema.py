import pytest
from pydantic import ValidationError

from app.schemas.membership import MemberRead, MemberUpdate, MembershipRole


def test_member_update_accepts_admin_role():
    update = MemberUpdate(role="ADMIN")

    assert update.role is MembershipRole.ADMIN


def test_member_update_rejects_owner_role():
    with pytest.raises(ValidationError):
        MemberUpdate(role="OWNER")


def test_member_update_rejects_unknown_role():
    with pytest.raises(ValidationError):
        MemberUpdate(role="SUPERADMIN")


def test_member_read_accepts_payload():
    member = MemberRead(
        id=1,
        user_id=2,
        tenant_id=3,
        role="MEMBER",
        email="User@Example.com",
        created_at="2026-01-01T00:00:00Z",
    )

    assert member.role is MembershipRole.MEMBER
    assert str(member.email) == "User@example.com"
