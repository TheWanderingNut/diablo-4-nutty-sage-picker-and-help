"""DIABLO BOB - HUMAN-PROOF GUIDANCE (Joe's design, 10/10). Shows you exactly what to click; YOU click.
Never moves your mouse or presses keys.

  python bob.py                       # best Maxroll build for your class + level
  python bob.py <maxroll guide url>   # a specific build
  F12 = quit

1. Open the FULL skill tree, zoom all the way out, hover any big skill square (that tells BOB your class).
2. A ghost outline of one tree SECTION appears (big section number in the diamond). A circle shows where that
   section is right now. Drag the tree until the real squares sit in the outline - it turns GREEN (chime).
3. Every node to pick in that section gets BOXED at once, with a line to how many times to click it (x1, x14).
   Click them. Each box turns into a green check as its points land.
4. Section done -> chime -> the next section's outline. At the end: a how-to-play note with your action bar.
"""
import ctypes
import sys
import threading
import time
import winsound

import numpy as np

import pyautogui  # pyautogui.position() only: where YOUR mouse is

from guide import PointsWatcher, calibrate, f12, squares, wait_for_tree
from highlight import Overlay
from lineup import Lineup
from maxplan import best_guide, make_plan
from screen import load_profile, points_left, read_level, read_spent, region, screen_size, screenshot
from treemap import TreeMap


class ClickRecorder(threading.Thread):
    """Joe 10/10: he clicked 3 nodes faster than the ~1 s points OCR, the whole drop went to one box and the section
    never finished. So remember WHERE each left click landed (polled every 10 ms) and credit points to those clicks."""

    def __init__(self):
        super().__init__(daemon=True)
        self.clicks, self.stop, self._lock = [], False, threading.Lock()

    def run(self):
        start = None  # (x, y, time) of the press
        while not self.stop:
            now = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
            if now and start is None:
                start = (*pyautogui.position(), time.time())
            elif not now and start is not None:
                x, y = pyautogui.position()
                # Joe 10/10: a box went green that he never clicked - grabbing the tree to drag it counted.
                # A real click = released quickly without moving.
                if abs(x - start[0]) <= 6 and abs(y - start[1]) <= 6 and time.time() - start[2] < 0.6:
                    with self._lock:
                        self.clicks.append((start[0], start[1]))
                start = None
            time.sleep(0.01)

    def take(self):
        with self._lock:
            c, self.clicks = self.clicks, []
        return c


def key_down(vk):
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def chime(kind="turn"):
    winsound.PlaySound("SystemAsterisk" if kind == "turn" else "SystemExclamation",
                       winsound.SND_ALIAS | winsound.SND_ASYNC)


def gray(img):
    import cv2
    g = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY).astype(np.float32)
    H, W = g.shape
    return g[int(0.1 * H):int(0.88 * H), int(0.25 * W):int(0.75 * W)]


def follow(origin, last, img):
    """Frame-to-frame tree motion (phase correlation) -> moved origin, new reference frame."""
    import cv2
    g = gray(img)
    if last is not None and origin is not None:
        win = cv2.createHanningWindow(g.shape[::-1], cv2.CV_32F)
        (dx, dy), resp = cv2.phaseCorrelate(last, g, win)
        if resp > 0.1 and (abs(dx) > 1.5 or abs(dy) > 1.5):
            origin = (origin[0] + dx, origin[1] + dy)
    return origin, g


