import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.errors.models import ErrorStatus


class AnalysisTriggerResponse(BaseModel):
    status: ErrorStatus
    message: str = "Analysis started — poll GET /errors/<error_id>/analysis for results"


class AnalysisData(BaseModel):
    """The AI result, present only when status == completed."""

    id: uuid.UUID
    summary: str
    root_cause: str
    suggestions: list[dict[str, Any]]
    ai_model: str
    tokens_used: int | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisResultResponse(BaseModel):
    """Polling response — includes analysis only when completed."""

    error_id: uuid.UUID
    status: ErrorStatus
    analysis: AnalysisData | None  # None while pending / analyzing / failed
