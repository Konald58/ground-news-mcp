"""React Server Components (RSC) payload fetcher + parser for Ground News.

Ground News uses Next.js App Router with server-side rendering. By passing
the `RSC: 1` header, we receive the underlying RSC payload (Content-Type:
text/x-component) — structured JSON data instead of rendered HTML.

The payload is a stream of `<hex_id>:<value>\\n` lines. Most values are
JSON literals. We walk the parsed JSON trees to extract story and source
data using stable field names from Ground News's data model.

This is dramatically more reliable than HTML scraping: we depend on
backend property names (which match their data model) rather than CSS
classes or text-proximity heuristics that change every deploy.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any
from urllib.parse import urlparse

import requests

from .ratelimit import call_with_limits

logger = logging.getLogger(__name__)

BASE_URL = "https://ground.news"
USER_AGENT = "ground-news-mcp/0.1 (+https://github.com/Konald58/ground-news-mcp)"
REQUEST_TIMEOUT = 20

# Process-wide TTL cache: {url: (timestamp, parsed_data)}.
# Thread-safe via _cache_lock — concurrent MCP tool calls for the same URL
# would otherwise race on TOCTOU between the read and the write.
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 300  # 5 minutes

# Defensive caps against malicious/malformed payloads.
# Real article payloads top out around 2.5 MB; 8 MB is a generous ceiling.
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
# Most articles have ~50-150 chunks; cap stops a degenerate payload from
# triggering thousands of failed JSON parses.
MAX_JSON_CHUNKS = 2000
# Recursion ceiling for tree walks. RSC trees are typically <30 deep.
MAX_WALK_DEPTH = 200
# Field-length caps on strings flowing back to Claude (prompt-injection defense).
MAX_STRING_FIELD = 2048
# Slug must look like a slug — no path traversal characters.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,200}$")


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def slug_from_url(url_or_slug: str) -> str:
    """Extract slug from a Ground News article URL or pass through a bare slug.

    The returned slug is allowlist-validated to prevent path traversal or
    URL-injection through the user-controlled argument.
    """
    if not url_or_slug or not url_or_slug.strip():
        raise ValueError("Empty slug or URL")
    if url_or_slug.startswith("http"):
        path = urlparse(url_or_slug).path
        m = re.match(r"/article/(.+)", path)
        if not m:
            raise ValueError(f"Not a Ground News article URL: {url_or_slug}")
        slug = m.group(1)
    else:
        slug = url_or_slug.lstrip("/").removeprefix("article/")
    if not _SLUG_RE.match(slug):
        raise ValueError(f"Invalid slug: {slug!r}")
    return slug


def topic_slug(query: str) -> str:
    """Normalize a query string to a Ground News interest slug."""
    slug = query.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def article_url(slug_or_url: str) -> str:
    return f"{BASE_URL}/article/{slug_from_url(slug_or_url)}"


def interest_url(topic: str) -> str:
    return f"{BASE_URL}/interest/{topic_slug(topic)}"


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    headers = {
        "RSC": "1",
        "Accept": "text/x-component",
        "User-Agent": USER_AGENT,
    }
    cookie = os.environ.get("GN_SESSION_COOKIE")
    if cookie:
        headers["Cookie"] = cookie
    return headers


def fetch_rsc(url: str) -> str:
    """Fetch the RSC payload for a Ground News URL.

    Rate-limited via the central ratelimit module. Caching happens at the
    parsed-data layer (`get_article_data` / `get_interest_data`), not here —
    raw text caching would double memory cost for the same hit rate.
    """
    logger.info("Fetching RSC: %s", url)
    response = call_with_limits(
        lambda: requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    )
    # Next.js streams RSC as UTF-8 but the text/x-component response carries no
    # charset, so requests falls back to latin-1 and mangles non-ASCII outlet
    # names (Cyrillic, Korean, …). Force UTF-8 before decoding.
    response.encoding = "utf-8"
    text = response.text
    if len(text) > MAX_PAYLOAD_BYTES:
        logger.warning(
            "Payload size %d exceeds cap %d — truncating", len(text), MAX_PAYLOAD_BYTES
        )
        text = text[:MAX_PAYLOAD_BYTES]
    return text


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Next.js streams multiple chunks per "line" without newline separators.
# Each chunk starts with a hex id + colon followed by a typed payload:
#   T<lenHex>,<text>  — text data (length-prefixed)
#   I[...]            — component import
#   HL[...]           — head link
#   H<json>           — hint
#   <json>            — data ({, [, ", number, null, true, false)
#
# We don't need to parse text/import/HL chunks. We only need JSON chunks
# that contain story or source data, so we scan for `<hex>:` markers
# followed by a JSON-start character and use raw_decode to extract one
# JSON value at a time.

_JSON_CHUNK_START = re.compile(r"(?:^|[^a-zA-Z0-9])([0-9a-fA-F]+):([\[{])")
_DECODER = json.JSONDecoder()


def _iter_json_values(payload: str):
    """Yield the parsed JSON value for each RSC JSON chunk in the payload.

    Uses json.JSONDecoder.raw_decode to read one JSON value at a time
    starting from each `<hex>:` marker followed by `{` or `[`. This is
    robust to chunks being concatenated without newline separators and
    to JSON strings containing real newline bytes.

    Stops yielding after MAX_JSON_CHUNKS to bound CPU on degenerate input.
    """
    yielded = 0
    for m in _JSON_CHUNK_START.finditer(payload):
        if yielded >= MAX_JSON_CHUNKS:
            logger.warning("Hit chunk cap (%d) — stopping parse", MAX_JSON_CHUNKS)
            return
        start = m.start(2)  # position of the JSON-start char
        try:
            value, _end = _DECODER.raw_decode(payload, start)
        except json.JSONDecodeError:
            continue
        yielded += 1
        yield value


def _walk(node: Any, predicates: list, buckets: list[list]) -> None:
    """Iterative DFS — for each predicate in `predicates`, append matches
    to `buckets[i]`. Bounded by MAX_WALK_DEPTH to prevent stack blowups
    on deeply nested or maliciously crafted payloads.
    """
    stack: list[tuple[Any, int]] = [(node, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_WALK_DEPTH:
            continue
        if isinstance(current, dict):
            for i, pred in enumerate(predicates):
                if pred(current):
                    buckets[i].append(current)
            # Push children
            for v in current.values():
                if isinstance(v, dict | list):
                    stack.append((v, depth + 1))
        elif isinstance(current, list):
            for v in current:
                if isinstance(v, dict | list):
                    stack.append((v, depth + 1))


def _find_many(payload: str, predicates: list) -> list[list[dict]]:
    """Single-pass over the payload that fills one bucket per predicate.

    Replaces what used to be two full payload scans (one for the story
    object, one for source articles).
    """
    buckets: list[list[dict]] = [[] for _ in predicates]
    for value in _iter_json_values(payload):
        _walk(value, predicates, buckets)
    return buckets


# ---------------------------------------------------------------------------
# Public extractors
# ---------------------------------------------------------------------------


def _is_story(d: dict) -> bool:
    return "biasSourceCount" in d and "slug" in d


def _is_source(d: dict) -> bool:
    sort_data = d.get("sortData")
    if not isinstance(sort_data, dict):
        return False
    bias = sort_data.get("bias")
    return (
        isinstance(bias, dict) and "labelData" in bias and "url" in d and "title" in d
    )


def _is_story_card(d: dict) -> bool:
    return (
        "slug" in d
        and "title" in d
        and ("sourceCount" in d or "biasSourceCount" in d)
        and "biasRatings" not in d  # exclude source-info objects
    )


def parse_article(payload: str) -> dict[str, Any]:
    """Extract structured story + sources data from an article RSC payload.

    Single-pass scan: collects both the story object and all source
    article objects in one walk.
    """
    stories, sources = _find_many(payload, [_is_story, _is_source])
    if not stories:
        raise ValueError("No article data found in RSC payload")
    return {"story": stories[0], "sources": sources}


def parse_interest(payload: str) -> dict[str, Any]:
    """Extract a list of story cards from an interest/topic RSC payload."""
    (cards,) = _find_many(payload, [_is_story_card])
    seen: set[str] = set()
    unique = []
    for c in cards:
        slug = c.get("slug")
        if slug and slug not in seen:
            seen.add(slug)
            unique.append(c)
    return {"stories": unique}


# ---------------------------------------------------------------------------
# Cached fetch+parse helpers (the public API for scraper.py)
# ---------------------------------------------------------------------------


def _cache_get(url: str) -> dict[str, Any] | None:
    with _cache_lock:
        entry = _cache.get(url)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts >= CACHE_TTL:
        return None
    logger.debug("Cache hit: %s", url)
    return data


def _cache_put(url: str, data: dict[str, Any]) -> None:
    with _cache_lock:
        _cache[url] = (time.monotonic(), data)


def get_article_data(url_or_slug: str) -> dict[str, Any]:
    """Fetch + parse an article. TTL-cached, thread-safe."""
    url = article_url(url_or_slug)
    cached = _cache_get(url)
    if cached is not None:
        return cached
    payload = fetch_rsc(url)
    data = parse_article(payload)
    _cache_put(url, data)
    return data


def get_interest_data(topic: str) -> dict[str, Any]:
    """Fetch + parse an interest page. TTL-cached, thread-safe."""
    url = interest_url(topic)
    cached = _cache_get(url)
    if cached is not None:
        return cached
    payload = fetch_rsc(url)
    data = parse_interest(payload)
    _cache_put(url, data)
    return data


def clear_cache() -> None:
    """Clear the in-memory cache. Used in tests."""
    with _cache_lock:
        _cache.clear()
