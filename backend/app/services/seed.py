"""啟動時建立預設帳號、閾值與範例資料（僅在不存在時）。"""
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models import DataRecord, MetricThreshold, User, UserRole
from app.services import thresholds
from app.services.importer import parse_csv

logger = logging.getLogger("app.seed")


async def seed(session: AsyncSession) -> None:
    if settings.SEED_DEFAULT_USERS:
        defaults = [
            (settings.ADMIN_USERNAME, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD, UserRole.ADMIN, "System Admin"),
            ("user", "user@example.com", settings.DEMO_USER_PASSWORD, UserRole.USER, "Demo User"),
            ("viewer", "viewer@example.com", settings.DEMO_VIEWER_PASSWORD, UserRole.VIEWER, "Demo Viewer"),
        ]
        for username, email, pwd, role, name in defaults:
            exists = await session.scalar(select(User.id).where(User.username == username))
            if not exists:
                session.add(
                    User(username=username, email=email, full_name=name, hashed_password=hash_password(pwd), role=role)
                )
                logger.info("Seeded user %s (%s)", username, role.value)
        await session.commit()

    existing = set((await session.scalars(select(MetricThreshold.name))).all())
    for name, value in settings.THRESHOLDS.items():
        if name not in existing:
            session.add(MetricThreshold(name=name, threshold=value))
    await session.commit()
    await thresholds.load(session)

    if settings.SEED_SAMPLE_DATA:
        count = await session.scalar(select(func.count(DataRecord.id)))
        path = Path(settings.SAMPLE_DATA_PATH)
        if not count and path.exists():
            owner_id = await session.scalar(select(User.id).where(User.username == "user"))
            rows, _ = parse_csv(path.read_bytes())
            session.add_all(
                [
                    DataRecord(**r.model_dump(), owner_id=owner_id, is_anomaly=thresholds.is_anomaly(r.category, r.value))
                    for r in rows
                ]
            )
            await session.commit()
            logger.info("Seeded %d sample records from %s", len(rows), path)
