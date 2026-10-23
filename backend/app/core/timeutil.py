"""時間工具：資料庫一律存放「容器時區（TZ）的 naive datetime」。"""
from datetime import datetime


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def to_naive_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt
