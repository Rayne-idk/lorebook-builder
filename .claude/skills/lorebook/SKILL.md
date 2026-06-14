---
name: lorebook
description: Research a fictional universe through its wikis (Firecrawl-first, WebSearch fallback) and produce a comprehensive SillyTavern/Chub-format lorebook JSON covering lore, characters, locations, factions, and history. Use when the user asks to create, build, or generate a lorebook or world info for a franchise, game, anime, book series, show, or fictional world.
argument-hint: <universe name> [count | scope: <sub-domain>] [spoiler-light] [resume | fresh]
---

# Lorebook Builder

Research the universe named in the arguments and produce a comprehensive lorebook. The entry
count is **derived from the universe's size in Phase 2** (see size bands there), not a fixed
default; an explicit count or scope in the arguments overrides the derivation. Work through the
phases in order. Do not skip the manifest phase and do not write final JSON by hand.

**Reference files** (don't preload both in full — the orchestrator delegates the writing):
- `references/writing-style.md` — content and keyword rules. **Writer subagents** read this; the
  orchestrator only consults its key-rule sections when triaging Phase 5 warnings.
- `references/format.md` — the fragment / intermediate / final JSON formats. Reference when a
  build error needs interpreting; the script enforces it otherwise.

**File layout per run** (`<slug>` = kebab-case universe name):

```
research/<slug>/manifest.md         entity inventory + research status
research/<slug>/map/*.json          firecrawl URL maps (written by -o, never read into chat)
research/<slug>/raw/*.md            scraped source pages
research/<slug>/fragments/*.json    per-batch entry fragments (writer subagents)
research/<slug>/entries.json        merged intermediate entries (script-built)
output/<slug>.lorebook.json         final deliverable (script-built)
```

## Model strategy — read this first

**One model for the whole run — the user's active model.** This skill leans hard on Anthropic's
prompt caching: the orchestrator thread and every subagent share large, stable prefixes (these
instructions, the rule files, repeated batch scaffolding), and the cache makes re-reading them
nearly free. **Switching models mid-run throws all of that away** — each distinct model keeps its
own cache, so every model switch re-writes the prefix from scratch and the token cost balloons.
So this workflow deliberately runs *everything* — orchestrator and all subagents — on a single
model: **whichever model the user currently has active.**

Concretely: when you spawn a subagent with the **Agent** tool (`subagent_type: general-purpose`),
**do not pass a `model` override.** Omitting it makes the subagent inherit the orchestrator's
(active) model, which is exactly what keeps the cache warm. Never set `model: haiku`,
`model: sonnet`, etc. — a mixed-model run is the single biggest token waste here.

> **Cost warning — check before you start.** If the active model is **Opus** or **Fable**, this
> skill will run a large volume of bulk, mechanical work (mapping wikis, scraping dozens to
> hundreds of pages, writing an entry per page) on a frontier model. That is **very expensive** —
> this work was designed for Haiku/Sonnet-class models. At the start of Phase 0, before doing any
> work, **warn the user**: tell them the active model is Opus/Fable, that a lorebook run will
> consume a lot of frontier-model tokens, and recommend they switch to **Sonnet** (or **Haiku**
> for the cheapest run) via `/model` and re-invoke. Proceed only if they confirm they want to
> continue on the expensive model. Do not switch the model yourself — changing it mid-run is the
> cache-busting problem above; the user must pick one model up front.

Delegation still matters even with one model: this skill spends most of its tokens on bulk work
that does **not** need to sit in the orchestrator's context. So delegate by isolation — keep the
orchestrator thread thin and push the heavy tokens into subagents and onto disk. A subagent starts
cold; pass it everything it needs (paths, batch list, the rule files to read) and require it to
**save its output to disk and return only a short status**, never the scraped or written text.

| Work | Runs on | Why delegate |
|---|---|---|
| Mapping a wiki, scraping pages to `raw/`, running the build script | subagent (active model) | Pure tool-calls-to-disk; Firecrawl `-o` writes the file, the agent just checks it. Keeps page bytes out of the orchestrator. |
| Writing entries from `raw/` sources; QA fact-check; fixing lint warnings | subagent (active model) | Bounded by the style guide + the sources. Keeps source/entry text out of the orchestrator. |
| Intake/disambiguation, choosing the wiki & canon, **sizing**, **tiering**, warning triage, final report | orchestrator (this thread) | The irreducible judgment. Keep it here; do not delegate. |

The biggest lever is **keeping web content out of *every* LLM context, not just this one.**
Firecrawl writes straight to disk: `firecrawl scrape "<url>" --only-main-content -o <file>` and
`firecrawl map "<url>" --json -o <file>`. A subagent that uses `-o` runs the command, checks the
file with `wc -c`/`head`, and reports status — the page tokens are paid in Firecrawl credits, not
model tokens, on any tier. Reach into a page's text with the model only when you must reason over
it (writing an entry, a borderline stub, a targeted fact-check).

Rules of thumb: dispatch scrape and write batches **in parallel** (several Agent calls in one
message, or `run_in_background: true`). Never pull a `raw/` page or an entry's full text into
this thread just to look at it — send a subagent. Reserve orchestrator reads for the manifest,
the script's stdout, and the handful of entries you personally spot-check.

**Hard rules:**
1. Every fact in every entry must come from a scraped or fetched source in `research/<slug>/raw/`.
   Never write canon from memory alone — memory chooses *what* to look up, sources decide *what is true*.
2. The final JSON is produced only by `scripts/build_lorebook.py` (`merge` then `build`). Never hand-write it.
3. Full spoilers, all canon, in-universe perspective (see writing-style.md), unless the user
   said otherwise at invocation.
4. Prefer Firecrawl skills (`firecrawl-map`, `firecrawl-scrape`, `firecrawl-search`,
   `firecrawl-crawl`) for all web access; fall back to WebSearch/WebFetch only when Firecrawl
   fails or quota is a concern.

## Phase 0 — Intake & resume check (orchestrator)

0. **Cost check (see Model strategy).** If your active model is **Opus** or **Fable**, warn the
   user now — before any scraping or sizing — that a lorebook run does a large amount of bulk work
   and will be very expensive on a frontier model, and recommend switching to **Sonnet** (or
   **Haiku**) via `/model` and re-invoking. Only continue if they confirm. Whatever single model
   the run proceeds on, all subagents inherit it (never pass a `model` override).
1. Parse the universe name from the arguments. If the name is ambiguous (matches multiple
   franchises, e.g. "Avatar"), ask the user which one via AskUserQuestion. This is the only
   blocking question in the workflow.
2. Derive the slug: lowercase the universe name and collapse each run of non-alphanumeric
   characters to a single hyphen (`"The Elder Scrolls"` → `the-elder-scrolls`). The build script's
   `status`/`merge` use this exact rule, and **every `raw/<slug>.md` filename must match it** so a
   resume can reconcile a manifest entity to its scraped file.
3. **Resume check — never redo work that's already on disk.** Run:

   ```
   python .claude/skills/lorebook/scripts/build_lorebook.py status research/<slug> --lorebook output/<slug>.lorebook.json
   ```

   - Prints `FRESH:` (dir absent), or the user passed `fresh`/`rebuild` → start clean at step 4.
     For `fresh` over an existing dir, move the old `research/<slug>/` aside first.
   - Otherwise it prints what is already scraped/written/built and a `-> NEXT:` phase. **Jump to
     that phase and reuse every artifact on disk.** The `resume`/`continue` keyword forces this.
   - This is safe because every phase below is idempotent: Phase 3 skips entities whose `raw/`
     file already exists, and Phase 4 skips any batch whose fragment file already exists. So a run
     interrupted by a token/context reset resumes for the cost of only the work that remains.
4. If the franchise has materially conflicting canons (anime vs manga endings, game vs show
   continuity), pick the most complete/primary canon, note the choice in the manifest, and
   mention it in the final report — do not block on it.
5. Create `research/<slug>/raw/`, `research/<slug>/map/`, and `research/<slug>/fragments/`.

## Phase 1 — Source discovery (scout subagent → orchestrator decides)

1. Dispatch a **scout** subagent (active model, no `model` override) to find and map the wiki.
   Tell it to: search `"<universe> wiki"`
   (firecrawl-search or WebSearch), preferring a dedicated Fandom / wiki.gg / Miraheze /
   independent wiki over general sites; map the chosen wiki **to a file**, never into its reply —
   `firecrawl map "<wiki>" --search "<category>" --limit <n> --json -o research/<slug>/map/<category>.json`
   per category on big wikis (one map per category beats one giant map); then grep/read those files
   locally and **return only a compact digest** — the wiki base URL plus the index/category page
   URLs for Characters, Locations, Factions/Organizations, Races/Species, Events/History/Timeline,
   Items/Artifacts, Magic/Technology/Power system, and Terminology. The raw URL dump stays on disk.
2. From that digest the orchestrator picks the authoritative wiki and confirms the category URLs.
   Record the chosen wiki and category URLs at the top of `manifest.md`.

## Phase 2 — Entity manifest (scraper subagent scrapes index pages → orchestrator sizes & tiers)

1. Dispatch a **scraper** subagent (active model, no `model` override) to scrape the
   category/index pages and the wiki main page
   (`firecrawl scrape "<index-url>" --only-main-content -o research/<slug>/raw/_index-<category>.md`,
   or `--format links` when a page is just a link list) and **return an inventory digest**: for
   each category, the count of real *content* articles (ignore meta/template/file/category pages)
   and a flat list of `entity name | source URL`. The full page text stays on disk and in the
   subagent; only the digest comes back.
2. **Size the lorebook (orchestrator judgment — derive the target, don't guess it).** The right
   count is a property of the universe, not a fixed default. Using the inventory digest:
   1. The content-article count is the natural ceiling — "has its own wiki page" is a good proxy
      for "has enough material for an entry."
   2. Apply the **entry-worthiness test** to set the realistic target below that ceiling: an
      entity earns an entry only if its sources support ≥2 dense factual sentences *and* it would
      plausibly come up in roleplay set in this world. Stubs and trivia fail this test.
   3. Sanity-check against the size bands:

      | Universe scale | Examples | Comprehensive ≈ |
      |---|---|---|
      | Single work (one novel/film/short game/anime cour) | a standalone story | 20–40 |
      | Complete series (trilogy, mid-size RPG, finished anime) | one full canon | 40–80 |
      | Large / long-running (long shonen, big open-world RPG, extended book series) | — | 80–150 |
      | Sprawling multi-decade (One Piece, Elder Scrolls, Warhammer, Marvel) | — | 150–400+, scope down |

   4. **Precedence:** an explicit count from the user is a hard cap/target and wins. An explicit
      scope ("just the games", "only the first arc") bounds the universe first, then size within
      it. With neither, use the derived number. For sprawling universes with no scope given,
      pick the most prominent sub-domain, state that choice, and size within it rather than
      attempting 400 entries.
   5. Record the derived target and the reasoning (article counts, scale band, scope) at the top
      of `manifest.md`.
3. Build the entity inventory in `research/<slug>/manifest.md` as a table:
   `| entity | category | tier | source URL | status |` (status: `pending` → `scraped` →
   `written` or `dropped: <reason>`).
4. Assign categories (`world`, `character`, `location`, `faction`, `race`, `event`, `concept`,
   `item`, `creature`) and tiers. Split the derived target roughly **25% / 45% / 30%** across
   tiers 1/2/3, adjusting to the universe:
   - **Tier 1:** the world-overview entry (exactly one), protagonists, antagonists, major
     characters, primary locations, central factions, the power/magic system, defining events.
   - **Tier 2:** secondary characters, regions, minor factions, races, signature items, key terms.
   - **Tier 3:** supporting cast, creatures, artifacts, lesser events — filled toward the target,
     stopping when remaining candidates fail the entry-worthiness test rather than padding.
5. Comprehensiveness checklist — the manifest should answer yes to each: every named major
   character? every location the story visits repeatedly? every faction with a name? the
   magic/power/tech system? the historical backstory events? the races/species? If a category is
   genuinely empty for this universe, note that. If the universe is larger than the target,
   tier-1 and tier-2 coverage is non-negotiable; tier 3 is what gets trimmed.
6. Print a one-paragraph manifest summary (derived target + reasoning, counts per category/tier,
   notable inclusions) and proceed. Do not wait for approval — the user can interrupt.

## Phase 3 — Research (scraper subagents, batched & parallel)

The orchestrator never scrapes in this phase — it dispatches and tracks status only.

1. Split the `pending` manifest rows into batches of 5–10 entities. For each batch, spawn a
   **scraper** subagent (active model, no `model` override) and give it the batch as
   `entity name | URL | entity-slug` lines, the output
   dir `research/<slug>/raw/`, and these instructions:
   - **Scrape straight to disk — the page text must never enter your context.** Run
     `firecrawl scrape "<url1>" "<url2>" … --only-main-content -o research/<slug>/raw/<entity-slug>.md`
     (multiple URLs per call scrape concurrently). `--only-main-content` drops nav/footer/galleries
     at the source, so there is nothing to hand-strip and nothing to read back.
   - **Skip work already done:** if `raw/<entity-slug>.md` already exists and is over the stub
     threshold, leave it and report `cached`. (Makes re-runs and resumes nearly free.)
   - **Detect stubs by size, not by reading:** after scraping, check `wc -c` on each file. Treat
     roughly < 700 chars as a likely stub; only then `head` the file to confirm. A healthy article
     is several KB — you never load a full page into context to classify it.
   - **Return only one status line per entity** (`scraped` / `cached` / `dropped: <reason>`).
2. Dispatch batches in parallel (multiple Agent calls per message, or `run_in_background: true`),
   then update each entity's manifest status from the returned status lines.
3. Gaps: if a subagent finds a page missing/stub, it should itself run **firecrawl-search**
   (or WebSearch) for `"<entity>" <universe>` and scrape the best alternative (again with
   `--only-main-content -o`) before giving up. Only `dropped: no sources` if nothing substantive
   exists — never pad an entry with invented facts. If `--only-main-content` ever drops an infobox
   the entry needs, re-scrape that one URL without the flag.
4. While reviewing returned statuses, the orchestrator may add newly discovered tier-1/2 entities
   to the manifest (a major faction the index missed) and queue them in a follow-up batch. Don't
   add tier-3 strays once the target count is reached.

## Phase 4 — Write entries (writer subagents, batched & parallel → fragments)

The orchestrator never writes entry prose in this phase — it dispatches and merges.

1. Split the `scraped` entities into batches (group by category or tier; keep each batch's `raw/`
   files to a manageable size) and give each a **stable label** so its fragment path is
   deterministic — `research/<slug>/fragments/<NN-batch-label>.json` (e.g. `10-characters-t1.json`).
   **On a resume, skip any batch whose fragment file already exists** (writers save the fragment in
   one atomic Write, so a fragment is either complete or absent). For each remaining batch spawn a
   **writer** subagent (active model, no `model` override) and give it: the batch's entities with
   their `category`, `tier`, and
   `raw/<slug>.md` paths; instruction to **read `references/writing-style.md` and the listed `raw/`
   files first** (writers do *not* need `references/format.md` — that spec is for the build script,
   not the author); and the fragment output path. As each batch's fragment lands, mark its entities
   `written` in the manifest so the worklist and final report stay accurate.
2. Each writer applies `references/writing-style.md` strictly — plain prose, names not pronouns,
   self-contained, in-universe, full spoilers, tier-based length caps, 2–6 keys per entry — and
   writes its batch as a **fragment file**: a JSON list of entry objects, each with exactly these
   fields — `name` (string), `keys` (2–6 strings), `content` (plain-prose lore), `category` (one of
   world/character/location/faction/race/event/concept/item/creature), `tier` (1, 2, or 3). It
   returns only a one-line summary (count written, any `dropped` and why). The entry text does not
   pass back through the orchestrator.
3. Writers key each entry to its own entity (writing-style.md §Key rule 5). Shared keys between
   independently-written batches are expected and usually fine — linked entities surfacing together
   is a feature, so there's no need to coordinate keys across writers. The build lint in Phase 5
   flags only the narrow case of a common word shared by (often unrelated) entries.
4. The orchestrator sets the top-level `name` and `description` (it is not in any fragment):
   `name` follows `"The World of <Universe>"` or the universe's own styling (e.g.
   `"The Fantasy World of Adolion"`); `description` is 1–2 sentences stating coverage and canon scope.

## Phase 5 — Merge & build (orchestrator runs script; subagent fixes warnings)

1. Merge the fragments, then build:

   ```
   python .claude/skills/lorebook/scripts/build_lorebook.py merge research/<slug>/fragments -o research/<slug>/entries.json --name "<name>" --description "<description>"
   python .claude/skills/lorebook/scripts/build_lorebook.py build research/<slug>/entries.json -o output/<slug>.lorebook.json
   ```

2. Read the script's stdout (this is cheap — read it directly). Fix every ERROR (rerun until
   clean). Triage every WARN against writing-style.md: oversized entries (tier token-cap
   violations) are the priority fix, and risky keys get replaced or justified. Shared-key warnings
   are low priority — only disambiguate when a common word is shared by genuinely unrelated entries
   (§Key rule 5); natural overlap between related entries is fine and can stay.
