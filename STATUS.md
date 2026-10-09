---
status: active
---

# ground-news-mcp

## What it is

MCP server that exposes Ground News media-bias and coverage data as tools Claude can call. Instead of scraping rendered HTML, it fetches and parses the React Server Components (RSC) payload Next.js streams alongside every Ground News page — the field names come from the backend data model, so they're stable across normal deploys. 8 tools: story bias breakdown, topic browsing, keyword-to-slug search, missing-perspectives surfacing, content bias check, source filtering by lean, and settings get/update. Private repo (github.com/Konald58/ground-news-mcp).

## Where it stands

**2026-09-12** — Repo moved from `~/ground-news-mcp` to `~/code/ground-news-mcp` as part of a system-wide reorg; no file in the repo hardcodes the old path (checked `src/`, `tests/`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `pyproject.toml`, `.github/workflows/ci.yml` — none reference `/Users/konstantindragovic/ground-news-mcp` or `~/ground-news-mcp`). The `.venv` was already regenerated at the new path.

Currently checked out on `feat/rsc-rebuild`, which is 6 commits ahead of `main` (`main` sits at the original scaffold commit only — the entire RSC-based rebuild, portfolio polish, and this branch's later work have never been merged to `main`).

Today's commit on this branch, `chore: commit in-progress work before system migration` (3849222), bundled the pending UTF-8 fix from the 2026-07-16 handoff into `rsc.py` (forces `response.encoding = "utf-8"` since the charset-less `text/x-component` response was defaulting to latin-1 and mangling non-Latin outlet names), added a `TestFetchEncoding` regression test, updated `CHANGELOG.md`, and touched three HTML fixtures. This work has **landed on the branch but has not been re-verified** since — the 2026-07-16 handoff's live end-to-end probe predates this commit, and there's been no fresh live check against ground.news since.

As of 2026-10-09: live check passed. `get_topic_stories('ai')` returned 3 current stories and `get_story_bias` returned a full breakdown (17 sources, 47/41/12 L/C/R), so the RSC approach still works. 51 tests pass, ruff clean. Landscape checked the same day: no Ground News API or official MCP, nothing on npm, PyPI or MCP registries; on GitHub only `vicatnight/groundnewsmcp` (generic page text, no bias data) and `jtk18/groundnews-crawler` (bias JSON, CLI, MCP "planned"). This is the only MCP returning the bias breakdown. Ground News Terms (about.ground.news/terms-and-conditions, updated 2024-11-26) ban automated access (6.1(d)), reverse engineering (3.1(c)), making functionality available to third parties (3.1(e)) and building a similar service (3.1(f)); Ontario law, Toronto arbitration (IP disputes go to court). API Anything (reel-73) was considered and rejected as a dependency; at most a one-off tool to discover a real search endpoint.

## Next up

- Decide public vs private (see Open questions); everything below is safe either way.
- README: test count (26 -> 51), install steps that assume a public clone, and reword the `get_missing_perspectives` "free-tier proxy for Blindspot Premium" line.
- Version consistency: User-Agent says 0.1, CHANGELOG has 0.2.0.
- Investigate `source_count` mismatch: topic list said 22 sources, `get_story_bias` said 17 for the same story (likely rated sources only); fix or label.
- Add a demo (sample Claude question + tool output, GIF or screenshot) to the README.
- Add a non-Latin-source fixture to `tests/fixtures/`.
- Merge `feat/rsc-rebuild` into `main` (`main` is still the scaffold), then merge `personal-website` branch `feat/portfolio-ground-news`.
- Optional: run API Anything once against the Ground News search page to find a real search request; `search_stories` currently maps keywords to interest slugs.

## Open questions

- Timeline for the eventual Next.js RSC chunk-format migration risk (~1–2 year estimated half-life) — no action needed yet, just a known future maintenance trigger.
- Whether to make the repo public as a portfolio piece. The Terms forbid it on their face; realistic risk for a public, rate-limited, non-commercial repo is a takedown request, while hosting it for others is the real exposure (assessment 2026-10-09, not legal advice). Kon's call.
