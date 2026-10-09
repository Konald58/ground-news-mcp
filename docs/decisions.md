# Decisions

- **2026-05-09** — Replaced BeautifulSoup HTML scraping with RSC payload parsing (`rsc.py`). Rationale: Ground News is fully SSR with no public API; RSC field names come from the backend data model and are stable across normal deploys, unlike CSS-class-dependent HTML scraping.
- **2026-05-09** — Kept this tool personal-use only rather than hosting as a public multi-user service. Rationale: using the `RSC: 1` header against public infrastructure is a ToS gray zone; a public-facing version with real users would raise that risk materially.
- **2026-09-12** — Moved the repo from `~/ground-news-mcp` to `~/code/ground-news-mcp` as part of a system-wide directory reorg. No code or config changes beyond location.
- **2026-10-09** — `total_sources` means every outlet (`sourceCount`) and `rated_sources` only the rated ones (`biasSourceCount`); the L/C/R split stays over rated sources. Rationale: Ground News itself shows both numbers, the topic list and story breakdown were quoting different ones, and relabeling beats silently picking one.
- **2026-10-09** — User-Agent version comes from package metadata, never a literal. Rationale: it drifted (0.1 vs 0.2.0) the first time the version moved.
- **2026-10-09** — No new non-Latin fixture; the existing article fixture already carries Cyrillic, Hebrew, Arabic and CJK outlet names, so a test over it covers the case without a second 2 MB file.
