"""寫入 system_logs（以獨立 Session，失敗不影響主流程）。"""
import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.models.log import SystemLog

logger = logging.getLogger("app.audit")
_pending: set[asyncio.Task] = set()


async def write_log(message: str, *, level: str = "INFO", category: str = "event", **fields) -> None:
    try:
        async with AsyncSessionLocal() as session:
            session.add(SystemLog(message=message[:5000], level=level, category=category, **fields))
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to persist system log: %s", message, exc_info=True)


def log_in_background(message: str, **kwargs) -> None:
    """不阻塞請求的日誌寫入。"""
    task = asyncio.create_task(write_log(message, **kwargs))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
