"""模擬即時資料產生器：每秒為每個指標產生一筆隨機資料並透過 WebSocket 推送。"""
import asyncio
import logging
import random
from collections import deque

from app.core.config import settings
from app.core.timeutil import now
from app.services import thresholds
from app.services.audit import log_in_background
from app.services.batch_writer import batch_writer
from app.services.ws_manager import manager

logger = logging.getLogger("app.generator")

# 各指標的基準值與擾動幅度
PROFILES: dict[str, tuple[float, float]] = {
    "temperature": (26.0, 1.2),
    "humidity": (62.0, 2.5),
    "cpu_usage": (45.0, 6.0),
    "pressure": (1013.0, 2.0),
}
SPIKE_PROBABILITY = 0.03


class DataGenerator:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._state: dict[str, float] = {}
        self.recent: deque[dict] = deque(maxlen=60 * 10 * 4)  # 約 10 分鐘
        self.total_generated = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def _next_value(self, metric: str) -> float:
        base, jitter = PROFILES.get(metric, (50.0, 5.0))
        current = self._state.get(metric, base)
        # 均值回歸的隨機漫步
        current += (base - current) * 0.1 + random.gauss(0, jitter)
        self._state[metric] = current
        value = current
        if random.random() < SPIKE_PROBABILITY:
            value = thresholds.get(metric) + abs(random.gauss(jitter * 3, jitter * 2))
        if metric in ("humidity", "cpu_usage"):
            value = min(max(value, 0.0), 100.0)
        return round(value, 2)

    def generate_tick(self) -> list[dict]:
        ts = now()
        points = []
        for metric in settings.REALTIME_METRICS:
            value = self._next_value(metric)
            threshold = thresholds.get(metric)
            points.append(
                {
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "is_anomaly": value > threshold,
                    "timestamp": ts,
                }
            )
        return points

    async def _run(self) -> None:
        logger.info("Realtime generator started (metrics=%s)", settings.REALTIME_METRICS)
        while True:
            try:
                points = self.generate_tick()
                self.total_generated += len(points)
                self.recent.extend(points)
                alerts = [p for p in points if p["is_anomaly"]]
                await manager.broadcast(
                    {
                        "type": "tick",
                        "points": [_jsonable(p) for p in points],
                        "alerts": [_jsonable(p) for p in alerts],
                    }
                )
                for a in alerts:
                    log_in_background(
                        f"Anomaly: {a['metric']}={a['value']} > threshold {a['threshold']}",
                        level="WARNING",
                        category="alert",
                    )
                await batch_writer.add(points)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Generator tick failed")
            await asyncio.sleep(settings.GENERATOR_INTERVAL_SECONDS)

    def start(self) -> bool:
        if self.running:
            return False
        self._task = asyncio.create_task(self._run(), name="realtime-generator")
        return True

    async def stop(self) -> bool:
        if not self.running:
            return False
        assert self._task is not None
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Realtime generator stopped")
        return True

    def snapshot(self, limit: int = 300) -> list[dict]:
        items = list(self.recent)[-limit:]
        return [_jsonable(p) for p in items]


def _jsonable(p: dict) -> dict:
    return {**p, "timestamp": p["timestamp"].isoformat()}


generator = DataGenerator()
