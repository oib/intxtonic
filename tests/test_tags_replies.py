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
    # Synchronous psycopg connect in a thread to keep test async simple
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
async def test_tags_admin_and_replies_flow():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Register normal user and promote to admin
        r = await client.post("/auth/register", json={
            "handle": "adminuser",
            "email": "adminuser@intxtonic.net",
            "password": "Admin1234"
        })
        assert r.status_code == 200, r.text
        await promote_to_admin("adminuser")
        # Login
        r = await client.post("/auth/login", json={
            "handle_or_email": "adminuser",
            "password": "Admin1234"
        })
        assert r.status_code == 200
        admin_token = r.json()["access_token"]

        # Create a tag (admin)
        r = await client.post(
            "/tags",
            headers=auth_headers(client, admin_token),
            json={"label": "Announcements"},
        )
        assert r.status_code in (200, 201), r.text
        tag = r.json()
        assert tag["slug"] == "announcements"

        # List tags and find it
        r = await client.get("/tags?query=ann")
        assert r.status_code == 200
        rows = r.json()
        assert any(t["id"] == tag["id"] for t in rows)

        # Ban/unban
        r = await client.post(
            f"/tags/{tag['id']}/ban",
            headers=auth_headers(client, admin_token),
        )
        assert r.status_code == 200
        r = await client.post(
            f"/tags/{tag['id']}/unban",
            headers=auth_headers(client, admin_token),
        )
        assert r.status_code == 200

        # Create a regular user to post and reply
        r = await client.post("/auth/register", json={
            "handle": "bob",
            "email": "bob@intxtonic.net",
            "password": "bob12345"
        })
        assert r.status_code == 200
        r = await client.post("/auth/login", json={
            "handle_or_email": "bob",
            "password": "bob12345"
        })
        assert r.status_code == 200
        bob_token = r.json()["access_token"]

        # Create a post
        r = await client.post(
            "/posts",
            headers=auth_headers(client, bob_token),
            json={
                "title": "Tag test post",
                "body_md": "Hello under announcements",
                "lang": "en",
                "visibility": "logged_in",
            },
        )
        assert r.status_code == 200, r.text
        post_id = r.json()["id"]

        # Create a reply
        r = await client.post(
            "/posts/reply",
            headers=auth_headers(client, bob_token),
            json={
                "post_id": post_id,
                "body_md": "Nice post!",
                "lang": "en",
            },
        )
        assert r.status_code == 200
        reply_id = r.json()["id"]

        # List replies and find
        r = await client.get(f"/posts/{post_id}/replies")
        assert r.status_code == 200
        replies = r.json()
        assert any(x["id"] == reply_id for x in replies)

        # Vote reply
        r = await client.post(
            "/posts/vote",
            headers=auth_headers(client, bob_token),
            json={
                "target_type": "reply",
                "target_id": reply_id,
                "value": 1,
            },
        )
        assert r.status_code == 200
