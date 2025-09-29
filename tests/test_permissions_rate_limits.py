import os
import pytest
import httpx

from src.backend.app.main import app
from src.backend.app.core.config import get_settings
from tests.conftest import auth_headers

@pytest.mark.asyncio
async def test_non_admin_cannot_create_tag():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Register normal user
        r = await client.post("/auth/register", json={
            "handle": "charlie",
            "email": "charlie@example.com",
            "password": "Char12345"
        })
        assert r.status_code == 200, r.text
        # Login
        r = await client.post("/auth/login", json={
            "handle_or_email": "charlie",
            "password": "Char12345"
        })
        assert r.status_code == 200
        token = r.json()["access_token"]

        # Attempt to create tag -> should be 403
        r = await client.post(
            "/tags",
            headers=auth_headers(client, token),
            json={"label": "PrivateTag"},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_rate_limit_posts_and_replies():
    settings = get_settings()
    max_posts = settings.default_max_posts_per_day
    max_replies = settings.default_max_replies_per_day

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Register
        r = await client.post("/auth/register", json={
            "handle": "ratelimit1",
            "email": "rl1@example.com",
            "password": "Rl1pass123"
        })
        assert r.status_code == 200, r.text
        # Login
        r = await client.post("/auth/login", json={
            "handle_or_email": "ratelimit1",
            "password": "Rl1pass123"
        })
        assert r.status_code == 200
        token = r.json()["access_token"]

        # Create posts until limit
        created_ids = []
        for i in range(max_posts):
            r = await client.post(
                "/posts",
                headers=auth_headers(client, token),
                json={
                    "title": f"P{i}",
                    "body_md": "body",
                    "lang": "en",
                    "visibility": "logged_in",
                },
            )
            assert r.status_code == 200, r.text
            created_ids.append(r.json()["id"])
        # Next should be 429
        r = await client.post(
            "/posts",
            headers=auth_headers(client, token),
            json={
                "title": "overflow",
                "body_md": "body",
                "lang": "en",
                "visibility": "logged_in",
            },
        )
        assert r.status_code == 429, r.text
        j = r.json()
        assert "error" in j and j["error"]["status"] == 429

        # Replies rate limit: use first created post
        post_id = created_ids[0]
        for i in range(max_replies):
            r = await client.post(
                "/posts/reply",
                headers=auth_headers(client, token),
                json={
                    "post_id": post_id,
                    "body_md": f"R{i}",
                    "lang": "en",
                },
            )
            assert r.status_code == 200, (i, r.text)
        r = await client.post(
            "/posts/reply",
            headers=auth_headers(client, token),
            json={
                "post_id": post_id,
                "body_md": "overflow",
                "lang": "en",
            },
        )
        assert r.status_code == 429, r.text
        j = r.json()
        assert "error" in j and j["error"]["status"] == 429
