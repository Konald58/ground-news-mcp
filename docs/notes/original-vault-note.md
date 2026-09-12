---
status: complete
type: project
goal: expose Ground News media-bias data as Claude tools via RSC reverse-engineering — private
completion: 100
---

# [[ground-news-mcp]]

**Status:** complete (private) | **Type:** MCP server | **Stack:** Python 3.12, FastMCP, requests

## Overview

MCP server that exposes Ground News media-bias data as Claude tools. Reverse-engineers Next.js React Server Components (RSC) payloads instead of HTML scraping — uses backend-property names (`biasSourceCount`, `leftSrcPercent`) that are stable across deploys.

8 tools covering: full bias breakdown, topic browsing, missing-perspectives surfacing, content bias check, source filtering by lean, and settings.

## Code

`~/ground-news-mcp/`

## The technique (the actual portfolio asset)

1. **Dead end:** Ground News has no `api.ground.news`. Network tab on the live site shows zero data fetches — fully SSR.
2. **Insight:** Next.js App Router serializes server-rendered data into `__next_f` script tags as RSC chunks. Adding the header `RSC: 1` to any URL returns the raw payload directly (`text/x-component`).
3. **Parser:** chunks are concatenated without newline separators and JSON strings can contain real newlines. Use `json.JSONDecoder().raw_decode()` from each `<hex_id>:[` or `<hex_id>:{` marker. Walk the parsed trees by structural predicates (`"biasSourceCount" in d and "slug" in d` finds the story object).

## Architecture

- `rsc.py` — fetcher + parser, single-pass `_walk` with depth cap
- `ratelimit.py` — token bucket (2s default) + exponential backoff with `Retry-After` + circuit breaker
- `scraper.py` — public API wrapping rsc.py, returns frozen dataclasses
- `server.py` — FastMCP wiring, 8 tools, `_to_dict` flattens dataclasses + tuples for JSON
- `settings.py` — profile persistence at `~/.ground-news-mcp/settings.json`
- `models.py` — frozen dataclasses

## Resilience layers

| Layer | What it does |
|---|---|
| 5-min TTL cache | Most repeat queries skip the network |
| Token bucket (thread-safe) | Min 2s between live requests |
| Backoff on 429/503 | Honors `Retry-After`; 4s/8s/16s otherwise |
| Circuit breaker | Trips after 3 consecutive failures, 5min cooldown |

## Security hardening

- Slug allowlist regex blocks path traversal + special chars
- 8 MB payload cap, 2000-chunk parse cap
- `_safe_str` truncates every string flowing back to Claude (prompt-injection defense)
- `MAX_LIMIT=50` clamps user-controlled limit
- bandit clean, scan-before-public passed (only false positives in `.venv/`)

## Testing

51 tests, all offline via captured RSC fixtures in `tests/fixtures/`. CI workflow runs pytest + ruff + bandit on push. Fixtures are English-only, so they structurally can't catch encoding regressions (see the UTF-8 bug below) — a future refresh should add a story with non-Latin sources.

## Status

- **Public repo live**: github.com/Konald58/[[ground-news-mcp]] (MIT, non-affiliation disclaimer, v0.2.0)
- **Live-verified working 2026-07-16** — offline suite + a real end-to-end probe against ground.news (current stories + bias breakdown, today-dated timestamp). The RSC approach still holds in production.
- **UTF-8 fix pending commit**: `fetch_rsc` now forces `response.encoding = "utf-8"` (the charset-less `text/x-component` response was defaulting to latin-1 and mangling Cyrillic/Korean outlet names). In the working tree, uncommitted — next step is branch `fix/rsc-utf8-encoding`.
- Candidate flagship for the portfolio; entry staged in [[personal-website]] `projects.ts` (branch `feat/portfolio-ground-news`) but that page doesn't render yet — see [[personal-website]].
- Blog draft at `~/Vault/resources/blog-drafts/rsc-reverse-engineering.md`

## Watch-outs

- **Next.js major-version migration** — chunk format may change. Comment in `rsc.py` documents the format. Realistic ~1-2 year half-life.
- **No keyword search** — Ground News doesn't expose one in RSC. `search_stories` falls back to interest slugs.
- **Blindspot Premium gated** — `GN_SESSION_COOKIE` env var wired but requires a paid Ground News session.
- **2 MB per article** — fine interactively, terrible for bulk. Don't.
- **ToS gray zone** — RSC header is using public infrastructure, not bypassing auth, but a public version with users could attract a C&D. Keep it personal.

## Related

[[mcp-servers]] — the FastMCP family this belongs to
[[sam-gov-mcp]] — same MCP distribution pattern
[[florida-leads]] — same Keychain secrets pattern (not used here yet)
[[keychain-secrets]] — pattern reference (no runtime key needed here)

## Refs

Blog write-up: [[rsc-reverse-engineering]]
GitHub: not yet created (private)
Plan: `~/.claude/plans/so-now-what-do-soft-beaver.md`
Polish plan: [[plans/2026-05-09-portfolio-polish]]
Transcript: `~/Vault/transcripts/2026-05-09-19-19.md`
