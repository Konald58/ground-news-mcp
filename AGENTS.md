# AGENTS.md — ground-news-mcp

MCP server exposing Ground News media-bias and coverage data as tools for any MCP client.
Parses the Next.js React Server Components (RSC) payload instead of scraping rendered HTML.

## Stack

- Python 3.12+
- `mcp` (FastMCP), `requests`, `python-dotenv`
- `ruff` (lint + format), `pytest` + `pytest-cov` (`src/` layout, tests in `tests/`)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
ground-news-mcp                          # entry point
python -m ground_news_mcp.server         # module form
```

## Test / Lint

```bash
pytest -q --cov=src --cov-report=term-missing
ruff check src/ tests/
ruff format --check src/ tests/
bandit -r src/                           # security scan, run before any push
```

CI (`.github/workflows/ci.yml`) runs all four on push/PR to `main`.

## Layout

- `src/ground_news_mcp/rsc.py` — fetches the RSC payload (`RSC: 1` header → `text/x-component`), parses concatenated chunks via `json.JSONDecoder().raw_decode()`, walks the JSON tree by structural predicates (e.g. `"biasSourceCount" in d and "slug" in d` identifies the story object).
- `src/ground_news_mcp/ratelimit.py` — token bucket (2s min interval, lock held across sleep), exponential backoff on 429/503 honoring `Retry-After`, circuit breaker (3 failures → 5min cooldown).
- `src/ground_news_mcp/scraper.py` — public API wrapping `rsc.py`; returns frozen dataclasses from `models.py`.
- `src/ground_news_mcp/server.py` — FastMCP server, 8 tools; `_to_dict` flattens frozen dataclasses/tuples to JSON.
- `src/ground_news_mcp/settings.py` — JSON persistence at `~/.ground-news-mcp/settings.json`; three profiles (`minimal`/`balanced`/`full`).
- `src/ground_news_mcp/models.py` — frozen dataclasses for all return types.
- `tests/fixtures/*.rsc` — captured RSC payloads; all tests run offline against these.

## Conventions

- Return types are frozen dataclasses (`@dataclass(frozen=True)`), converted to plain dict/list at the MCP boundary in `server.py`, never passed through as-is.
- Every string flowing back to the model goes through `_safe_str` (truncation) as a prompt-injection defense — don't bypass it when adding a new tool.
- Slug/user input is validated against an allowlist regex before being used in a URL — blocks path traversal.
- `response.encoding` must be forced to `"utf-8"` explicitly in `rsc.py` — the `text/x-component` response carries no charset header, so `requests` silently falls back to latin-1 and mangles non-ASCII outlet names (Cyrillic, Korean, …).
- Payload/parse caps: 8 MB response body, 2000 chunks per parse — don't remove these when touching `rsc.py`.

## Pitfalls

- **Don't bulk-harvest.** RSC payloads are ~2 MB each; 50 calls = 100 MB of bandwidth against a third-party site.
- **No keyword search exists upstream.** `search_stories` maps queries to interest slugs, not a real search API.
- **Blindspot Premium data is gated** behind `GN_SESSION_COOKIE` (see `.env.example`) from a paid Ground News session — most dev/test work won't have this.
- **RSC chunk format is Next.js-internal** and will change on a Next.js major-version migration (unversioned, no upstream contract). Refresh fixtures with:
  ```bash
  curl -H "RSC: 1" "https://ground.news/article/<slug>" > tests/fixtures/article_sample.rsc
  ```
- **This is a personal-use tool.** Ground News has no public API; keep usage patterns polite (rate limits above exist for this reason) and don't host this as a public multi-user service.
- The article fixture carries Cyrillic, Hebrew, Arabic and CJK outlet names and `TestNonLatinOutlets` guards them, but the fixture is read from disk as UTF-8 either way; a response-decoding regression only shows in `TestFetchEncoding` or a live probe.