def wait_lineup(ov, lu, sec, n_points, prev_origin):
    """Ghost outline + 'Section N is HERE' circle; returns the exact tree origin once it locks (3 checks in a row)."""
    r = region()
    scr = lambda p: (r["left"] + p[0], r["top"] + p[1])
    (hx, hy), sq = lu.layout(sec)
    chime("turn")
    streak, origin, last = 0, prev_origin, None
    let_go = None  # when the player released the mouse while lined up
    while True:
        if f12():
            raise SystemExit
        img = screenshot()
        origin, last = follow(origin, last, img)
        locked, n, fix = lu.check(sec, squares(img))
        if key_down(0x76) and origin is not None:  # F7: "it's lined up, trust me" (re-lock after points are spent)
            while key_down(0x76):
                time.sleep(0.05)
            ov.clear("ring")
            chime("locked")
            return origin
        streak = streak + 1 if locked else 0
        lined_up = streak >= 3
        # Joe 10/10: it jumped to the boxes while he was still holding the tree and threw his hand off.
        # Only lock once he LETS GO of the mouse, and the tree then stays lined up for 1 more second.
        if not lined_up or key_down(0x01):
            let_go = None
        elif let_go is None:
            let_go = time.time()
        ok = let_go is not None and time.time() - let_go >= 1.0
        ov.ghost(scr((hx, hy)), [scr(p) for p in sq], lu.half_square(), locked=lined_up,
                 label=f"Section {sec['section']}" + ("  LOCKED" if ok else ""), number=sec["section"])
        if lined_up and not ok:
            ov.clear("ring")
            ov.banner("Lined up! Let go of the mouse" if let_go is None else "Hold still...",
                      f"Section {sec['section']} fits the outline", color="#30ff60", size=26)
            time.sleep(0.1)
            continue
        if ok:
            ov.clear("ring")
            chime("locked")
            # Joe 10/10: it jumped to the boxes so fast you never saw it go green - hold the green lock a moment
            ov.banner(f"LOCKED - section {sec['section']}", "Nice! Your nodes are coming up...", color="#30ff60",
                      size=28)
            time.sleep(1.2)
            return lu.origin(sec, fix)
        if origin is not None:  # where is that section right now?
            cx, cy = origin[0] + lu.sx * sec["hub"][0], origin[1] + lu.sy * sec["hub"][1]
            if 0.05 * lu.w < cx < 0.95 * lu.w and 0.1 * lu.h < cy < 0.9 * lu.h:
                ov.show(*scr((cx, cy)), radius=int(lu.half_square() * 2.4),
                        label=f"Section {sec['section']} is HERE - drag it into the outline")
            else:
                d = "up" if cy < 0.1 * lu.h else "down" if cy > 0.9 * lu.h else "left" if cx < 0.05 * lu.w else "right"
                ov.arrow(*scr((min(max(cx, 0.12 * lu.w), 0.88 * lu.w), min(max(cy, 0.2 * lu.h), 0.8 * lu.h))), d,
                         f"Section {sec['section']} is this way")
        ov.banner(f"Drag the tree so section {sec['section']} fits the outline",
                  f"{n}/{min(3, len(sq))} squares lined up  |  {n_points} points in this section  |  "
                  f"F7 = it's lined up",
                  color="#ffd34d", size=24)
        time.sleep(0.2)


