"""Tests for the RSC payload parser using saved fixtures.

These tests do not hit the network. They exercise the parser against
a real Ground News RSC payload captured to tests/fixtures/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ground_news_mcp.rsc import (
    parse_article,
    parse_interest,
    slug_from_url,
    topic_slug,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def article_payload() -> str:
    return (FIXTURES / "article_sample.rsc").read_text()


@pytest.fixture
def interest_payload() -> str:
    return (FIXTURES / "interest_sample.rsc").read_text()


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSlugHelpers:
    def test_slug_from_full_url(self):
        assert slug_from_url("https://ground.news/article/foo-bar") == "foo-bar"

    def test_slug_from_bare_slug(self):
        assert slug_from_url("foo-bar") == "foo-bar"

    def test_slug_strips_article_prefix(self):
        assert slug_from_url("article/foo-bar") == "foo-bar"

    def test_slug_rejects_non_article_url(self):
        with pytest.raises(ValueError):
            slug_from_url("https://example.com/somewhere")

    def test_topic_slug_normalizes(self):
        assert topic_slug("Iran War") == "iran-war"
        assert topic_slug("  AI / Tech  ") == "ai-tech"


# ---------------------------------------------------------------------------
# Article parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseArticle:
    def test_extracts_story(self, article_payload):
        data = parse_article(article_payload)
        story = data["story"]
        assert story["biasSourceCount"] > 0
        assert story["slug"]
        assert "leftSrcPercent" in story

    def test_percentages_sum_to_one(self, article_payload):
        story = parse_article(article_payload)["story"]
        total = (
            (story.get("leftSrcPercent") or 0)
            + (story.get("cntrSrcPercent") or 0)
            + (story.get("rightSrcPercent") or 0)
        )
        assert 0.99 <= total <= 1.01

    def test_extracts_sources(self, article_payload):
        sources = parse_article(article_payload)["sources"]
        assert len(sources) > 10
        for s in sources[:5]:
            assert s.get("url")
            assert s.get("title")
            assert "sortData" in s

    def test_sources_have_outlet_metadata(self, article_payload):
        sources = parse_article(article_payload)["sources"]
        with_outlet = [s for s in sources if (s.get("sourceInfo") or {}).get("name")]
        assert len(with_outlet) > 5

    def test_raises_on_empty_payload(self):
        with pytest.raises(ValueError):
            parse_article("")


# ---------------------------------------------------------------------------
# Interest parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseInterest:
    def test_extracts_stories(self, interest_payload):
        stories = parse_interest(interest_payload)["stories"]
        assert len(stories) > 0
        for s in stories[:3]:
            assert s.get("slug")
            assert s.get("title")

    def test_stories_are_unique_by_slug(self, interest_payload):
        stories = parse_interest(interest_payload)["stories"]
        slugs = [s.get("slug") for s in stories]
        assert len(slugs) == len(set(slugs))
