"""Joe's ghost-outline lineup (10/10). READ-ONLY - shared by the bot (Build Pilot) and the guide (BOB).

For each tree section we know (from the game data) where its hub and skill squares are. We pick a spot on screen
where that whole section fits, draw it as a ghost outline, and the PLAYER drags the tree until the real skill squares
sit inside the outline. Then we know exactly where every node of that section is - no drift, no guessing.
Assumes the tree is zoomed all the way out (the same scale the bot always uses).
"""
from treemap import SX_H, SY_H
from hubs import tree_sections


class Lineup:
    def __init__(self, tree_key: str, tmap, w: int, h: int):
        self.w, self.h = w, h
        self.sx, self.sy = SX_H * h, SY_H * h
        self.sections = tree_sections(tree_key)
        self.by_skill = {name: s for s in self.sections for name in s["skills"]}
        self.tmap = tmap

    def section_of(self, skill: str) -> dict:
        return self.by_skill[skill]

    def _hub_screen(self, sec) -> tuple[float, float]:
        """Hub position on screen that centres the whole section (skills + their upgrades) in the safe middle."""
        names = set(sec["skills"])
        pts = [sec["hub"]] + [(n["x"], n["y"]) for n in self.tmap.nodes.values() if n["skill"] in names]
        cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
        cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
        hx, hy = sec["hub"]
        return 0.5 * self.w + self.sx * (hx - cx), 0.47 * self.h + self.sy * (hy - cy)

    def layout(self, sec) -> tuple[tuple, list]:
        """(hub screen px, [skill square screen px]) where the section SHOULD sit."""
        hx, hy = self._hub_screen(sec)
        bx, by = sec["hub"]
        return (hx, hy), [(hx + self.sx * (x - bx), hy + self.sy * (y - by)) for x, y in sec["skills"].values()]

    def check(self, sec, detected: list) -> tuple[bool, int, tuple]:
        """detected = skill-square centres found on screen (px). Locked when enough of the section's squares sit
        inside their outlines. Returns (locked, how many fit, (dx, dy) fine correction)."""
        _, want = self.layout(sec)
        tol = 0.022 * self.h
        res = []
        for wx, wy in want:
            near = min(detected, key=lambda p: (p[0] - wx) ** 2 + (p[1] - wy) ** 2, default=None)
            if near and abs(near[0] - wx) < tol and abs(near[1] - wy) < tol:
                res.append((near[0] - wx, near[1] - wy))
        need = min(3, len(want))
        if not res:
            return False, 0, (0.0, 0.0)
        dx = sum(r[0] for r in res) / len(res)
        dy = sum(r[1] for r in res) / len(res)
        return len(res) >= need, len(res), (dx, dy)

    def origin(self, sec, fix=(0.0, 0.0)) -> tuple[float, float]:
        """Tree origin on screen (screen = origin + scale * tree_pos) once the section is locked."""
        (hx, hy), _ = self.layout(sec)
        bx, by = sec["hub"]
        return hx + fix[0] - self.sx * bx, hy + fix[1] - self.sy * by

    def half_square(self) -> float:
        return 0.022 * self.h
