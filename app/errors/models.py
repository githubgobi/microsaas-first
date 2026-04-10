import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utc_now


class ErrorStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ErrorLog(Base):
    __tablename__ = "error_logs"
    __table_args__ = (
        # Composite index: covers WHERE user_id = ? ORDER BY created_at DESC
        # Eliminates a sort step on every list query — critical at scale
        Index("ix_error_logs_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_error: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # SQLAlchemyEnum with native_enum=False adds a CHECK constraint at the DB level
    status: Mapped[ErrorStatus] = mapped_column(
        SQLAlchemyEnum(ErrorStatus, native_enum=False, length=20),
        nullable=False,
        default=ErrorStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    analysis: Mapped["Analysis"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="error_log",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="noload",  # never auto-loaded; fetched explicitly when needed
    )
