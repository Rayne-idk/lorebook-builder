# Lorebook JSON Format Specification (Chub / SillyTavern hybrid)

Two formats matter in this pipeline:

1. **Intermediate format** (`entries.json`) — what the agent writes by hand during Phase 4.
2. **Final format** (`*.lorebook.json`) — what `build_lorebook.py` emits. Never hand-write this.

---

## 1. Intermediate format (agent-authored)

```json
{
  "name": "The Fantasy World of Adolion",
  "description": "Comprehensive lorebook covering the characters, locations, factions, and history of Adolion.",
  "entries": [
    {
      "name": "Aegis City",
      "keys": ["Aegis City", "Aegis", "Holy City"],
      "content": "Aegis City is the capital city of the Darran Kingdom. It is the largest city on the continent of Sebela. Its ruler is King Davolan. It is otherwise known as the Holy City.",
      "category": "location",
      "tier": 1
    }
  ]
}
```

Per-entry fields:

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | yes | — | Entity name. Becomes `comment` and `name` in the final JSON. |
| `keys` | yes | — | Trigger keywords. 2–6 strings. See writing-style.md for selection rules. |
| `content` | yes | — | The lore text. Plain prose, no markdown. |
| `category` | yes | — | One of: `world`, `character`, `location`, `faction`, `race`, `event`, `concept`, `item`, `creature`. Used for QA reporting only; not emitted. |
| `tier` | yes | — | 1, 2, or 3. Used for QA reporting only; not emitted. |
| `constant` | no | `false` | Set `true` only for the single world-overview entry if always-on context is wanted. |
| `probability` | no | `100` | Leave default unless an entry should fire intermittently. |
| `order` | no | `100` | Insertion order. Leave default. |

## 2. Final format (script-emitted)

### Top level

| Field | Value | Notes |
|---|---|---|
| `name` | from intermediate | e.g. `"The Fantasy World of Adolion"` |
| `description` | from intermediate | One-to-two sentence summary of coverage. |
| `is_creation` | `false` | Fixed. |
| `scan_depth` | `4` | Fixed. How many recent messages are scanned for keys. |
| `token_budget` | `512` | Fixed. Max tokens of entries injected at once. |
| `recursive_scanning` | `false` | Fixed. Entry contents do not trigger other entries. |
| `extensions.chub` | boilerplate | `id: 0`, `full_path: ""`, all other fields null/empty — filled in by Chub on upload. |
| `entries` | object | Keyed by stringified uid: `"1"`, `"2"`, ... |

### Per entry

Every entry carries this exact field set. Values marked *fixed* never vary; values marked *derived* are computed by the builder.

| Field | Value | Kind |
|---|---|---|
| `uid` | 1-based integer | derived (sequential) |
| `key` | keyword array | from intermediate `keys` |
| `keysecondary` | `[]` | fixed |
| `comment` | entity name | from intermediate `name` |
| `content` | lore text | from intermediate `content` |
| `constant` | `false` | from intermediate (default false) |
| `selective` | `true` | fixed |
| `selectiveLogic` | `0` | fixed |
| `order` | `100` | from intermediate (default 100) |
| `position` | `1` | fixed |
| `disable` | `false` | fixed |
| `addMemo` | `true` | fixed |
| `excludeRecursion` | `true` | fixed |
| `probability` | `100` | from intermediate (default 100) |
| `displayIndex` | 0-based integer | derived (sequential) |
| `useProbability` | `true` | fixed |
| `secondary_keys` | `[]` | fixed (mirrors `keysecondary`) |
| `keys` | keyword array | mirrors `key` |
| `id` | same as `uid` | derived |
| `priority` | `10` | fixed |
| `insertion_order` | `100` | mirrors `order` |
| `enabled` | `true` | fixed |
| `name` | entity name | mirrors `comment` |
| `extensions` | object below | derived |
| `case_sensitive` | `false` | fixed |
| `depth` | `4` | fixed |
| `characterFilter` | `null` | fixed |

Entry `extensions` object:

```json
{
  "depth": 4,
  "weight": 10,
  "addMemo": true,
  "displayIndex": <same as entry displayIndex>,
  "useProbability": true,
  "characterFilter": null,
  "excludeRecursion": true
}
```

### Reference entry (verbatim shape)

```json
"2": {
  "uid": 2,
  "key": ["Aegis City", "Aegis", "Holy City"],
  "keysecondary": [],
  "comment": "Aegis City",
  "content": "Aegis City is the capital city of the Darran Kingdom. It is the largest city on the continent of Sebela. Its ruler is King Davolan. It is otherwise known as the Holy City.",
  "constant": false,
  "selective": true,
  "selectiveLogic": 0,
  "order": 100,
  "position": 1,
  "disable": false,
  "addMemo": true,
  "excludeRecursion": true,
  "probability": 100,
  "displayIndex": 1,
  "useProbability": true,
  "secondary_keys": [],
  "keys": ["Aegis City", "Aegis", "Holy City"],
  "id": 2,
  "priority": 10,
  "insertion_order": 100,
  "enabled": true,
  "name": "Aegis City",
  "extensions": {
    "depth": 4,
    "weight": 10,
    "addMemo": true,
    "displayIndex": 1,
    "useProbability": true,
    "characterFilter": null,
    "excludeRecursion": true
  },
  "case_sensitive": false,
  "depth": 4,
  "characterFilter": null
}
```

### Behavioral implications of the fixed settings

- `recursive_scanning: false` + `excludeRecursion: true` — entries never trigger each other. Cross-mentions between entries exist for the LLM's benefit only.
- `token_budget: 512` — only ~3–6 entries can be active simultaneously. This is why individual entries must stay compact (see writing-style.md).
- `case_sensitive: false` — never add case variants of the same key (`"adolion"` and `"Adolion"` are redundant; keep one).
- `scan_depth: 4` — keys are matched against the last 4 messages, so keys must be words people actually type in chat.
