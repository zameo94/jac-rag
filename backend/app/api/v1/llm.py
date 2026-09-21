from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.chat import provider_error
from app.core.deps import get_current_membership, get_current_user, require_role
from app.core.errors import api_error
from app.database import get_session
from app.models import Membership, User
from app.schemas.llm import (
    LLMConfigRead,
    LLMSettingsRead,
    LLMSettingsUpdate,
    ProviderInfo,
    ProviderSelection,
)
from app.schemas.membership import MembershipRole
from app.schemas.setting import SettingScope
from app.services.llm.base import LLMProviderError
from app.services.llm.resolution.capability import KNOWN_PROVIDER_IDS, provider_capabilities
from app.services.llm.resolution.external import external_config, set_external_config
from app.services.llm.providers.openai import EXTERNAL_API_PROVIDER_NAME
from app.services.llm.resolution.tenant import (
    ALLOWED_PROVIDERS_KEY,
    DEFAULT_PROVIDER_KEY,
    LLM_SETTING_TYPE,
    MODEL_KEY,
    available_providers_for_tenant,
    tenant_allowed_provider_ids,
    tenant_default_provider,
    tenant_model_override,
)
from app.services.llm.resolution.user import set_user_provider, user_selected_provider
from app.services.settings import set_value

router = APIRouter()

ADMIN = require_role(MembershipRole.OWNER, MembershipRole.ADMIN)


@router.get("/{tenant_id}/llm/config", response_model=LLMConfigRead)
async def get_llm_config(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> LLMConfigRead:
    from app.core.config import get_settings

    external_cfg = await external_config(session, tenant_id)
    providers = []
    for capability in provider_capabilities():
        models = list(capability.models)
        if capability.id == EXTERNAL_API_PROVIDER_NAME and external_cfg is not None:
            models = [external_cfg.model]
        providers.append(
            ProviderInfo(id=capability.id, enabled=capability.enabled, models=models)
        )

    return LLMConfigRead(
        providers=providers,
        allowed_providers=list(await tenant_allowed_provider_ids(session, tenant_id)),
        selected_provider=await user_selected_provider(session, current_user.id),
        default_provider=get_settings().llm_default_provider,
    )


@router.put("/{tenant_id}/llm/provider")
async def select_llm_provider(
    tenant_id: int,
    payload: ProviderSelection,
    current_user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        selected = await set_user_provider(
            session, tenant_id, current_user.id, payload.provider_id
        )
    except LLMProviderError as exc:
        raise provider_error(exc)
    await session.commit()
    return {"selected_provider": selected}


@router.get("/{tenant_id}/llm/settings", response_model=LLMSettingsRead)
async def get_llm_settings(
    tenant_id: int,
    membership: Membership = Depends(ADMIN),
    session: AsyncSession = Depends(get_session),
) -> LLMSettingsRead:
    config = await external_config(session, tenant_id)
    return LLMSettingsRead(
        allowed_providers=list(await tenant_allowed_provider_ids(session, tenant_id)),
        default_provider=await tenant_default_provider(session, tenant_id),
        model=await tenant_model_override(session, tenant_id),
        external_configured=config is not None,
        external_base_url=config.base_url if config else None,
        external_model=config.model if config else None,
    )


@router.put("/{tenant_id}/llm/settings", response_model=LLMSettingsRead)
async def update_llm_settings(
    tenant_id: int,
    payload: LLMSettingsUpdate,
    membership: Membership = Depends(ADMIN),
    session: AsyncSession = Depends(get_session),
) -> LLMSettingsRead:
    if payload.allowed_providers is not None:
        unknown = [p for p in payload.allowed_providers if p not in KNOWN_PROVIDER_IDS]
        if unknown:
            raise api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "UNKNOWN_PROVIDER",
                f"Unknown provider(s): {', '.join(unknown)}",
            )
        await set_value(
            session,
            SettingScope.TENANT,
            tenant_id,
            LLM_SETTING_TYPE,
            ALLOWED_PROVIDERS_KEY,
            payload.allowed_providers,
        )
    if payload.default_provider is not None:
        if payload.default_provider not in KNOWN_PROVIDER_IDS:
            raise api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "UNKNOWN_PROVIDER",
                f"Unknown provider: {payload.default_provider}",
            )
        await set_value(
            session,
            SettingScope.TENANT,
            tenant_id,
            LLM_SETTING_TYPE,
            DEFAULT_PROVIDER_KEY,
            payload.default_provider,
        )
    if payload.model is not None:
        await set_value(
            session,
            SettingScope.TENANT,
            tenant_id,
            LLM_SETTING_TYPE,
            MODEL_KEY,
            payload.model,
        )
    if any(
        (
            payload.external_base_url,
            payload.external_model,
            payload.external_api_key,
        )
    ):
        current = await external_config(session, tenant_id)
        base_url = (payload.external_base_url or "").strip() or (
            current.base_url if current else None
        )
        model = (payload.external_model or "").strip() or (
            current.model if current else None
        )
        api_key = (payload.external_api_key or "").strip() or (
            current.api_key if current else None
        )
        if not (base_url and model and api_key):
            raise api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "INCOMPLETE_EXTERNAL_CONFIG",
                "external_base_url, external_model and external_api_key are all required",
            )
        await set_external_config(
            session,
            tenant_id,
            base_url=base_url,
            model=model,
            api_key=api_key,
        )
    await session.commit()
    return await get_llm_settings(tenant_id, membership, session)
