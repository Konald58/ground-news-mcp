# Changelog

All notable changes to this project will be documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- `BiasBreakdown.rated_sources` and `unrated_count`; `StoryResult.rated_source_count`. Ground News shows two numbers per story: every outlet covering it (`sourceCount`) and only the outlets with a bias rating (`biasSourceCount`). The topic list reported the first and `get_story_bias` the second, so the same story showed 25 sources in one tool and 18 in the other. Both are now exposed and labeled.
- Regression test that non-Latin outlet names (Cyrillic, Hebrew, Arabic, CJK) in the article fixture parse intact.
- README demo with real tool output.

### Changed
- `BiasBreakdown.total_sources` now counts every outlet (`sourceCount`), matching the topic list; the Left/Center/Right counts and percentages remain over rated sources only. Unrated outlets still appear in `sources` as `Unknown`.
- `check_content_bias` explanation says "rated sources".
- User-Agent version is read from package metadata instead of a hardcoded `0.1`, so it can no longer drift from `pyproject.toml`.
- `pyproject.toml` version set to 0.2.0; the 0.2.0 release was cut in this changelog but never declared there.

### Fixed
- `fetch_rsc` now forces UTF-8 decoding. The `text/x-component` response carries no charset, so `requests` defaulted to latin-1 and mangled non-ASCII outlet names (Cyrillic, Korean, …). Offline fixtures (English stories) never surfaced this; caught via a live probe. Added `TestFetchEncoding` regression test.

## [0.2.0] — 2026-05-09

### Added
- `rsc.py` — React Server Components payload fetcher and parser. Replaces fragile HTML scraping with stable backend-property-name extraction.
- `ratelimit.py` — token bucket, exponential backoff with `Retry-After` support, and a circuit breaker.
- `server.py` — FastMCP server exposing 8 tools to Claude.
- `tests/test_rsc.py`, `tests/test_scraper.py`, `tests/test_ratelimit.py` — 26 tests, all offline.
- `tests/fixtures/article_sample.rsc`, `interest_sample.rsc` — captured RSC payloads for tests.
- `list_outlets_by_bias` tool — filter a story's sources by Left/Center/Right.
- README documenting the RSC approach and resilience model.
- LICENSE, CI workflow, and an integration test (portfolio polish).

### Changed
- `scraper.py` — public API preserved; internals now route through `rsc.py` instead of BeautifulSoup.
- Identifying User-Agent (`ground-news-mcp/0.1 (+...)`) replaces the Chrome spoof.
- `pyproject.toml` — dropped `beautifulsoup4` dependency; added `unit`/`integration` pytest markers.

### Fixed
- Review findings: concurrency, DoS exposure, prompt injection, and assorted bugs.

### Removed
- BeautifulSoup-based HTML scraping (text-proximity parsing of Coverage Details, regex on rendered bias percentages).

## [0.1.0] — initial scaffold

### Added
- Project scaffold: `pyproject.toml`, `models.py`, `settings.py`.
- Frozen dataclasses for return types (`BiasBreakdown`, `Source`, `StoryResult`, `MissingPerspectives`, `BiasCheck`).
- Settings persistence with `minimal` / `balanced` / `full` profiles.
