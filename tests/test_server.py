"""Integration test for the FastMCP server wiring.

Verifies that:
- All declared tools register with the MCP server
- Each tool can be called through the FastMCP machinery and returns the
  expected shape (when scraper internals are monkeypatched to fixtures)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ground_news_mcp import rsc, scraper, server
from ground_news_mcp.rsc import parse_article, parse_interest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    """Replace network-touching helpers with fixture-backed stubs."""
    rsc.clear_cache()
    article = parse_article((FIXTURES / "article_sample.rsc").read_text())
    interest = parse_interest((FIXTURES / "interest_sample.rsc").read_text())
    monkeypatch.setattr(scraper, "get_article_data", lambda _u: article)
    monkeypatch.setattr(scraper, "get_interest_data", lambda _t: interest)
    yield
    rsc.clear_cache()


@pytest.mark.unit
def test_all_tools_registered():
    """Every public scraper function should be exposed as an MCP tool."""
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "get_story_bias",
        "get_topic_stories",
        "search_stories",
        "get_missing_perspectives",
        "check_content_bias",
        "list_outlets_by_bias",
        "get_server_settings",
        "update_server_setting",
    }
    assert expected.issubset(names), f"Missing tools: {expected - names}"


@pytest.mark.unit
def test_tools_have_descriptions():
    """All registered tools must have a non-empty description."""
    tools = asyncio.run(server.mcp.list_tools())
    for t in tools:
        assert t.description, f"Tool {t.name} has no description"


@pytest.mark.unit
def test_get_story_bias_returns_dict():
    result = server.get_story_bias("any-slug")
    assert isinstance(result, dict)
    assert "total_sources" in result
    assert "rated_sources" in result
    assert "unrated_count" in result
    assert "dominant_bias" in result
    assert isinstance(result["sources"], list)


@pytest.mark.unit
def test_get_topic_stories_returns_list_of_dicts():
    result = server.get_topic_stories("ukraine", limit=3)
    assert isinstance(result, list)
    assert 0 < len(result) <= 3
    for s in result:
        assert "slug" in s
        assert "url" in s


@pytest.mark.unit
def test_list_outlets_by_bias_filters():
    result = server.list_outlets_by_bias("any-slug", bias="Right")
    assert isinstance(result, list)
    for s in result:
        assert s["bias_label"] == "Right"


@pytest.mark.unit
def test_get_server_settings_returns_dict():
    result = server.get_server_settings()
    assert isinstance(result, dict)
    assert "profile" in result
