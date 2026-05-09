# ground-news-mcp

An MCP server that exposes [Ground News](https://ground.news/) media-bias and coverage data to Claude as tools.

Ground News doesn't publish a public API. This server doesn't scrape rendered HTML either — it parses the React Server Components (RSC) payload that Next.js streams alongside every page, and pulls the structured story and source data straight out of it.

> **Why this matters:** RSC field names (`biasSourceCount`, `leftSrcPercent`, `sortData.bias.labelData`, …) come from the backend data model, so they stay stable across deploys. Traditional scrapers break the moment a Tailwind class changes; this one breaks only on a major framework migration.

## Tools

| Tool | What it does |
|---|---|
| `get_story_bias` | Full bias breakdown for a story: source counts, percentages, dominant lean, list of all source articles |
| `get_topic_stories` | Recent stories on an interest topic (e.g. `ukraine`, `ai`, `elections`) |
| `search_stories` | Keyword search — maps to interest slugs |
| `get_missing_perspectives` | Surface the underreported side of a story (free-tier proxy for Blindspot Premium) |
| `check_content_bias` | Heuristic bias check on user-provided text, grounded against current Ground News coverage |
| `list_outlets_by_bias` | Filter a story's sources to one bucket (Left / Center / Right) |
| `get_server_settings` / `update_server_setting` | Adjust profile and feature toggles |

## Install

```bash
git clone https://github.com/Konald58/ground-news-mcp
cd ground-news-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Register with Claude

```bash
claude mcp add-json ground-news '{
  "type": "stdio",
  "command": "/absolute/path/to/.venv/bin/ground-news-mcp"
}'
```

## How it works

1. **Fetch** any Ground News URL with the header `RSC: 1`. The server returns `text/x-component` — the same payload Next.js streams to its own client, with all data baked in.
2. **Parse** the chunk stream using `json.JSONDecoder().raw_decode()` from each `<hex_id>:` marker. RSC chunks are concatenated without newline separators and JSON strings can contain real newlines, so naive line-splitting won't work.
3. **Walk** the parsed JSON trees with structural predicates (e.g. `"biasSourceCount" in d and "slug" in d` identifies the story object).

See [`src/ground_news_mcp/rsc.py`](src/ground_news_mcp/rsc.py) for the full parser.

## Resilience

Three layers protect Ground News from rude usage:

1. **5-minute TTL cache** — most repeat queries never hit the network
2. **Token bucket** — minimum 2 seconds between requests, configurable
3. **Exponential backoff + circuit breaker** — retries 429/503 with `Retry-After` honored, trips after 3 consecutive failures

Identifying `User-Agent`: `ground-news-mcp/0.1 (+https://github.com/Konald58/ground-news-mcp)`.

## Settings

Settings persist in `~/.ground-news-mcp/settings.json`. Three profiles: `minimal`, `balanced` (default), `full`.

```python
from ground_news_mcp import settings
settings.update_settings("profile", "full")
```

## Testing

```bash
pytest                # 26 tests, all offline (uses fixtures in tests/fixtures/)
ruff check . && ruff format .
```

To capture a fresh fixture:

```bash
curl -H "RSC: 1" -H "User-Agent: test" \
  "https://ground.news/article/<slug>" \
  > tests/fixtures/article_sample.rsc
```

## Limits & caveats

- **Blindspot Premium** data is gated behind a session cookie. Set `GN_SESSION_COOKIE` if you have one.
- **No keyword search.** Ground News doesn't expose one in the RSC payload, so `search_stories` maps queries to interest slugs.
- **2 MB per article fetch.** Acceptable for interactive use; would be wasteful for bulk harvesting (which would also be a ToS problem — don't).
- **Stability.** RSC field names are stable across normal deploys. They won't survive a Next.js major-version migration without a parser update.

## License

MIT.
