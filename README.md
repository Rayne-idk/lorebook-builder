# Lorebook Builder

A [Claude Code](https://claude.com/claude-code) skill that researches a fictional universe
through its wikis and produces a comprehensive **SillyTavern / Chub-format lorebook** (World
Info) — characters, locations, factions, races, history, and lore, all written from real wiki
sources.

> **Compatibility:** built and tested against Claude Code. The skill is plain markdown
> (instructions + a standalone Python script), so it should be portable to other agent
> frameworks with a similar skills/tools mechanism — but that has not been tried.

## ⚠️ Token usage warning

**Running `/lorebook` consumes a very large number of tokens.** This is inherent to the task,
not a bug: the model has to read through dozens to hundreds of wiki pages and condense an
entire fictional universe into prose, then write 20–400+ dense lorebook entries from that
research. A single run is comparable to summarizing a small book, and large/sprawling
franchises (see the size bands in [WORKFLOW.md](WORKFLOW.md)) cost proportionally more and take
a long time to finish. Keep this in mind before pointing it at a huge, long-running series.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3 (standard library only — used by the build/validate script)
- Firecrawl skills configured (preferred research path); falls back to built-in
  WebSearch/WebFetch if unavailable, but is slower and less thorough. Firecrawl's
  [free trial](https://www.firecrawl.dev/) covers a generous number of scrapes, which is enough
  to get started without a paid plan.

## Usage

```
/lorebook <universe name> [count | scope: <sub-domain>] [spoiler-light]
```

Examples:

```
/lorebook Berserk
/lorebook The Stormlight Archive 100
/lorebook Elden Ring, scope: base game
/lorebook Mistborn, spoiler-light
```

The entry count is derived automatically from the size of the universe unless you give an
explicit count or scope. Defaults are full spoilers and all canon.

## Output

The final lorebook is written to `output/<slug>.lorebook.json`:

- **SillyTavern:** World Info panel → Import → select the file, then bind it globally, to a
  character, or to a chat.
- **Chub:** Create → Lorebook → Import.

Intermediate working files (entity manifest, raw scraped pages, hand-authored intermediate
entries) are written to `research/<slug>/` for traceability and are not needed after the build.

## How it works

See [WORKFLOW.md](WORKFLOW.md) for the full phased pipeline (source discovery, entity manifest,
research, writing, build, QA) and the design decisions behind it.

## Repo layout

```
.claude/skills/lorebook/
  SKILL.md                       the /lorebook skill definition
  scripts/build_lorebook.py      intermediate -> final JSON builder + validator
  references/format.md           JSON format spec (intermediate + final)
  references/writing-style.md    entry content + keyword rules
  examples/                       sample intermediate + final lorebook
research/<slug>/                  per-universe working files (created at runtime, gitignored)
output/<slug>.lorebook.json       final deliverables (created at runtime)
WORKFLOW.md                       pipeline documentation
```
