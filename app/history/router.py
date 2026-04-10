import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.pagination import PageParams, PagedResponse
from app.database import get_db
from app.history.schemas import HistoryDetail, HistorySummary
from app.history.service import HistoryService

router = APIRouter()


@router.get(
    "",
    response_model=PagedResponse[HistorySummary],
    summary="List your analysis history",
)
async def list_history(
    params: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[HistorySummary]:
    return await HistoryService(db).list(current_user.id, params)


@router.get(
    "/{analysis_id}",
    response_model=HistoryDetail,
    summary="Get a single analysis result",
)
async def get_history_item(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HistoryDetail:
    return await HistoryService(db).get(analysis_id, current_user.id)


@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an analysis and reset the error for re-analysis",
)
async def delete_history_item(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await HistoryService(db).delete(analysis_id, current_user.id)
