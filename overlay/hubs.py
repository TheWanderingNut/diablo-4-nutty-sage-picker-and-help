"""Skill-tree SECTIONS and their HUBS (the big diamonds), from Maxroll's game data. Read-only, shared by the bot
(Build Pilot) and the guide (BOB) for Joe's ghost-outline lineup (10/10): the overlay draws a section's hub + skill
squares where they should sit, the player drags the tree until it locks green.

A hub = the no-reward node that a section's big skill squares are wired to. Each base skill belongs to the hub it
connects to; sections are numbered from the top of the tree.
"""
import collections
import json

from treemap import DATA, ensure_data


def tree_sections(tree_key: str) -> list[dict]:
    """[{"hub": (x, y), "skills": {skill name: (x, y)}, "section": n}, ...] top to bottom (tree units)."""
    ensure_data()
    d = json.load(open(DATA / "d4_data.min.json", encoding="utf-8"))
    e = json.load(open(DATA / "d4_data.enus.json", encoding="utf-8"))
    rw = d["skillTreeRewards"]
    t = d["skillTrees"][tree_key]
    nodes = dict(enumerate(t["nodes"]))  # connections refer to the node's POSITION in the list, not its id
    adj = collections.defaultdict(set)
    for c in t["connections"]:
        adj[c["node1"]].add(c["node2"])
        adj[c["node2"]].add(c["node1"])

    def base(n):
        r = rw.get(n.get("rewardId"), {})
        return r.get("type") == 0 and r.get("power")

    hubs = collections.defaultdict(dict)
    for nid, n in nodes.items():
        if not base(n):
            continue
        name = e["skills"][rw[n["rewardId"]]["power"]]["name"]
        # the hub = the no-reward neighbour with the MOST base skills attached
        cands = [m for m in adj[nid] if not rw.get(nodes[m].get("rewardId"), {}).get("power")]
        if not cands:
            continue
        h = max(cands, key=lambda m: sum(1 for x in adj[m] if base(nodes[x])))
        hubs[h][name] = (n["pos"]["x"], n["pos"]["y"])
    out = [{"hub": (nodes[h]["pos"]["x"], nodes[h]["pos"]["y"]), "skills": sk}
           for h, sk in hubs.items() if len(sk) >= 2]
    out.sort(key=lambda s: s["hub"][1])
    for i, s in enumerate(out, 1):
        s["section"] = i
    return out


if __name__ == "__main__":
    import sys
    for s in tree_sections(sys.argv[1] if len(sys.argv) > 1 else "Warlock"):
        print(f"section {s['section']}: hub {tuple(round(v) for v in s['hub'])} -> {sorted(s['skills'])}")
