import pytest
from httpx import AsyncClient

_ERROR = {
    "title": "NullPointerException",
    "raw_error": "java.lang.NullPointerException at com.example.Service.process(Service.java:42)",
}


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

class TestSubmitError:
    async def test_returns_201_with_detail(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/errors", json=_ERROR, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "NullPointerException"
        assert body["status"] == "pending"
        assert "id" in body
        assert "user_id" in body

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.post("/errors", json=_ERROR)
        assert resp.status_code == 403

    async def test_blank_title_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/errors",
            json={"title": "   ", "raw_error": "error text"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_whitespace_only_title_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/errors",
            json={"title": "\t\n", "raw_error": "error text"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_missing_raw_error_returns_422(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/errors",
            json={"title": "Error title"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_with_context_stores_metadata(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/errors",
            json={**_ERROR, "context": {"env": "production", "service": "auth"}},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["context"]["env"] == "production"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListErrors:
    async def test_empty_returns_zero_total(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/errors", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    async def test_returns_all_submitted_errors(self, client: AsyncClient, auth_headers: dict):
        await client.post("/errors", json=_ERROR, headers=auth_headers)
        await client.post("/errors", json={**_ERROR, "title": "Second"}, headers=auth_headers)

        resp = await client.get("/errors", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_only_own_errors_returned(
        self,
        client: AsyncClient,
        auth_headers: dict,
        second_auth_headers: dict,
    ):
        await client.post("/errors", json=_ERROR, headers=auth_headers)

        resp = await client.get("/errors", headers=second_auth_headers)
        assert resp.json()["total"] == 0

    async def test_pagination(self, client: AsyncClient, auth_headers: dict):
        for i in range(5):
            await client.post(
                "/errors", json={**_ERROR, "title": f"Error {i}"}, headers=auth_headers
            )

        page1 = await client.get("/errors?page=1&page_size=2", headers=auth_headers)
        page2 = await client.get("/errors?page=2&page_size=2", headers=auth_headers)

        assert page1.status_code == 200
        assert len(page1.json()["items"]) == 2
        assert page1.json()["total"] == 5
        assert page1.json()["pages"] == 3
        # Items on page 1 and page 2 are distinct
        ids_p1 = {item["id"] for item in page1.json()["items"]}
        ids_p2 = {item["id"] for item in page2.json()["items"]}
        assert ids_p1.isdisjoint(ids_p2)


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

class TestGetError:
    async def test_returns_full_detail(self, client: AsyncClient, auth_headers: dict):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        resp = await client.get(f"/errors/{error_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == error_id
        assert resp.json()["raw_error"] == _ERROR["raw_error"]

    async def test_not_found_returns_404(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/errors/00000000-0000-0000-0000-000000000000", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_other_users_error_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict,
        second_auth_headers: dict,
    ):
        """
        Ownership enforcement: wrong owner gets 404, not 403.
        Returning 403 would confirm the resource exists, enabling enumeration.
        """
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        resp = await client.get(f"/errors/{error_id}", headers=second_auth_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteError:
    async def test_returns_204(self, client: AsyncClient, auth_headers: dict):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        resp = await client.delete(f"/errors/{error_id}", headers=auth_headers)
        assert resp.status_code == 204

    async def test_deleted_error_not_found(self, client: AsyncClient, auth_headers: dict):
        create = await client.post("/errors", json=_ERROR, headers=auth_headers)
        error_id = create.json()["id"]

        await client.delete(f"/errors/{error_id}", headers=auth_headers)

        resp = await client.get(f"/errors/{error_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_not_found_returns_404(self, client: AsyncClient, auth_headers: dict):
        resp = await client.delete(
            "/errors/00000000-0000-0000-0000-000000000000", headers=auth_headers
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

        resp = await client.delete(f"/errors/{error_id}", headers=second_auth_headers)
        assert resp.status_code == 404
        # Original owner can still access it
        assert (await client.get(f"/errors/{error_id}", headers=auth_headers)).status_code == 200
