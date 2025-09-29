import pytest
import httpx
from uuid import uuid4

from src.backend.app.main import app
from src.backend.app.core.db import POOL_KEY

pytestmark = pytest.mark.asyncio


def _unique_handle(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


async def _register_user(client: httpx.AsyncClient, password: str) -> tuple[str, str, str]:
    handle = _unique_handle("pwduser")
    email = f"{handle}@example.com"
    response = await client.post(
        "/auth/register",
        json={
            "handle": handle,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return handle, body["access_token"], body["account_id"]


async def _login(client: httpx.AsyncClient, handle_or_email: str, password: str) -> httpx.Response:
    return await client.post(
        "/auth/login",
        json={"handle_or_email": handle_or_email, "password": password},
    )


async def _get_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_change_password_success():
    client = await _get_client()
    async with client:
        old_password = "OldPass123!"
        new_password = "NewPass456!"
        handle, token, _ = await _register_user(client, old_password)

        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": client.cookies.get("csrf_token", ""),
        }
        response = await client.patch(
            "/users/me/password",
            headers=headers,
            json={
                "current_password": old_password,
                "new_password": new_password,
            },
        )
        assert response.status_code == 204, response.text

        # Old password should now fail
        login_old = await _login(client, handle, old_password)
        assert login_old.status_code == 401

        # New password should work
        login_new = await _login(client, handle, new_password)
        assert login_new.status_code == 200, login_new.text


async def test_change_password_wrong_current():
    client = await _get_client()
    async with client:
        password = "WrongPass123!"
        handle, token, _ = await _register_user(client, password)

        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": client.cookies.get("csrf_token", ""),
        }
        response = await client.patch(
            "/users/me/password",
            headers=headers,
            json={
                "current_password": "totally_wrong",
                "new_password": "AnotherPass123!",
            },
        )
        assert response.status_code == 403
        data = response.json()
        error = data.get("error", {})
        assert error.get("status") == 403
        assert error.get("message") == "Current password incorrect"

        # Password remains unchanged
        login = await _login(client, handle, password)
        assert login.status_code == 200, login.text


async def test_change_password_missing_hash():
    client = await _get_client()
    async with client:
        password = "NoHashPass123!"
        handle, token, account_id = await _register_user(client, password)

        pool = getattr(app.state, POOL_KEY, None)
        assert pool is not None, "DB pool should be initialized for tests"
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE app.accounts SET password_hash=NULL WHERE id=%s",
                    (account_id,),
                )
            await conn.commit()

        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": client.cookies.get("csrf_token", ""),
        }
        response = await client.patch(
            "/users/me/password",
            headers=headers,
            json={
                "current_password": password,
                "new_password": "AnotherPass789!",
            },
        )
        assert response.status_code == 409
        data = response.json()
        error = data.get("error", {})
        assert error.get("status") == 409
        assert error.get("message") == "Password login disabled for this account"

        # Existing password no longer works because hash is missing
        login = await _login(client, handle, password)
        assert login.status_code == 401
