"""告警閾值快取（啟動時由 DB 載入，Admin 更新時同步）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.realtime import MetricThreshold

_cache: dict[str, float] = {}


async def load(session: AsyncSession) -> None:
    rows = (await session.scalars(select(MetricThreshold))).all()
    _cache.clear()
    _cache.update({r.name: r.threshold for r in rows})


def get(name: str) -> float:
    return _cache.get(name, settings.DEFAULT_THRESHOLD)


def set_value(name: str, value: float) -> None:
    _cache[name] = value


def remove(name: str) -> None:
    _cache.pop(name, None)


def is_anomaly(name: str, value: float) -> bool:
    return value > get(name)
