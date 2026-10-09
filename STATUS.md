---
status: active
---

# ground-news-mcp

## What it is

MCP server that exposes Ground News media-bias and coverage data as tools Claude can call. Instead of scraping rendered HTML, it fetches and parses the React Server Components (RSC) payload Next.js streams alongside every Ground News page — the field names come from the backend data model, so they're stable across normal deploys. 8 tools: story bias breakdown, topic browsing, keyword-to-slug search, missing-perspectives surfacing, content bias check, source filtering by lean, and settings get/update. Private repo (github.com/Konald58/ground-news-mcp).

## Where it stands

**2026-10-09** — v0.3.0 cut on `feat/rsc-rebuild` (tag `v0.3.0`, local only until pushed). The branch is 12 commits ahead of `main` and fast-forwards cleanly; `main` is still the scaffold. 55 tests pass offline, ruff and bandit clean. Live check the same day: `get_topic_stories('ai')` and `get_story_bias` both work and the UTF-8 fix holds (Korean outlet name intact).

Done this session, from the previous Next up list:
- Source-count mismatch explained and fixed: `sourceCount` is every outlet, `biasSourceCount` only rated ones. `BiasBreakdown` now has `total_sources` (all), `rated_sources` and `unrated_count`; `StoryResult` has `rated_source_count`. Unrated outlets stay in `sources` as `Unknown`.
- User-Agent version read from package metadata; `pyproject.toml` aligned (it still said 0.1.0 after the 0.2.0 changelog entry).
- Non-Latin outlet regression test over the existing fixture (no new fixture needed).
- README: live demo with real output, two-count explanation, test count, install wording for a private repo, Blindspot line reworded.
- Server docstring tool names corrected.

Earlier context: RSC approach, Terms review and landscape check are in the 2026-10-09 entry of `docs/decisions.md` and the git log. Ground News Terms ban automated access and reverse engineering; no official API or MCP exists; this is the only MCP returning the bias breakdown.

## Next up

- Push `feat/rsc-rebuild` and tag `v0.3.0`, fast-forward `main`, delete the branch (Kon's go needed for the push to main).
- Then merge `personal-website` branch `feat/portfolio-ground-news`.
- Decide public vs private (see Open questions).
- Housekeeping candidate, not yet done: delete `tests/fixtures/*.html` (three files from the BeautifulSoup era, about 1.2 MB, referenced by nothing).
- Optional: run API Anything once against the Ground News search page to find a real search request; `search_stories` still maps keywords to interest slugs.

## Open questions

- Timeline for the eventual Next.js RSC chunk-format migration risk (~1–2 year estimated half-life) — no action needed yet, just a known future maintenance trigger.
- Whether to make the repo public as a portfolio piece. The Terms forbid it on their face; realistic risk for a public, rate-limited, non-commercial repo is a takedown request, while hosting it for others is the real exposure (assessment 2026-10-09, not legal advice). Kon's call.
