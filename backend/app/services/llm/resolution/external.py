from __future__ import annotations

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.setting import SettingScope
from app.services.crypto import decrypt, encrypt
from app.services.llm.resolution.workspace import LLM_SETTING_TYPE
from app.services.settings import get_value, set_value

EXTERNAL_BASE_URL_KEY = "external_base_url"
EXTERNAL_MODEL_KEY = "external_model"
EXTERNAL_API_KEY_KEY = "external_api_key"


@dataclass(frozen=True)
class ExternalConfig:
    base_url: str
    model: str
    api_key: str


async def external_config(
    session: AsyncSession, workspace_id: int
) -> ExternalConfig | None:
    base_url = await get_value(
        session, SettingScope.WORKSPACE, workspace_id, LLM_SETTING_TYPE, EXTERNAL_BASE_URL_KEY
    )
    model = await get_value(
        session, SettingScope.WORKSPACE, workspace_id, LLM_SETTING_TYPE, EXTERNAL_MODEL_KEY
    )
    encrypted = await get_value(
        session, SettingScope.WORKSPACE, workspace_id, LLM_SETTING_TYPE, EXTERNAL_API_KEY_KEY
    )
    if not (
        isinstance(base_url, str)
        and base_url.strip()
        and isinstance(model, str)
        and model.strip()
        and isinstance(encrypted, str)
        and encrypted.strip()
    ):
        return None
    return ExternalConfig(
        base_url=base_url.strip(),
        model=model.strip(),
        api_key=decrypt(encrypted),
    )


async def set_external_config(
    session: AsyncSession,
    workspace_id: int,
    *,
    base_url: str,
    model: str,
    api_key: str,
) -> None:
    await set_value(
        session,
        SettingScope.WORKSPACE,
        workspace_id,
        LLM_SETTING_TYPE,
        EXTERNAL_BASE_URL_KEY,
        base_url.strip(),
    )
    await set_value(
        session,
        SettingScope.WORKSPACE,
        workspace_id,
        LLM_SETTING_TYPE,
        EXTERNAL_MODEL_KEY,
        model.strip(),
    )
    await set_value(
        session,
        SettingScope.WORKSPACE,
        workspace_id,
        LLM_SETTING_TYPE,
        EXTERNAL_API_KEY_KEY,
        encrypt(api_key),
    )
