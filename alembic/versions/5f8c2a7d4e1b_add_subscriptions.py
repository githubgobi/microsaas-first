"""add subscriptions table

Revision ID: 5f8c2a7d4e1b
Revises: 3c7a9e2f1b84
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5f8c2a7d4e1b"
down_revision: Union[str, None] = "3c7a9e2f1b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=100), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=100), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=100), nullable=True),
        sa.Column(
            "plan",
            sa.Enum("free", "pro", name="plantier", native_enum=False, length=20),
            nullable=False,
            server_default="free",
        ),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_customer_id"),
        sa.UniqueConstraint("stripe_subscription_id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=True
    )
    op.create_index(
        op.f("ix_subscriptions_stripe_customer_id"),
        "subscriptions",
        ["stripe_customer_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_subscriptions_stripe_customer_id"), table_name="subscriptions"
    )
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
