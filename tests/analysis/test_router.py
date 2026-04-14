"""
Analysis endpoint tests.

AI calls are mocked so tests run without an Anthropic API key and without
making real network requests.

Background task note:
  FastAPI background tasks execute synchronously within httpx's ASGITransport
  before `await client.post(...)` returns, so the "trigger → completed" flow
  is testable in a single test function without polling or sleeps.

  Background tasks create their own DB sessions via AsyncSessionFactory.
  The `patch_bg_session` fixture re-routes that factory to the test database
  so background task writes are visible to subsequent GET assertions.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.analysis.ai_client import AnalysisResult

_ERROR = {"title": "RuntimeError", "raw_error": "RuntimeError: division by zero at line 7"}


def _mock_ai_result() -> AnalysisResult:
    return AnalysisResult(
        summary="Division by zero detected.",
        root_cause="Variable 'divisor' is zero when passed to calculate().",
        suggestions=[{"step": 1, "action": "Add a guard: if divisor == 0: raise ValueError"}],
        model="claude-sonnet-4-6",
        tokens_used=250,
        duration_ms=1100,
    )


def _mock_ai_client() -> AsyncMock:
    client = AsyncMock()
    client.analyze_error.return_value = _mock_ai_result()
    return client


# ---------------------------------------------------------------------------
# Trigger analysis
# ---------------------------------------------------------------------------

class TestTriggerAnalysis:
    async def test_returns_202_and_status_analyzing(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
            resp = await client.post(f"/errors/{error_id}/analyze", headers=auth_headers)

        assert resp.status_code == 202
        assert resp.json()["status"] == "analyzing"

    async def test_duplicate_trigger_returns_409(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        """Second trigger while ANALYZING (or COMPLETED) must be rejected."""
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
            await client.post(f"/errors/{error_id}/analyze", headers=auth_headers)
            resp = await client.post(f"/errors/{error_id}/analyze", headers=auth_headers)

        assert resp.status_code == 409

    async def test_no_api_key_returns_503(self, client: AsyncClient, auth_headers: dict):
        """With ANTHROPIC_API_KEY unset (default in tests), trigger returns 503."""
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        # No patch — get_ai_client raises ServiceUnavailableError (no API key)
        resp = await client.post(f"/errors/{error_id}/analyze", headers=auth_headers)
        assert resp.status_code == 503

    async def test_nonexistent_error_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
            resp = await client.post(
                "/errors/00000000-0000-0000-0000-000000000000/analyze",
                headers=auth_headers,
            )
        assert resp.status_code == 404

    async def test_other_users_error_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        second_auth_headers: dict,
    ):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
            resp = await client.post(
                f"/errors/{error_id}/analyze", headers=second_auth_headers
            )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Get analysis result
# ---------------------------------------------------------------------------

class TestGetAnalysisResult:
    async def test_pending_error_has_no_analysis(
        self, client: AsyncClient, auth_headers: dict
    ):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        resp = await client.get(f"/errors/{error_id}/analysis", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        assert resp.json()["analysis"] is None

    async def test_completed_analysis_returned_after_background_task(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        """
        Full end-to-end: trigger → background task runs → result is visible.

        The background task completes before await client.post() returns
        (ASGITransport executes the full ASGI lifecycle synchronously).
        patch_bg_session ensures its DB writes go to the test database.
        """
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
            await client.post(f"/errors/{error_id}/analyze", headers=auth_headers)

        resp = await client.get(f"/errors/{error_id}/analysis", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        analysis = resp.json()["analysis"]
        assert analysis["summary"] == "Division by zero detected."
        assert analysis["root_cause"] == "Variable 'divisor' is zero when passed to calculate()."
        assert len(analysis["suggestions"]) == 1

    async def test_nonexistent_error_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/errors/00000000-0000-0000-0000-000000000000/analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_other_users_analysis_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        second_auth_headers: dict,
        patch_bg_session,
    ):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
            await client.post(f"/errors/{error_id}/analyze", headers=auth_headers)

        resp = await client.get(
            f"/errors/{error_id}/analysis", headers=second_auth_headers
        )
        assert resp.status_code == 404
