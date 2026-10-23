from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class RealtimeData(Base):
    """模擬器產生的即時資料，由批次寫入器定期/條件觸發寫入。"""

    __tablename__ = "realtime_data"
    __table_args__ = (Index("ix_realtime_metric_ts", "metric", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)


class MetricThreshold(TimestampMixin, Base):
    """各指標/分類的告警閾值；超過即標記為異常。"""

    __tablename__ = "metric_thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
