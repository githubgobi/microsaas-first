import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.errors.models import ErrorLog, ErrorStatus


class ErrorLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        raw_error: str,
        context: dict | None,
    ) -> ErrorLog:
        error = ErrorLog(
            user_id=user_id,
            title=title,
            raw_error=raw_error,
            context=context,
        )
        self.db.add(error)
        await self.db.flush()
        return error

    async def get_by_id_and_user(
        self, error_id: uuid.UUID, user_id: uuid.UUID
    ) -> ErrorLog | None:
        """Enforces ownership: returns None if not found OR wrong owner."""
        result = await self.db.execute(
            select(ErrorLog).where(
                ErrorLog.id == error_id,
                ErrorLog.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: uuid.UUID, params: PageParams
    ) -> tuple[list[ErrorLog], int]:
        # Separate targeted queries — no subquery wrapping
        count_result = await self.db.execute(
            select(func.count(ErrorLog.id)).where(ErrorLog.user_id == user_id)
        )
        total = count_result.scalar_one()

        items_result = await self.db.execute(
            select(ErrorLog)
            .where(ErrorLog.user_id == user_id)
            .order_by(ErrorLog.created_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = list(items_result.scalars().all())

        return items, total

    async def update_status(
        self, error_id: uuid.UUID, status: ErrorStatus
    ) -> None:
        """Used internally by the analysis module. Raises if the ID is not found
        — a silent no-op would leave the error stuck in 'analyzing' forever.

        Uses UPDATE … RETURNING instead of GET + SET to avoid a redundant SELECT
        round-trip on every status transition.
        """
        result = await self.db.execute(
            update(ErrorLog)
            .where(ErrorLog.id == error_id)
            .values(status=status)
            .returning(ErrorLog.id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError(f"ErrorLog {error_id} not found — cannot update status")

    async def delete_by_id_and_user(
        self, error_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Single-query delete with ownership check. Returns True if a row was deleted."""
        result = await self.db.execute(
            delete(ErrorLog)
            .where(ErrorLog.id == error_id, ErrorLog.user_id == user_id)
            .returning(ErrorLog.id)
        )
        return result.scalar_one_or_none() is not None
