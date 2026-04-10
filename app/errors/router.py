import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.pagination import PageParams, PagedResponse
from app.database import get_db
from app.errors.schemas import ErrorDetail, ErrorSubmitRequest, ErrorSummary
from app.errors.service import ErrorLogService

router = APIRouter()


@router.post(
    "",
    response_model=ErrorDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an error log",
)
async def submit_error(
    data: ErrorSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ErrorDetail:
    return await ErrorLogService(db).submit(current_user.id, data)


@router.get(
    "",
    response_model=PagedResponse[ErrorSummary],
    summary="List your error logs",
)
async def list_errors(
    params: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PagedResponse[ErrorSummary]:
    return await ErrorLogService(db).list(current_user.id, params)


@router.get(
    "/{error_id}",
    response_model=ErrorDetail,
    summary="Get a single error log",
)
async def get_error(
    error_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ErrorDetail:
    return await ErrorLogService(db).get(error_id, current_user.id)


@router.delete(
    "/{error_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an error log",
)
async def delete_error(
    error_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await ErrorLogService(db).delete(error_id, current_user.id)
