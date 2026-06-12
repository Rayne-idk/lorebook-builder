#!/usr/bin/env python3
"""Build and validate Chub/SillyTavern-format lorebooks.

Usage:
    python build_lorebook.py build  <entries.json> -o <out.lorebook.json>
    python build_lorebook.py validate <lorebook.json>

The intermediate entries.json format is documented in ../references/format.md.
The builder emits the full Chub-format JSON deterministically so the boilerplate
fields never have to be hand-written.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

VALID_CATEGORIES = {
    "world", "character", "location", "faction", "race",
    "event", "concept", "item", "creature",
}

# Words too common in ordinary chat to be safe single-word keys.
RISKY_KEYS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "is", "it",
    "he", "she", "they", "you", "i", "we", "me", "my", "his", "her",
    "man", "woman", "boy", "girl", "king", "queen", "god", "gods", "world",
    "war", "magic", "city", "home", "light", "dark", "fire", "water", "time",
    "day", "night", "mother", "father", "son", "daughter", "love", "death",
}

# Per-tier token caps (see references/writing-style.md).
TIER_TOKEN_CAPS = {1: 300, 2: 150, 3: 80}


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def chub_extensions() -> dict:
    return {
        "chub": {
            "expressions": None,
            "alt_expressions": None,
            "id": 0,
            "full_path": "",
            "related_lorebooks": [],
            "background_image": "",
            "preset": None,
            "extensions": [],
            "custom_css": None,
        }
    }


def build_entry(uid: int, display_index: int, e: dict) -> dict:
    keys = e["keys"]
    return {
        "uid": uid,
        "key": keys,
        "keysecondary": [],
        "comment": e["name"],
        "content": e["content"],
        "constant": e.get("constant", False),
        "selective": True,
        "selectiveLogic": 0,
        "order": e.get("order", 100),
        "position": 1,
        "disable": False,
        "addMemo": True,
        "excludeRecursion": True,
        "probability": e.get("probability", 100),
        "displayIndex": display_index,
        "useProbability": True,
        "secondary_keys": [],
        "keys": keys,
        "id": uid,
        "priority": 10,
        "insertion_order": e.get("order", 100),
        "enabled": True,
        "name": e["name"],
        "extensions": {
            "depth": 4,
            "weight": 10,
            "addMemo": True,
            "displayIndex": display_index,
            "useProbability": True,
            "characterFilter": None,
            "excludeRecursion": True,
        },
        "case_sensitive": False,
        "depth": 4,
        "characterFilter": None,
    }


def check_intermediate(data: dict) -> list[str]:
    """Return a list of fatal error strings for an intermediate entries file."""
    errors = []
    for field in ("name", "entries"):
        if field not in data:
            errors.append(f"top-level field '{field}' is missing")
    if errors:
        return errors
    if not isinstance(data["entries"], list) or not data["entries"]:
        return ["'entries' must be a non-empty list"]

    for i, e in enumerate(data["entries"], 1):
        label = f"entry {i} ({e.get('name', '?')})"
        for field in ("name", "keys", "content", "category", "tier"):
            if not e.get(field) and e.get(field) != 0:
                errors.append(f"{label}: missing or empty '{field}'")
        if e.get("category") and e["category"] not in VALID_CATEGORIES:
            errors.append(f"{label}: category '{e['category']}' not in {sorted(VALID_CATEGORIES)}")
        if e.get("tier") not in (1, 2, 3, None):
            errors.append(f"{label}: tier must be 1, 2, or 3")
        if isinstance(e.get("keys"), list):
            lowered = [k.lower() for k in e["keys"]]
            if len(set(lowered)) != len(lowered):
                errors.append(f"{label}: case-duplicate keys (case_sensitive is false)")
    return errors


def lint_entries(entries: list[dict]) -> list[str]:
    """Return warnings (non-fatal) about content length and key quality."""
    warnings = []
    key_owners: dict[str, list[str]] = {}

    world_entries = [e for e in entries if e.get("category") == "world"]
    if len(world_entries) != 1:
        warnings.append(f"expected exactly 1 'world' entry, found {len(world_entries)}")

    for e in entries:
        name, tier = e["name"], e.get("tier", 2)
        tokens = estimate_tokens(e["content"])
        cap = TIER_TOKEN_CAPS.get(tier, 150)
        if tokens > cap:
            warnings.append(f"'{name}': ~{tokens} tokens exceeds tier-{tier} cap of {cap}")
        if len(e["keys"]) > 6:
            warnings.append(f"'{name}': {len(e['keys'])} keys (max recommended is 6)")
        lowered = [k.lower().strip() for k in e["keys"]]
        if len(set(lowered)) != len(lowered):
            warnings.append(f"'{name}': case-duplicate keys (case_sensitive is false)")
        for k in e["keys"]:
            kl = k.lower().strip()
            if kl in RISKY_KEYS:
                warnings.append(f"'{name}': key '{k}' is a common word likely to false-trigger")
            if len(kl) < 3:
                warnings.append(f"'{name}': key '{k}' is under 3 characters")
        for kl in set(lowered):
            key_owners.setdefault(kl, []).append(name)

    for k, owners in key_owners.items():
        if len(owners) > 1:
            warnings.append(f"key '{k}' is shared by multiple entries: {owners}")
    return warnings


def report_stats(entries: list[dict]) -> None:
    total = sum(estimate_tokens(e["content"]) for e in entries)
    print(f"  entries: {len(entries)}, total ~{total} tokens, "
          f"avg ~{total // max(1, len(entries))} tokens/entry")
    for counter, label in ((Counter(e.get("category", "?") for e in entries), "by category"),
                           (Counter(f"tier {e.get('tier', '?')}" for e in entries), "by tier")):
        print(f"  {label}: " + ", ".join(f"{k}={v}" for k, v in sorted(counter.items())))


def cmd_build(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.entries).read_text(encoding="utf-8"))
    errors = check_intermediate(data)
    if errors:
        print(f"FAILED: {len(errors)} error(s) in {args.entries}")
        for err in errors:
            print(f"  ERROR: {err}")
        return 1

    entries = data["entries"]
    book = {
        "name": data["name"],
        "description": data.get("description", ""),
        "is_creation": False,
        "scan_depth": 4,
        "token_budget": 512,
        "recursive_scanning": False,
        "extensions": chub_extensions(),
        "entries": {
            str(i): build_entry(i, i - 1, e) for i, e in enumerate(entries, 1)
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(book, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: wrote {out}")
    report_stats(entries)
    for w in lint_entries(entries):
        print(f"  WARN: {w}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    book = json.loads(Path(args.lorebook).read_text(encoding="utf-8"))
    errors, warnings = [], []

    for field, expected in (("is_creation", False), ("scan_depth", 4),
                            ("token_budget", 512), ("recursive_scanning", False)):
        if book.get(field) != expected:
            errors.append(f"top-level '{field}' should be {expected}, got {book.get(field)!r}")
    if not book.get("name"):
        errors.append("top-level 'name' is empty")
    if "chub" not in book.get("extensions", {}):
        errors.append("missing extensions.chub block")

    entries = book.get("entries", {})
    if not isinstance(entries, dict) or not entries:
        errors.append("'entries' must be a non-empty object keyed by uid strings")
        entries = {}

    reference = build_entry(0, 0, {"name": "", "keys": [], "content": ""})
    for k, e in entries.items():
        label = f"entry {k} ({e.get('name', '?')})"
        if str(e.get("uid")) != k:
            errors.append(f"{label}: dict key {k!r} != uid {e.get('uid')!r}")
        if e.get("id") != e.get("uid"):
            errors.append(f"{label}: id != uid")
        if e.get("key") != e.get("keys"):
            errors.append(f"{label}: 'key' and 'keys' differ")
        if e.get("keysecondary") != e.get("secondary_keys"):
            errors.append(f"{label}: 'keysecondary' and 'secondary_keys' differ")
        if e.get("comment") != e.get("name"):
            errors.append(f"{label}: 'comment' and 'name' differ")
        if e.get("extensions", {}).get("displayIndex") != e.get("displayIndex"):
            errors.append(f"{label}: extensions.displayIndex != displayIndex")
        missing = set(reference) - set(e)
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}")
        if not e.get("content", "").strip():
            errors.append(f"{label}: empty content")
        if not e.get("keys"):
            errors.append(f"{label}: no keys")

    simple = [{"name": e.get("name", "?"), "keys": e.get("keys", []),
               "content": e.get("content", ""), "tier": 2}
              for e in entries.values()]
    if simple:
        warnings.extend(w for w in lint_entries(simple)
                        if "world' entry" not in w)  # final file has no category info

    if errors:
        print(f"FAILED: {len(errors)} error(s) in {args.lorebook}")
        for err in errors:
            print(f"  ERROR: {err}")
        return 1
    print(f"OK: {args.lorebook} is structurally valid")
    if simple:
        report_stats([dict(e, category="?") for e in simple])
    for w in warnings:
        print(f"  WARN: {w}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build final lorebook from intermediate entries.json")
    p_build.add_argument("entries", help="path to intermediate entries.json")
    p_build.add_argument("-o", "--output", required=True, help="output lorebook.json path")
    p_build.set_defaults(func=cmd_build)

    p_val = sub.add_parser("validate", help="validate a final lorebook.json")
    p_val.add_argument("lorebook", help="path to final lorebook.json")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
