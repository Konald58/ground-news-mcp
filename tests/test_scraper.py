"""Tests for scraper.py — the public API. Uses monkeypatched fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from ground_news_mcp import rsc, scraper
from ground_news_mcp.rsc import parse_article, parse_interest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _stub_rsc_fetch(monkeypatch):
    """Replace the network-fetching helpers with fixture-backed versions."""
    rsc.clear_cache()
    article = parse_article((FIXTURES / "article_sample.rsc").read_text())
    interest = parse_interest((FIXTURES / "interest_sample.rsc").read_text())

    monkeypatch.setattr(scraper, "get_article_data", lambda _u: article)
    monkeypatch.setattr(scraper, "get_interest_data", lambda _t: interest)
    yield
    rsc.clear_cache()


@pytest.mark.unit
class TestGetStoryBias:
    def test_returns_bias_breakdown(self):
        result = scraper.get_story_bias("any-slug")
        assert result.total_sources > 0
        assert result.left_pct + result.center_pct + result.right_pct in range(99, 102)
        assert result.dominant_bias in ("Left", "Center", "Right")

    def test_includes_sources(self):
        result = scraper.get_story_bias("any-slug")
        assert len(result.sources) > 10
        for s in result.sources[:5]:
            assert s.outlet
            assert s.bias_label in ("Left", "Center", "Right", "Unknown")


@pytest.mark.unit
class TestGetTopicStories:
    def test_returns_stories(self):
        results = scraper.get_topic_stories("ukraine", limit=5)
        assert 0 < len(results) <= 5
        for s in results:
            assert s.slug
            assert s.url.startswith("https://ground.news/article/")

    def test_search_aliases_topic(self):
        a = scraper.search_stories("ukraine", limit=3)
        b = scraper.get_topic_stories("ukraine", limit=3)
        assert [s.slug for s in a] == [s.slug for s in b]


@pytest.mark.unit
class TestMissingPerspectives:
    def test_returns_underreported_side(self):
        result = scraper.get_missing_perspectives("any-slug")
        assert result.underreported_side in ("Left", "Center", "Right")
        # Either we surfaced sources OR the message tells the user it's paywalled
        assert result.headlines or result.paywalled


@pytest.mark.unit
class TestListOutletsByBias:
    def test_filters_by_bucket(self):
        right_outlets = scraper.list_outlets_by_bias("any-slug", bias="Right")
        for s in right_outlets:
            assert s.bias_label == "Right"


@pytest.mark.unit
class TestCheckContentBias:
    def test_neutral_text_returns_center(self):
        result = scraper.check_content_bias(
            "Markets opened higher today on positive earnings.", topic="ukraine"
        )
        assert result.dominant_lean in ("Center", "Unknown")
        assert result.confidence in ("low", "medium")

    def test_right_signals_detected(self):
        text = (
            "Border security and election integrity remain top concerns. "
            "Open borders threaten law and order."
        )
        result = scraper.check_content_bias(text, topic="ukraine")
        assert result.dominant_lean == "Right"
