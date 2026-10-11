"""Self-labeling Diablo IV UI dataset (Joe 10/10). READ-ONLY: saves screenshots + YOLO labels, never touches the game.

Every time a tree section LOCKS in the ghost-outline lineup we know exactly where every node is (the tree is rigid
and the game data has every node's position), so the frame labels itself. A few hundred of these -> train a small,
fast YOLO detector (Project AIRI did the same for Balatro with ~1.1k shots).

Only on when the dataset folder exists (Joe's PC) or BOB_COLLECT=1; BOB_COLLECT=0 switches it off. Saves to D4_DATASET (default
C:\\Users\\<you>\\Projects\\d4-ui-dataset): images/<id>.jpg + labels/<id>.txt (YOLO: class cx cy w h, 0..1).
"""
import os
import time
from pathlib import Path

CLASSES = ["hub", "skill", "upgrade"]  # section diamond, big skill square, small upgrade node
ROOT = Path(os.environ.get("D4_DATASET", Path.home() / "Projects" / "d4-ui-dataset"))
HALF = {"hub": 0.045, "skill": 0.026, "upgrade": 0.015}  # box half-size as a fraction of screen height
_last = 0.0


def hidden(fx, fy):
    """Game panels that cover the tree (fractions of the screen): 'points spent' box top-left, Keyword Search top-right,
    Skill Assignment bar bottom-middle. Nodes under them aren't visible, so they get no label."""
    return ((fx < 0.155 and fy < 0.19) or (fx > 0.765 and fy < 0.12)
            or (0.36 < fx < 0.64 and fy > 0.84))


def enabled():
    """Off for other players: on only when BOB_COLLECT=1, or when the dataset folder already exists (Joe's PC)."""
    v = os.environ.get("BOB_COLLECT")
    return v == "1" if v is not None else ROOT.exists()


def save(img, origin, lu, tag="tree", min_gap=1.5, scale=None):
    """img = the game-region screenshot (PIL) taken right after a lock; origin from Lineup.origin().
    Labels every node whose box is fully inside the tree area. Returns the sample id or None."""
    global _last
    if not enabled() or origin is None or time.time() - _last < min_gap:
        return None
    w, h = img.size
    ox, oy = origin
    ksx, ksy = scale or (lu.sx, lu.sy)  # detector-fitted scale when the caller has one
    boxes = []

    def add(cls, x, y):
        sx, sy = ox + ksx * x, oy + ksy * y
        half = HALF[cls] * h
        # skip the edges and the game's own panels (points box top-left, tabs on top, Skill Assignment at the bottom)
        if sx - half < 0.02 * w or sx + half > 0.98 * w or sy - half < 0.08 * h or sy + half > 0.86 * h:
            return
        if hidden(sx / w, sy / h):
            return
        boxes.append(f"{CLASSES.index(cls)} {sx / w:.6f} {sy / h:.6f} {2 * half / w:.6f} {2 * half / h:.6f}")

    for sec in lu.sections:
        add("hub", *sec["hub"])
    for n in lu.tmap.nodes.values():
        add("upgrade" if n.get("upgrade") else "skill", n["x"], n["y"])
    if len(boxes) < 5:
        return None
    (ROOT / "images").mkdir(parents=True, exist_ok=True)
    (ROOT / "labels").mkdir(parents=True, exist_ok=True)
    sid = f"{tag}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 1000:03d}"
    img.convert("RGB").save(ROOT / "images" / f"{sid}.jpg", quality=92)
    (ROOT / "labels" / f"{sid}.txt").write_text("\n".join(boxes) + "\n", encoding="utf-8")
    yaml = ROOT / "data.yaml"
    if not yaml.exists():
        yaml.write_text(f"path: {ROOT.as_posix()}\ntrain: images\nval: images\n"
                        f"names: {dict(enumerate(CLASSES))}\n", encoding="utf-8")
    _last = time.time()
    print(f"[collect] saved {sid} ({len(boxes)} boxes)", flush=True)
    return sid
