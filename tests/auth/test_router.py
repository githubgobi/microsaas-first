from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.auth.utils import create_password_reset_token, create_verification_token


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _patch_email():
    """Context manager that stubs out email sending for the entire test suite."""
    return patch("app.auth.service.send_verification_email", new_callable=AsyncMock)


class TestRegister:
    async def test_success_returns_tokens(self, client: AsyncClient):
        with _patch_email():
            resp = await client.post(
                "/auth/register",
                json={"email": "new@test.com", "password": "password123"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_duplicate_email_returns_409(self, client: AsyncClient):
        data = {"email": "dup@test.com", "password": "password123"}
        with _patch_email():
            await client.post("/auth/register", json=data)
            resp = await client.post("/auth/register", json=data)
        assert resp.status_code == 409

    async def test_email_case_insensitive(self, client: AsyncClient):
        """UPPER@TEST.COM and upper@test.com must be the same account."""
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "UPPER@TEST.COM", "password": "password123"},
            )
            resp = await client.post(
                "/auth/register",
                json={"email": "upper@test.com", "password": "password123"},
            )
        assert resp.status_code == 409

    async def test_short_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "x@test.com", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_password_over_72_bytes_returns_422(self, client: AsyncClient):
        # bcrypt silently truncates at 72 bytes — we reject at the schema level
        resp = await client.post(
            "/auth/register",
            json={"email": "x@test.com", "password": "a" * 73},
        )
        assert resp.status_code == 422

    async def test_invalid_email_format_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    async def test_register_sends_verification_email(self, client: AsyncClient):
        with _patch_email() as mock_send:
            await client.post(
                "/auth/register",
                json={"email": "verify@test.com", "password": "password123"},
            )
        mock_send.assert_called_once()
        call_email = mock_send.call_args[0][0]
        assert call_email == "verify@test.com"

    async def test_new_user_is_not_verified(self, client: AsyncClient):
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "unverified@test.com", "password": "password123"},
            )
        token = reg.json()["access_token"]
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["is_verified"] is False


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    async def test_success_returns_tokens(self, client: AsyncClient):
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        resp = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_wrong_password_returns_401(self, client: AsyncClient):
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        resp = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_unknown_email_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/auth/login",
            json={"email": "ghost@test.com", "password": "password123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    async def test_wrong_password_and_unknown_email_same_message(self, client: AsyncClient):
        """Both failure modes return the same message — prevents user enumeration."""
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        wrong_pass = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "wrong"},
        )
        no_user = await client.post(
            "/auth/login",
            json={"email": "ghost@test.com", "password": "password123"},
        )
        assert wrong_pass.json()["detail"] == no_user.json()["detail"]

    async def test_login_normalises_email_case(self, client: AsyncClient):
        """Registered with mixed case; login with lowercase should succeed."""
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "User@Test.COM", "password": "password123"},
            )
        resp = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------

class TestMe:
    async def test_returns_user_info(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "user@test.com"
        assert body["is_active"] is True
        assert body["is_verified"] is False
        assert "id" in body

    async def test_no_token_returns_403(self, client: AsyncClient):
        # HTTPBearer raises 403 when the Authorization header is absent entirely
        resp = await client.get("/auth/me")
        assert resp.status_code == 403

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token refresh and logout
# ---------------------------------------------------------------------------

class TestRefreshAndLogout:
    async def test_refresh_issues_new_tokens(self, client: AsyncClient):
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        old_refresh = reg.json()["refresh_token"]

        resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 200
        assert resp.json()["access_token"] != reg.json()["access_token"]

    async def test_refresh_token_is_rotated(self, client: AsyncClient):
        """Old refresh token must not work after it has been used once."""
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        old_refresh = reg.json()["refresh_token"]
        await client.post("/auth/refresh", json={"refresh_token": old_refresh})

        resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    async def test_logout_invalidates_refresh_token(self, client: AsyncClient):
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        refresh_token = reg.json()["refresh_token"]

        await client.post("/auth/logout", json={"refresh_token": refresh_token})

        resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401

    async def test_logout_unknown_token_returns_204(self, client: AsyncClient):
        """Logout is idempotent — unknown tokens return 204, not 4xx."""
        resp = await client.post(
            "/auth/logout", json={"refresh_token": "nonexistent-token"}
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

class TestVerifyEmail:
    async def test_valid_token_sets_verified(self, client: AsyncClient):
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        access_token = reg.json()["access_token"]

        # Build a real token using the same function the service uses
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        user_id = me.json()["id"]
        token = create_verification_token(user_id)

        resp = await client.post("/auth/verify-email", json={"token": token})
        assert resp.status_code == 204

        me2 = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me2.json()["is_verified"] is True

    async def test_invalid_token_returns_400(self, client: AsyncClient):
        resp = await client.post("/auth/verify-email", json={"token": "not.a.valid.jwt"})
        assert resp.status_code == 400

    async def test_expired_token_returns_400(self, client: AsyncClient):
        from datetime import timedelta
        from app.auth.utils import settings as auth_settings
        from jose import jwt
        from app.config import JWT_ALGORITHM

        # Forge a token that expired 1 second ago
        expired = jwt.encode(
            {
                "sub": "00000000-0000-0000-0000-000000000000",
                "type": "email_verification",
                "exp": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ) - timedelta(seconds=1),
            },
            auth_settings.SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        resp = await client.post("/auth/verify-email", json={"token": expired})
        assert resp.status_code == 400

    async def test_wrong_type_claim_returns_400(self, client: AsyncClient):
        """Access tokens must not be accepted as verification tokens."""
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        access_token = reg.json()["access_token"]

        # Submit the access token where a verification token is expected
        resp = await client.post("/auth/verify-email", json={"token": access_token})
        assert resp.status_code == 400

    async def test_verify_is_idempotent(self, client: AsyncClient):
        """Verifying twice returns 204 both times — no error on second call."""
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        user_id = (
            await client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {reg.json()['access_token']}"},
            )
        ).json()["id"]
        token = create_verification_token(user_id)

        assert (await client.post("/auth/verify-email", json={"token": token})).status_code == 204
        assert (await client.post("/auth/verify-email", json={"token": token})).status_code == 204


# ---------------------------------------------------------------------------
# Resend verification
# ---------------------------------------------------------------------------

class TestResendVerification:
    async def test_sends_email_for_unverified_user(self, client: AsyncClient):
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )

        with _patch_email() as mock_send:
            resp = await client.post(
                "/auth/resend-verification", json={"email": "user@test.com"}
            )
        assert resp.status_code == 204
        mock_send.assert_called_once()

    async def test_unknown_email_returns_204_silently(self, client: AsyncClient):
        """Must not reveal whether the email exists."""
        resp = await client.post(
            "/auth/resend-verification", json={"email": "ghost@test.com"}
        )
        assert resp.status_code == 204

    async def test_already_verified_returns_204_no_email(self, client: AsyncClient):
        """No email sent if the account is already verified."""
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        user_id = (
            await client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {reg.json()['access_token']}"},
            )
        ).json()["id"]
        token = create_verification_token(user_id)
        await client.post("/auth/verify-email", json={"token": token})

        with _patch_email() as mock_send:
            resp = await client.post(
                "/auth/resend-verification", json={"email": "user@test.com"}
            )
        assert resp.status_code == 204
        mock_send.assert_not_called()

    async def test_invalid_email_format_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/resend-verification", json={"email": "not-an-email"}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------

