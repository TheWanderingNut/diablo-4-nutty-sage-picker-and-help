"""Phase 3: Maxroll guide link -> click plan for YOUR level and points. No Claude, no guessing.

  python maxplan.py https://maxroll.gg/d4/build-guides/blazing-scream-warlock-leveling-guide --points 30
  python maxplan.py <guide url or profile id> --points 30 --out plans/my_build.json

How: the guide page embeds a Maxroll planner profile (data-d4-profile). That profile has staged skill-tree
snapshots (node id -> rank). We take the furthest stage you can afford, then spend leftovers the way the NEXT
stage does, and order clicks so base skills come before their upgrades (D4 requires that).
"""
import argparse
import json
import re

import requests

from treemap import TreeMap, ensure_data, DATA

CLASS_TREES = {"Warlock": "Warlock", "Sorcerer": "Sorcerer", "Druid": "Druid", "Barbarian": "Barbarian",
               "Rogue": "Rogue", "Necromancer": "Necromancer", "Spiritborn": "Spiritborn", "Paladin": "Paladin_NEW"}


TIERLISTS = {"leveling": "https://maxroll.gg/d4/tierlists/leveling-tier-list",
             "endgame": "https://maxroll.gg/d4/tierlists/endgame-tier-list"}


def best_guide(cls: str, level: int) -> str:
    """Joe's idea: no link needed. Read class + level, take the highest-ranked Maxroll build for that class.
    Tier list pages list guides best-first (S tier at the top); the class is in each guide's URL."""
    kind = "leveling" if level < 60 else "endgame"
    html = requests.get(TIERLISTS[kind], timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    slug = cls.lower().replace("_new", "")
    for path in dict.fromkeys(re.findall(r'(/d4/build-guides/[a-z0-9-]+)', html)):
        if f"-{slug}-" in path + "-":
            return "https://maxroll.gg" + path
    raise SystemExit(f"no {kind} {cls} build on Maxroll's tier list")


def profile_id_from(src: str) -> str:
    if re.fullmatch(r"[a-z0-9]{6,12}", src):
        return src
    html = requests.get(src, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    ids = re.findall(r'data-d4-profile="([a-z0-9]+)"\s+data-d4-type="skills', html) or \
        re.findall(r'data-d4-profile="([a-z0-9]+)"', html) or \
        [i for i in re.findall(r'd4/planner/([a-z0-9]{6,12})', html) if i != "builds"]  # endgame guides link it
    if not ids:
        raise SystemExit("no Maxroll planner profile found on that page")
    return ids[0]


def load_profile(pid: str) -> dict:
    p = requests.get(f"https://planners.maxroll.gg/profiles/d4/{pid}", timeout=30).json()
    p["data"] = json.loads(p["data"])
    return p


def pick_variant(variants: list, level: int) -> int:
    """A planner holds several versions (e.g. 'Leveling', 'Starter', 'Endgame', 'Push'). Pick by NAME for the
    character's level, only among versions that actually have a staged skill tree."""
    usable = [i for i, v in enumerate(variants) if v.get("skillTree", {}).get("steps")] or [0]
    want = ("level",) if level < 60 else ("endgame", "end game", "midgame", "starter")
    for w in want:
        for i in usable:
            if w in (variants[i].get("name") or "").lower():
                return i
    return usable[0]


def make_plan(src: str, points: int, level: int = 100, variant: int | None = None) -> dict:
    ensure_data()
    pid = profile_id_from(src)
    prof = load_profile(pid)
    if variant is None:
        variant = pick_variant(prof["data"]["profiles"], level)
    pv = prof["data"]["profiles"][variant]
    cls = prof.get("class") or "Warlock"
    tree_key = CLASS_TREES.get(cls, cls)
    d = json.load(open(DATA / "d4_data.min.json", encoding="utf-8"))
    nodes = {n["id"]: n for n in d["skillTrees"][tree_key]["nodes"]}
    rewards = d["skillTreeRewards"]
    tmap = TreeMap(tree_key)
    by_id = {v["id"]: v for v in tmap.nodes.values()}

    def is_basic(nid):  # Basic skills come with 1 free rank (Maxroll counts it)
        return "_Basic_" in nodes[nid].get("rewardId", "") and rewards[nodes[nid]["rewardId"]].get("type") == 0

    def cost(state):
        return sum(v - (1 if is_basic(int(k)) else 0) for k, v in state.items() if v)

    stages = [{int(k): v for k, v in s["data"].items() if v} for s in pv["skillTree"]["steps"]]
    # furthest affordable stage
    chosen, nxt = {}, None
    for i, st in enumerate(stages):
        if cost(st) <= points:
            chosen = st
            nxt = stages[i + 1] if i + 1 < len(stages) else None
        else:
            nxt = st
            break
    target = dict(chosen)

    def skill_of(nid):
        return rewards[nodes[nid]["rewardId"]].get("power")

    def is_variant(nid):
        return re.search(r"_Upgrade[ABC]$", nodes[nid].get("rewardId", "")) is not None

    # level-aware variant swaps: later stages replace a variant (e.g. Meat Shields -> Fallen Rush @30)
    for st in stages:
        for nid in st:
            if is_variant(nid) and nid not in target and nodes[nid].get("requiredLevel", 0) <= level:
                old = [t for t in target if is_variant(t) and skill_of(t) == skill_of(nid)]
                if old and stages.index(st) > stages.index(chosen) if chosen in stages else False:
                    for o in old:
                        target.pop(o)
                    target[nid] = 1
    # a Basic skill's free rank doesn't unlock upgrades: it needs 1 real point (rank 2)
    for nid in list(target):
        if not is_basic(nid) and rewards[nodes[nid]["rewardId"]].get("type") == 1:
            base = next(b for b in nodes if rewards.get(nodes[b].get("rewardId"), {}).get("type") == 0
                        and skill_of(b) == skill_of(nid))
            if is_basic(base) and target.get(base, 1) < 2:
                target[base] = 2
    def group(nid):  # D4 pick-one sets: Upgrade1|2, Upgrade3|4, one Variant/UpgradeA-C
        m = re.search(r"_(Upgrade|Variant)([1-4A-C])$", nodes[nid].get("rewardId", ""))
        if not m:
            return None
        g = m.group(2)
        return "V" if g in "ABC" or m.group(1) == "Variant" else ("P12" if g in "12" else "P34")

    def clash(a, b):
        return a != b and skill_of(a) == skill_of(b) and group(a) is not None and group(a) == group(b)

    left = points - cost(target)
    # spend leftovers toward the next stage like a person would: every skill + its upgrades first (top of the tree
    # first), THEN extra ranks. (Endgame planners often have ONE stage that costs more than the character has -
    # the old "ranks only" fill dropped every upgrade.)
    if nxt and left > 0:
        is_skill = lambda n: rewards[nodes[n]["rewardId"]].get("type") == 0
        for b in sorted((n for n in nxt if is_skill(n)), key=lambda n: nodes[n]["pos"]["y"]):
            need = (2 if is_basic(b) and any(not is_skill(u) and skill_of(u) == skill_of(b) for u in nxt) else 1)
            add = max(0, need - target.get(b, 0)) - (1 if is_basic(b) and not target.get(b) else 0)
            if add > left:
                continue
            if need > target.get(b, 0):
                target[b], left = need, left - add
            for u in nxt:
                if left > 0 and not is_skill(u) and skill_of(u) == skill_of(b) and u not in target \
                        and not any(clash(u, t) for t in target):
                    target[u], left = 1, left - 1
        for nid, r in nxt.items():
            if left <= 0:
                break
            if is_skill(nid) and r > target.get(nid, 0):
                add = min(left, r - target.get(nid, 0))
                target[nid] = target.get(nid, 0) + add
                left -= add
    # click order: finish each base skill's planned ranks -> its upgrades
    steps = []
    bases = sorted((n for n in target if rewards[nodes[n]["rewardId"]].get("type") == 0),
                   key=lambda n: nodes[n]["pos"]["y"])  # top of the tree first = fewest drags
    for b in bases:
        info = by_id[b]
        clicks = target[b] - (1 if is_basic(b) else 0)
        if clicks > 0:
            steps.append({"skill": info["skill"], "upgrade": None, "times": clicks})
        for u in target:
            ui = by_id.get(u)
            if ui and ui["upgrade"] and ui["skill"] == info["skill"]:
                steps.append({"skill": ui["skill"], "upgrade": ui["upgrade"], "times": 1})
    spent = sum(s["times"] for s in steps)
    return {"game": "diablo4", "class": tree_key,
            "build_name": f"{prof.get('name')} [{pv.get('name')}] - {spent} points",
            "source": f"https://planners.maxroll.gg/profiles/d4/{pid}",
            "skill_bar": [json.load(open(DATA / "d4_data.enus.json", encoding="utf-8"))["skills"][s]["name"]
                          for s in pv.get("skillBar", [])],
            "unspent": points - spent, "steps": steps, "book_of_the_dead": book_of_the_dead(pv),
            "minion_upgrades": pv.get("minionUpgrades") or [],
            "class_setup": class_setup(pv),
            "specialization": _enus_name(pv["specialization"]) if pv.get("specialization") else None,
            "basic_skills": [by_id[n]["skill"] for n in target if is_basic(n)]}  # come with 1 free rank


def tree_sections(tree_key: str) -> dict:
    """Joe (10/9): name WHERE a node is for the 'click by hand' report. Each hub + its circle of skills is one skill
    category; number them from the top of the tree: {skill name: section number}."""
    d = json.load(open(DATA / "d4_data.min.json", encoding="utf-8"))
    nodes = {n["id"]: n for n in d["skillTrees"][tree_key]["nodes"]}
    rewards = d["skillTreeRewards"]
    cat_y, skill_cat = {}, {}
    for v in TreeMap(tree_key).nodes.values():
        if v["upgrade"]:
            continue
        rw = rewards.get(nodes[v["id"]].get("rewardId"), {})
        cat = d["skills"].get(str(rw.get("power")), {}).get("category")
        skill_cat[v["skill"]] = cat
        cat_y.setdefault(cat, []).append(v["y"])
    order = sorted(cat_y, key=lambda c: sum(cat_y[c]) / len(cat_y[c]))
    return {s: order.index(c) + 1 for s, c in skill_cat.items()}


def where(step: dict, sections: dict) -> str:
    """'Section 6 (from the top): Blood Wave -> upgrade "Hematolagnia"' style text for one plan step."""
    sec = sections.get(step["skill"])
    loc = f"Section {sec} (counting the hubs from the top)" if sec else "?"
    if step.get("upgrade"):
        return f'{loc}: {step["skill"]}, the small upgrade node "{step["upgrade"]}"'
    return f'{loc}: the big square "{step["skill"]}"' + (f' x{step["times"]}' if step.get("times", 1) > 1 else "")


def _enus_name(key: str, with_desc: bool = False) -> str | None:
    """Find a game id like 'Rogue_Talent_Mechanic_T1_N2' in any enus table -> 'Preparation' (+ short description)."""
    e = json.load(open(DATA / "d4_data.enus.json", encoding="utf-8"))
    for table in e.values():
        if isinstance(table, dict) and isinstance(table.get(key), dict) and table[key].get("name"):
            n = table[key]["name"]
            if with_desc and table[key].get("desc"):
                d = re.sub(r"\{[^}]*\}|\\\[\+\\\]|\[[^\]]*\]", "", table[key]["desc"]).replace("\r\n", " ")
                d = re.sub(r"\s+", " ", d).strip()
                n += f" - {d[:150]}{'...' if len(d) > 150 else ''}"
            return n
    return None


def class_setup(pv: dict) -> list[str]:
    """Things the bot doesn't click yet but the guide sets (Joe 10/9: 'put in the note what it should be set to'):
    class specialization / mechanic and the mercenary pair."""
    out = []
    spec = pv.get("specialization")
    if spec:
        out.append(f"Specialization (class panel, Shift+C): {_enus_name(spec, True) or spec}")
    merc = pv.get("mercenary") or {}
    if merc.get("id"):
        hired = _enus_name(merc["id"]) or merc["id"]
        line = f"Mercenary: hire {hired}"
        if merc.get("support"):
            line += f", reinforcement {_enus_name(merc['support']) or merc['support']}"
            skills = [_enus_name(s) for s in merc.get("supportSkills", []) if s.startswith("Mercenary_")]
            if any(skills):
                line += f" (its skill: {', '.join(s for s in skills if s)})"
        out.append(line)
    return out


def book_of_the_dead(pv: dict) -> list[str]:
    """Necromancer minion choices, e.g. 'Necromancer_SkeletonMage_Shadow_Passive_UpgradeB' -> readable lines."""
    names = {"SkeletonWarrior": "Skeletal Warriors", "SkeletonMage": "Skeletal Mages", "Golem": "Golem"}
    pick = {"Sacrifice": "SACRIFICE (no minion, big bonus instead)", "UpgradeA": "1st upgrade",
            "UpgradeB": "2nd upgrade"}
    out = []
    for u in pv.get("minionUpgrades") or []:
        m = re.match(r"Necromancer_([A-Za-z]+)_([A-Za-z]+)_Passive_([A-Za-z]+)", u)
        if m:
            out.append(f"{names.get(m.group(1), m.group(1)):18} {m.group(2):10} -> {pick.get(m.group(3), m.group(3))}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="maxroll guide URL or planner profile id")
    ap.add_argument("--points", type=int, required=True)
    ap.add_argument("--level", type=int, default=100)
    ap.add_argument("--out")
    a = ap.parse_args()
    plan = make_plan(a.src, a.points, a.level)
    out = a.out or f"plans/diablo4_auto_{a.points}pts.json"
    json.dump(plan, open(out, "w", encoding="utf-8"), indent=2)
    print(f"{plan['build_name']}  ->  {out}  (unspent {plan['unspent']})")
    print("skill bar:", plan["skill_bar"])
    for s in plan["steps"]:
        print(f"  {s['skill']}" + (f" -> {s['upgrade']}" if s["upgrade"] else "") + f"  x{s['times']}")
