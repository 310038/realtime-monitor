"""即時資料批次寫入器。

觸發條件：
  1. 定期：每 BATCH_FLUSH_INTERVAL_SECONDS 秒
  2. 條件：緩衝區筆數 >= BATCH_MAX_SIZE
  3. 條件：出現異常值（FLUSH_ON_ANOMALY=true）
  4. 關機前：將剩餘資料寫入
"""
import asyncio
import logging
from datetime import datetime

from app.core.config import settings
from app.core.timeutil import now
from app.db.session import AsyncSessionLocal
from app.models.realtime import RealtimeData

logger = logging.getLogger("app.batch_writer")

MAX_BUFFER = 10_000  # DB 長時間無法連線時的保護上限


class BatchWriter:
    def __init__(self) -> None:
        self._buffer: list[dict] = []
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.total_flushed = 0
        self.last_flush_at: datetime | None = None
        self.last_flush_reason: str | None = None

    @property
    def size(self) -> int:
        return len(self._buffer)

    async def add(self, points: list[dict]) -> None:
        has_anomaly = any(p["is_anomaly"] for p in points)
        async with self._lock:
            self._buffer.extend(points)
            if len(self._buffer) > MAX_BUFFER:
                dropped = len(self._buffer) - MAX_BUFFER
                del self._buffer[:dropped]
                logger.error("Buffer overflow, dropped %d oldest points", dropped)
            size = len(self._buffer)
        if size >= settings.BATCH_MAX_SIZE:
            await self.flush("size")
        elif has_anomaly and settings.FLUSH_ON_ANOMALY:
            await self.flush("anomaly")

    async def flush(self, reason: str = "manual") -> int:
        async with self._lock:
            if not self._buffer:
                return 0
            batch, self._buffer = self._buffer, []
            try:
                async with AsyncSessionLocal() as session:
                    session.add_all([RealtimeData(**p) for p in batch])
                    await session.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Batch flush failed (%d points), re-queued", len(batch))
                self._buffer = batch + self._buffer
                return 0
            self.total_flushed += len(batch)
            self.last_flush_at = now()
            self.last_flush_reason = reason
        logger.info("Flushed %d realtime points (reason=%s)", len(batch), reason)
        return len(batch)

    async def _periodic(self) -> None:
        while True:
            await asyncio.sleep(settings.BATCH_FLUSH_INTERVAL_SECONDS)
            await self.flush("interval")

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._periodic(), name="batch-writer")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.flush("shutdown")


batch_writer = BatchWriter()
