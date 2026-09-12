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

## Next up

- Re-verify the UTF-8 fix and the RSC-parsing approach still work live against ground.news (last confirmed live 2026-07-16, before today's commit).
- Decide whether/when to merge `feat/rsc-rebuild` into `main` — `main` is 6 commits stale.
- Finish the portfolio integration: an entry is staged in `personal-website` (`projects.ts`, branch `feat/portfolio-ground-news`), but that page doesn't render yet.
- Consider adding a non-Latin-source fixture to `tests/fixtures/` — current fixtures are English-only and structurally can't catch encoding regressions like the one just fixed.

## Open questions

- Timeline for the eventual Next.js RSC chunk-format migration risk (~1–2 year estimated half-life) — no action needed yet, just a known future maintenance trigger.
- Whether to keep this permanently private/personal-use given the Ground News ToS gray zone, or revisit that stance later.
