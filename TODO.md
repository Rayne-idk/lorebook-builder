- [ ] add option to omit Phase 6 / fact-checking (token usage)
- [x] add dynamic model use based on tasks
      (haiku=scrape/map, sonnet=write/QA/fixes, orchestrator=judgment; subagents save to
      disk + return status only so bulk tokens never hit the orchestrator. See SKILL.md
      "Model strategy" + new `merge` step in build_lorebook.py.)
- [x] find more ways to bring down token usage — round 1 applied:
      - Firecrawl `--only-main-content -o <file>`: scrape/map write straight to disk, so page
        text is paid in credits, never LLM tokens — not even in the subagent. (Phases 1–3)
      - skip already-scraped pages (`cached`) → cheap re-runs/resumes; stub detection via `wc -c`
        instead of reading the page; multiple URLs per scrape call.
      - writer subagents no longer read format.md (~1.6k tok each); per-entry shape inlined.
      - orchestrator no longer preloads both reference files in full.
      Still open (need your call): effort levels (lite/standard/deep), omit-Phase-6 flag.
- [x] continue / resume from artifacts (ran out of tokens, reloading context nukes token count)
      `build_lorebook.py status research/<slug> [--lorebook ...]` reconciles manifest vs. raw/ +
      fragments/ on disk and prints the next phase to run. Phase 0 runs it and jumps there;
      `resume`/`continue` forces it, `fresh`/`rebuild` ignores it. Phases 3 (cached scrapes) and 4
      (skip existing fragment files, atomic writes) are idempotent, so a resume costs only the
      work left. Raw filenames use a canonical slug so reconciliation is deterministic.