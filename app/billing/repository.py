import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import Subscription


class SubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_user_id(self, user_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_customer_id(self, stripe_customer_id: str) -> Subscription | None:
        """Used by webhook handlers to locate a subscription from Stripe's customer ID."""
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.stripe_customer_id == stripe_customer_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: uuid.UUID, stripe_customer_id: str) -> Subscription:
        sub = Subscription(user_id=user_id, stripe_customer_id=stripe_customer_id)
        self.db.add(sub)
        await self.db.flush()
        return sub
