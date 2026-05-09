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
