# Decisions

- **2026-05-09** — Replaced BeautifulSoup HTML scraping with RSC payload parsing (`rsc.py`). Rationale: Ground News is fully SSR with no public API; RSC field names come from the backend data model and are stable across normal deploys, unlike CSS-class-dependent HTML scraping.
- **2026-05-09** — Kept this tool personal-use only rather than hosting as a public multi-user service. Rationale: it reads a third-party site; keeping it personal, rate-limited and cached keeps the load negligible, and a hosted version with real users would not.
- **2026-09-12** — Moved the repo from `~/ground-news-mcp` to `~/code/ground-news-mcp` as part of a system-wide directory reorg. No code or config changes beyond location.
- **2026-10-09** — `total_sources` means every outlet (`sourceCount`) and `rated_sources` only the rated ones (`biasSourceCount`); the L/C/R split stays over rated sources. Rationale: Ground News itself shows both numbers, the topic list and story breakdown were quoting different ones, and relabeling beats silently picking one.
- **2026-10-09** — User-Agent version comes from package metadata, never a literal. Rationale: it drifted (0.1 vs 0.2.0) the first time the version moved.
- **2026-10-09** — Public repo as a portfolio piece. Internal notes left the repo first; the full background assessment lives in the vault archive.
- **2026-10-09** — No new non-Latin fixture; the existing article fixture already carries Cyrillic, Hebrew, Arabic and CJK outlet names, so a test over it covers the case without a second 2 MB file.
- **2026-10-09** — Published with full git history rather than a fresh single-commit repo. Rationale: the commit log is the evidence that the work was iterative and reviewed; the old internal note it still contains holds nothing secret.
- **2026-10-09** — Pin `mcp<2` instead of migrating now. Rationale: 2.x renamed `FastMCP` and broke a fresh install on the day the repo went public; a pin restores green CI in one line, the migration is its own change.
