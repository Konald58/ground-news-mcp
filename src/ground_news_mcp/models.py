"""Frozen dataclasses for all Ground News MCP return types."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """A single news outlet covering a story."""

    outlet: str
    bias_label: str
    article_url: str


@dataclass(frozen=True)
class BiasBreakdown:
    """Full bias breakdown for a single story.

    `total_sources` counts every outlet covering the story (Ground News's
    `sourceCount`). `rated_sources` counts only outlets with a bias rating
    (`biasSourceCount`); the Left/Center/Right counts and percentages are
    computed over those. `unrated_count` is the difference, and those
    sources appear in `sources` with `bias_label == "Unknown"`.
    """

    title: str
    story_url: str
    total_sources: int
    rated_sources: int
    unrated_count: int
    left_count: int
    center_count: int
    right_count: int
    left_pct: int
    center_pct: int
    right_pct: int
    dominant_bias: str
    last_updated: str
    sources: tuple[Source, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StoryResult:
    """A story card returned from search or topic pages."""

    title: str
    url: str
    slug: str
    source_count: int | None = None  # every outlet (`sourceCount`)
    rated_source_count: int | None = None  # outlets with a rating (`biasSourceCount`)


@dataclass(frozen=True)
class MissingPerspectives:
    """Underreported angle for a story."""

    underreported_side: str
    headlines: tuple[Source, ...]
    paywalled: bool = False
    message: str = ""


@dataclass(frozen=True)
class BiasCheck:
    """Result of checking a piece of content for bias."""

    dominant_lean: str
    confidence: str  # "low" | "medium" | "high"
    explanation: str
    suggested_perspectives: tuple[Source, ...]