def click_section(ov, lu, tmap, sec, steps, origin, pw, clicks, left):
    """Box every node of the section with its click count; follow the tree; tick boxes off as points land.
    Points are credited to the boxes the player actually clicked (ClickRecorder), oldest click first.
    Safety net: once the section's whole point total has been spent it is done. F7 = skip ("I did it").
    `left` (clicks still needed per step) belongs to the caller, so a re-lock keeps the progress.
    Returns (origin, "done") or (origin, "relock") if the boxes lost the tree."""
    r = region()
    scr = lambda p: (r["left"] + p[0], r["top"] + p[1])
    need = sum(left)
    down_since = None
    last_click = time.time()
    nodes = [tmap.get(s["skill"], s.get("upgrade")) for s in steps]
    last, last_pts, lost_since = None, pw.value, None
    start_pts = pw.value
    items = []
    clicks.take()  # forget clicks made while lining up
    _, sq_want = lu.layout(sec)
    while True:
        if f12():
            raise SystemExit
        if key_down(0x76):  # F7: player says the section is done
            ov.clear("targets")
            return origin, "done"
        img = screenshot()
        # Joe's video 10/10: the boxes slid right while he clicked - the pop-up tooltips looked like the tree
        # moving. The tree only moves while the mouse is HELD (dragging), so only track motion then.
        if key_down(0x01):
            down_since = down_since or time.time()
        else:
            down_since = None
        if down_since is not None and time.time() - down_since > 0.2:
            origin, last = follow(origin, last, img)
        else:
            last = gray(img)
        # keep the boxes glued to the real tree: nudge onto the visible skill squares
        found = squares(img)
        pred = [(origin[0] + lu.sx * x, origin[1] + lu.sy * y) for x, y in sec["skills"].values()]
        res = []
        for px, py in pred:
            near = min(found, key=lambda p: (p[0] - px) ** 2 + (p[1] - py) ** 2, default=None)
            if near and abs(near[0] - px) < 0.022 * lu.h and abs(near[1] - py) < 0.022 * lu.h:
                res.append((near[0] - px, near[1] - py))
        # Joe 10/10: a clicked node's tooltip has a skill-icon square at its top - one stray square pulled the boxes.
        # Need 2+ squares that agree; when not dragging the tree can't move, so only allow tiny corrections.
        dragging = down_since is not None
        if len(res) >= 2:
            mx = sorted(a for a, _ in res)[len(res) // 2]
            my = sorted(b for _, b in res)[len(res) // 2]
            agree = [(a, b) for a, b in res if abs(a - mx) < 4 and abs(b - my) < 4]
            if len(agree) >= 2:
                dx = sum(a for a, _ in agree) / len(agree)
                dy = sum(b for _, b in agree) / len(agree)
                cap = 0.022 * lu.h if dragging else 3
                origin = (origin[0] + max(-cap, min(cap, dx)), origin[1] + max(-cap, min(cap, dy)))
            lost_since = None
        elif dragging:
            lost_since = lost_since or time.time()
            if time.time() - lost_since > 2.5:
                ov.clear("targets")
                return origin, "relock"
        else:
            lost_since = None  # not dragging = the tree hasn't moved, so it isn't lost
        # which box was each new click in? (boxes from the previous frame; generous margin)
        for cx, cy in clicks.take():
            hit = [i for i, (bx, by, bh, _, _) in enumerate(items)
                   if abs(cx - bx) <= bh * 1.4 and abs(cy - by) <= bh * 1.4]
            if hit:
                open_hit = [i for i in hit if left[i] > 0] or hit  # prefer a box that still needs clicks
                j = min(open_hit, key=lambda i: (items[i][0] - cx) ** 2 + (items[i][1] - cy) ** 2)
                # Joe 10/10: the points OCR is too slow/flaky to judge single clicks (it saw 4 of his 9 and un-counted
                # 5). The CLICK is the count - instantly, and it never un-counts. Points only double-check the section.
                if left[j] > 0:
                    left[j] -= 1
                last_click = time.time()
                print(f"[bob] click on {steps[j]['skill']}{' / ' + steps[j]['upgrade'] if steps[j].get('upgrade') else ''}"
                      f"  -> x{left[j]} left", flush=True)
        items = []
        for i, (s, n, k) in enumerate(zip(steps, nodes, left)):
            x, y = origin[0] + lu.sx * n["x"], origin[1] + lu.sy * n["y"]
            half = (0.016 if s.get("upgrade") else 0.030) * lu.h  # Joe 10/10: boxes a bit bigger
            items.append((*scr((x, y)), half, f"x{max(k, 0)}", k <= 0))
        ov.targets(items)
        pts = pw.value
        if pts is not None and last_pts is not None and pts != last_pts:
            print(f"[bob] points {last_pts} -> {pts}", flush=True)
        last_pts = pts if pts is not None else last_pts
        spent_here = (start_pts - pts) if (pts is not None and start_pts is not None) else 0
        # (no points-based auto-finish any more: the slow reader could still be counting the LAST section's points)
        # section done: every box clicked AND (the points agree, or 3 s since the last click - the reader lags)
        if all(k <= 0 for k in left) and (spent_here >= need or time.time() - last_click > 3.0):
            if spent_here < need:
                print(f"[bob] section {sec['section']}: clicks say done, points reader saw {spent_here}/{need}", flush=True)
            ov.clear("targets")
            return origin, "done"
        todo = sum(max(0, k) for k in left)
        ov.banner(f"Click each boxed node the number of times shown",
                  f"Section {sec['section']}: {todo} clicks to go  |  points available: {pts if pts is not None else '?'}"
                  f"  |  F7 = section done",
                  color="#ffd34d", size=24)
        time.sleep(0.15)


def main():
    load_profile("diablo4")
    ov = Overlay()
    try:
        wait_for_tree(ov)
        level, avail, spent = read_level(), points_left(), read_spent()
        spent = spent or 0
        if spent:  # Joe 10/10: pick up where you left off (you've been following BOB's own section order)
            ov.banner(f"Picking up where you left off", f"{spent} points already in - skipping those",
                      color="#30ff60", size=28)
            time.sleep(2)
        cls, _, _, _ = calibrate(ov)
        guide = sys.argv[1] if len(sys.argv) > 1 else best_guide(cls, level or 60)
        plan = make_plan(guide, (avail or 0) + spent, level or 60)
        tmap = TreeMap(plan["class"])
        w, h = screen_size()
        lu = Lineup(plan["class"], tmap, w, h)
        steps = sorted(plan["steps"], key=lambda s: lu.section_of(s["skill"])["section"])
        groups = []
        for s in steps:
            sec = lu.section_of(s["skill"])
            if groups and groups[-1][0] is sec:
                groups[-1][1].append(s)
            else:
                groups.append((sec, [s]))
        print(f"[bob] {plan['build_name']}: {len(groups)} sections to line up", flush=True)
        pw = PointsWatcher()
        pw.start()
        clicks = ClickRecorder()
        clicks.start()
        origin = None
        skip = spent  # points already in: the first ones in BOB's section order
        for sec, sec_steps in groups:
            left = [s.get("times", 1) for s in sec_steps]  # survives a re-lock (Joe's video: it forgot his clicks)
            for i in range(len(left)):
                take = min(left[i], skip)
                left[i] -= take
                skip -= take
            if not any(left):
                continue  # this whole section is already done
            while True:
                origin = wait_lineup(ov, lu, sec, sum(left), origin)
                ov.clear("ghost")
                origin, result = click_section(ov, lu, tmap, sec, sec_steps, origin, pw, clicks, left)
                while key_down(0x76):  # F7 still held: don't let it skip the next section too
                    time.sleep(0.05)
                if result == "done":
                    break
                ov.banner("I lost the tree - line the section up again", "", color="#ff3030", size=26)
                time.sleep(1.5)
        pw.stop = True
        clicks.stop = True
        ov.clear()
        chime("locked")
        ov.banner("All done! Your skill points are in.", "A how-to-play note with your action bar is opening.",
                  color="#30ff60", size=28)
        from howto import write_howto
        write_howto(plan, guide)
        time.sleep(6)
    finally:
        ov.close()


if __name__ == "__main__":
    main()
