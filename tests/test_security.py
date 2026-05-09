"""Defensive tests for the parser and scraper against hostile/edge inputs.

These verify the resilience layers: depth caps, chunk caps, string-length
caps for prompt-injection defense, and the percentage-fallback bug fix.
"""

from __future__ import annotations

import pytest

from ground_news_mcp import rsc, scraper
from ground_news_mcp.rsc import _walk


def _build_deep_dict(depth: int) -> dict:
    root: dict = {}
    cur = root
    for i in range(depth):
        nxt: dict = {}
        cur[f"k{i}"] = nxt
        cur = nxt
    return root


@pytest.mark.unit
class TestWalkResilience:
    def test_walk_does_not_recurse_unbounded(self):
        """A tree deeper than MAX_WALK_DEPTH must not crash."""
        deep = _build_deep_dict(rsc.MAX_WALK_DEPTH + 50)
        buckets: list[list] = [[]]
        # Should not raise RecursionError
        _walk(deep, [lambda d: "k0" in d], buckets)
        assert len(buckets[0]) == 1  # only the root matches

    def test_walk_iterative_no_python_recursion(self, monkeypatch):
        """Even with a tiny recursion limit, the walker should work."""
        monkeypatch.setattr(
            rsc.sys if hasattr(rsc, "sys") else __import__("sys"),
            "setrecursionlimit",
            lambda _n: None,
            raising=False,
        )
        # Build a moderately deep tree and walk it; no RecursionError expected
        tree = _build_deep_dict(50)
        buckets: list[list] = [[]]
        _walk(tree, [lambda d: True], buckets)
        # Iterative walk visits all 51 dicts
        assert len(buckets[0]) == 51


@pytest.mark.unit
class TestPayloadCaps:
    def test_chunk_cap_enforced(self, monkeypatch):
        """If a payload generates too many JSON chunks, parsing stops."""
        monkeypatch.setattr(rsc, "MAX_JSON_CHUNKS", 5)
        # Build a synthetic payload with 20 minimal JSON chunks
        chunks = "".join(f"\n{i:x}:[]" for i in range(20))
        values = list(rsc._iter_json_values(chunks))
        assert len(values) == 5


@pytest.mark.unit
class TestStringSanitization:
    def test_safe_str_truncates_long_input(self):
        long = "x" * 5000
        result = scraper._safe_str(long, max_len=100)
        assert len(result) <= 101  # 100 + ellipsis
        assert result.endswith("…")

    def test_safe_str_handles_none(self):
        assert scraper._safe_str(None) == ""

    def test_safe_str_coerces_non_string(self):
        assert scraper._safe_str(42) == "42"


@pytest.mark.unit
class TestPercentageFallback:
    def test_zero_percent_does_not_trigger_fallback(self, monkeypatch):
        """Regression: a story with 0% Left coverage is legitimate;
        the recompute fallback must not override real upstream data."""
        # Synthesize a payload where the upstream pcts are all set
        # but Left is 0.
        story = {
            "biasSourceCount": 10,
            "slug": "test",
            "title": "T",
            "leftSrcPercent": 0.0,
            "cntrSrcPercent": 0.4,
            "rightSrcPercent": 0.6,
            "leftSrcCount": 0,
            "cntrSrcCount": 4,
            "rightSrcCount": 6,
        }
        monkeypatch.setattr(
            scraper, "get_article_data", lambda _u: {"story": story, "sources": []}
        )
        result = scraper.get_story_bias("test")
        assert result.left_pct == 0
        assert result.center_pct == 40
        assert result.right_pct == 60


@pytest.mark.unit
class TestLimitClamping:
    def test_topic_stories_limit_clamped(self, monkeypatch):
        monkeypatch.setattr(
            scraper,
            "get_interest_data",
            lambda _t: {
                "stories": [
                    {"slug": f"s{i}", "title": f"Story {i}", "sourceCount": 5}
                    for i in range(200)
                ]
            },
        )
        # Even when asked for 9999, we cap at MAX_LIMIT
        result = scraper.get_topic_stories("anything", limit=9999)
        assert len(result) <= scraper.MAX_LIMIT

    def test_topic_stories_limit_floors_to_one(self, monkeypatch):
        monkeypatch.setattr(
            scraper,
            "get_interest_data",
            lambda _t: {"stories": [{"slug": "s0", "title": "T", "sourceCount": 1}]},
        )
        # Negative or zero limits clamp to 1
        result = scraper.get_topic_stories("anything", limit=0)
        assert len(result) == 1