def _patch_reset_email():
    return patch("app.auth.service.send_password_reset_email", new_callable=AsyncMock)


class TestForgotPassword:
    async def test_sends_email_for_known_user(self, client: AsyncClient):
        with _patch_email():
            await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )

        with _patch_reset_email() as mock_send:
            resp = await client.post(
                "/auth/forgot-password", json={"email": "user@test.com"}
            )
        assert resp.status_code == 204
        mock_send.assert_called_once()
        assert mock_send.call_args[0][0] == "user@test.com"

    async def test_unknown_email_returns_204_silently(self, client: AsyncClient):
        """Must not reveal whether the address is registered."""
        with _patch_reset_email() as mock_send:
            resp = await client.post(
                "/auth/forgot-password", json={"email": "ghost@test.com"}
            )
        assert resp.status_code == 204
        mock_send.assert_not_called()

    async def test_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/forgot-password", json={"email": "not-an-email"}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------

class TestResetPassword:
    async def _register_and_get_reset_token(self, client: AsyncClient) -> tuple[str, str]:
        """Register a user and return (access_token, reset_token)."""
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        access_token = reg.json()["access_token"]

        # Capture the reset token that the service would send
        with _patch_reset_email() as mock_send:
            await client.post(
                "/auth/forgot-password", json={"email": "user@test.com"}
            )
        reset_token = mock_send.call_args[0][1]
        return access_token, reset_token

    async def test_valid_token_changes_password(self, client: AsyncClient):
        _, reset_token = await self._register_and_get_reset_token(client)

        resp = await client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword99"},
        )
        assert resp.status_code == 204

        # Old password no longer works
        old_login = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )
        assert old_login.status_code == 401

        # New password works
        new_login = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "newpassword99"},
        )
        assert new_login.status_code == 200

    async def test_reset_revokes_all_refresh_tokens(self, client: AsyncClient):
        """Active sessions should be invalidated after a password reset."""
        access_token, reset_token = await self._register_and_get_reset_token(client)

        # Obtain a refresh token before the reset
        login = await client.post(
            "/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )
        refresh_token = login.json()["refresh_token"]

        await client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword99"},
        )

        # Old refresh token must be rejected
        resp = await client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert resp.status_code == 401

    async def test_token_is_single_use(self, client: AsyncClient):
        """Using a reset token invalidates it — the second use must be rejected."""
        _, reset_token = await self._register_and_get_reset_token(client)

        await client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "newpassword99"},
        )
        resp = await client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "anotherpassword"},
        )
        assert resp.status_code == 400

    async def test_invalid_token_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/auth/reset-password",
            json={"token": "not.a.valid.jwt", "new_password": "newpassword99"},
        )
        assert resp.status_code == 400

    async def test_wrong_type_claim_returns_400(self, client: AsyncClient):
        """Verification tokens must not be accepted as reset tokens."""
        with _patch_email():
            reg = await client.post(
                "/auth/register",
                json={"email": "user@test.com", "password": "password123"},
            )
        user_id = (
            await client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {reg.json()['access_token']}"},
            )
        ).json()["id"]
        wrong_token = create_verification_token(user_id)

        resp = await client.post(
            "/auth/reset-password",
            json={"token": wrong_token, "new_password": "newpassword99"},
        )
        assert resp.status_code == 400

    async def test_weak_new_password_returns_422(self, client: AsyncClient):
        _, reset_token = await self._register_and_get_reset_token(client)
        resp = await client.post(
            "/auth/reset-password",
            json={"token": reset_token, "new_password": "short"},
        )
        assert resp.status_code == 422
