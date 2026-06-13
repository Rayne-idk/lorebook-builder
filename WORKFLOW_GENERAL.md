# Lorebook Builder Workflow

Generate a comprehensive SillyTavern/Chub-format lorebook for any fictional universe by
researching its wikis. Implemented as the **`/lorebook`** Claude Code skill in
`.claude/skills/lorebook/`; this document explains the pipeline for humans.

## Usage

```
/lorebook Berserk
/lorebook The Stormlight Archive 100
/lorebook Elden Ring, spoiler-light
```

Defaults: full spoilers, all canon, Firecrawl-first research, and an **entry count derived from
the universe's size** (Phase 2). Anything after the universe name (an explicit count, a `scope:`
sub-domain, a spoiler preference, a canon restriction) overrides the defaults at intake.

### Estimating the entry count

You normally don't pick the number — it falls out of the wiki. The count is set by one test
applied per entity: *does this thing have enough sourced material for ≥2 dense factual sentences,
and would it plausibly come up in roleplay set in this world?* Everything that clears that bar
gets an entry; the rest is trivia. Phase 2 measures the natural ceiling by counting content
articles in the wiki's Characters/Locations/Factions/Races/Events/Items categories, then sizes
against these bands:

| Universe scale | Examples | Comprehensive ≈ |
|---|---|---|
| Single work | one novel, film, short game, anime cour | 20–40 |
| Complete series | trilogy, mid-size RPG, finished anime | 40–80 |
| Large / long-running | long shonen, big open-world RPG, extended book series | 80–150 |
| Sprawling multi-decade | One Piece, Elder Scrolls, Warhammer, Marvel | 150–400+, scope down |

More entries isn't "more thorough" past a point: only ~3–6 entries fire at once (512-token
budget), so extra entries don't bloat any prompt, but each costs research time and adds
key-collision risk. The binding constraint is sourced material per entity, not tokens — which is
why padding a small universe is forbidden. Pass an explicit number only to force a hard cap or
minimum; pass `scope: <sub-domain>` to bound a sprawling franchise instead of capping by count.

## Pipeline

```
Phase 0  Intake            disambiguate universe, pick canon, set up research/<slug>/
Phase 1  Source discovery  find the authoritative wiki, map it with firecrawl-map
Phase 2  Entity manifest   enumerate 60–120 entities from category pages, tier them
Phase 3  Research          batch-scrape every entity's page to research/<slug>/raw/
Phase 4  Write entries     Marinara-style prose entries -> research/<slug>/entries.json
Phase 5  Build             build_lorebook.py emits output/<slug>.lorebook.json
Phase 6  QA                validate, lint keys, fact spot-check vs sources, report
```

### Key design decisions

- **Two-file split.** The agent only ever hand-writes a small *intermediate* file
  (name + keys + content + category + tier per entry). A deterministic Python script
  (`scripts/build_lorebook.py`) expands it into the full Chub format — 27 boilerplate fields
  per entry that would otherwise be hand-copied 100+ times with inevitable drift.
- **Sources are mandatory.** Every entry is written from a scraped page saved under
  `research/<slug>/raw/`, never from model memory. Memory decides what to look up; the wiki
  decides what is true. Entities with no findable sources are dropped, not improvised.
- **Manifest before research.** Phase 2 produces a tiered inventory first, so coverage is a
  deliberate decision (every major character? every named faction? the magic system?) instead
  of an accident of which pages got scraped.
- **Tiered length budget.** The format's `token_budget: 512` means only ~3–6 entries can fire
  at once, so entries are capped at ~300/150/80 tokens for tier 1/2/3 and the linter enforces it.

### Research stack

1. `firecrawl-map` — enumerate a wiki's URLs / find category pages
2. `firecrawl-scrape` — pull entity pages as markdown
3. `firecrawl-search` — fill gaps when a wiki page is missing or thin
4. Built-in WebSearch/WebFetch — fallback when Firecrawl fails or to conserve quota

### The builder script

```
# expand intermediate entries into the final Chub-format JSON
python .claude/skills/lorebook/scripts/build_lorebook.py build research/<slug>/entries.json -o output/<slug>.lorebook.json

# validate any final lorebook (also works on downloaded Chub exports)
python .claude/skills/lorebook/scripts/build_lorebook.py validate output/<slug>.lorebook.json
```

Errors (fatal): missing fields, uid/id/key-mirror inconsistencies, empty content/keys.
Warnings (triaged in QA): entries over tier token caps, >6 keys, sub-3-char keys,
common-word keys likely to false-trigger, the same key owned by two entries, case-duplicate
keys (the format is case-insensitive).

### Entry style in one paragraph

Plain encyclopedic prose, third person, no markdown. Proper names instead of pronouns so every
sentence survives being injected in isolation. Present tense for standing facts, past for
history. In-universe perspective only (no "in Season 2"). Full spoilers — fates and reveals
stated as plain facts. Keys are 2–6 strings covering what people actually type in chat:
canonical name, nicknames, titles, epithets. Full rules with examples:
`.claude/skills/lorebook/references/writing-style.md`.

### Format contract

The output matches the Chub export format exactly (verified field-for-field against a real
export): top level `scan_depth: 4`, `token_budget: 512`, `recursive_scanning: false`; entries
keyed `"1"`-based with mirrored `key`/`keys`, `comment`/`name`, `keysecondary`/`secondary_keys`,
fixed `position: 1`, `order: 100`, `priority: 10`, `excludeRecursion: true`,
`case_sensitive: false`, `depth: 4`. Field-by-field spec:
`.claude/skills/lorebook/references/format.md`.

## Repo layout

```
.claude/skills/lorebook/
  SKILL.md                      the /lorebook skill (phased agent workflow)
  scripts/build_lorebook.py     intermediate -> final JSON builder + validator
  references/format.md          JSON format spec (both formats, field semantics)
  references/writing-style.md   entry content + keyword rules
  examples/adolion.entries.json sample intermediate file (3 entries)
  examples/adolion.lorebook.json  the built result, matching the Chub reference
research/<slug>/                per-universe working files (created at runtime)
output/<slug>.lorebook.json     final deliverables (created at runtime)
WORKFLOW.md                     this document
```

## Importing the result

- **SillyTavern:** World Info panel → Import → select `output/<slug>.lorebook.json`, then bind
  it globally, to a character, or to a chat.
- **Chub:** upload via Create → Lorebook → Import; Chub assigns `extensions.chub.id` and
  `full_path` on upload (the builder leaves them as `0` / `""`).
