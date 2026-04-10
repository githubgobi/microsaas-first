import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.errors.models import ErrorStatus

_MAX_RAW_ERROR_BYTES = 65_536  # 64 KB
_MAX_CONTEXT_BYTES = 4_096     # 4 KB — context is metadata, not content


class ErrorSubmitRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    raw_error: str = Field(..., min_length=1)
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata: language, service, environment, etc.",
    )

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title cannot be blank or whitespace only")
        return stripped

    @field_validator("raw_error")
    @classmethod
    def check_raw_error_size(cls, v: str) -> str:
        if len(v.encode()) > _MAX_RAW_ERROR_BYTES:
            raise ValueError(
                f"raw_error exceeds maximum size of {_MAX_RAW_ERROR_BYTES // 1024} KB"
            )
        return v

    @field_validator("context")
    @classmethod
    def check_context_size(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return v
        if len(json.dumps(v).encode()) > _MAX_CONTEXT_BYTES:
            raise ValueError(
                f"context exceeds maximum size of {_MAX_CONTEXT_BYTES // 1024} KB"
            )
        return v


class ErrorSummary(BaseModel):
    """Returned in list responses — raw_error omitted to keep payloads small."""

    id: uuid.UUID
    title: str
    status: ErrorStatus  # validated enum, not a free-form str
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorDetail(BaseModel):
    """Returned for single-item GET — includes full raw_error and context."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    raw_error: str
    context: dict[str, Any] | None
    status: ErrorStatus  # validated enum, not a free-form str
    created_at: datetime

    model_config = {"from_attributes": True}
