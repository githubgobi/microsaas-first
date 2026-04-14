"""
Stripe billing service.

Stripe's Python SDK is synchronous; all API calls are wrapped in
anyio.to_thread.run_sync so they don't block the async event loop.

Webhook signature verification (HMAC) is lightweight and runs inline.
"""
from datetime import datetime, timezone

import anyio
import stripe
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import PlanTier, Subscription
from app.billing.repository import SubscriptionRepository
from app.billing.schemas import CheckoutResponse, PortalResponse, SubscriptionResponse
from app.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError, ServiceUnavailableError

logger = structlog.get_logger()


async def _stripe_call(fn, *args, **kwargs):
    """Run a blocking Stripe SDK call in a thread pool."""
    return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))


class BillingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SubscriptionRepository(db)

    def _require_stripe(self) -> None:
        """Raise 503 and set stripe.api_key if Stripe is configured."""
        settings = get_settings()
        if not settings.STRIPE_SECRET_KEY:
            raise ServiceUnavailableError("Billing is not configured")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    async def create_checkout_session(self, user: User) -> str:
        """Create a Stripe Checkout session and return its URL."""
        self._require_stripe()
        settings = get_settings()

        sub = await self.repo.get_by_user_id(user.id)

        # Block repeat subscriptions — send active Pro users to the portal instead
        if (
            sub
            and sub.plan == PlanTier.PRO
            and sub.status == "active"
            and not sub.cancel_at_period_end
        ):
            raise ConflictError(
                "You already have an active Pro subscription. "
                "Use the billing portal to manage it."
            )

        # Get or create Stripe customer
        if sub and sub.stripe_customer_id:
            customer_id = sub.stripe_customer_id
        else:
            customer = await _stripe_call(
                stripe.Customer.create,
                email=user.email,
                metadata={"user_id": str(user.id)},
            )
            customer_id = customer.id

            if sub is None:
                sub = await self.repo.create(user.id, customer_id)
            else:
                sub.stripe_customer_id = customer_id

            await self.db.commit()

        session = await _stripe_call(
            stripe.checkout.Session.create,
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
            # {CHECKOUT_SESSION_ID} is a Stripe template variable, not a Python f-string
            success_url=(
                f"{settings.FRONTEND_URL}/billing/success"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=f"{settings.FRONTEND_URL}/billing/cancelled",
        )
        return session.url

    async def create_portal_session(self, user: User) -> str:
        """Create a Stripe billing portal session and return its URL."""
        self._require_stripe()
        settings = get_settings()

        sub = await self.repo.get_by_user_id(user.id)
        if not sub or not sub.stripe_customer_id:
            raise BadRequestError(
                "No billing account found. Start a subscription first."
            )

        session = await _stripe_call(
            stripe.billing_portal.Session.create,
            customer=sub.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/billing",
        )
        return session.url

    async def get_subscription(self, user: User) -> SubscriptionResponse:
        sub = await self.repo.get_by_user_id(user.id)
        if sub is None:
            return SubscriptionResponse(
                plan=PlanTier.FREE,
                status=None,
                current_period_end=None,
                cancel_at_period_end=False,
            )
        return SubscriptionResponse.model_validate(sub)

    async def handle_webhook(self, payload: bytes, sig_header: str) -> None:
        """Verify and dispatch a Stripe webhook event."""
        settings = get_settings()
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ServiceUnavailableError("Webhook secret is not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise BadRequestError("Invalid payload")
        except stripe.SignatureVerificationError:
            raise BadRequestError("Invalid webhook signature")

        event_type = event.type
        obj = event.data.object

        logger.info("webhook_received", event_type=event_type)

        if event_type == "checkout.session.completed":
            await self._on_checkout_completed(obj)
        elif event_type == "customer.subscription.updated":
            await self._on_subscription_updated(obj)
        elif event_type == "customer.subscription.deleted":
            await self._on_subscription_deleted(obj)
        # All other events are acknowledged with 200 and ignored

    # ------------------------------------------------------------------
    # Webhook handlers (private)
    # ------------------------------------------------------------------

    async def _on_checkout_completed(self, session) -> None:
        """A checkout completed — activate the subscription."""
        customer_id = session.customer
        subscription_id = session.subscription

        sub = await self.repo.get_by_customer_id(customer_id)
        if sub is None:
            logger.warning("webhook_customer_not_found", customer_id=customer_id)
            return

        sub.stripe_subscription_id = subscription_id
        sub.plan = PlanTier.PRO
        sub.status = "active"
        await self.db.commit()
        logger.info("subscription_activated", user_id=str(sub.user_id))

    async def _on_subscription_updated(self, stripe_sub) -> None:
        """Plan, status, or period changed."""
        customer_id = stripe_sub.customer

        sub = await self.repo.get_by_customer_id(customer_id)
        if sub is None:
            logger.warning("webhook_customer_not_found", customer_id=customer_id)
            return

        settings = get_settings()

        sub.stripe_subscription_id = stripe_sub.id
        sub.status = stripe_sub.status
        sub.cancel_at_period_end = bool(stripe_sub.cancel_at_period_end)

        if stripe_sub.current_period_end:
            sub.current_period_end = datetime.fromtimestamp(
                stripe_sub.current_period_end, tz=timezone.utc
            )

        # Resolve price → plan tier
        price_id = None
        try:
            price_id = stripe_sub.items.data[0].price.id
        except (AttributeError, IndexError, TypeError):
            pass
        sub.stripe_price_id = price_id
        sub.plan = (
            PlanTier.PRO
            if price_id and price_id == settings.STRIPE_PRO_PRICE_ID
            else PlanTier.FREE
        )

        await self.db.commit()
        logger.info(
            "subscription_updated",
            user_id=str(sub.user_id),
            status=sub.status,
            plan=sub.plan,
        )

    async def _on_subscription_deleted(self, stripe_sub) -> None:
        """Subscription cancelled — revert to Free."""
        customer_id = stripe_sub.customer

        sub = await self.repo.get_by_customer_id(customer_id)
        if sub is None:
            return

        sub.status = "cancelled"
        sub.plan = PlanTier.FREE
        sub.stripe_subscription_id = None
        sub.cancel_at_period_end = False
        await self.db.commit()
        logger.info("subscription_cancelled", user_id=str(sub.user_id))
