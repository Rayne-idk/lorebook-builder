"""Temporary script: repeatedly sample a few entries from both lorebooks for side-by-side comparison."""
import json, random, sys, textwrap

FILES = {
    "model1": "model1.solo-leveling.lorebook.json",
    "model2": "model2.solo-leveling.lorebook.json",
}

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    entries = d["entries"]
    return {e.get("comment") or (e.get("key") or ["?"])[0]: e for e in entries.values()}

def stats(name, entries):
    lens = [len(e.get("content", "")) for e in entries.values()]
    keyc = [len((e.get("key") or [])) + len((e.get("keysecondary") or [])) for e in entries.values()]
    print(f"[{name}] {len(entries)} entries | content chars: "
          f"total={sum(lens):,} avg={sum(lens)//len(lens)} "
          f"min={min(lens)} max={max(lens)} | avg keys/entry={sum(keyc)/len(keyc):.1f}")

def show(name, title, e):
    keys = ", ".join((e.get("key") or [])[:8])
    sec = ", ".join((e.get("keysecondary") or [])[:8])
    content = e.get("content", "")
    print(f"\n--- [{name}] {title} ---")
    print(f"  keys: {keys}")
    if sec:
        print(f"  secondary: {sec}")
    print(f"  content ({len(content)} chars):")
    print(textwrap.indent(textwrap.fill(content, 110, max_lines=14, placeholder=" […]"), "    "))

def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    per = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    random.seed()
    books = {n: load(p) for n, p in FILES.items()}

    print("=" * 70)
    print("CORPUS STATS")
    for n, e in books.items():
        stats(n, e)

    m1keys, m2keys = set(books["model1"]), set(books["model2"])
    print(f"\nentry titles only in model1 ({len(m1keys - m2keys)}): {sorted(m1keys - m2keys)}")
    print(f"\nentry titles only in model2 ({len(m2keys - m1keys)}): {sorted(m2keys - m1keys)}")
    shared = sorted(m1keys & m2keys)
    print(f"\nshared titles ({len(shared)})")

    for r in range(rounds):
        print("\n" + "=" * 70)
        print(f"ROUND {r+1}: shared entries (head-to-head)")
        for title in random.sample(shared, min(per, len(shared))):
            show("model1", title, books["model1"][title])
            show("model2", title, books["model2"][title])

if __name__ == "__main__":
    main()
