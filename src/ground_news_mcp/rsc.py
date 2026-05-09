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
import time
from typing import Any
from urllib.parse import urlparse

import requests

from .ratelimit import call_with_limits

logger = logging.getLogger(__name__)

BASE_URL = "https://ground.news"
USER_AGENT = "ground-news-mcp/0.1 (+https://github.com/Konald58/ground-news-mcp)"
REQUEST_TIMEOUT = 20

# Process-wide TTL cache: {url: (timestamp, parsed_data)}
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
CACHE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def slug_from_url(url_or_slug: str) -> str:
    """Extract slug from a Ground News article URL or pass through a bare slug."""
    if url_or_slug.startswith("http"):
        path = urlparse(url_or_slug).path
        m = re.match(r"/article/(.+)", path)
        if m:
            return m.group(1)
        raise ValueError(f"Not a Ground News article URL: {url_or_slug}")
    return url_or_slug.lstrip("/").removeprefix("article/")


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
    """Fetch the RSC payload for a Ground News URL. Cached + rate-limited."""
    now = time.monotonic()
    if url in _cache:
        ts, _ = _cache[url]
        if now - ts < CACHE_TTL:
            logger.debug("Cache hit (raw): %s", url)
            # Re-fetch is rare; keep the parsed cache below as the primary cache
    logger.info("Fetching RSC: %s", url)
    response = call_with_limits(
        lambda: requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
    )
    return response.text


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
    """
    for m in _JSON_CHUNK_START.finditer(payload):
        start = m.start(2)  # position of the JSON-start char
        try:
            value, _end = _DECODER.raw_decode(payload, start)
        except json.JSONDecodeError:
            continue
        yield value


def _walk(node: Any, predicate, out: list):
    """Depth-first walk yielding nodes that satisfy predicate(node)."""
    if isinstance(node, dict):
        if predicate(node):
            out.append(node)
        for v in node.values():
            _walk(v, predicate, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, predicate, out)


def _find_first(payload: str, predicate) -> dict | None:
    for value in _iter_json_values(payload):
        out: list = []
        _walk(value, predicate, out)
        if out:
            return out[0]
    return None


def _find_all(payload: str, predicate) -> list[dict]:
    matches: list[dict] = []
    for value in _iter_json_values(payload):
        _walk(value, predicate, matches)
    return matches


# ---------------------------------------------------------------------------
# Public extractors
# ---------------------------------------------------------------------------


def parse_article(payload: str) -> dict[str, Any]:
    """Extract structured story + sources data from an article RSC payload."""
    story = _find_first(payload, lambda d: "biasSourceCount" in d and "slug" in d)
    if story is None:
        raise ValueError("No article data found in RSC payload")

    # Sources are dicts with sortData.bias.labelData and a url
    def is_source(d: dict) -> bool:
        sort_data = d.get("sortData")
        if not isinstance(sort_data, dict):
            return False
        bias = sort_data.get("bias")
        return (
            isinstance(bias, dict)
            and "labelData" in bias
            and "url" in d
            and "title" in d
        )

    sources = _find_all(payload, is_source)

    return {
        "story": story,
        "sources": sources,
    }


def parse_interest(payload: str) -> dict[str, Any]:
    """Extract a list of story cards from an interest/topic RSC payload."""

    def is_story_card(d: dict) -> bool:
        # Story cards have slug + title + sourceCount but NOT the deep source list
        return (
            "slug" in d
            and "title" in d
            and ("sourceCount" in d or "biasSourceCount" in d)
            and "biasRatings" not in d  # exclude source-info objects
        )

    cards = _find_all(payload, is_story_card)
    # Deduplicate by slug
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


def get_article_data(url_or_slug: str) -> dict[str, Any]:
    """Fetch + parse an article. TTL-cached."""
    url = article_url(url_or_slug)
    now = time.monotonic()
    if url in _cache:
        ts, data = _cache[url]
        if now - ts < CACHE_TTL:
            logger.debug("Cache hit: %s", url)
            return data
    payload = fetch_rsc(url)
    data = parse_article(payload)
    _cache[url] = (now, data)
    return data


def get_interest_data(topic: str) -> dict[str, Any]:
    """Fetch + parse an interest page. TTL-cached."""
    url = interest_url(topic)
    now = time.monotonic()
    if url in _cache:
        ts, data = _cache[url]
        if now - ts < CACHE_TTL:
            logger.debug("Cache hit: %s", url)
            return data
    payload = fetch_rsc(url)
    data = parse_interest(payload)
    _cache[url] = (now, data)
    return data


def clear_cache() -> None:
    """Clear the in-memory cache. Used in tests."""
    _cache.clear()
