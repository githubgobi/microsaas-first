import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.analysis.models import Analysis
from app.errors.models import ErrorLog


class HistorySummary(BaseModel):
    """One row in the paginated list — no root_cause or suggestions to keep payload small."""

    id: uuid.UUID          # analysis id
    error_id: uuid.UUID
    error_title: str
    summary: str
    ai_model: str
    tokens_used: int | None
    created_at: datetime

    @classmethod
    def from_row(cls, analysis: Analysis, error_title: str) -> "HistorySummary":
        return cls(
            id=analysis.id,
            error_id=analysis.error_log_id,
            error_title=error_title,
            summary=analysis.summary,
            ai_model=analysis.ai_model,
            tokens_used=analysis.tokens_used,
            created_at=analysis.created_at,
        )


class HistoryDetail(BaseModel):
    """Full analysis result for a single history entry."""

    id: uuid.UUID
    error_id: uuid.UUID
    error_title: str
    summary: str
    root_cause: str
    suggestions: list[dict[str, Any]]
    ai_model: str
    tokens_used: int | None
    duration_ms: int | None
    created_at: datetime

    @classmethod
    def from_row(cls, analysis: Analysis, error_title: str) -> "HistoryDetail":
        return cls(
            id=analysis.id,
            error_id=analysis.error_log_id,
            error_title=error_title,
            summary=analysis.summary,
            root_cause=analysis.root_cause,
            suggestions=analysis.suggestions,
            ai_model=analysis.ai_model,
            tokens_used=analysis.tokens_used,
            duration_ms=analysis.duration_ms,
            created_at=analysis.created_at,
        )
