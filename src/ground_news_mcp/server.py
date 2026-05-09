"""MCP server exposing Ground News data extraction as tools.

Tools:
- get_story_bias        — full bias breakdown for one story
- get_topic_stories     — recent stories on an interest/topic
- get_missing_perspectives — surface the underreported side of a story
- check_content_bias    — heuristic bias check on user text
- list_outlets_by_bias  — filter a story's sources by Left/Center/Right
- get_settings / update_settings — adjust this server's behavior

Run with `ground-news-mcp` (entry point) or `python -m ground_news_mcp.server`.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import scraper, settings

logger = logging.getLogger(__name__)

mcp = FastMCP("ground-news-mcp")


def _to_dict(obj: Any) -> Any:
    """Recursively convert frozen dataclasses (and tuples of them) to plain
    JSON-serializable dicts and lists. Tuples become lists so MCP clients
    receive standard JSON arrays.
    """
    if isinstance(obj, list | tuple):
        return [_to_dict(x) for x in obj]
    if is_dataclass(obj) and not isinstance(obj, type):
        # asdict recursively converts; then walk to coerce any nested tuples
        # (frozen dataclass tuple fields) into lists.
        return _coerce_tuples(asdict(obj))
    return obj


def _coerce_tuples(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _coerce_tuples(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_coerce_tuples(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_story_bias(url_or_slug: str) -> dict[str, Any]:
    """Return full bias breakdown for a Ground News story.

    Args:
        url_or_slug: Full ground.news article URL or just the slug.
    """
    return _to_dict(scraper.get_story_bias(url_or_slug))


@mcp.tool()
def get_topic_stories(topic: str, limit: int = 10) -> list[dict[str, Any]]:
    """List recent stories from a Ground News interest/topic page.

    Args:
        topic: Topic name (e.g. "ukraine", "AI", "elections").
        limit: Max stories to return (default 10).
    """
    return _to_dict(scraper.get_topic_stories(topic, limit=limit))


@mcp.tool()
def search_stories(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search Ground News for stories matching a topic. Maps to interest slugs.

    Args:
        query: Search keyword(s).
        limit: Max results (default 10).
    """
    return _to_dict(scraper.search_stories(query, limit=limit))


@mcp.tool()
def get_missing_perspectives(url_or_slug: str) -> dict[str, Any]:
    """Return what the underreported side covers for a story.

    Args:
        url_or_slug: Ground News article URL or slug.
    """
    return _to_dict(scraper.get_missing_perspectives(url_or_slug))


@mcp.tool()
def check_content_bias(text: str, topic: str) -> dict[str, Any]:
    """Heuristic bias check on user text, grounded in Ground News coverage.

    Args:
        text: The content to check.
        topic: A topic to ground the assessment against.
    """
    return _to_dict(scraper.check_content_bias(text, topic=topic))


@mcp.tool()
def list_outlets_by_bias(url_or_slug: str, bias: str) -> list[dict[str, Any]]:
    """List a story's sources filtered to one bias bucket.

    Args:
        url_or_slug: Ground News article URL or slug.
        bias: One of "Left", "Center", "Right".
    """
    return _to_dict(scraper.list_outlets_by_bias(url_or_slug, bias=bias))


@mcp.tool()
def get_server_settings() -> dict[str, Any]:
    """Return current server settings (profile, feature toggles)."""
    return settings.get_settings()


@mcp.tool()
def update_server_setting(key: str, value: Any) -> dict[str, Any]:
    """Persist a single server setting.

    Args:
        key: Setting key (profile, passive_context, bias_checker, missing_perspectives).
        value: New value (string for profile, bool otherwise).
    """
    return settings.update_settings(key, value)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    mcp.run()


if __name__ == "__main__":
    main()
