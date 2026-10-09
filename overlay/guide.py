"""BUILD PILOT - GUIDE MODE. Shows you where to click; YOU click. Never moves your mouse or presses keys.

The Nutty Sage • tinkered together by The Nut, learning with AI.

  python guide.py                       # best Maxroll build for your class + level
  python guide.py <maxroll guide url>   # a specific build
  F8 = manually confirm the current node if a click is not detected; F12 = quit

How it works:
  1. Open the FULL skill tree (A, then the red arrow) and scroll all the way OUT.
  2. Hover your mouse over any big skill square: it reads the tooltip to learn your class and where the tree is.
  3. A glowing ring marks the next node. Click it. When the points counter drops, the ring moves on.
     If the next node is off screen, an arrow tells you which way to drag the tree.
"""
import ctypes
import sys
import threading
import time

import cv2
import numpy as np
import pyautogui  # pyautogui.position() only: where YOUR mouse is

from highlight import Overlay
from maxplan import CLASS_TREES, best_guide, make_plan
from screen import load_profile, points_left, read_level, read_spent, read_tooltip, region, screen_size, screenshot
from treemap import SX_H, SY_H, TreeMap, title_match


def f12() -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x7B) & 0x8001)  # just READS the key state


def f8_pressed() -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x0001)  # one manual next per key press


def f9_pressed() -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x78) & 0x0001)  # one zoom-complete confirmation per key press


def tree_open(img) -> bool:
    """The full tree shows a solid red 'Skill Tree' tab at the top centre."""
    hsv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2HSV)
    H, W = hsv.shape[:2]
    roi = hsv[0:int(0.07 * H), int(0.40 * W):int(0.52 * W)]
    m = cv2.inRange(roi, (0, 170, 60), (8, 255, 255)) | cv2.inRange(roi, (172, 170, 60), (180, 255, 255))
    return cv2.countNonZero(m) / max(1, m.size) > 0.08


def squares(img) -> list:
    """Centres (screen px) of the big skill squares: tan frames, plus plain square edges."""
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    H, W = bgr.shape[:2]
    mask = cv2.inRange(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV), (5, 20, 150), (35, 140, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    out = []
    for c in cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if 0.025 * H < w < 0.065 * H and 0.025 * H < h < 0.065 * H and 0.8 < w / h < 1.25 \
                and cv2.countNonZero(mask[y:y + h, x:x + w]) / (w * h) < 0.6:
            cx, cy = x + w / 2, y + h / 2
            if 0.08 * H < cy < 0.9 * H and all(abs(cx - a) > 15 or abs(cy - b) > 15 for a, b in out):
                out.append((cx, cy))
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    e = cv2.dilate(cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 40, 120), np.ones((2, 2), np.uint8))
    for c in cv2.findContours(e, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
        x, y, w, h = cv2.boundingRect(c)
        if not (0.028 * H < w < 0.06 * H and 0.028 * H < h < 0.06 * H and 0.85 < w / h < 1.18):
            continue
        ap = cv2.approxPolyDP(c, 0.06 * cv2.arcLength(c, True), True).reshape(-1, 2)
        if len(ap) != 4 or not all(abs(px - x) < 0.2 * w or abs(px - x - w) < 0.2 * w for px, _ in ap):
            continue
        cx, cy = x + w / 2, y + h / 2
        if 0.08 * H < cy < 0.9 * H and all(abs(cx - a) > 15 or abs(cy - b) > 15 for a, b in out):
            out.append((cx, cy))
    return out


class Tracker:
    """screen = origin + scale * tree_pos. Follows the tree while the player drags it: frame-to-frame motion
    (phase correlation) + snapping to the skill squares it can see."""

    def __init__(self, tmap: TreeMap):
        w, h = screen_size()
        self.w, self.h = w, h
        self.sx, self.sy = SX_H * h, SY_H * h
        self.ox = self.oy = None
        self.bases = [n for k, n in tmap.nodes.items() if k[1] is None]
        self.last = None

    def anchor(self, node, x, y):
        self.ox, self.oy = x - self.sx * node["x"], y - self.sy * node["y"]

    def predict(self, node):
        return self.ox + self.sx * node["x"], self.oy + self.sy * node["y"]

    def _gray(self, img):
        g = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY).astype(np.float32)
        H, W = g.shape
        return g[int(0.1 * H):int(0.88 * H), int(0.25 * W):int(0.75 * W)]

    def update(self, img):
        g = self._gray(img)
        if self.last is not None:
            win = cv2.createHanningWindow(g.shape[::-1], cv2.CV_32F)
            (dx, dy), resp = cv2.phaseCorrelate(self.last, g, win)
            if resp > 0.1 and (abs(dx) > 1.5 or abs(dy) > 1.5):
                self.ox += dx
                self.oy += dy
        self.last = g
        self._snap(squares(img))

    def _snap(self, sq):
        """Nudge the origin so the visible squares sit on the map's skill positions (only small corrections)."""
        if len(sq) < 2:
            return
        tol, best = 0.015 * self.h, (0, 0.0, 0.0)
        for px, py in sq:
            for n in self.bases:
                cx, cy = px - self.sx * n["x"], py - self.sy * n["y"]
                if abs(cx - self.ox) > 0.06 * self.h or abs(cy - self.oy) > 0.06 * self.h:
                    continue
                fit = sum(any(abs(cx + self.sx * b["x"] - qx) < tol and abs(cy + self.sy * b["y"] - qy) < tol
                              for b in self.bases) for qx, qy in sq)
                if fit > best[0]:
                    best = (fit, cx, cy)
        if best[0] >= 2:
            self.ox, self.oy = best[1], best[2]


