"""
Billing endpoint tests.

All Stripe API calls are mocked — no real network calls, no API key needed.
The _billing_settings() helper patches get_settings() inside the billing service
so that STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, and STRIPE_PRO_PRICE_ID are
always present without modifying the process environment.
"""
import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRO_PRICE_ID = "price_pro_test123"
_CUSTOMER_ID = "cus_test123"
_SUBSCRIPTION_ID = "sub_test123"


@contextmanager
def _billing_settings(**overrides):
    """Patch get_settings in both the router and the service.

    The router's _require_billing() dependency reads BILLING_ENABLED; the
    service reads STRIPE_SECRET_KEY etc.  Both are patched here so billing
    tests work without touching the real environment.
    """
    mock = MagicMock()
    mock.BILLING_ENABLED = True
    mock.STRIPE_SECRET_KEY = "sk_test_abc"
    mock.STRIPE_WEBHOOK_SECRET = "whsec_test"
    mock.STRIPE_PRO_PRICE_ID = _PRO_PRICE_ID
    mock.FRONTEND_URL = "http://localhost:3000"
    for k, v in overrides.items():
        setattr(mock, k, v)
    with (
        patch("app.billing.router.get_settings", return_value=mock),
        patch("app.billing.service.get_settings", return_value=mock),
    ):
        yield mock


def _mock_customer():
    c = MagicMock()
    c.id = _CUSTOMER_ID
    return c


def _mock_checkout_session(url="https://checkout.stripe.com/test"):
    s = MagicMock()
    s.url = url
    return s


def _mock_portal_session(url="https://billing.stripe.com/portal/test"):
    s = MagicMock()
    s.url = url
    return s


def _make_webhook_event(event_type: str, obj: dict) -> MagicMock:
    event = MagicMock()
    event.type = event_type
    # Build a MagicMock that supports attribute access for nested Stripe objects
    data_obj = MagicMock()
    for k, v in obj.items():
        setattr(data_obj, k, v)
    event.data.object = data_obj
    return event


# ---------------------------------------------------------------------------
# GET /billing/subscription
# ---------------------------------------------------------------------------

class TestGetSubscription:
    async def test_free_plan_when_no_subscription(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get("/billing/subscription", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] == "free"
        assert body["status"] is None
        assert body["current_period_end"] is None
        assert body["cancel_at_period_end"] is False

    async def test_billing_disabled_returns_503(self, client: AsyncClient):
        resp = await client.get("/billing/subscription")
        assert resp.status_code == 503

    async def test_no_token_returns_403(self, client: AsyncClient):
        # Billing enabled but no auth token
        with _billing_settings():
            resp = await client.get("/billing/subscription")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /billing/checkout
# ---------------------------------------------------------------------------

class TestCreateCheckout:
    async def test_returns_checkout_url(
        self, client: AsyncClient, auth_headers: dict
    ):
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()),
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            resp = await client.post("/billing/checkout", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"

    async def test_reuses_existing_customer_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Second checkout call must not create a second Stripe customer."""
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()) as mock_create,
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            await client.post("/billing/checkout", headers=auth_headers)
            await client.post("/billing/checkout", headers=auth_headers)

        # Customer.create must be called exactly once across both requests
        assert mock_create.call_count == 1

    async def test_billing_disabled_returns_503(
        self, client: AsyncClient, auth_headers: dict
    ):
        # No _billing_settings() patch → BILLING_ENABLED defaults to False
        resp = await client.post("/billing/checkout", headers=auth_headers)
        assert resp.status_code == 503

    async def test_active_pro_returns_409(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Users already on an active Pro plan get a 409 directing them to the portal."""
        # First checkout — activates the subscription
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()),
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            await client.post("/billing/checkout", headers=auth_headers)

        # Simulate webhook activating the subscription
        event = _make_webhook_event(
            "checkout.session.completed",
            {"customer": _CUSTOMER_ID, "subscription": _SUBSCRIPTION_ID},
        )
        with (
            _billing_settings(),
            patch("stripe.Webhook.construct_event", return_value=event),
        ):
            await client.post(
                "/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "sig"},
            )

        # Second checkout must be rejected
        with _billing_settings():
            resp = await client.post("/billing/checkout", headers=auth_headers)

        assert resp.status_code == 409

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.post("/billing/checkout")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /billing/portal
# ---------------------------------------------------------------------------

