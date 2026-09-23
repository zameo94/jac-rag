import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from app.core import security
from app.core.deps import authenticate_user, load_membership
from app.models import Membership, Workspace, User
from app.schemas.membership import MembershipRole


def make_request() -> Request:
    return Request({"type": "http", "headers": []})


def bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def add_user(
    session_factory, email: str = "deps@example.com", is_active: bool = True
) -> User:
    async with session_factory() as session:
        user = User(email=email, locale="it", password_hash="hash", is_active=is_active)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def add_workspace(session_factory, name: str = "Acme") -> Workspace:
    async with session_factory() as session:
        workspace = Workspace(name=name, slug=name.lower())
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)
        return workspace


async def add_membership(
    session_factory, user_id: int, workspace_id: int, role: MembershipRole = MembershipRole.OWNER
) -> Membership:
    async with session_factory() as session:
        membership = Membership(user_id=user_id, workspace_id=workspace_id, role=role)
        session.add(membership)
        await session.commit()
        await session.refresh(membership)
        return membership


async def test_authenticate_user_valid_token(session_factory):
    user = await add_user(session_factory)
    token = security.create_access_token(user.id)

    async with session_factory() as session:
        result = await authenticate_user(session, make_request(), bearer(token))

    assert result.id == user.id


async def test_authenticate_user_missing_credentials(session_factory):
    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await authenticate_user(session, make_request(), None)

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "NOT_AUTHENTICATED"


async def test_authenticate_user_invalid_token(session_factory):
    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await authenticate_user(session, make_request(), bearer("not-a-jwt"))

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "INVALID_TOKEN"


async def test_authenticate_user_unknown_user(session_factory):
    token = security.create_access_token(987654)

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await authenticate_user(session, make_request(), bearer(token))

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "INVALID_TOKEN"


async def test_authenticate_user_disabled_account(session_factory):
    user = await add_user(session_factory, email="off@example.com", is_active=False)
    token = security.create_access_token(user.id)

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await authenticate_user(session, make_request(), bearer(token))

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "ACCOUNT_DISABLED"


async def test_load_membership_returns_membership(session_factory):
    user = await add_user(session_factory)
    workspace = await add_workspace(session_factory)
    membership = await add_membership(session_factory, user.id, workspace.id)

    async with session_factory() as session:
        result = await load_membership(session, user, workspace.id)

    assert result.id == membership.id
    assert result.role is MembershipRole.OWNER


async def test_load_membership_missing_workspace(session_factory):
    user = await add_user(session_factory)

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await load_membership(session, user, 123456)

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "WORKSPACE_NOT_FOUND"


async def test_load_membership_not_a_member(session_factory):
    user = await add_user(session_factory)
    workspace = await add_workspace(session_factory)

    async with session_factory() as session:
        with pytest.raises(HTTPException) as exc:
            await load_membership(session, user, workspace.id)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "NOT_A_MEMBER"
