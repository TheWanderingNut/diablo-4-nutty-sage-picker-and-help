"""Skill tree map from Maxroll's game data (node positions). Read-only."""
import json
import re

from screen import ROOT


DATA = ROOT / "data"


DATA_URLS = {
    "d4_data.min.json": "https://assets-ng.maxroll.gg/d4-tools/game/data.min.json",
    "d4_data.enus.json": "https://assets-ng.maxroll.gg/d4-tools/game/data.enus.json",
}


SX_H = 6.88e-5


SY_H = 1.259e-4


def ensure_data():
    import requests
    DATA.mkdir(exist_ok=True)
    for name, url in DATA_URLS.items():
        f = DATA / name
        if not f.exists():
            print(f"[d4map] downloading {name} from maxroll...")
            f.write_bytes(requests.get(url, timeout=120).content)


class TreeMap:
    def __init__(self, cls: str):
        ensure_data()
        d = json.load(open(DATA / "d4_data.min.json", encoding="utf-8"))
        e = json.load(open(DATA / "d4_data.enus.json", encoding="utf-8"))
        rewards = d["skillTreeRewards"]
        self.nodes = {}  # (skill, upgrade|None) -> {"id","x","y","level"}
        for n in d["skillTrees"][cls]["nodes"]:
            rw = rewards.get(n.get("rewardId"), {})
            power = rw.get("power")
            if not power:
                continue
            skill = e["skills"][power]["name"]
            up = None
            if rw.get("type") == 1:
                idx = next(i for i, m in enumerate(d["skills"][power]["mods"]) if m["id"] == rw["mod"])
                up = e["skills"][power]["mods"][idx]["name"]
            self.nodes[(skill.lower(), up.lower() if up else None)] = {
                "id": n["id"], "x": n["pos"]["x"], "y": n["pos"]["y"], "level": n.get("requiredLevel", 0),
                "skill": skill, "upgrade": up}

    def get(self, skill: str, upgrade: str | None = None) -> dict:
        key = (skill.lower(), upgrade.lower() if upgrade else None)
        if key not in self.nodes:
            raise KeyError(f"{skill} -> {upgrade} not in the {len(self.nodes)}-node map")
        return self.nodes[key]


def title_match(tip: dict, want: str) -> bool:
    """Tooltip title == wanted name, tolerant of OCR splitting a title across lines or 1-2 wrong letters."""
    import difflib
    lines = [t for t in [tip.get("name")] + tip.get("lines", []) if t]
    cands = lines + [a + b for a, b in zip(lines, lines[1:])]  # "Cooldown" + "Reduction"
    w = _norm(want)
    for c in cands:
        n = _norm(c)
        if n == w or (len(w) >= 6 and difflib.SequenceMatcher(None, n, w).ratio() >= 0.86):
            return True
    return False


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())
