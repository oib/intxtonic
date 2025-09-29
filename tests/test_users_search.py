import pytest
import asyncio
import json
import os
from uuid import uuid4
import psycopg
from httpx import AsyncClient
from fastapi import FastAPI
import pytest_asyncio

from src.backend.app.main import app
from tests.conftest import auth_headers

# Use pytest-asyncio for async tests
pytestmark = pytest.mark.asyncio

# Fixture for async HTTP client
DB_DSN = "postgresql://{user}:{password}@{host}:{port}/{db}".format(
    user=os.getenv("DB_USER", "langsum"),
    password=os.getenv("DB_PASSWORD", "password"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    db=os.getenv("DB_NAME", "langsum"),
)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


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


async def ensure_authenticated_headers(client: AsyncClient, *, handle: str | None = None, password: str | None = None) -> dict:
    handle = handle or f"searchuser_{uuid4().hex[:8]}"
    password = password or "Search123!"
    register_resp = await client.post(
        "/auth/register",
        json={"handle": handle, "email": f"{handle}@intxtonic.net", "password": password},
    )
    assert register_resp.status_code in (200, 409), register_resp.text
    login_resp = await client.post(
        "/auth/login",
        json={"handle_or_email": handle, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return auth_headers(client, token)


# Test users endpoints
async def test_get_user(client: AsyncClient):
    headers = await ensure_authenticated_headers(client)
    response = await client.get("/users/testuser", headers=headers)
    assert response.status_code == 404  # Assuming testuser doesn't exist initially
    # Future: Add a test user creation and then test retrieval

async def test_get_user_posts(client: AsyncClient):
    headers = await ensure_authenticated_headers(client)
    response = await client.get("/users/testuser/posts", headers=headers)
    assert response.status_code == 404  # Assuming testuser doesn't exist initially
    # Future: Add a test user with posts and then test retrieval

async def test_get_user_replies(client: AsyncClient):
    headers = await ensure_authenticated_headers(client)
    response = await client.get("/users/testuser/replies", headers=headers)
    assert response.status_code == 404  # Assuming testuser doesn't exist initially
    # Future: Add a test user with replies and then test retrieval

# Test search functionality with multiple tags
async def test_search_posts_multiple_tags(client: AsyncClient):
    # Assuming some posts with tags exist or need to be created
    admin_handle = "tagadmin"
    admin_password = "TagAdmin123"
    register_resp = await client.post(
        "/auth/register",
        json={"handle": admin_handle, "email": f"{admin_handle}@intxtonic.net", "password": admin_password},
    )
    assert register_resp.status_code == 200, register_resp.text
    await promote_to_admin(admin_handle)
    login_resp = await client.post(
        "/auth/login",
        json={"handle_or_email": admin_handle, "password": admin_password},
    )
    assert login_resp.status_code == 200, login_resp.text
    admin_token = login_resp.json()["access_token"]
    admin_headers = auth_headers(client, admin_token)
    for label in ("Tag1", "Tag2"):
        resp = await client.post(
            "/tags",
            headers=admin_headers,
            json={"label": label},
        )
        assert resp.status_code in (200, 201), resp.text

    headers = await ensure_authenticated_headers(client)
    response = await client.get("/posts?tag=tag1&tag=tag2", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # Future: Create posts with specific tags and assert that only posts with all specified tags are returned
    # For now, just check if the endpoint responds correctly
    assert isinstance(data["items"], list)

# Placeholder for additional test setup (like creating test users or posts)
# async def setup_test_data():
#     # Create test user, posts, tags, etc.
#     pass

if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))
