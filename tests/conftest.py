"""
Shared fixtures for the entire test suite.

Design decisions:
  - Real PostgreSQL (saas_test database) — never mock the DB; mocked tests
    passed in prod CI before when the real migration failed.
  - Each HTTP request gets its own session (via _override_get_db) so the
    identity map from one request never bleeds into the next request's reads.
  - Tables are truncated before every test — clean slate, predictable state.
  - `db` fixture is a separate direct-access session for test setup and
    assertions that cannot go through the HTTP layer.
  - `patch_bg_session` re-routes analysis background tasks to the test DB so
    their writes land in the same database the test assertions read from.
"""
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import create_app

# ---------------------------------------------------------------------------
# Test database — separate from dev; never share data between environments
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/saas_test",
)

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSessionFactory = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# Session-scoped: drop and recreate schema once per test run.
# The database itself is created by scripts/create_test_db.py which runs
# before pytest starts (see the 'test' service command in docker-compose.yml).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
async def create_schema():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped: wipe all rows before every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def truncate_tables():
    """
    TRUNCATE before each test, not after. This ensures a clean state even
    when a previous test failed partway through and left partial data.
    CASCADE handles foreign-key ordering automatically.
    """
    async with _engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, refresh_tokens, error_logs, analyses, subscriptions CASCADE"
            )
        )


# ---------------------------------------------------------------------------
# HTTP client — each request gets its own session (matches production behaviour)
# ---------------------------------------------------------------------------

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Full-stack test client: FastAPI app + real async DB sessions.

    A fresh AsyncSession is created per HTTP request (same as production).
    This avoids identity-map conflicts when the same object is modified by
    two consecutive requests in the same test.
    """
    app = create_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with _TestSessionFactory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Direct DB session — for test setup and assertions outside the HTTP layer
# ---------------------------------------------------------------------------

@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with _TestSessionFactory() as session:
        yield session


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Registers the primary test user and returns Bearer auth headers."""
    with patch("app.auth.service.send_verification_email", new_callable=AsyncMock):
        resp = await client.post(
            "/auth/register",
            json={"email": "user@test.com", "password": "password123"},
        )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def second_auth_headers(client: AsyncClient) -> dict[str, str]:
    """Registers a second user — used for ownership isolation tests."""
    with patch("app.auth.service.send_verification_email", new_callable=AsyncMock):
        resp = await client.post(
            "/auth/register",
            json={"email": "other@test.com", "password": "password123"},
        )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Analysis: patch background task session to use the test database
# ---------------------------------------------------------------------------

@pytest.fixture
def patch_bg_session():
    """
    _run_analysis opens its own AsyncSessionFactory session (because the
    request-scoped session is closed before the background task runs).
    This patch re-routes that factory to the test database so background
    task writes are visible to subsequent assertions in the same test.
    """
    with patch("app.analysis.service.AsyncSessionFactory", _TestSessionFactory):
        yield
