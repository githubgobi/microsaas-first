from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.billing.schemas import CheckoutResponse, PortalResponse, SubscriptionResponse
from app.billing.service import BillingService
from app.config import get_settings
from app.core.rate_limit import limiter
from app.database import get_db


def _require_billing() -> None:
    """Dependency applied to every billing route.
    Returns immediately when BILLING_ENABLED=true; raises 503 otherwise."""
    if not get_settings().BILLING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not enabled",
        )


router = APIRouter(dependencies=[Depends(_require_billing)])


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    return await BillingService(db).get_subscription(current_user)


@router.post("/checkout", response_model=CheckoutResponse)
@limiter.limit("10/minute")
async def create_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    url = await BillingService(db).create_checkout_session(current_user)
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
@limiter.limit("10/minute")
async def create_portal_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortalResponse:
    url = await BillingService(db).create_portal_session(current_user)
    return PortalResponse(portal_url=url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Read raw bytes before any parsing — Stripe verifies the exact bytes
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    await BillingService(db).handle_webhook(payload, sig_header)
    return {"received": True}
