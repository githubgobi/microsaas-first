import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    async def test_success_returns_tokens(self, client: AsyncClient):
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
        await client.post("/auth/register", json=data)
        resp = await client.post("/auth/register", json=data)
        assert resp.status_code == 409

    async def test_email_case_insensitive(self, client: AsyncClient):
        """UPPER@TEST.COM and upper@test.com must be the same account."""
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


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    async def test_success_returns_tokens(self, client: AsyncClient):
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
        reg = await client.post(
            "/auth/register",
            json={"email": "user@test.com", "password": "password123"},
        )
        old_refresh = reg.json()["refresh_token"]
        await client.post("/auth/refresh", json={"refresh_token": old_refresh})

        resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    async def test_logout_invalidates_refresh_token(self, client: AsyncClient):
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
