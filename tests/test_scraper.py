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

    def test_total_counts_every_source_and_rated_counts_only_rated(self):
        """`sourceCount` (all) vs `biasSourceCount` (rated) — the two numbers
        Ground News shows differ, and so must ours, with explicit labels."""
        result = scraper.get_story_bias("any-slug")
        assert result.total_sources == 533
        assert result.rated_sources == 322
        assert result.unrated_count == 533 - 322
        assert result.total_sources == len(result.sources)
        assert (
            result.left_count + result.center_count + result.right_count
            == result.rated_sources
        )
        unknown = [s for s in result.sources if s.bias_label == "Unknown"]
        assert len(unknown) == result.unrated_count


@pytest.mark.unit
class TestNonLatinOutlets:
    def test_non_latin_outlet_names_survive_parsing(self):
        """Fixture holds Cyrillic, Hebrew, Arabic and CJK outlet names; none
        may come back as mojibake or get dropped."""
        outlets = {s.outlet for s in scraper.get_story_bias("any-slug").sources}
        for name in ("5 канал", "Європейська правда", "וואלה!", "大纪元 Epoch Times"):
            assert name in outlets
        assert not any("Ã" in o or "Ð" in o for o in outlets)


@pytest.mark.unit
class TestGetTopicStories:
    def test_returns_stories(self):
        results = scraper.get_topic_stories("ukraine", limit=5)
        assert 0 < len(results) <= 5
        for s in results:
            assert s.slug
            assert s.url.startswith("https://ground.news/article/")

    def test_cards_carry_both_counts(self):
        results = scraper.get_topic_stories("ukraine", limit=5)
        for s in results:
            assert s.source_count is not None
            assert s.rated_source_count is not None
            assert s.rated_source_count <= s.source_count

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
