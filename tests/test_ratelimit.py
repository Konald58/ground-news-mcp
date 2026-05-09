"""Tests for ratelimit.py — token bucket, retry, circuit breaker."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
import requests

from ground_news_mcp import ratelimit
from ground_news_mcp.ratelimit import (
    CircuitOpen,
    RateLimitConfig,
    call_with_limits,
    reset_state,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


def _ok(status: int = 200) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = b"{}"
    return r


@pytest.mark.unit
def test_returns_successful_response_immediately():
    cfg = RateLimitConfig(min_interval=0.0, max_retries=0)
    result = call_with_limits(lambda: _ok(200), cfg)
    assert result.status_code == 200


@pytest.mark.unit
def test_retries_on_503_then_succeeds():
    cfg = RateLimitConfig(min_interval=0.0, max_retries=2, backoff_base=0.0)
    fn = MagicMock(side_effect=[_ok(503), _ok(503), _ok(200)])
    result = call_with_limits(fn, cfg)
    assert result.status_code == 200
    assert fn.call_count == 3


@pytest.mark.unit
def test_raises_after_max_retries():
    cfg = RateLimitConfig(min_interval=0.0, max_retries=1, backoff_base=0.0)
    fn = MagicMock(side_effect=[_ok(503), _ok(503)])
    with pytest.raises(requests.HTTPError):
        call_with_limits(fn, cfg)
    assert fn.call_count == 2


@pytest.mark.unit
def test_circuit_breaker_trips_after_failures():
    cfg = RateLimitConfig(
        min_interval=0.0,
        max_retries=0,
        backoff_base=0.0,
        breaker_threshold=2,
        breaker_cooldown=60.0,
    )

    def fn_fail():
        return _ok(503)

    # First two failures trip the breaker
    for _ in range(2):
        with pytest.raises(requests.HTTPError):
            call_with_limits(fn_fail, cfg)
    # Third call short-circuits before any HTTP work
    fn_check = MagicMock()
    with pytest.raises(CircuitOpen):
        call_with_limits(fn_check, cfg)
    fn_check.assert_not_called()


@pytest.mark.unit
def test_min_interval_enforced():
    cfg = RateLimitConfig(min_interval=0.1, max_retries=0)
    start = time.monotonic()
    call_with_limits(lambda: _ok(200), cfg)
    call_with_limits(lambda: _ok(200), cfg)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1


@pytest.mark.unit
def test_resets_consecutive_failures_on_success():
    cfg = RateLimitConfig(
        min_interval=0.0,
        max_retries=0,
        backoff_base=0.0,
        breaker_threshold=3,
    )
    with pytest.raises(requests.HTTPError):
        call_with_limits(lambda: _ok(503), cfg)
    call_with_limits(lambda: _ok(200), cfg)
    # Counter reset — breaker stays closed
    assert ratelimit._state.consecutive_failures == 0