class PointsWatcher(threading.Thread):
    """Reads 'Available Points' in the background (OCR takes ~1 s) so the ring stays smooth."""

    def __init__(self):
        super().__init__(daemon=True)
        self.value, self.stop = points_left(), False

    def run(self):
        while not self.stop:
            v = points_left()
            if v is not None:
                self.value = v
            time.sleep(0.3)


def wait_for_tree(ov):
    ov.banner("OPEN THE FULL SKILL TREE", "Press A, then click the red expand arrow. F12 stops the guide.",
              color="#ff3030", size=32)
    while not tree_open(screenshot()):
        if f12():
            raise SystemExit
        time.sleep(0.5)
    sw, sh = ov.root.winfo_screenwidth(), ov.root.winfo_screenheight()
    ov.banner("ZOOM ALL THE WAY OUT", "Scroll down to maximum zoom, then press F9 to continue.",
              color="#ff3030", size=40, at=(sw // 2, sh // 2), flash=True)
    while not f9_pressed():
        if f12():
            raise SystemExit
        if not tree_open(screenshot()):
            wait_for_tree(ov)
            return
        time.sleep(0.12)
    ov.clear("banner")


def calibrate(ov):
    """The player hovers a big skill; we read its tooltip -> class + an exact anchor point."""
    trees = {c: TreeMap(t) for c, t in CLASS_TREES.items()}
    ov.banner("NOW HOVER OVER A BIG SKILL SQUARE", "Just hover - no click. The guide will show the first skill after it reads this one.",
              color="#ff3030", size=30)
    r = region()
    while True:
        if f12():
            raise SystemExit
        img = screenshot()
        tip = read_tooltip(img)
        mx, my = pyautogui.position()
        mx, my = mx - r["left"], my - r["top"]
        for cls, tm in trees.items():
            for k, n in tm.nodes.items():
                if k[1] is None and title_match(tip, n["skill"]):
                    detected = squares(img)
                    if not detected:
                        ov.banner("I read the skill name, but can’t find its square",
                                  "Hover near the CENTER of a large square and wait for me to detect its border.")
                        break
                    sq = min(detected, key=lambda p: (p[0] - mx) ** 2 + (p[1] - my) ** 2)
                    if (sq[0] - mx) ** 2 + (sq[1] - my) ** 2 > (0.04 * r["height"]) ** 2:
                        ov.banner("Move onto the large skill square",
                                  "I can read its name, but the detected square is too far from your mouse.")
                        break
                    return cls, tm, n, sq
        time.sleep(0.4)


def main():
    load_profile("diablo4")
    ov = Overlay()
    try:
        wait_for_tree(ov)
        level, avail, spent = read_level(), points_left(), read_spent()
        if avail is None:
            ov.banner("I CAN'T READ AVAILABLE POINTS", "No changes made. Check the top-left counter, then restart. F12 quits.",
                      color="#ff3030", size=30)
            while not f12():
                time.sleep(0.25)
            raise SystemExit
        if avail == 0 and not spent:
            ov.banner("I READ ZERO AVAILABLE POINTS", "No changes made. Check the counter and restart. F12 quits.",
                      color="#ff3030", size=30)
            while not f12():
                time.sleep(0.25)
            raise SystemExit
        cls, tmap, node, (ax, ay) = calibrate(ov)
        guide = sys.argv[1] if len(sys.argv) > 1 else best_guide(cls, level or 60)
        plan = make_plan(guide, (avail or 0) + (spent or 0), level or 60)
        planned = sum(s.get("times", 1) for s in plan["steps"])
        print(f"[guide] class={plan['class']} level={level} available={avail} spent={spent} "
              f"planned={planned} build={plan['build_name']}", flush=True)
        if not plan["steps"] and (avail > 0 or not spent):
            ov.banner("NO POINTS WERE PLANNED", f"I read {avail} available points and {spent} spent. No changes made. F12 quits.",
                      color="#ff3030", size=30)
            while not f12():
                time.sleep(0.25)
            raise SystemExit
        basics, rank = set(plan.get("basic_skills") or []), {}
        skill_points = {}
        for s in plan["steps"]:  # target rank shown under each big square, counted over the WHOLE plan
            if not s.get("upgrade"):
                rank[s["skill"]] = rank.get(s["skill"], 1 if s["skill"] in basics else 0) + s.get("times", 1)
                s["target"] = rank[s["skill"]]
                skill_points[s["skill"]] = skill_points.get(s["skill"], 0) + s.get("times", 1)
        if spent:  # resume: assume the player followed these same steps, skip what's already in the tree
            done, keep = spent, []
            for s in plan["steps"]:
                t = s.get("times", 1)
                if done >= t:
                    done -= t
                    continue
                keep.append(dict(s, times=t - done))
                done = 0
            plan["steps"] = keep
            ov.banner(f"{spent} points already in - picking up where you left off", "")
            time.sleep(2)
        tmap = TreeMap(plan["class"])
        trk = Tracker(tmap)
        trk.anchor(tmap.get(node["skill"]), ax, ay)
        steps = [dict(s, left=s.get("times", 1)) for s in plan["steps"]]
        pw = PointsWatcher()
        pw.start()
        last_pts = pw.value
        r = region()
        hover_check = 0.0
        warn = ""
        pending_spend = 0
        manual_request_until = 0.0
        # Joe 10/9: a countdown lags behind the OCR. Say the TARGET RANK the node itself shows ("15/15") instead.
        got_until = 0.0
        for i, s in enumerate(steps):
            n = tmap.get(s["skill"], s.get("upgrade"))
            name = s.get("upgrade") or s["skill"]
            small = bool(s.get("upgrade"))
            while s["left"] > 0:
                if f12():
                    raise SystemExit
                if f8_pressed():
                    if pending_spend:
                        pending_spend -= 1
                        s["left"] -= 1
                        warn = ""
                        got_until = time.time() + 1.5
                    else:
                        manual_request_until = time.time() + 6
                        warn = "F8 received. Waiting for the point to register; don't click again yet."
                img = screenshot()
                trk.update(img)
                x, y = trk.predict(n)
                mx, my = pyautogui.position()
                mx, my = mx - r["left"], my - r["top"]
                near = (mx - x) ** 2 + (my - y) ** 2 < (0.12 * trk.h) ** 2
                # 10/9 Joe test: the player's own hover is the best sensor. Mouse near the ring -> read the tooltip;
                # right node = snap the ring (and the whole map) exactly onto it.
                if near and time.time() - hover_check > 1.0:
                    hover_check = time.time()
                    tip = read_tooltip(img)
                    if title_match(tip, name):
                        trk.ox += mx - x
                        trk.oy += my - y
                        x, y = mx, my
                        warn = ""
                label = (f"{skill_points.get(s['skill'], 0)} POINTS TOTAL"
                         if not small else "1 POINT")
                if time.time() < got_until:
                    label = "✓ POINT CONFIRMED   " + label
                pts = pw.value
                available_text = str(pts) if pts is not None else "reading"
                point_prompt = (f"{s['skill'].upper()} — {skill_points.get(s['skill'], 1)} POINTS TOTAL"
                                if not small else f"{name.upper()} — 1 POINT")
                if pts == 0:
                    point_prompt = "STOP — 0 POINTS AVAILABLE"
                    point_detail = f"Still need points for {name}. Don't click; check the counter."
                else:
                    point_detail = f"Left overall: {available_text}  |  Click once; if stuck, press F8 NEXT."
                if warn:
                    point_detail = warn
                if 0.06 * trk.w < x < 0.94 * trk.w and 0.12 * trk.h < y < 0.86 * trk.h:
                    radius = int((0.014 if small else 0.034) * trk.h)
                    screen_x, screen_y = r["left"] + x, r["top"] + y
                    banner_y = screen_y + radius + 76
                    if banner_y > ov.root.winfo_screenheight() - 105:
                        banner_y = screen_y - radius - 76
                    connector_y = screen_y + radius + 8 if banner_y > screen_y else screen_y - radius - 8
                    ov.banner(point_prompt, point_detail, color="#ff3030", size=24,
                              at=(screen_x, banner_y), connect=(screen_x, connector_y))
                    ov.show(screen_x, screen_y, radius=radius,
                            label=label)
                else:
                    d = "up" if y < 0.12 * trk.h else "down" if y > 0.86 * trk.h else "left" if x < 0.06 * trk.w else "right"
                    ex = min(max(x, 0.1 * trk.w), 0.9 * trk.w)
                    ey = min(max(y, 0.2 * trk.h), 0.8 * trk.h)
                    ov.banner(point_prompt, f"Target is {d} of screen; drag the tree to bring it into view. "
                              f"Points available: {available_text}. Don't click yet.", color="#ff3030", size=30)
                    ov.arrow(r["left"] + ex, r["top"] + ey, d, label)
                if manual_request_until and time.time() > manual_request_until:
                    manual_request_until = 0.0
                    warn = "No new point was detected. Check the points counter before trying again."
                if pts is not None and last_pts is not None and pts < last_pts:
                    spent_now = last_pts - pts
                    # a point was spent: WHICH node? the one under the player's mouse (they just clicked it)
                    if spent_now:
                        if manual_request_until:
                            s["left"] -= min(spent_now, s["left"])
                            manual_request_until = 0.0
                            warn = ""
                            got_until = time.time() + 1.5
                        else:
                            tip = read_tooltip(screenshot())
                            if title_match(tip, name) or not (tip.get("lines")):
                                s["left"] -= spent_now  # right node (or unreadable - trust the ring)
                                warn = ""
                                got_until = time.time() + 1.5
                            else:
                                got = (tip.get("name") or "another node")
                                pending_spend += spent_now
                                warn = f"Point detected on {got}. Press F8 NEXT to accept, or right-click to undo."
                last_pts = pts if pts is not None else last_pts
                time.sleep(0.25)
        pw.stop = True
        ov.clear("ring")
        ov.banner("All done!", "Your skills are set. A 'how to play' note is opening.")
        from howto import write_howto
        write_howto(plan, guide)
        time.sleep(6)
    finally:
        ov.close()


if __name__ == "__main__":
    main()
