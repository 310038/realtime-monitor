"""資料記錄共用篩選條件（列表、統計、匯出共用）。"""
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from sqlalchemy import Select

from app.core.timeutil import to_naive_local
from app.models.record import DataRecord


@dataclass
class RecordFilters:
    start: datetime | None = None
    end: datetime | None = None
    categories: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None
    keyword: str | None = None
    owner_id: int | None = None
    is_anomaly: bool | None = None

    def apply(self, stmt: Select) -> Select:
        if self.start:
            stmt = stmt.where(DataRecord.timestamp >= to_naive_local(self.start))
        if self.end:
            stmt = stmt.where(DataRecord.timestamp <= to_naive_local(self.end))
        if self.categories:
            stmt = stmt.where(DataRecord.category.in_(self.categories))
        if self.min_value is not None:
            stmt = stmt.where(DataRecord.value >= self.min_value)
        if self.max_value is not None:
            stmt = stmt.where(DataRecord.value <= self.max_value)
        if self.keyword:
            stmt = stmt.where(DataRecord.title.ilike(f"%{self.keyword}%"))
        if self.owner_id is not None:
            stmt = stmt.where(DataRecord.owner_id == self.owner_id)
        if self.is_anomaly is not None:
            stmt = stmt.where(DataRecord.is_anomaly == self.is_anomaly)
        return stmt


def record_filters(
    start: datetime | None = Query(None, description="起始時間（含），ISO 8601"),
    end: datetime | None = Query(None, description="結束時間（含），ISO 8601"),
    category: list[str] | None = Query(None, description="分類，可多選：?category=a&category=b"),
    min_value: float | None = Query(None),
    max_value: float | None = Query(None),
    keyword: str | None = Query(None, max_length=100, description="標題關鍵字"),
    owner_id: int | None = Query(None),
    is_anomaly: bool | None = Query(None),
) -> RecordFilters:
    return RecordFilters(start, end, category, min_value, max_value, keyword, owner_id, is_anomaly)
