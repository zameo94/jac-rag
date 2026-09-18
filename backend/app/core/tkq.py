from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import ListQueueBroker, ListRedisScheduleSource

from app.core.config import get_settings

settings = get_settings()

broker = ListQueueBroker(settings.redis_url, socket_timeout=None)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[
        ListRedisScheduleSource(settings.redis_url),
        LabelScheduleSource(broker),
    ],
)

from app.tasks import ingest  # noqa: E402,F401
