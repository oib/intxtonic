import pytest
import httpx
from src.backend.app.main import app
from tests.conftest import auth_headers

@pytest.mark.asyncio
async def test_register_login_me_and_create_post():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Register
        r = await client.post("/auth/register", json={
            "handle": "alice",
            "email": "alice@intxtonic.net",
            "password": "test1234"
        })
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]

        # Login
        r = await client.post("/auth/login", json={
            "handle_or_email": "alice",
            "password": "test1234"
        })
        assert r.status_code == 200, r.text
        token2 = r.json()["access_token"]
        assert token2

        # Me
        r = await client.get("/auth/me", headers=auth_headers(client, token2))
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["handle"] == "alice"

        # Create post
        r = await client.post("/posts", headers=auth_headers(client, token2), json={
            "title": "Hello World",
            "body_md": "This is my first post",
            "lang": "en",
            "visibility": "logged_in"
        })
        assert r.status_code == 200, r.text
        post_id = r.json()["id"]
        assert post_id

        # List posts (should contain the new one)
        r = await client.get("/posts?limit=5&offset=0&sort=newest")
        assert r.status_code == 200, r.text
        page = r.json()
        assert isinstance(page, dict)
        items = page.get("items", [])
        assert any(p["id"] == post_id for p in items)

        # Vote up
        r = await client.post("/posts/vote", headers=auth_headers(client, token2), json={
            "target_type": "post",
            "target_id": post_id,
            "value": 1
        })
        assert r.status_code == 200, r.text
