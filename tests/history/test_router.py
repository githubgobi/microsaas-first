"""
History endpoint tests.

Setup pattern: create an error → trigger analysis with a mocked AI client →
then exercise the history endpoints. The `patch_bg_session` fixture ensures
background task writes land in the test database.
"""
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.analysis.ai_client import AnalysisResult

_ERROR = {"title": "KeyError", "raw_error": "KeyError: 'user_id' in process_request at line 42"}
_ERROR_2 = {"title": "TypeError", "raw_error": "TypeError: unsupported operand type(s) for +: 'int' and 'str'"}


def _mock_ai_result() -> AnalysisResult:
    return AnalysisResult(
        summary="Missing key in dict.",
        root_cause="'user_id' key is absent from the request payload.",
        suggestions=[{"step": 1, "action": "Validate request schema before processing."}],
        model="claude-sonnet-4-6",
        tokens_used=180,
        duration_ms=900,
    )


def _mock_ai_client():
    from unittest.mock import AsyncMock
    client = AsyncMock()
    client.analyze_error.return_value = _mock_ai_result()
    return client


async def _create_analyzed_error(
    client: AsyncClient, headers: dict, error: dict = _ERROR
) -> tuple[str, str]:
    """Creates an error, runs analysis, returns (error_id, analysis_id)."""
    create = await client.post("/errors", json=error, headers=headers)
    assert create.status_code == 201
    error_id = create.json()["id"]

    with patch("app.analysis.service.get_ai_client", return_value=_mock_ai_client()):
        await client.post(f"/errors/{error_id}/analyze", headers=headers)

    result = await client.get(f"/errors/{error_id}/analysis", headers=headers)
    analysis_id = result.json()["analysis"]["id"]
    return error_id, analysis_id


# ---------------------------------------------------------------------------
# GET /history — list
# ---------------------------------------------------------------------------

class TestListHistory:
    async def test_empty_list_when_no_analyses(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get("/history", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["page"] == 1

    async def test_returns_own_analyses(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        await _create_analyzed_error(client, auth_headers)

        resp = await client.get("/history", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

        item = body["items"][0]
        assert item["error_title"] == _ERROR["title"]
        assert item["summary"] == "Missing key in dict."
        assert item["ai_model"] == "claude-sonnet-4-6"
        assert item["tokens_used"] == 180
        assert "id" in item
        assert "error_id" in item
        assert "created_at" in item

    async def test_does_not_return_other_users_analyses(
        self,
        client: AsyncClient,
        auth_headers: dict,
        second_auth_headers: dict,
        patch_bg_session,
    ):
        """User A creates and analyzes an error. User B's history must be empty."""
        await _create_analyzed_error(client, auth_headers)

        resp = await client.get("/history", headers=second_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_pagination_splits_results(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        """Create two analyses, fetch page_size=1 to verify pagination metadata."""
        await _create_analyzed_error(client, auth_headers, _ERROR)
        await _create_analyzed_error(client, auth_headers, _ERROR_2)

        resp = await client.get("/history?page=1&page_size=1", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["pages"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 1
        assert len(body["items"]) == 1

    async def test_pagination_second_page(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        await _create_analyzed_error(client, auth_headers, _ERROR)
        await _create_analyzed_error(client, auth_headers, _ERROR_2)

        resp = await client.get("/history?page=2&page_size=1", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert len(body["items"]) == 1

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.get("/history")
        assert resp.status_code == 403

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/history", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /history/{analysis_id} — detail
# ---------------------------------------------------------------------------

class TestGetHistoryItem:
    async def test_returns_full_analysis_detail(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        error_id, analysis_id = await _create_analyzed_error(client, auth_headers)

        resp = await client.get(f"/history/{analysis_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["id"] == analysis_id
        assert body["error_id"] == error_id
        assert body["error_title"] == _ERROR["title"]
        assert body["summary"] == "Missing key in dict."
        assert body["root_cause"] == "'user_id' key is absent from the request payload."
        assert len(body["suggestions"]) == 1
        assert body["ai_model"] == "claude-sonnet-4-6"
        assert body["tokens_used"] == 180
        assert body["duration_ms"] == 900
        assert "created_at" in body

    async def test_nonexistent_id_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/history/00000000-0000-0000-0000-000000000000",
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
        _, analysis_id = await _create_analyzed_error(client, auth_headers)

        resp = await client.get(
            f"/history/{analysis_id}", headers=second_auth_headers
        )
        assert resp.status_code == 404

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.get("/history/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /history/{analysis_id}
# ---------------------------------------------------------------------------

class TestDeleteHistoryItem:
    async def test_delete_returns_204(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        _, analysis_id = await _create_analyzed_error(client, auth_headers)

        resp = await client.delete(f"/history/{analysis_id}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_deleted_item_not_in_list(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        _, analysis_id = await _create_analyzed_error(client, auth_headers)

        await client.delete(f"/history/{analysis_id}", headers=auth_headers)

        resp = await client.get("/history", headers=auth_headers)
        assert resp.json()["total"] == 0

    async def test_deleted_item_get_returns_404(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        _, analysis_id = await _create_analyzed_error(client, auth_headers)

        await client.delete(f"/history/{analysis_id}", headers=auth_headers)

        resp = await client.get(f"/history/{analysis_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_delete_resets_error_to_pending(
        self, client: AsyncClient, auth_headers: dict, patch_bg_session
    ):
        """After deleting an analysis the parent error goes back to PENDING
        so it can be submitted for re-analysis."""
        error_id, analysis_id = await _create_analyzed_error(client, auth_headers)

        await client.delete(f"/history/{analysis_id}", headers=auth_headers)

        error_resp = await client.get(f"/errors/{error_id}", headers=auth_headers)
        assert error_resp.status_code == 200
        assert error_resp.json()["status"] == "pending"

    async def test_nonexistent_id_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.delete(
            "/history/00000000-0000-0000-0000-000000000000",
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
        _, analysis_id = await _create_analyzed_error(client, auth_headers)

        resp = await client.delete(
            f"/history/{analysis_id}", headers=second_auth_headers
        )
        assert resp.status_code == 404

    async def test_no_token_returns_403(self, client: AsyncClient):
        resp = await client.delete("/history/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 403
