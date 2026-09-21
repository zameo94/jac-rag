from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.setting import SettingScope
from app.services.llm.base import LLMProviderError
from app.services.llm.resolution.capability import default_provider_id
from app.services.llm.resolution.tenant import LLM_SETTING_TYPE
from app.services.settings import get_value

GLOBAL_DEFAULT_PROVIDER_KEY = "default_provider"


async def global_default_provider(session: AsyncSession) -> str | None:
    """Global default provider: the ``global`` setting, else the env default."""
    value = await get_value(
        session,
        SettingScope.GLOBAL,
        None,
        LLM_SETTING_TYPE,
        GLOBAL_DEFAULT_PROVIDER_KEY,
    )
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    try:
        return default_provider_id()
    except LLMProviderError:
        return None
