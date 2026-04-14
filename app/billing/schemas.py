from datetime import datetime

from pydantic import BaseModel

from app.billing.models import PlanTier


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionResponse(BaseModel):
    plan: PlanTier
    status: str | None
    current_period_end: datetime | None
    cancel_at_period_end: bool

    model_config = {"from_attributes": True}
