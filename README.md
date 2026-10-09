# ground-news-mcp

An MCP server that exposes [Ground News](https://ground.news/) media-bias and coverage data as tools for any MCP client: Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, Codex, or your own agent.

> **Disclaimer:** This is an independent, unofficial project with no affiliation to, endorsement by, or sponsorship from Ground News. "Ground News" is a trademark of its respective owner; it's referenced here only to describe the data source this tool parses.

Ground News doesn't publish a public API. This server doesn't scrape rendered HTML either — it parses the React Server Components (RSC) payload that Next.js streams alongside every page, and pulls the structured story and source data straight out of it.

> **Why this matters:** RSC field names (`biasSourceCount`, `leftSrcPercent`, `sortData.bias.labelData`, …) come from the backend data model, so they stay stable across deploys. Traditional scrapers break the moment a Tailwind class changes; this one breaks only on a major framework migration.

## Tools

| Tool | What it does |
|---|---|
| `get_story_bias` | Full bias breakdown for a story: total and rated source counts, Left/Center/Right split, dominant lean, every source article |
| `get_topic_stories` | Recent stories on an interest topic (e.g. `ukraine`, `ai`, `elections`) |
| `search_stories` | Keyword search — maps to interest slugs |
| `get_missing_perspectives` | Name the least-covered side of a story and list the outlets reporting from it |
| `check_content_bias` | Heuristic bias check on user-provided text, grounded against current Ground News coverage |
| `list_outlets_by_bias` | Filter a story's sources to one bucket (Left / Center / Right) |
| `get_server_settings` / `update_server_setting` | Adjust profile and feature toggles |

## Demo

Ask your assistant: *"How is the Japan cyberattack warning being covered across the spectrum?"*

The model calls `get_topic_stories("ai", limit=3)`, picks the first story, then `get_story_bias(slug)`:

```json
{
  "title": "Japan warns for increased vigilance against rising cyberattacks",
  "story_url": "https://ground.news/article/breaking-news-japan-govt-to-urge-firms-to-address-system-flaws-amid-cyberattacks_75a8a1",
  "total_sources": 25,
  "rated_sources": 18,
  "unrated_count": 7,
  "left_count": 9,
  "center_count": 7,
  "right_count": 2,
  "left_pct": 50,
  "center_pct": 39,
  "right_pct": 11,
  "dominant_bias": "Left",
  "last_updated": "2026-10-09T15:12:00.000Z",
  "sources": [
    {"outlet": "The Record", "bias_label": "Left", "article_url": "https://www.therecord.com/business/japan-warns-for-increased-vigilance-against-rising-cyberattacks/article_5df68df9-0e93-5e39-91fc-7c72f5739c72.html"},
    {"outlet": "The Independent (US)", "bias_label": "Left", "article_url": "https://www.the-independent.com/news/japan-tokyo-japanese-b3063944.html"},
    {"outlet": "연합뉴스-Yonhap News Agency", "bias_label": "Right", "article_url": "https://www.yna.co.kr/view/AKR20261009037700073"},
    "… 22 more"
  ]
}
```

It then answers with the split, names the two Right-leaning outlets, and flags that 7 of the 25 sources carry no rating. Captured live on 2026-10-09.

## Install

There is no package on an index; install from a checkout.

```bash
git clone https://github.com/Konald58/ground-news-mcp
cd ground-news-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Register with an MCP client

The server speaks stdio MCP, so any client that can launch a local command works. Point it at the `ground-news-mcp` entry point inside the venv.

**Claude Code**

```bash
claude mcp add-json ground-news '{
  "type": "stdio",
  "command": "/absolute/path/to/.venv/bin/ground-news-mcp"
}'
```

**Claude Desktop, Cursor, Windsurf** (`claude_desktop_config.json`, `.cursor/mcp.json`, `mcp_config.json`)

```json
{
  "mcpServers": {
    "ground-news": {
      "command": "/absolute/path/to/.venv/bin/ground-news-mcp"
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`)

```json
{
  "servers": {
    "ground-news": {
      "type": "stdio",
      "command": "/absolute/path/to/.venv/bin/ground-news-mcp"
    }
  }
}
```

**Codex** (`~/.codex/config.toml`)

```toml
[mcp_servers.ground-news]
command = "/absolute/path/to/.venv/bin/ground-news-mcp"
```

Any other client: run the command above over stdio. Set `GN_SESSION_COOKIE` in the client's env block if you use one.

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

Identifying `User-Agent`: `ground-news-mcp/<version> (+https://github.com/Konald58/ground-news-mcp)`, with the version read from package metadata.

## Settings

Settings persist in `~/.ground-news-mcp/settings.json`. Three profiles: `minimal`, `balanced` (default), `full`.

```python
from ground_news_mcp import settings
settings.update_settings("profile", "full")
```

## Testing

```bash
pytest                # 55 tests, all offline (uses fixtures in tests/fixtures/)
ruff check . && ruff format .
```

To capture a fresh fixture:

```bash
curl -H "RSC: 1" -H "User-Agent: test" \
  "https://ground.news/article/<slug>" \
  > tests/fixtures/article_sample.rsc
```

## Limits & caveats

- **Two source counts.** Ground News counts every outlet covering a story (`total_sources`, shown on topic cards as `source_count`) and, separately, only the outlets it has rated (`rated_sources`). The Left/Center/Right split is over rated sources; the rest appear in `sources` as `Unknown`. The two numbers differ on almost every story, so quote the one you mean.
- **Blindspot Premium** data is gated behind a session cookie. Set `GN_SESSION_COOKIE` if you have one. Without it, `get_missing_perspectives` works from the public per-source ratings only.
- **No keyword search.** Ground News doesn't expose one in the RSC payload, so `search_stories` maps queries to interest slugs.
- **2 MB per article fetch.** Acceptable for interactive use; would be wasteful for bulk harvesting, so don't.
- **Stability.** RSC field names are stable across normal deploys. They won't survive a Next.js major-version migration without a parser update.

## License

MIT.
