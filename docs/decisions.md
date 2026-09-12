# Decisions

- **2026-05-09** — Replaced BeautifulSoup HTML scraping with RSC payload parsing (`rsc.py`). Rationale: Ground News is fully SSR with no public API; RSC field names come from the backend data model and are stable across normal deploys, unlike CSS-class-dependent HTML scraping.
- **2026-05-09** — Kept this tool personal-use only rather than hosting as a public multi-user service. Rationale: using the `RSC: 1` header against public infrastructure is a ToS gray zone; a public-facing version with real users would raise that risk materially.
- **2026-09-12** — Moved the repo from `~/ground-news-mcp` to `~/code/ground-news-mcp` as part of a system-wide directory reorg. No code or config changes beyond location.