class TestCreatePortal:
    async def test_returns_portal_url(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Set up a customer first via checkout
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()),
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            await client.post("/billing/checkout", headers=auth_headers)

        with (
            _billing_settings(),
            patch(
                "stripe.billing_portal.Session.create",
                return_value=_mock_portal_session(),
            ),
        ):
            resp = await client.post("/billing/portal", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.json()["portal_url"] == "https://billing.stripe.com/portal/test"

    async def test_no_customer_returns_400(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Portal requires an existing Stripe customer (i.e. checkout started before)."""
        with _billing_settings():
            resp = await client.post("/billing/portal", headers=auth_headers)
        assert resp.status_code == 400

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.post("/billing/portal")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /billing/webhook
# ---------------------------------------------------------------------------

class TestWebhook:
    async def test_checkout_completed_activates_subscription(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Create a Stripe customer row first
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()),
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            await client.post("/billing/checkout", headers=auth_headers)

        # Send checkout.session.completed webhook
        event = _make_webhook_event(
            "checkout.session.completed",
            {"customer": _CUSTOMER_ID, "subscription": _SUBSCRIPTION_ID},
        )
        with (
            _billing_settings(),
            patch("stripe.Webhook.construct_event", return_value=event),
        ):
            resp = await client.post(
                "/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "sig"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": True}

        # Subscription must now show Pro
        sub_resp = await client.get("/billing/subscription", headers=auth_headers)
        assert sub_resp.json()["plan"] == "pro"
        assert sub_resp.json()["status"] == "active"

    async def test_subscription_updated_changes_status(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Bootstrap a customer + active subscription
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()),
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            await client.post("/billing/checkout", headers=auth_headers)

        checkout_event = _make_webhook_event(
            "checkout.session.completed",
            {"customer": _CUSTOMER_ID, "subscription": _SUBSCRIPTION_ID},
        )
        with (
            _billing_settings(),
            patch("stripe.Webhook.construct_event", return_value=checkout_event),
        ):
            await client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
            )

        # Now send subscription.updated with past_due + cancel_at_period_end
        stripe_sub = MagicMock()
        stripe_sub.customer = _CUSTOMER_ID
        stripe_sub.id = _SUBSCRIPTION_ID
        stripe_sub.status = "past_due"
        stripe_sub.cancel_at_period_end = True
        stripe_sub.current_period_end = 9999999999  # far future Unix timestamp
        stripe_sub.items.data[0].price.id = _PRO_PRICE_ID

        update_event = MagicMock()
        update_event.type = "customer.subscription.updated"
        update_event.data.object = stripe_sub

        with (
            _billing_settings(),
            patch("stripe.Webhook.construct_event", return_value=update_event),
        ):
            resp = await client.post(
                "/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
            )

        assert resp.status_code == 200
        sub_resp = await client.get("/billing/subscription", headers=auth_headers)
        body = sub_resp.json()
        assert body["status"] == "past_due"
        assert body["cancel_at_period_end"] is True
        assert body["plan"] == "pro"  # price ID still matches Pro

    async def test_subscription_deleted_reverts_to_free(
        self, client: AsyncClient, auth_headers: dict
    ):
        # Bootstrap customer + active Pro subscription
        with (
            _billing_settings(),
            patch("stripe.Customer.create", return_value=_mock_customer()),
            patch(
                "stripe.checkout.Session.create",
                return_value=_mock_checkout_session(),
            ),
        ):
            await client.post("/billing/checkout", headers=auth_headers)

        for event_type, obj in [
            (
                "checkout.session.completed",
                {"customer": _CUSTOMER_ID, "subscription": _SUBSCRIPTION_ID},
            ),
            (
                "customer.subscription.deleted",
                {"customer": _CUSTOMER_ID, "id": _SUBSCRIPTION_ID},
            ),
        ]:
            ev = _make_webhook_event(event_type, obj)
            with (
                _billing_settings(),
                patch("stripe.Webhook.construct_event", return_value=ev),
            ):
                await client.post(
                    "/billing/webhook",
                    content=b"{}",
                    headers={"stripe-signature": "sig"},
                )

        sub_resp = await client.get("/billing/subscription", headers=auth_headers)
        body = sub_resp.json()
        assert body["plan"] == "free"
        assert body["status"] == "cancelled"

    async def test_invalid_signature_returns_400(self, client: AsyncClient):
        import stripe

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.SignatureVerificationError("bad", "sig"),
        ):
            with _billing_settings():
                resp = await client.post(
                    "/billing/webhook",
                    content=b"{}",
                    headers={"stripe-signature": "bad_sig"},
                )
        assert resp.status_code == 400

    async def test_billing_disabled_returns_503(self, client: AsyncClient):
        # No _billing_settings() patch → BILLING_ENABLED defaults to False
        resp = await client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "sig"},
        )
        assert resp.status_code == 503

    async def test_unknown_event_type_returns_200(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Unhandled event types are acknowledged silently."""
        ev = MagicMock()
        ev.type = "invoice.payment_succeeded"
        ev.data.object = MagicMock()
        with (
            _billing_settings(),
            patch("stripe.Webhook.construct_event", return_value=ev),
        ):
            resp = await client.post(
                "/billing/webhook",
                content=b"{}",
                headers={"stripe-signature": "sig"},
            )
        assert resp.status_code == 200
