---
name: lorebook
description: Research a fictional universe through its wikis (Firecrawl-first, WebSearch fallback) and produce a comprehensive SillyTavern/Chub-format lorebook JSON covering lore, characters, locations, factions, and history. Use when the user asks to create, build, or generate a lorebook or world info for a franchise, game, anime, book series, show, or fictional world.
argument-hint: <universe name> [count | scope: <sub-domain>] [spoiler-light]
---

# Lorebook Builder

Research the universe named in the arguments and produce a comprehensive lorebook. The entry
count is **derived from the universe's size in Phase 2** (see size bands there), not a fixed
default; an explicit count or scope in the arguments overrides the derivation. Work through the
phases in order. Do not skip the manifest phase and do not write final JSON by hand.

**Read before writing anything:**
- `references/format.md` — intermediate + final JSON formats
- `references/writing-style.md` — content and keyword rules

**File layout per run** (`<slug>` = kebab-case universe name):

```
research/<slug>/manifest.md      entity inventory + research status
research/<slug>/raw/*.md         scraped source pages
research/<slug>/entries.json     intermediate entries (agent-authored)
output/<slug>.lorebook.json      final deliverable (script-built)
```

**Hard rules:**
1. Every fact in every entry must come from a scraped or fetched source in `research/<slug>/raw/`.
   Never write canon from memory alone — memory chooses *what* to look up, sources decide *what is true*.
2. The final JSON is produced only by `scripts/build_lorebook.py`. Never hand-write it.
3. Full spoilers, all canon, in-universe perspective (see writing-style.md), unless the user
   said otherwise at invocation.
4. Prefer Firecrawl skills (`firecrawl-map`, `firecrawl-scrape`, `firecrawl-search`,
   `firecrawl-crawl`) for all web access; fall back to WebSearch/WebFetch only when Firecrawl
   fails or quota is a concern.

## Phase 0 — Intake

1. Parse the universe name from the arguments. If the name is ambiguous (matches multiple
   franchises, e.g. "Avatar"), ask the user which one via AskUserQuestion. This is the only
   blocking question in the workflow.
2. If the franchise has materially conflicting canons (anime vs manga endings, game vs show
   continuity), pick the most complete/primary canon, note the choice in the manifest, and
   mention it in the final report — do not block on it.
3. Set the slug and create `research/<slug>/raw/`.

## Phase 1 — Source discovery

1. Find the authoritative wiki: search `"<universe> wiki"` (firecrawl-search or WebSearch).
   Prefer a dedicated Fandom / wiki.gg / Miraheze / independent wiki over general sites.
   Note secondary sources (official site, encyclopedia pages, Wikipedia for overview).
2. Map the wiki with **firecrawl-map** to enumerate its URLs. On huge wikis, map with search
   filters per category instead of mapping everything.
3. From the map, identify the index/category pages: Characters, Locations,
   Factions/Organizations, Races/Species, Events/History/Timeline, Items/Artifacts,
   Magic/Technology/Power system, Terminology. Record the chosen wiki and category URLs at the
   top of `manifest.md`.

## Phase 2 — Entity manifest

1. Scrape the category/index pages and the wiki's main page.
2. **Size the lorebook (derive the target, don't guess it).** The right count is a property of
   the universe, not a fixed default. Estimate it before listing entities:
   1. From the map and category pages, count the *content* articles in Characters, Locations,
      Factions, Races, major Events, and key Items/Concepts (ignore meta/template/file/category
      pages). This article count is the natural ceiling — "has its own wiki page" is a good proxy
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

## Phase 3 — Research

1. Work through the manifest in batches of 5–10 entities. For each batch, scrape the entities'
   wiki pages (**firecrawl-scrape**, markdown format) and save each to
   `research/<slug>/raw/<entity-slug>.md`. Strip navboxes, galleries, and reference lists if
   the page is huge — keep the infobox data, lead section, history/plot, relationships,
   abilities sections.
2. Update each entity's manifest status as it lands.
3. Gaps: if a page is missing, thin, or a stub, run **firecrawl-search** (or WebSearch) for
   `"<entity>" <universe>` and scrape the best alternative source. If nothing substantive
   exists, mark the entity `dropped: no sources` — never pad an entry with invented facts.
4. While reading sources, opportunistically add newly discovered tier-1/2 entities to the
   manifest (a major faction the index missed). Don't add tier-3 strays once the target count
   is reached.

## Phase 4 — Write entries

1. Apply `references/writing-style.md` strictly: plain prose, names not pronouns,
   self-contained, in-universe, full spoilers, tier-based length caps, 2–6 keys per entry,
   no cross-entry key collisions.
2. Write all entries into `research/<slug>/entries.json` in the intermediate format
   (`references/format.md` §1). Order entries: world overview first, then tier 1 → 2 → 3,
   alphabetical within tier.
3. Top-level `name`: follow the pattern `"The World of <Universe>"` or the universe's own
   styling (e.g. `"The Fantasy World of Adolion"`). `description`: 1–2 sentences stating
   coverage and canon scope.
4. Write entries in batches per category, rereading the relevant raw scrapes for each batch —
   do not write from the manifest alone.

## Phase 5 — Build

```
python .claude/skills/lorebook/scripts/build_lorebook.py build research/<slug>/entries.json -o output/<slug>.lorebook.json
```

Fix every ERROR (rerun until clean). Triage every WARN: oversized entries get trimmed, risky
keys get replaced or justified, shared keys get disambiguated per writing-style.md §Key rule 5.
Rebuild after fixes.

## Phase 6 — QA and delivery

1. `python .claude/skills/lorebook/scripts/build_lorebook.py validate output/<slug>.lorebook.json`
   — must pass with no errors.
2. Fact spot-check: pick 5 entries spanning tiers and verify each claim against the
   corresponding `raw/` file. Fix discrepancies and rebuild.
3. Trigger sanity-check: for 5 entries, ask "would the keys actually appear in a chat about
   this topic, and would they fire on unrelated chat?" Adjust keys if either answer is wrong.
4. Final report to the user: output path, entry count by category and tier, total token
   estimate, canon/spoiler scope chosen, sources used, entities dropped and why, and any
   remaining warnings that were accepted deliberately.