3. Apply fixes by dispatching a subagent (active model, no `model` override) with the specific
   warnings and the affected
   fragment file paths — it edits the fragments in place and returns a one-line summary. Then
   re-run `merge` and `build`. The orchestrator decides *what* to fix; the subagent does the editing.

## Phase 6 — QA and delivery (QA subagent → orchestrator reports)

1. `python .claude/skills/lorebook/scripts/build_lorebook.py validate output/<slug>.lorebook.json`
   — must pass with no errors (orchestrator runs this and reads stdout).
2. Dispatch one QA subagent (active model, no `model` override) to do the content checks against
   the sources and return a
   short findings list (not the entry text):
   - **Fact spot-check:** pick 5 entries spanning tiers; verify each claim against the matching
     `raw/` file; report any discrepancy as `entry — claim — source says`.
   - **Trigger sanity:** for 5 entries, judge "would these keys actually appear in a chat about
     this topic, and would they fire on unrelated chat?"; report keys that should change.
3. The orchestrator applies the QA fixes (directly for a one-liner, or via a fragment-edit
   subagent — active model, no `model` override — for anything larger), then re-runs
   `merge` → `build` → `validate`.
4. Final report to the user: output path, entry count by category and tier, total token estimate,
   canon/spoiler scope chosen, sources used, entities dropped and why, and any remaining warnings
   that were accepted deliberately.
