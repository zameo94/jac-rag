from __future__ import annotations

from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.setting import Setting
from app.schemas.setting import SettingScope


async def get_setting(
    session: AsyncSession,
    scope_type: SettingScope,
    scope_id: int,
    type: str,
    key: str,
) -> Setting | None:
    statement = select(Setting).where(
        Setting.scope_type == scope_type,
        Setting.scope_id == scope_id,
        Setting.type == type,
        Setting.key == key,
    )
    return (await session.exec(statement)).first()


async def get_value(
    session: AsyncSession,
    scope_type: SettingScope,
    scope_id: int,
    type: str,
    key: str,
    default: Any = None,
) -> Any:
    row = await get_setting(session, scope_type, scope_id, type, key)
    if row is None:
        return default
    return row.value


async def set_value(
    session: AsyncSession,
    scope_type: SettingScope,
    scope_id: int,
    type: str,
    key: str,
    value: Any,
) -> Setting:
    row = await get_setting(session, scope_type, scope_id, type, key)
    if row is None:
        row = Setting(
            scope_type=scope_type,
            scope_id=scope_id,
            type=type,
            key=key,
            value=value,
        )
    else:
        row.value = value
    session.add(row)
    await session.flush()
    return row
