"""Joe's idea: after a run, open a short "how to play" note in Notepad for the build that was just set up.

  python howto.py plans/_last_auto_plan.json      # write + open the note for the last run

Content: the build name + link, what's on each key, and the first sentence of up to 5 gameplay tips from the
Maxroll guide (its Skills section on endgame guides, Summary on leveling guides). Short on purpose; the link has the rest.
"""
import html as H
import json
import re
import subprocess
import sys
from pathlib import Path

import requests

from screen import ROOT  # noqa: E402  (next to the .exe when bundled)
KEYS = ["1", "2", "3", "4", "Left mouse", "Right mouse"]


def _sections(url: str) -> dict:
    page = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", page, flags=re.S)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        name = re.sub(r"<[^>]+>|Collapse", "", parts[i]).strip()
        lines = [H.unescape(re.sub(r"<[^>]+>", " ", x)) for x in re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>",
                                                                          parts[i + 1], re.S)]
        out[name] = [re.sub(r"\s+([.,!?])", r"\1", re.sub(r"\s+", " ", x)).strip() for x in lines
                     if len(x.strip()) > 25]
    return out


def tips(url: str, n: int = 5) -> list[str]:
    try:
        s = _sections(url)
    except Exception:
        return []
    skills = [x for x in s.get("Skills", []) if not x.lower().startswith("learn more")]
    picked = skills if len(skills) >= 3 else s.get("Summary", [])
    if picked is not skills:
        picked = picked[1:]  # leveling Summary opens with flavour text
    out = []
    for x in picked[:n]:
        first = re.split(r"(?<=[.!?])\s", x)[0]
        out.append(first if len(first) <= 160 else first[:157] + "...")
    return out


def write_howto(plan: dict, guide_url: str, open_it: bool = True) -> Path:
    name = re.sub(r" - \d+ points$", "", plan.get("build_name", "Build"))
    lines = [name, "=" * len(name), ""]
    if plan.get("by_hand"):
        lines += ["MISSED! The bot couldn't click these - please add them by hand in the skill tree (A):"] + \
                 [f"   - {x}" for x in plan["by_hand"]] + [""]
    lines += ["YOUR KEYS"]
    later = set(plan.get("not_learned_yet") or [])
    for k, sk in zip(KEYS, plan.get("skill_bar", [])):
        lines.append(f"  {k:12} {sk}" + ("   (not learned yet - comes later as you level)" if sk in later else ""))
    if plan.get("class_setup"):
        lines += ["", "SET THESE BY HAND (the bot doesn't click them yet)"] + [f"  - {x}" for x in plan["class_setup"]]
    book = plan.get("book_of_the_dead") or []
    if book:
        lines += ["", "BOOK OF THE DEAD (Necromancer)"] + [f"  {x}" for x in book]
    t = tips(guide_url)
    if t:
        lines += ["", "HOW TO PLAY IT (from the Maxroll guide)"] + [f"  - {x}" for x in t]
    lines += ["", f"Full guide: {guide_url}"]
    if plan.get("source"):
        lines.append(f"Planner (gear, paragon, glyphs): {plan['source']}")
    lines += ["", "Set up by Build Pilot."]
    path = ROOT / "plans" / (re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + "_HOW_TO_PLAY.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    if open_it:
        subprocess.Popen(["notepad.exe", str(path)])
    return path


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1] if len(sys.argv) > 1 else ROOT / "plans" / "_last_auto_plan.json",
                          encoding="utf-8"))
    print(write_howto(plan, plan.get("guide") or plan["source"], open_it="--no-open" not in sys.argv))
