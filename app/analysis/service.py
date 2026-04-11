"""
Analysis service and background task.

Request lifecycle:
  1. trigger()      — validates AI client + rate limit + state, commits ANALYZING,
                      schedules background task, returns 202
  2. _run_analysis() — runs after response is sent; calls AI, persists result, updates status

Session ownership:
  - trigger() / get_result() use the request-scoped session (passed via __init__)
  - _run_analysis() opens its OWN session from AsyncSessionFactory
    (the request session is closed before the background task runs)
"""

import asyncio
import uuid

import structlog
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.ai_client import AnthropicClient, get_ai_client
from app.analysis.models import Analysis
from app.analysis.repository import AnalysisRepository
from app.analysis.schemas import AnalysisData, AnalysisResultResponse, AnalysisTriggerResponse
from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.database import AsyncSessionFactory
from app.errors.models import ErrorLog, ErrorStatus
from app.errors.repository import ErrorLogRepository

logger = structlog.get_logger()

# PostgreSQL error code for unique constraint violation
_PG_UNIQUE_VIOLATION = "23505"


# ---------------------------------------------------------------------------
# Background task — module-level so it owns its own DB session
# ---------------------------------------------------------------------------

async def _run_analysis(
    error_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    raw_error: str,
    context: dict | None,
    ai_client: AnthropicClient,
) -> None:
    """Runs after the HTTP 202 response is sent. Opens its own DB session."""
    try:
        result = await ai_client.analyze_error(title, raw_error, context)
    except asyncio.TimeoutError:
        logger.error("ai_call_timeout", error_id=str(error_id))
        await _mark_failed(error_id)
        return
    except Exception:
        logger.exception("ai_call_failed", error_id=str(error_id))
        await _mark_failed(error_id)
        return

    async with AsyncSessionFactory() as db:
        try:
            await AnalysisRepository(db).create(
                error_log_id=error_id,
                user_id=user_id,
                summary=result.summary,
                root_cause=result.root_cause,
                suggestions=result.suggestions,
                ai_model=result.model,
                tokens_used=result.tokens_used,
                duration_ms=result.duration_ms,
            )
            await ErrorLogRepository(db).update_status(error_id, ErrorStatus.COMPLETED)
            await db.commit()
            logger.info(
                "analysis_saved",
                error_id=str(error_id),
                tokens=result.tokens_used,
                duration_ms=result.duration_ms,
            )
        except IntegrityError as exc:
            await db.rollback()
            pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
            if pgcode == _PG_UNIQUE_VIOLATION:
                # A duplicate trigger raced through — first writer wins, discard this one
                logger.warning("analysis_duplicate_discarded", error_id=str(error_id))
            else:
                # FK violation (error deleted mid-flight), check failure, etc.
                logger.exception(
                    "analysis_integrity_error", error_id=str(error_id), pgcode=pgcode
                )
                await _mark_failed(error_id)
        except Exception:
            await db.rollback()
            logger.exception("analysis_save_failed", error_id=str(error_id))
            await _mark_failed(error_id)


async def _mark_failed(error_id: uuid.UUID) -> None:
    """Best-effort status update to FAILED. Uses a fresh session — never re-raises."""
    async with AsyncSessionFactory() as db:
        try:
            await ErrorLogRepository(db).update_status(error_id, ErrorStatus.FAILED)
            await db.commit()
        except Exception:
            logger.exception("mark_failed_error", error_id=str(error_id))


# ---------------------------------------------------------------------------
# Service — uses the request-scoped session only
# ---------------------------------------------------------------------------

class AnalysisService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger(
        self,
        error_id: uuid.UUID,
        user_id: uuid.UUID,
        background_tasks: BackgroundTasks,
    ) -> AnalysisTriggerResponse:
        # Validate AI client is ready BEFORE accepting the job.
        # Raises 503 synchronously — the caller never gets a misleading 202.
        ai_client = get_ai_client()

        error_repo = ErrorLogRepository(self.db)
        analysis_repo = AnalysisRepository(self.db)

        error = await error_repo.get_by_id_and_user(error_id, user_id)
        if not error:
            raise NotFoundError("Error log not found")

        if error.status != ErrorStatus.PENDING:
            raise ConflictError(
                f"Cannot trigger analysis: current status is '{error.status.value}'"
            )

        # Per-user daily rate limit
        settings = get_settings()
        if settings.MAX_ANALYSES_PER_DAY > 0:
            count = await analysis_repo.count_today_by_user(user_id)
            if count >= settings.MAX_ANALYSES_PER_DAY:
                raise ConflictError(
                    f"Daily analysis limit of {settings.MAX_ANALYSES_PER_DAY} reached"
                )

        # Commit ANALYZING before scheduling — any concurrent trigger now sees
        # status != PENDING and gets a 409 without making an AI call.
        await error_repo.update_status(error_id, ErrorStatus.ANALYZING)
        await self.db.commit()

        # Snapshot fields — the ORM object must not be accessed after the session closes
        background_tasks.add_task(
            _run_analysis,
            error_id=error.id,
            user_id=error.user_id,
            title=error.title,
            raw_error=error.raw_error,
            context=error.context,
            ai_client=ai_client,
        )

        return AnalysisTriggerResponse(status=ErrorStatus.ANALYZING)

    async def get_result(
        self, error_id: uuid.UUID, user_id: uuid.UUID
    ) -> AnalysisResultResponse:
        # Single LEFT JOIN — one round-trip; returns error + analysis (if exists)
        result = await self.db.execute(
            select(ErrorLog, Analysis)
            .outerjoin(Analysis, Analysis.error_log_id == ErrorLog.id)
            .where(
                ErrorLog.id == error_id,
                ErrorLog.user_id == user_id,
            )
        )
        row = result.first()
        if row is None:
            raise NotFoundError("Error log not found")

        error_log, analysis = row.tuple()

        return AnalysisResultResponse(
            error_id=error_id,
            status=error_log.status,
            analysis=AnalysisData.model_validate(analysis) if analysis else None,
        )
