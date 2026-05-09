"""Rate limiting and resilience for Ground News HTTP requests.

Three layers:
1. Token bucket — minimum interval between requests (default 2s)
2. Exponential backoff on 429/503
3. Circuit breaker — short-circuit after consecutive failures
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

import requests

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RateLimitConfig:
    min_interval: float = 2.0  # seconds between requests
    max_retries: int = 3
    backoff_base: float = 4.0  # 4s, 8s, 16s
    breaker_threshold: int = 3  # consecutive failures before tripping
    breaker_cooldown: float = 300.0  # seconds open before half-opening


DEFAULT_CONFIG = RateLimitConfig()


class CircuitOpen(Exception):
    """Raised when the circuit breaker is open (too many recent failures)."""


class _State:
    """Process-wide state for the rate limiter."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_request_at = 0.0
        self.consecutive_failures = 0
        self.breaker_opened_at: float | None = None


_state = _State()


def _wait_for_token(min_interval: float) -> None:
    """Sleep until min_interval has passed since the last request."""
    with _state.lock:
        now = time.monotonic()
        wait = (_state.last_request_at + min_interval) - now
        _state.last_request_at = max(now, _state.last_request_at + min_interval)
    if wait > 0:
        logger.debug("Rate limit: sleeping %.2fs", wait)
        time.sleep(wait)


def _check_breaker(cfg: RateLimitConfig) -> None:
    """Raise CircuitOpen if the breaker is tripped and still cooling down."""
    with _state.lock:
        if _state.breaker_opened_at is None:
            return
        elapsed = time.monotonic() - _state.breaker_opened_at
        if elapsed < cfg.breaker_cooldown:
            remaining = cfg.breaker_cooldown - elapsed
            raise CircuitOpen(
                f"Circuit breaker open for {remaining:.0f}s more "
                f"(after {_state.consecutive_failures} consecutive failures)"
            )
        # Half-open: reset and let the next call try
        logger.info("Circuit breaker entering half-open state")
        _state.breaker_opened_at = None
        _state.consecutive_failures = 0


def _record_success() -> None:
    with _state.lock:
        _state.consecutive_failures = 0
        _state.breaker_opened_at = None


def _record_failure(cfg: RateLimitConfig) -> None:
    with _state.lock:
        _state.consecutive_failures += 1
        if (
            _state.consecutive_failures >= cfg.breaker_threshold
            and _state.breaker_opened_at is None
        ):
            _state.breaker_opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker tripped after %d consecutive failures",
                _state.consecutive_failures,
            )


def call_with_limits(
    fn: Callable[[], requests.Response],
    cfg: RateLimitConfig = DEFAULT_CONFIG,
) -> requests.Response:
    """Execute a request callable under rate-limit + retry + breaker policy.

    Retries on HTTP 429 and 503 with exponential backoff. Honors the
    Retry-After header when present.
    """
    _check_breaker(cfg)

    last_exc: Exception | None = None
    for attempt in range(cfg.max_retries + 1):
        _wait_for_token(cfg.min_interval)
        try:
            response = fn()
        except requests.RequestException as exc:
            last_exc = exc
            wait = cfg.backoff_base * (2**attempt)
            logger.warning(
                "Request error (attempt %d): %s — waiting %.1fs", attempt + 1, exc, wait
            )
            time.sleep(wait)
            continue

        if response.status_code in (429, 503):
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = float(retry_after)
            else:
                wait = cfg.backoff_base * (2**attempt)
            logger.warning(
                "HTTP %d on attempt %d — backing off %.1fs",
                response.status_code,
                attempt + 1,
                wait,
            )
            if attempt < cfg.max_retries:
                time.sleep(wait)
                continue
            # Out of retries
            _record_failure(cfg)
            response.raise_for_status()

        if not response.ok:
            _record_failure(cfg)
            response.raise_for_status()

        _record_success()
        return response

    _record_failure(cfg)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Exhausted retries with no response")


def reset_state() -> None:
    """Reset rate-limiter state. Used in tests."""
    with _state.lock:
        _state.last_request_at = 0.0
        _state.consecutive_failures = 0
        _state.breaker_opened_at = None
