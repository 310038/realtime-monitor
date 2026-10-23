from datetime import datetime

from pydantic import BaseModel


class SummaryStats(BaseModel):
    count: int
    total: float | None
    average: float | None
    maximum: float | None
    minimum: float | None
    anomalies: int
    start: datetime | None = None
    end: datetime | None = None


class CategoryStats(BaseModel):
    category: str
    count: int
    total: float | None
    average: float | None
    maximum: float | None
    minimum: float | None
    anomalies: int


class TrendPoint(BaseModel):
    bucket: str
    category: str | None = None
    count: int
    average: float | None
    maximum: float | None
    minimum: float | None
