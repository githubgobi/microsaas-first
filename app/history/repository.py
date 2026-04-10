import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Analysis
from app.core.pagination import PageParams
from app.errors.models import ErrorLog


class HistoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_user(
        self, user_id: uuid.UUID, params: PageParams
    ) -> tuple[list[tuple[Analysis, str]], int]:
        """Returns (rows, total). Each row is (Analysis, error_title)."""

        # Count — no join needed; user_id is on analyses directly
        count_result = await self.db.execute(
            select(func.count(Analysis.id)).where(Analysis.user_id == user_id)
        )
        total = count_result.scalar_one()

        # Data — join only to fetch error title
        rows_result = await self.db.execute(
            select(Analysis, ErrorLog.title.label("error_title"))
            .join(ErrorLog, ErrorLog.id == Analysis.error_log_id)
            .where(Analysis.user_id == user_id)
            .order_by(Analysis.created_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        rows = [(row.Analysis, row.error_title) for row in rows_result.all()]
        return rows, total

    async def get_by_id_and_user(
        self, analysis_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[Analysis, str] | None:
        """Ownership enforced via user_id. Returns (Analysis, error_title) or None."""
        result = await self.db.execute(
            select(Analysis, ErrorLog.title.label("error_title"))
            .join(ErrorLog, ErrorLog.id == Analysis.error_log_id)
            .where(
                Analysis.id == analysis_id,
                Analysis.user_id == user_id,
            )
        )
        row = result.first()
        if row is None:
            return None
        return row.Analysis, row.error_title

    async def delete_by_id_and_user(
        self, analysis_id: uuid.UUID, user_id: uuid.UUID
    ) -> uuid.UUID | None:
        """Single-query delete with ownership check.
        Returns the deleted error_log_id (to reset its status), or None if not found."""
        result = await self.db.execute(
            delete(Analysis)
            .where(Analysis.id == analysis_id, Analysis.user_id == user_id)
            .returning(Analysis.error_log_id)
        )
        return result.scalar_one_or_none()
