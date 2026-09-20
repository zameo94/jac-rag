import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Setting
from app.schemas.setting import SettingBase, SettingScope
from app.services.settings import get_setting, get_value


def test_scope_has_only_tenant_and_user():
    assert {scope.value for scope in SettingScope} == {"tenant", "user"}
    assert not hasattr(SettingScope, "SYSTEM")


def test_setting_rejects_invalid_scope():
    with pytest.raises(ValueError):
        SettingBase(scope_type="system", scope_id=1, type="llm", key="k", value=1)


def test_setting_rejects_non_positive_scope_id():
    with pytest.raises(ValueError):
        SettingBase(scope_type="tenant", scope_id=0, type="llm", key="k", value=1)


def test_setting_rejects_blank_type_and_key():
    with pytest.raises(ValueError):
        SettingBase(scope_type="tenant", scope_id=1, type="  ", key="k", value=1)
    with pytest.raises(ValueError):
        SettingBase(scope_type="tenant", scope_id=1, type="llm", key="  ", value=1)


def test_setting_normalizes_type_and_key():
    setting = SettingBase(
        scope_type="tenant",
        scope_id=1,
        type=" LLM ",
        key=" Allowed_Providers ",
        value=1,
    )

    assert setting.type == "llm"
    assert setting.key == "allowed_providers"


async def test_get_setting_and_value(session_factory):
    async with session_factory() as session:
        session.add(
            Setting(
                scope_type=SettingScope.TENANT,
                scope_id=1,
                type="llm",
                key="allowed_providers",
                value=["ollama"],
            )
        )
        await session.commit()

    async with session_factory() as session:
        row = await get_setting(
            session, SettingScope.TENANT, 1, "llm", "allowed_providers"
        )

    assert row is not None
    assert row.value == ["ollama"]


async def test_get_value_default_when_missing(session_factory):
    async with session_factory() as session:
        assert (
            await get_value(
                session, SettingScope.TENANT, 999, "llm", "missing", default="fallback"
            )
            == "fallback"
        )
        assert await get_value(session, SettingScope.TENANT, 999, "llm", "missing") is None


async def test_setting_value_json_roundtrip(session_factory):
    async with session_factory() as session:
        session.add_all(
            [
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=1,
                    type="llm",
                    key="providers",
                    value=["ollama", "external_api"],
                ),
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=1,
                    type="llm",
                    key="provider",
                    value="ollama",
                ),
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=1,
                    type="rag",
                    key="params",
                    value={"threshold": 0.5},
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        assert await get_value(session, SettingScope.TENANT, 1, "llm", "providers") == [
            "ollama",
            "external_api",
        ]
        assert (
            await get_value(session, SettingScope.TENANT, 1, "llm", "provider")
            == "ollama"
        )
        assert await get_value(session, SettingScope.TENANT, 1, "rag", "params") == {
            "threshold": 0.5
        }


async def test_setting_is_unique_per_scope_and_key(session_factory):
    async with session_factory() as session:
        session.add(
            Setting(
                scope_type=SettingScope.TENANT,
                scope_id=1,
                type="llm",
                key="allowed_providers",
                value=["ollama"],
            )
        )
        await session.commit()

    with pytest.raises(IntegrityError):
        async with session_factory() as session:
            session.add(
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=1,
                    type="llm",
                    key="allowed_providers",
                    value=["external_api"],
                )
            )
            await session.commit()


async def test_setting_distinct_scope_or_key_allowed(session_factory):
    async with session_factory() as session:
        session.add_all(
            [
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=1,
                    type="llm",
                    key="allowed_providers",
                    value=["ollama"],
                ),
                Setting(
                    scope_type=SettingScope.USER,
                    scope_id=1,
                    type="llm",
                    key="allowed_providers",
                    value=["ollama"],
                ),
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=2,
                    type="llm",
                    key="allowed_providers",
                    value=["ollama"],
                ),
                Setting(
                    scope_type=SettingScope.TENANT,
                    scope_id=1,
                    type="llm",
                    key="model",
                    value="llama3.1",
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        row = await get_setting(session, SettingScope.TENANT, 1, "llm", "model")

    assert row is not None
    assert row.value == "llama3.1"
