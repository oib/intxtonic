import os
import asyncio
import pytest
import httpx
import psycopg

from src.backend.app.main import app
from tests.conftest import auth_headers

DB_DSN = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
    user=os.getenv("DB_USER", "langsum"),
    password=os.getenv("DB_PASSWORD", "password"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    db=os.getenv("DB_NAME", "langsum"),
)


async def promote_to_admin(account_handle: str):
    def _work():
        with psycopg.connect(DB_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM app.accounts WHERE lower(handle)=lower(%s)", (account_handle,))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("account not found")
                account_id = row[0]
                cur.execute("SELECT id FROM app.roles WHERE name='admin' LIMIT 1")
                role_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO app.account_roles (account_id, role_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """,
                    (account_id, role_id),
                )
                conn.commit()
    await asyncio.to_thread(_work)


@pytest.mark.asyncio
async def test_posts_include_tags_and_filtering():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Create admin user
        r = await client.post("/auth/register", json={
            "handle": "tagadmin",
            "email": "tagadmin@intxtonic.net",
            "password": "TagAdmin123"
        })
        assert r.status_code == 200, r.text
        await promote_to_admin("tagadmin")
        r = await client.post("/auth/login", json={
            "handle_or_email": "tagadmin",
            "password": "TagAdmin123"
        })
        assert r.status_code == 200
        admin_token = r.json()["access_token"]

        # Create a tag as admin
        r = await client.post(
            "/tags",
            headers=auth_headers(client, admin_token),
            json={"label": "Tech"},
        )
        assert r.status_code in (200, 201), r.text
        tag = r.json()
        slug = tag["slug"]

        # Create 2 posts (user bob)
        r = await client.post("/auth/register", json={
            "handle": "tagbob",
            "email": "tagbob@intxtonic.net",
            "password": "TagBob123"
        })
        assert r.status_code == 200
        r = await client.post("/auth/login", json={
            "handle_or_email": "tagbob",
            "password": "TagBob123"
        })
        assert r.status_code == 200
        bob_token = r.json()["access_token"]

        r = await client.post(
            "/posts",
            headers=auth_headers(client, bob_token),
            json={
                "title": "First",
                "body_md": "first body",
                "lang": "en",
                "visibility": "logged_in",
            },
        )
        assert r.status_code == 200
        post1 = r.json()["id"]

        r = await client.post(
            "/posts",
            headers=auth_headers(client, bob_token),
            json={
                "title": "Second",
                "body_md": "second body",
                "lang": "en",
                "visibility": "logged_in",
            },
        )
        assert r.status_code == 200
        post2 = r.json()["id"]

        # Attach tag to first post (admin)
        r = await client.post(
            f"/posts/{post1}/tags",
            headers=auth_headers(client, admin_token),
            json={"slug": slug},
        )
        assert r.status_code == 200, r.text

        # Get /posts and ensure tags are inline
        r = await client.get("/posts?limit=10&offset=0")
        assert r.status_code == 200, r.text
        page = r.json()
        items = page.get("items", []) if isinstance(page, dict) else page
        assert any(p["id"] == post1 and any(t["slug"] == slug for t in (p.get("tags") or [])) for p in items)

        # Filter by tag -> should include post1, exclude post2
        r = await client.get(f"/posts?tag={slug}")
        assert r.status_code == 200
        page = r.json()
        items = page.get("items", []) if isinstance(page, dict) else page
        assert any(p["id"] == post1 for p in items)
        assert not any(p["id"] == post2 for p in items)
