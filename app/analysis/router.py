import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.schemas import AnalysisResultResponse, AnalysisTriggerResponse
from app.analysis.service import AnalysisService
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_db

router = APIRouter()


@router.post(
    "/{error_id}/analyze",
    response_model=AnalysisTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI analysis on an error log",
)
async def trigger_analysis(
    error_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisTriggerResponse:
    return await AnalysisService(db).trigger(error_id, current_user.id, background_tasks)


@router.get(
    "/{error_id}/analysis",
    response_model=AnalysisResultResponse,
    summary="Get analysis result for an error log",
)
async def get_analysis(
    error_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResultResponse:
    return await AnalysisService(db).get_result(error_id, current_user.id)
