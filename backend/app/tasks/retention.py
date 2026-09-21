import logging
from datetime import timedelta

from sqlalchemy import delete
from sqlmodel import select

from app.core.config import get_settings
from app.core.datetimes import utcnow
from app.core.tkq import broker
from app.database import async_session_factory
from app.models import Conversation, Message

logger = logging.getLogger(__name__)

RETENTION_CRON = "0 3 * * *"


async def purge_old_conversations(
    session_factory, retention_days: int | None = None
) -> int:
    """Delete conversations (and their messages) older than the retention window."""
    settings = get_settings()
    days = settings.chat_retention_days if retention_days is None else retention_days
    if days <= 0:
        return 0

    cutoff = utcnow() - timedelta(days=days)
    async with session_factory() as session:
        ids = list(
            (
                await session.exec(
                    select(Conversation.id).where(Conversation.updated_at < cutoff)
                )
            ).all()
        )
        if not ids:
            return 0

        await session.exec(delete(Message).where(Message.conversation_id.in_(ids)))
        await session.exec(delete(Conversation).where(Conversation.id.in_(ids)))
        await session.commit()

    return len(ids)


@broker.task(schedule=[{"cron": RETENTION_CRON, "args": []}])
async def purge_conversations() -> int:
    purged = await purge_old_conversations(async_session_factory)
    logger.info("retention purge removed %s conversations", purged)
    return purged
