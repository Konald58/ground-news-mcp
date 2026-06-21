# CLAUDE.md — ground-news-mcp

## Project
MCP server for Ground News scraping and analysis. Provides Claude with tools to fetch and analyze news bias/coverage data from Ground News.

## Stack
- Python 3.12+
- MCP server protocol
- ruff, pytest (src/ layout with tests/)

## Key Directories
- `src/` — main package source
- `tests/` — pytest test suite

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run
```bash
ground-news-mcp                          # entry point
# or
python -m ground_news_mcp.server         # module form
```

## Architecture
- `rsc.py` — fetches Next.js RSC payload (`RSC: 1` header → `text/x-component`), parses chunks via `json.JSONDecoder.raw_decode()`, walks JSON trees by structural predicates.
- `ratelimit.py` — token bucket (2s default), exponential backoff on 429/503, circuit breaker (3 failures → 5min cooldown).
- `scraper.py` — public API wrapping rsc.py, returns frozen dataclasses from `models.py`.
- `server.py` — FastMCP server exposing 8 tools.
- `settings.py` — JSON persistence at `~/.ground-news-mcp/settings.json`.

## Testing
- All tests offline; live captures stored in `tests/fixtures/*.rsc`.
- Refresh fixture: `curl -H "RSC: 1" "https://ground.news/article/<slug>" > tests/fixtures/article_sample.rsc`.

## Test / Lint
```bash
pytest
ruff check . && ruff format .
```

## Resilience

- 5-min TTL parsed-data cache (thread-safe)
- Token bucket: 2s min interval, lock held across sleep
- Backoff on 429/503 honoring `Retry-After`
- Circuit breaker: 3 fails → 5min cooldown
- 8 MB payload cap, 2000-chunk parse cap
- Slug allowlist regex blocks path traversal

## Watch-outs

- **Don't bulk-harvest** — RSC payloads are ~2 MB each. 50 calls = 100 MB of bandwidth.
- **Next.js migration risk** — the RSC chunk format will eventually change. Realistic ~1–2 year half-life.
- **No keyword search** — Ground News doesn't expose one. `search_stories` maps queries to interest slugs.
- **Blindspot Premium gated** — needs `GN_SESSION_COOKIE` from a paid session.
- **ToS gray zone** — keep this personal-use; don't host as a public SaaS.

## Refs

- Vault: `~/Vault/projects/ground-news-mcp/ground-news-mcp.md`
- Blog draft: `~/Vault/resources/blog-drafts/rsc-reverse-engineering.md`
