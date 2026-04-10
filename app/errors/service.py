import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageParams, PagedResponse
from app.errors.repository import ErrorLogRepository
from app.errors.schemas import ErrorDetail, ErrorSubmitRequest, ErrorSummary


class ErrorLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ErrorLogRepository(db)

    async def submit(
        self, user_id: uuid.UUID, data: ErrorSubmitRequest
    ) -> ErrorDetail:
        error = await self.repo.create(
            user_id=user_id,
            title=data.title,
            raw_error=data.raw_error,
            context=data.context,
        )
        await self.db.commit()
        return ErrorDetail.model_validate(error)

    async def get(self, error_id: uuid.UUID, user_id: uuid.UUID) -> ErrorDetail:
        error = await self.repo.get_by_id_and_user(error_id, user_id)
        if not error:
            raise NotFoundError("Error log not found")
        return ErrorDetail.model_validate(error)

    async def list(
        self, user_id: uuid.UUID, params: PageParams
    ) -> PagedResponse[ErrorSummary]:
        items, total = await self.repo.list_by_user(user_id, params)
        return PagedResponse.create(
            items=[ErrorSummary.model_validate(e) for e in items],
            total=total,
            params=params,
        )

    async def delete(self, error_id: uuid.UUID, user_id: uuid.UUID) -> None:
        deleted = await self.repo.delete_by_id_and_user(error_id, user_id)
        if not deleted:
            raise NotFoundError("Error log not found")
        await self.db.commit()
