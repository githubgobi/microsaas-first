import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utc_now


class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # One subscription per user; cascade-delete when user is removed
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # Stripe customer ID — set when checkout starts, used to look up on webhooks
    stripe_customer_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    # Set after checkout.session.completed; None while subscription is pending
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    # Stripe price ID — stored so we can map price → plan on subscription.updated
    stripe_price_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    plan: Mapped[PlanTier] = mapped_column(
        SQLAlchemyEnum(PlanTier, native_enum=False, length=20),
        nullable=False,
        default=PlanTier.FREE,
    )
    # Mirrors Stripe's subscription status: active, past_due, cancelled, incomplete, …
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # True when the user cancelled but the period has not expired yet
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
