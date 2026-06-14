#!/usr/bin/env python3
"""Build and validate Chub/SillyTavern-format lorebooks.

Usage:
    python build_lorebook.py status   <research-dir> [--lorebook <out.lorebook.json>]
    python build_lorebook.py merge    <fragments-dir> -o <entries.json> --name <name> [--description <desc>]
    python build_lorebook.py build    <entries.json> -o <out.lorebook.json>
    python build_lorebook.py validate <lorebook.json>

The intermediate entries.json format is documented in ../references/format.md.
`merge` combines per-batch fragment files (each a bare JSON list of entries, or an
object with an "entries" list) into one intermediate entries.json.
The builder emits the full Chub-format JSON deterministically so the boilerplate
fields never have to be hand-written.
"""

import argparse
import json
import re
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

# A raw scrape smaller than this (chars) is treated as a stub, not real coverage.
# Keep in sync with the stub threshold quoted in SKILL.md Phase 3.
STUB_MIN_CHARS = 700


def slugify(name: str) -> str:
    """Canonical entity slug: lowercase, non-alphanumeric runs -> single hyphen.

    raw/<slug>.md filenames use this rule, so `status` can reconcile a manifest
    entity against its scraped file deterministically.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


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

    # Shared keys are expected and usually fine — linked entities surfacing
    # together is a feature, not a bug. Only flag the narrow false-trigger case:
    # a common word shared by multiple (often unrelated) entries.
    for k, owners in key_owners.items():
        if len(owners) > 1 and k in RISKY_KEYS:
            warnings.append(
                f"common word '{k}' is shared by multiple entries {owners} "
                f"and may false-trigger; consider a more specific key on the less-central one"
            )
    return warnings


def report_stats(entries: list[dict]) -> None:
    total = sum(estimate_tokens(e["content"]) for e in entries)
    print(f"  entries: {len(entries)}, total ~{total} tokens, "
          f"avg ~{total // max(1, len(entries))} tokens/entry")
    for counter, label in ((Counter(e.get("category", "?") for e in entries), "by category"),
                           (Counter(f"tier {e.get('tier', '?')}" for e in entries), "by tier")):
        print(f"  {label}: " + ", ".join(f"{k}={v}" for k, v in sorted(counter.items())))


def parse_manifest(path: Path) -> list[dict]:
    """Pull entity rows out of the manifest.md markdown table.

    Tolerant: any pipe row that isn't the header or a `---` separator is an
    entity. Columns follow `| entity | category | tier | source URL | status |`.
    """
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if cells[0].lower() == "entity":
            continue  # header
        if all(set(c) <= {"-", ":"} for c in cells if c):
            continue  # separator row
        row = {"entity": cells[0]}
        if len(cells) > 1:
            row["category"] = cells[1]
        if len(cells) > 2:
            row["tier"] = cells[2]
        row["status"] = cells[4] if len(cells) > 4 else (cells[-1] if len(cells) > 1 else "")
        rows.append(row)
    return rows


def written_names(frag_dir: Path) -> set[str]:
    """Lowercased names of every entry already present in any fragment file."""
    names: set[str] = set()
    if not frag_dir.is_dir():
        return names
    for ff in sorted(frag_dir.glob("*.json")):
        try:
            data = json.loads(ff.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "entries" in data:
            items = data["entries"]
        elif isinstance(data, list):
            items = data
        else:
            continue
        for e in items:
            nm = (e.get("name") or "").strip().lower()
            if nm:
                names.add(nm)
    return names


def _preview(names: list[str], n: int = 8) -> str:
    head = ", ".join(names[:n])
    return head + (f", ... (+{len(names) - n} more)" if len(names) > n else "")


def cmd_status(args: argparse.Namespace) -> int:
    """Report what a research dir already has on disk and the next phase to run.

    Lets an interrupted run resume from artifacts without re-deriving state in
    the model. The filesystem is ground truth (raw/ = scraped, fragments/ =
    written); the manifest is reconciled against it when present.
    """
    research = Path(args.research)
    if not research.is_dir():
        print(f"FRESH: {research} does not exist - start from Phase 0")
        return 0

    raw_dir, frag_dir = research / "raw", research / "fragments"
    manifest, entries_json = research / "manifest.md", research / "entries.json"

    raw_sizes: dict[str, int] = {}
    if raw_dir.is_dir():
        for f in raw_dir.glob("*.md"):
            if f.name.startswith("_index"):
                continue  # index-page scrapes aren't entity pages
            raw_sizes[f.stem] = f.stat().st_size
    written = written_names(frag_dir)
    rows = parse_manifest(manifest)
    lb = Path(args.lorebook) if args.lorebook else None

    n_stub = sum(1 for s in raw_sizes.values() if s < STUB_MIN_CHARS)
    print(f"Resume status for {research}:")
    print(f"  manifest:     {len(rows)} entities" if rows else "  manifest:     absent/empty")
    print(f"  raw/:         {len(raw_sizes)} scraped files ({n_stub} under stub threshold)")
    print(f"  fragments/:   {len(written)} entries written")
    print(f"  entries.json: {'present' if entries_json.is_file() else 'absent'}")
    if lb:
        print(f"  lorebook:     {'present' if lb.is_file() else 'absent'} ({lb})")

    if rows:
        pending, to_write = [], []
        for r in rows:
            if (r.get("status") or "").lower().startswith("dropped"):
                continue
            scraped = raw_sizes.get(slugify(r["entity"]), 0) >= STUB_MIN_CHARS
            if not scraped:
                pending.append(r["entity"])
            elif r["entity"].strip().lower() not in written:
                to_write.append(r["entity"])
        active = sum(1 for r in rows if not (r.get("status") or "").lower().startswith("dropped"))
        print(f"  reconciled ({active} active entities): "
              f"{len(pending)} need scraping, {len(to_write)} scraped but unwritten")
        if pending:
            print(f"  -> NEXT: Phase 3 - scrape {len(pending)}: {_preview(pending)}")
        elif to_write:
            print(f"  -> NEXT: Phase 4 - write {len(to_write)}: {_preview(to_write)}")
        elif not entries_json.is_file():
            print("  -> NEXT: Phase 5 - merge fragments & build")
        elif lb and not lb.is_file():
            print("  -> NEXT: Phase 5 - build from entries.json")
        else:
            print("  -> NEXT: Phase 6 - validate & QA (research looks complete)")
    else:
        if not raw_sizes:
            print("  -> NEXT: Phase 1 - no raw pages yet")
        elif not written:
            print("  -> NEXT: Phase 4 - raw pages exist but nothing written "
                  "(rebuild manifest first if it is missing)")
        elif not entries_json.is_file():
            print("  -> NEXT: Phase 5 - merge & build")
        else:
            print("  -> NEXT: Phase 6 - validate & QA")
    return 0


def _sort_key(e: dict) -> tuple:
    """world first, then tier ascending, then name; matches Phase 4 ordering."""
    is_world = 0 if e.get("category") == "world" else 1
    tier = e.get("tier") or 2
    return (is_world, tier, (e.get("name") or "").lower())


def cmd_merge(args: argparse.Namespace) -> int:
    """Combine per-batch fragment files into one intermediate entries.json.

    Each fragment is a bare JSON list of entry objects, or an object with an
    "entries" list. Writer subagents produce one fragment per batch so their
    entry text never has to pass back through the orchestrator's context.
    """
    frag_dir = Path(args.fragments)
    if not frag_dir.is_dir():
        print(f"FAILED: {frag_dir} is not a directory")
        return 1
    frag_files = sorted(frag_dir.glob("*.json"))
    if not frag_files:
        print(f"FAILED: no .json fragment files in {frag_dir}")
        return 1

    merged: list[dict] = []
    seen: dict[str, str] = {}  # lowercased name -> fragment it first appeared in
    warnings: list[str] = []
    for ff in frag_files:
        try:
            data = json.loads(ff.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"FAILED: {ff.name} is not valid JSON: {exc}")
            return 1
        if isinstance(data, dict) and "entries" in data:
            items = data["entries"]
        elif isinstance(data, list):
            items = data
        else:
            print(f"FAILED: {ff.name} must be a JSON list or an object with an 'entries' list")
            return 1
        for e in items:
            nm = (e.get("name") or "").strip().lower()
            if nm and nm in seen:
                warnings.append(f"duplicate entry '{e.get('name')}' in {ff.name} "
                                f"(already in {seen[nm]}); kept the first")
                continue
            if nm:
                seen[nm] = ff.name
            merged.append(e)

    merged.sort(key=_sort_key)
    out_obj = {
        "name": args.name,
        "description": args.description or "",
        "entries": merged,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(out_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: merged {len(frag_files)} fragment(s) into {out} ({len(merged)} entries)")
    for w in warnings:
        print(f"  WARN: {w}")

    errors = check_intermediate(out_obj)
    if errors:
        print(f"  {len(errors)} validation error(s) - fix in the fragments and re-merge:")
        for err in errors:
            print(f"  ERROR: {err}")
        return 1
    return 0


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

    p_status = sub.add_parser("status", help="report resume state of a research dir and the next phase to run")
    p_status.add_argument("research", help="path to research/<slug> directory")
    p_status.add_argument("--lorebook", help="optional path to output/<slug>.lorebook.json to check")
    p_status.set_defaults(func=cmd_status)

    p_merge = sub.add_parser("merge", help="merge per-batch entry fragments into one entries.json")
    p_merge.add_argument("fragments", help="directory of *.json fragment files")
    p_merge.add_argument("-o", "--output", required=True, help="output entries.json path")
    p_merge.add_argument("--name", required=True, help="top-level lorebook name")
    p_merge.add_argument("--description", default="", help="top-level lorebook description")
    p_merge.set_defaults(func=cmd_merge)

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
