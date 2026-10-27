import asyncio

import pytest

from src.backend.app.api.auth import (
    AUTH_FAIL_ACCT_LIMIT,
    AUTH_FAIL_IP_LIMIT,
    AUTH_FAIL_WINDOW_S,
    AUTH_TOKEN_IP_LIMIT,
    _auth_clear,
    _auth_count,
    _auth_hit,
    _auth_require_below,
)
from fastapi import HTTPException


def run(coro):
    return asyncio.run(coro)


class FakeRedis:
    """Minimal async redis stand-in covering the commands the throttle uses."""

    def __init__(self):
        self.store = {}
        self.expiries = {}

    async def get(self, key):
        return self.store.get(key)

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key) or 0) + 1)
        return int(self.store[key])

    async def expire(self, key, seconds):
        self.expiries[key] = seconds
        return True

    async def delete(self, *keys):
        n = 0
        for k in keys:
            n += self.store.pop(k, None) is not None
            self.expiries.pop(k, None)
        return n

    async def exists(self, key):
        return key in self.store


def test_hit_increments_and_sets_window():
    r = FakeRedis()
    run(_auth_hit(r, "k"))
    run(_auth_hit(r, "k"))
    assert run(_auth_count(r, "k")) == 2
    assert r.expiries["k"] == AUTH_FAIL_WINDOW_S


def test_require_below_raises_429_at_limit():
    r = FakeRedis()
    for _ in range(AUTH_FAIL_IP_LIMIT):
        run(_auth_hit(r, "ip"))
    with pytest.raises(HTTPException) as exc:
        run(_auth_require_below(r, "ip", AUTH_FAIL_IP_LIMIT))
    assert exc.value.status_code == 429
    # account key has its own limit and namespace
    assert run(_auth_count(r, "acct")) == 0


def test_clear_resets_counters():
    r = FakeRedis()
    run(_auth_hit(r, "ip"))
    run(_auth_hit(r, "acct"))
    run(_auth_clear(r, "ip", "acct"))
    assert run(_auth_count(r, "ip")) == 0
    assert run(_auth_count(r, "acct")) == 0


def test_no_redis_degrades_to_allow_all():
    assert run(_auth_count(None, "k")) == 0
    run(_auth_hit(None, "k"))                 # no-op, must not raise
    run(_auth_clear(None, "k"))               # no-op, must not raise
    run(_auth_require_below(None, "k", 1))    # must not raise


def test_token_window_has_own_limit():
    r = FakeRedis()
    for _ in range(AUTH_TOKEN_IP_LIMIT):
        run(_auth_hit(r, "tok"))
    with pytest.raises(HTTPException) as exc:
        run(_auth_require_below(r, "tok", AUTH_TOKEN_IP_LIMIT))
    assert exc.value.status_code == 429
    # a different namespace at the same count still passes
    assert AUTH_FAIL_ACCT_LIMIT < AUTH_TOKEN_IP_LIMIT
