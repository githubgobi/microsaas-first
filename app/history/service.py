import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, PagedResponse
from app.errors.models import ErrorStatus
from app.errors.repository import ErrorLogRepository
from app.history.repository import HistoryRepository
from app.history.schemas import HistoryDetail, HistorySummary


class HistoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = HistoryRepository(db)

    async def list(
        self, user_id: uuid.UUID, params: PageParams
    ) -> PagedResponse[HistorySummary]:
        rows, total = await self.repo.list_by_user(user_id, params)
        return PagedResponse.create(
            items=[HistorySummary.from_row(analysis, title) for analysis, title in rows],
            total=total,
            params=params,
        )

    async def get(self, analysis_id: uuid.UUID, user_id: uuid.UUID) -> HistoryDetail:
        row = await self.repo.get_by_id_and_user(analysis_id, user_id)
        if row is None:
            raise NotFoundError("Analysis not found")
        analysis, error_title = row
        return HistoryDetail.from_row(analysis, error_title)

    async def delete(self, analysis_id: uuid.UUID, user_id: uuid.UUID) -> None:
        error_log_id = await self.repo.delete_by_id_and_user(analysis_id, user_id)
        if error_log_id is None:
            raise NotFoundError("Analysis not found")

        # Reset the parent error to PENDING so it can be re-analyzed.
        # Leaving it as COMPLETED without an analysis record is inconsistent.
        await ErrorLogRepository(self.db).update_status(error_log_id, ErrorStatus.PENDING)
        await self.db.commit()
