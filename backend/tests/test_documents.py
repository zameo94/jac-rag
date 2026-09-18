from app.core.config import get_settings
from tests.helpers import register_and_login, user_id_for

TENANTS_URL = "/api/v1/tenants"


async def create_tenant(client, headers, name="Acme", slug="acme"):
    response = await client.post(
        TENANTS_URL, json={"name": name, "slug": slug}, headers=headers
    )
    return response.json()


async def upload(client, headers, tenant_id, filename="notes.txt", content=b"hello world"):
    return await client.post(
        f"{TENANTS_URL}/{tenant_id}/documents",
        files={"file": (filename, content, "text/plain")},
        headers=headers,
    )


async def test_upload_txt_document(client, stub_ingestion):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await upload(client, owner, tenant["id"])

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["mime"] == "text/plain"
    assert body["size"] == len(b"hello world")
    assert body["status"] == "pending"
    assert body["tenant_id"] == tenant["id"]
    assert stub_ingestion == [body["id"]]


async def test_upload_derives_mime_from_extension(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.post(
        f"{TENANTS_URL}/{tenant['id']}/documents",
        files={"file": ("notes.md", b"# title", "application/octet-stream")},
        headers=owner,
    )

    assert response.status_code == 201
    assert response.json()["mime"] == "text/markdown"


async def test_upload_rejects_unsupported_type(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.post(
        f"{TENANTS_URL}/{tenant['id']}/documents",
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
        headers=owner,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"


async def test_upload_rejects_empty_file(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await upload(client, owner, tenant["id"], content=b"")

    assert response.status_code == 422
    assert response.json()["code"] == "EMPTY_FILE"


async def test_upload_rejects_file_too_large(client, monkeypatch):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()

    response = await upload(client, owner, tenant["id"], content=b"x" * 10)

    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


async def test_upload_requires_admin_role(client, session_factory):
    from sqlmodel import select

    from app.models import Membership
    from app.schemas.membership import MembershipRole

    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    member = await register_and_login(client, "member@example.com")
    member_id = await user_id_for(client, member)
    async with session_factory() as session:
        session.add(
            Membership(user_id=member_id, tenant_id=tenant["id"], role=MembershipRole.MEMBER)
        )
        await session.commit()

    response = await upload(client, member, tenant["id"])

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_upload_requires_membership(client):
    owner = await register_and_login(client, "owner@example.com")
    outsider = await register_and_login(client, "outsider@example.com")
    tenant = await create_tenant(client, owner)

    response = await upload(client, outsider, tenant["id"])

    assert response.status_code == 403
    assert response.json()["code"] == "NOT_A_MEMBER"


async def test_upload_requires_authentication(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    client.cookies.clear()

    response = await client.post(
        f"{TENANTS_URL}/{tenant['id']}/documents",
        files={"file": ("notes.txt", b"data", "text/plain")},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_list_documents_is_tenant_scoped(client):
    owner_a = await register_and_login(client, "owner-a@example.com")
    tenant_a = await create_tenant(client, owner_a, name="Alpha", slug="alpha")
    owner_b = await register_and_login(client, "owner-b@example.com")
    tenant_b = await create_tenant(client, owner_b, name="Beta", slug="beta")

    await upload(client, owner_a, tenant_a["id"], filename="a.txt")
    await upload(client, owner_b, tenant_b["id"], filename="b.txt")

    list_a = await client.get(f"{TENANTS_URL}/{tenant_a['id']}/documents", headers=owner_a)
    list_b = await client.get(f"{TENANTS_URL}/{tenant_b['id']}/documents", headers=owner_b)

    assert [doc["filename"] for doc in list_a.json()] == ["a.txt"]
    assert [doc["filename"] for doc in list_b.json()] == ["b.txt"]


async def test_get_document_status(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    document = (await upload(client, owner, tenant["id"])).json()

    response = await client.get(
        f"{TENANTS_URL}/{tenant['id']}/documents/{document['id']}", headers=owner
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_get_document_from_other_tenant_returns_404(client):
    owner_a = await register_and_login(client, "owner-a@example.com")
    tenant_a = await create_tenant(client, owner_a, name="Alpha", slug="alpha")
    owner_b = await register_and_login(client, "owner-b@example.com")
    tenant_b = await create_tenant(client, owner_b, name="Beta", slug="beta")
    document = (await upload(client, owner_a, tenant_a["id"])).json()

    response = await client.get(
        f"{TENANTS_URL}/{tenant_b['id']}/documents/{document['id']}", headers=owner_b
    )

    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_NOT_FOUND"


async def test_delete_document(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    document = (await upload(client, owner, tenant["id"])).json()

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/documents/{document['id']}", headers=owner
    )

    assert response.status_code == 204
    listing = await client.get(f"{TENANTS_URL}/{tenant['id']}/documents", headers=owner)
    assert listing.json() == []


async def test_delete_document_requires_admin_role(client, session_factory):
    from app.models import Membership
    from app.schemas.membership import MembershipRole

    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)
    document = (await upload(client, owner, tenant["id"])).json()
    member = await register_and_login(client, "member@example.com")
    member_id = await user_id_for(client, member)
    async with session_factory() as session:
        session.add(
            Membership(user_id=member_id, tenant_id=tenant["id"], role=MembershipRole.MEMBER)
        )
        await session.commit()

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/documents/{document['id']}", headers=member
    )

    assert response.status_code == 403
    assert response.json()["code"] == "INSUFFICIENT_ROLE"


async def test_delete_unknown_document_returns_404(client):
    owner = await register_and_login(client, "owner@example.com")
    tenant = await create_tenant(client, owner)

    response = await client.delete(
        f"{TENANTS_URL}/{tenant['id']}/documents/999999", headers=owner
    )

    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_NOT_FOUND"
