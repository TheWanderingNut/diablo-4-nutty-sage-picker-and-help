"""Joe 10/10: trained YOLO detector for the skill tree (d4-ui-dataset). Finds the big skill squares + section hubs
in ~20-40 ms; the rigid tree map then places every small node ("it's all about measurement").
Falls back to the old shape finder (guide.squares) if ultralytics or the model file isn't there.

  find(img)            -> {"skill": [(x, y, conf)], "hub": [...], "upgrade": [...]}  (game-region pixels)
  fit(det, lu, guess)  -> (ox, oy, sx, sy) tree origin + scale fitted to what was seen, or None
"""
import os
from pathlib import Path

_TRAINED = Path.home() / "Projects" / "d4-ui-dataset" / "runs" / "d4ui" / "weights" / "best.pt"  # newest (Joe)
_SHIPPED = Path(__file__).with_name("models") / "d4ui.pt"  # the copy that ships with BOB
MODEL = Path(os.environ.get("D4_DETECTOR") or (_TRAINED if _TRAINED.exists() else _SHIPPED))
_model = None
_failed = False


def available():
    global _model, _failed
    if _model is None and not _failed:
        try:
            from ultralytics import YOLO
            _model = YOLO(str(MODEL)) if MODEL.exists() else None
            _failed = _model is None
        except Exception:
            _failed = True
    return _model is not None


def find(img, conf=0.35):
    """img = PIL game-region screenshot."""
    if not available():
        from guide import squares
        return {"skill": [(x, y, 1.0) for x, y in squares(img)], "hub": [], "upgrade": []}
    import numpy as np
    r = _model.predict(np.array(img)[:, :, ::-1], imgsz=1280, conf=conf, verbose=False)[0]
    out = {"skill": [], "hub": [], "upgrade": []}
    for (x0, y0, x1, y1), c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        out[r.names[int(c)]].append(((x0 + x1) / 2, (y0 + y1) / 2, s))
    return out


def _anchors(lu):
    pts = [((n["x"], n["y"]), "skill") for n in lu.tmap.nodes.values() if not n.get("upgrade")]
    pts += [(s["hub"], "hub") for s in lu.sections]
    return pts


def fit(det, lu, guess=None, tol=None, fix_scale=False):
    """Match detected squares/hubs to the map and fit origin + scale (least squares).
    guess = (ox, oy[, sx, sy]) to match near; without it the origin is found by voting (anywhere on screen)."""
    tol = tol or 0.03 * lu.h
    seen = [(x, y, k) for k in ("skill", "hub") for x, y, _ in det[k]]
    anchors = _anchors(lu)
    if len(seen) < 3:
        return None
    sx, sy = (guess[2], guess[3]) if guess and len(guess) == 4 else (lu.sx, lu.sy)
    if guess is None:  # vote: every (seen, map) pair of the same kind proposes an origin
        votes = {}
        cell = 14
        for fx, fy, k in seen:
            for (x, y), ak in anchors:
                if ak == k:
                    key = (round((fx - sx * x) / cell), round((fy - sy * y) / cell))
                    votes[key] = votes.get(key, 0) + 1
        (kx, ky), n = max(votes.items(), key=lambda kv: kv[1])
        if n < 3:
            return None
        guess = (kx * cell, ky * cell)
    ox, oy = guess[0], guess[1]
    pairs = []
    for fx, fy, k in seen:
        best = None
        for (x, y), ak in anchors:
            if ak != k:
                continue
            d = abs(ox + sx * x - fx) + abs(oy + sy * y - fy)
            if d < 2 * tol and (best is None or d < best[0]):
                best = (d, x, y)
        if best:
            pairs.append((fx, fy, best[1], best[2]))
    if len(pairs) < 3:
        return None
    # least squares per axis: f = o + s * map ; keep scale only if the points are spread out enough
    def solve(fs, ms, s0):
        n = len(fs)
        mm = sum(ms) / n
        ff = sum(fs) / n
        var = sum((m - mm) ** 2 for m in ms)
        s = s0
        if not fix_scale and var * s0 * s0 > (0.15 * lu.h) ** 2 * n / 4 and n >= 4:
            s = sum((m - mm) * (f - ff) for m, f in zip(ms, fs)) / var
            s = max(0.94 * s0, min(1.06 * s0, s))  # the zoom is fixed: allow a few % only
        return ff - s * mm, s
    ox, nsx = solve([p[0] for p in pairs], [p[2] for p in pairs], sx)
    oy, nsy = solve([p[1] for p in pairs], [p[3] for p in pairs], sy)
    return ox, oy, nsx, nsy


class Steady:
    """Joe 10/10: boxes jittered - every frame moved them to the newest (1-3 px noisy) fit, and the scale was refit
    every frame. Scale: median of the first good fits, then FROZEN (the zoom never changes). Position: median of the
    last few fits while the mouse is up; follows the newest fit directly while dragging."""

    def __init__(self, lu, keep=7):
        self.lu, self.keep = lu, keep
        self.scales, self.scale, self.recent = [], None, []

    def update(self, f, dragging):
        if f is None:
            return None
        ox, oy, sx, sy = f
        if self.scale is None:
            self.scales.append((sx, sy))
            if len(self.scales) >= 8:
                xs = sorted(s[0] for s in self.scales)
                ys = sorted(s[1] for s in self.scales)
                self.scale = (xs[len(xs) // 2], ys[len(ys) // 2])
        if dragging:
            self.recent = []
            return ox, oy, *(self.scale or (sx, sy))
        self.recent = (self.recent + [(ox, oy)])[-self.keep:]
        mx = sorted(p[0] for p in self.recent)[len(self.recent) // 2]
        my = sorted(p[1] for p in self.recent)[len(self.recent) // 2]
        return mx, my, *(self.scale or (sx, sy))

    def fit(self, det, guess):
        """detect.fit using the frozen scale once known."""
        if self.scale:
            return fit(det, self.lu, guess=(guess[0], guess[1], *self.scale), fix_scale=True)
        return fit(det, self.lu, guess=guess)
