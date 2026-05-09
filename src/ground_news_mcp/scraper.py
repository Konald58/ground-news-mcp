"""Public API for Ground News data extraction.

Backed by rsc.py — fetches and parses Ground News's React Server Components
payloads to extract structured story and source data without HTML scraping.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from .models import BiasBreakdown, BiasCheck, MissingPerspectives, Source, StoryResult
from .rsc import (
    article_url,
    get_article_data,
    get_interest_data,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_bias(label: str | None) -> str:
    """Reduce Ground News's 7 bias labels to {Left, Center, Right} buckets."""
    if not label:
        return "Unknown"
    lower = label.lower()
    if "left" in lower:
        return "Left"
    if "right" in lower:
        return "Right"
    if "center" in lower:
        return "Center"
    return "Unknown"


def _dedupe_sources(raw_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe by article URL (RSC payloads include nested duplicates)."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for s in raw_sources:
        url = s.get("url")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)
    return unique


def _build_source(raw: dict[str, Any]) -> Source:
    outlet = (raw.get("sourceInfo") or {}).get("name") or ""
    bias_label = _normalize_bias(
        (raw.get("sortData") or {}).get("bias", {}).get("labelData")
    )
    return Source(
        outlet=outlet, bias_label=bias_label, article_url=raw.get("url") or ""
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_story_bias(url_or_slug: str) -> BiasBreakdown:
    """Return full bias breakdown for a Ground News story."""
    data = get_article_data(url_or_slug)
    story = data["story"]
    raw_sources = _dedupe_sources(data["sources"])

    bucket_counts = Counter(_build_source(s).bias_label for s in raw_sources)
    left_count = story.get("leftSrcCount") or bucket_counts.get("Left", 0)
    right_count = story.get("rightSrcCount") or bucket_counts.get("Right", 0)
    center_count = story.get("cntrSrcCount") or bucket_counts.get("Center", 0)

    left_pct = round((story.get("leftSrcPercent") or 0) * 100)
    right_pct = round((story.get("rightSrcPercent") or 0) * 100)
    center_pct = round((story.get("cntrSrcPercent") or 0) * 100)

    if left_pct + right_pct + center_pct == 0:
        total = left_count + right_count + center_count or 1
        left_pct = round(left_count / total * 100)
        right_pct = round(right_count / total * 100)
        center_pct = round(center_count / total * 100)

    dominant = max(
        [("Left", left_pct), ("Center", center_pct), ("Right", right_pct)],
        key=lambda x: x[1],
    )[0]

    sources = tuple(_build_source(s) for s in raw_sources)
    title = (
        story.get("title") or (story.get("description") or "").split("\n", 1)[0][:80]
    )

    return BiasBreakdown(
        title=title,
        story_url=article_url(url_or_slug),
        total_sources=story.get("biasSourceCount") or len(sources),
        left_count=left_count,
        center_count=center_count,
        right_count=right_count,
        left_pct=left_pct,
        center_pct=center_pct,
        right_pct=right_pct,
        dominant_bias=dominant,
        last_updated=story.get("start") or "",
        sources=sources,
    )


def get_topic_stories(topic: str, limit: int = 10) -> list[StoryResult]:
    """List stories from a Ground News interest/topic page."""
    data = get_interest_data(topic)
    out: list[StoryResult] = []
    for s in data["stories"][:limit]:
        slug = s.get("slug")
        if not slug:
            continue
        out.append(
            StoryResult(
                title=s.get("title") or "",
                url=f"https://ground.news/article/{slug}",
                slug=slug,
                source_count=s.get("sourceCount") or s.get("biasSourceCount"),
            )
        )
    return out


def search_stories(query: str, limit: int = 10) -> list[StoryResult]:
    """Search by keyword. Maps the query to a Ground News interest topic slug.

    Ground News doesn't expose keyword search in the RSC payload, so queries
    normalize to interest slugs (e.g. "iran war" → /interest/iran-war).
    """
    return get_topic_stories(query, limit)


def get_missing_perspectives(url_or_slug: str) -> MissingPerspectives:
    """Return what the underreported side covers for a story.

    Ground News's full Blindspot Premium feature is paywalled — without a
    session cookie we surface sources from the underreported bucket as a
    free-tier proxy.
    """
    bias = get_story_bias(url_or_slug)
    sides = [
        ("Left", bias.left_pct),
        ("Right", bias.right_pct),
        ("Center", bias.center_pct),
    ]
    underreported, under_pct = min(sides, key=lambda x: x[1])

    minority = tuple(
        s for s in bias.sources if underreported.lower() in s.bias_label.lower()
    )

    if not minority:
        return MissingPerspectives(
            underreported_side=underreported,
            headlines=(),
            paywalled=True,
            message=(
                f"No {underreported}-leaning sources surfaced for this story. "
                "Full Blindspot Premium data may require a Ground News session "
                "cookie (set GN_SESSION_COOKIE)."
            ),
        )

    dominant_pct = max(p for _, p in sides)
    return MissingPerspectives(
        underreported_side=underreported,
        headlines=minority,
        paywalled=False,
        message=(
            f"The {underreported} perspective covers only {under_pct}% of this "
            f"story vs {bias.dominant_bias} at {dominant_pct}%."
        ),
    )


# ---------------------------------------------------------------------------
# Bias-checking heuristic
# ---------------------------------------------------------------------------

# These are deliberate signal-flag heuristics, not a model. Confidence is
# always reported honestly (low/medium) and the result is grounded against
# Ground News's actual coverage distribution for the topic.

_LEFT_SIGNALS = [
    "systemic racism",
    "marginalized",
    "equity",
    "climate crisis",
    "gun control",
    "reproductive rights",
    "social justice",
    "structural inequality",
    "lived experience",
    "white supremacy",
]
_RIGHT_SIGNALS = [
    "border security",
    "illegal alien",
    "election integrity",
    "radical left",
    "big government",
    "second amendment",
    "free market",
    "law and order",
    "woke",
    "traditional values",
    "open borders",
]


def check_content_bias(text: str, topic: str) -> BiasCheck:
    """Heuristic bias check on user text against current Ground News coverage."""
    try:
        stories = search_stories(topic, limit=3)
    except Exception as e:
        logger.warning("Could not load topic '%s': %s", topic, e)
        stories = []

    if not stories:
        return BiasCheck(
            dominant_lean="Unknown",
            confidence="low",
            explanation=(
                f"No Ground News coverage found for topic '{topic}'. "
                "Cannot ground a bias assessment."
            ),
            suggested_perspectives=(),
        )

    try:
        bias = get_story_bias(stories[0].url)
    except Exception as e:
        return BiasCheck(
            dominant_lean="Unknown",
            confidence="low",
            explanation=f"Could not fetch reference bias data: {e}",
            suggested_perspectives=(),
        )

    text_lower = text.lower()
    left_score = sum(1 for s in _LEFT_SIGNALS if s in text_lower)
    right_score = sum(1 for s in _RIGHT_SIGNALS if s in text_lower)

    if left_score > right_score + 1:
        lean, confidence, suggest_side = (
            "Left",
            ("medium" if left_score >= 3 else "low"),
            "Right",
        )
    elif right_score > left_score + 1:
        lean, confidence, suggest_side = (
            "Right",
            ("medium" if right_score >= 3 else "low"),
            "Left",
        )
    else:
        lean, confidence, suggest_side = "Center", "low", None

    suggested: tuple[Source, ...] = ()
    if suggest_side:
        suggested = tuple(
            s for s in bias.sources if suggest_side.lower() in s.bias_label.lower()
        )[:3]

    explanation = (
        f"Detected {left_score} left-coded and {right_score} right-coded framing "
        f"signals. Ground News currently shows {bias.dominant_bias} coverage "
        f"({bias.left_pct}% L / {bias.center_pct}% C / {bias.right_pct}% R) "
        f"across {bias.total_sources} sources on '{topic}'."
    )
    if suggest_side and suggested:
        explanation += f" Consider {suggest_side}-leaning sources for balance."

    return BiasCheck(
        dominant_lean=lean,
        confidence=confidence,
        explanation=explanation,
        suggested_perspectives=suggested,
    )


def list_outlets_by_bias(url_or_slug: str, bias: str) -> list[Source]:
    """Filter a story's sources to a single bias bucket (Left/Center/Right)."""
    bucket = _normalize_bias(bias)
    breakdown = get_story_bias(url_or_slug)
    return [s for s in breakdown.sources if s.bias_label == bucket]
