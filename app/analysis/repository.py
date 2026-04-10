import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Analysis


class AnalysisRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        error_log_id: uuid.UUID,
        user_id: uuid.UUID,
        summary: str,
        root_cause: str,
        suggestions: list,
        ai_model: str,
        tokens_used: int | None,
        duration_ms: int | None,
    ) -> Analysis:
        analysis = Analysis(
            error_log_id=error_log_id,
            user_id=user_id,
            summary=summary,
            root_cause=root_cause,
            suggestions=suggestions,
            ai_model=ai_model,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )
        self.db.add(analysis)
        await self.db.flush()
        return analysis

    async def get_by_error_id(self, error_log_id: uuid.UUID) -> Analysis | None:
        result = await self.db.execute(
            select(Analysis).where(Analysis.error_log_id == error_log_id)
        )
        return result.scalar_one_or_none()

    async def count_today_by_user(self, user_id: uuid.UUID) -> int:
        """Count analyses triggered by this user in the last 24 hours."""
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await self.db.execute(
            select(func.count(Analysis.id)).where(
                Analysis.user_id == user_id,
                Analysis.created_at >= since,
            )
        )
        return result.scalar_one()
