# Entry Writing Style Guide (Marinara-style plain prose)

These rules govern every `content` string and every `keys` array. They exist because of how
SillyTavern injects entries: an entry fires alone, mid-conversation, with no surrounding context,
into a 512-token shared budget, and its text must read as neutral world-fact to the model.

## Content rules

1. **Plain prose only.** No markdown, no headers, no bullet lists, no PList/bracket syntax inside
   `content`. Complete sentences.
2. **Third person, factual, encyclopedic.** State facts; never editorialize ("interestingly",
   "tragically") and never address the reader.
3. **Names, not pronouns.** Repeat the entity's proper name instead of using he/she/it/they where
   a pronoun could be ambiguous. The entry may be injected next to unrelated text, so every
   sentence should survive being read in isolation.
   - Bad: "She rules the city and her army defends it."
   - Good: "Queen Maren rules Aegis City. Queen Maren's army, the Silver Watch, defends Aegis City."
4. **Self-contained.** Never reference other entries structurally ("see above", "as mentioned").
   Mentioning other entities *by name* is encouraged — it gives the model hooks into the wider
   world — but the sentence must make sense if that other entry never fires.
5. **Tense:** present tense for standing facts ("Aegis City is the capital"), past tense for
   history and events ("The Sundering War ended in 3021").
6. **In-universe perspective.** Never reference the medium: no "in Season 2", "in chapter 45",
   "the player", "the anime reveals". Convert media chronology into in-universe chronology
   ("after the fall of the Empire" rather than "in the sequel").
7. **Full spoilers.** Deaths, betrayals, true identities, and endings are stated plainly as facts.
   A character's entry covers their whole arc including their fate. (If the user requested
   spoiler-light at intake, instead describe the status quo at story start and omit reveals.)
8. **Length by tier** (≈4 chars/token):
   - Tier 1 (world overview, protagonists, central factions): 4–8 sentences, 100–250 tokens. Hard cap 300.
   - Tier 2 (secondary characters, regions, systems): 3–5 sentences, 60–150 tokens.
   - Tier 3 (minor entities): 2–3 sentences, 30–80 tokens.
   The 512-token budget means roughly 3–6 entries can be active at once — an oversized entry
   crowds out every other entry that triggered alongside it.
9. **Density over coverage.** Every sentence must carry a concrete fact (who/what/where/when/
   relationship/ability). Cut atmosphere, fan commentary, and trivia.

## What each category covers

- **world** (exactly one entry, the universe itself): genre, scale, technology/magic level, major
  races or powers, the central conflict. This is the anchor entry; key it on the universe's name.
- **character**: role and affiliation → species/origin if relevant → 1 clause of appearance →
  personality in concrete terms → notable abilities → key relationships by name → major arc
  events and fate.
- **location**: type (city/region/realm) → where it sits relative to other named places → who
  rules it → why it matters → notable features or districts → major events that happened there.
- **faction**: purpose → leadership by name → structure/ranks if distinctive → notable members →
  goals and rivals → fate if disbanded/destroyed.
- **race**: defining traits → culture → homeland → relations with other races.
- **event**: when (in-universe) → who was involved → cause → outcome → lasting consequences.
- **concept** (magic/tech/power systems, laws, religions): how it works → limits and costs →
  who can use it → associated terminology.
- **item / creature**: what it is → what it does → who holds/where found → significance.

## Key selection rules

1. **2–6 keys per entry**: canonical name first, then real aliases — nicknames, titles, epithets,
   abbreviations, maiden/code names, common fan shorthand that appears in chat.
   Example: `["Aegis City", "Aegis", "Holy City"]`.
2. **Keys are what people type.** `scan_depth: 4` matches keys against the last 4 chat messages.
   A key nobody would type in conversation is dead weight; an alias everyone uses is mandatory.
3. **No case duplicates.** `case_sensitive` is false — `"adolion"` and `"Adolion"` are the same
   key. Keep one.
4. **Avoid false-trigger words.** Single common English words ("king", "war", "light", "mother",
   "guild" in a story with one unrelated guild) fire on unrelated chat. Use them only when the
   word overwhelmingly means this entity in this universe (e.g. "Guild" is fine when the
   Adventurer's Guild is the only guild). Prefer two-word keys when a single word is risky.
5. **No overlap between different entries' keys.** Two entries sharing the key "Shadow" will both
   fire and double-spend the budget. If a name collision is real in canon (two characters named
   Alex), disambiguate with multi-word keys ("Alex Mercer", "Alex Chen") and drop the bare name,
   or keep the bare name only on the more prominent one.
6. **Substring traps.** Keys match as words, but watch aliases that are substrings of common words
   or of other keys ("Ada" inside "Adalbert") — prefer the longer form.

## Worked example

```json
{
  "name": "Adventurer's Guild",
  "keys": ["Adventurer's Guild", "The Guild", "Guild"],
  "content": "The Adventurer's Guild is an organization that manages the many adventurers in Adolion. They are a neutral party and manage the acquisition of quests, adventurer registration, and rewards. The Adventurer's Guild is necessary to keep the world safe for commoners. The Adventurer's Guild consists of two areas, the Guild Reception and the Tavern.",
  "category": "faction",
  "tier": 1
}
```

Note: name repeated instead of pronouns, present tense, plain sentences, keys covering the forms
people actually type, references "Adolion" by name to hook into the world entry.
