"""READ-ONLY screen helpers for guide mode: capture the game window, OCR text, read the skill tree's numbers.
Nothing in this file moves the mouse or sends keys."""
import ctypes
import json
import re
import sys
from pathlib import Path

import mss
import pyautogui  # only pyautogui.position() (where the PLAYER's mouse is) - never moves or clicks
from PIL import Image

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG = {"reader": "ocr"}
TARGET_TITLE = None
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def ask_local(*a, **k):  # no AI vision model in the public version: OCR only
    raise RuntimeError("no vision model")


_points_ask = _read_tooltip_full = ask_local


class Abort(Exception):
    pass


def load_profile(game: str) -> dict:
    profile = json.loads((ROOT / "profiles" / f"{game}.json").read_text())
    set_target_window(profile.get("window_title"))
    return profile


def set_target_window(title: str | None):
    """Capture/click relative to a game window's client area (works windowed or fullscreen)."""
    global TARGET_TITLE
    TARGET_TITLE = title


def region() -> dict:
    """Screen rect (physical px) that screenshots cover and 0-1000 coords map onto."""
    if TARGET_TITLE:
        u = ctypes.windll.user32
        hwnd = u.FindWindowW(None, TARGET_TITLE)
        if hwnd:
            from ctypes import wintypes
            r, pt = wintypes.RECT(), wintypes.POINT(0, 0)
            u.GetClientRect(hwnd, ctypes.byref(r))
            u.ClientToScreen(hwnd, ctypes.byref(pt))
            if r.right > 100 and r.bottom > 100:
                return {"left": pt.x, "top": pt.y, "width": r.right, "height": r.bottom}
    with mss.mss() as sct:
        m = sct.monitors[1]
        return {"left": m["left"], "top": m["top"], "width": m["width"], "height": m["height"]}


def screenshot(save_as: str | None = None) -> Image.Image:
    with mss.mss() as sct:
        raw = sct.grab(region())
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    if save_as:
        img.save(ROOT / "shots" / save_as)
    return img


def screen_size() -> tuple[int, int]:
    r = region()
    return r["width"], r["height"]


def game_hwnd():
    return ctypes.windll.user32.FindWindowW(None, TARGET_TITLE) if TARGET_TITLE else 0


_OCR = None


def ocr_lines(img: Image.Image) -> list[tuple[str, float]]:
    """RapidOCR (PP-OCRv6, CPU, offline). Returns [(text, line_height_px)] top-to-bottom."""
    global _OCR
    import numpy as np
    if _OCR is None:
        import logging
        logging.getLogger("RapidOCR").setLevel(logging.ERROR)
        from rapidocr import RapidOCR
        try:  # few CPU threads: a full-power OCR burst made D4 stutter (hourglass cursor, stale tooltips - 10/9)
            _OCR = RapidOCR(params={"EngineConfig.onnxruntime.intra_op_num_threads": 2,
                                    "EngineConfig.onnxruntime.inter_op_num_threads": 1})
        except Exception:
            _OCR = RapidOCR()
    res = _OCR(np.array(img.convert("RGB")))
    if not res or not res.txts:
        return []
    out = []
    for txt, box in zip(res.txts, res.boxes):
        ys = [p[1] for p in box]
        out.append((txt.strip(), max(ys) - min(ys), min(ys)))
    out.sort(key=lambda t: t[2])
    return [(t, hgt) for t, hgt, _ in out]


def ocr_boxes(img: Image.Image) -> list[tuple[str, float, float]]:
    """Like ocr_lines but with WHERE each line is: [(text, centre_x, centre_y)] in img pixels."""
    global _OCR
    import numpy as np
    if _OCR is None:
        ocr_lines(Image.new("RGB", (8, 8)))  # initialise the engine once
    res = _OCR(np.array(img.convert("RGB")))
    if not res or not res.txts:
        return []
    return [(t.strip(), sum(p[0] for p in b) / 4, sum(p[1] for p in b) / 4) for t, b in zip(res.txts, res.boxes)]


def _digits(lines) -> int | None:
    s = " ".join(t for t, _ in lines).replace("Ø", "0").replace("ø", "0")
    # D4's font: OCR reads "31" as "3I". Inside a token that has a digit, I/l/|/! are 1 and O/o are 0.
    s = re.sub(r"\S*\d\S*", lambda m: m.group().translate(str.maketrans("Il|!iOo", "1111100")), s)
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None


def read_tooltip(img: Image.Image) -> dict:
    """Only the tooltip TITLE matters: crop around the mouse (tooltips open next to it) and shrink.
    Far less image for the AI = much faster on CPU."""
    try:
        r = region()
        mx, my = pyautogui.position()
        cx, cy = mx - r["left"], my - r["top"]
        w, h = img.size
        if 0 <= cx < w and 0 <= cy < h:
            # never include the tab bar (Skill Tree / Paragon) or the SKILL ASSIGNMENT bar: their big text
            # looks like a tooltip title
            box = (max(0, int(cx - 0.33 * h)), max(int(0.075 * h), int(cy - 0.62 * h)),
                   min(w, int(cx + 0.33 * h)), min(int(0.88 * h), int(cy + 0.25 * h)))
            img = img.crop(box)
    except Exception:
        pass
    if CONFIG.get("reader", "ocr") == "ocr":
        try:
            ui = ("skilltree", "paragon", "keywordsearch", "skillassignment", "availablepoints", "pointsspent",
                  "respec")
            lines = [(t, hgt) for t, hgt in ocr_lines(img) if sum(ch.isalpha() for ch in t) >= 3
                     and not any(u in re.sub(r"[^a-z]", "", t.lower()) for u in ui)]
            if lines:
                top = max(hgt for _, hgt in lines)
                titles = [t for t, hgt in lines if hgt >= 0.78 * top and len(t.split()) <= 4]  # short + big = title
                titles = titles or [max(lines, key=lambda l: l[1])[0]]
                return {"name": titles[0], "lines": titles, "all_lines": [t for t, _ in lines],
                        "rank": None, "locked": None}
            # no readable text = the mouse isn't on anything: answer instantly, don't ask the slow AI
            return {"name": None, "lines": [], "all_lines": [], "rank": None, "locked": None}
        except Exception as e:
            print(f"  [ocr] {e} - using the vision model")
    if img.width > 640:
        img = img.resize((640, int(img.height * 640 / img.width)))
    return _read_tooltip_full(img)


def points_left() -> int | None:
    """D4 'Available Points' only: crop the top-left panel so the level badge can't be mistaken for it."""
    img = screenshot()
    w, h = img.size
    crop = img.crop((int(w * 0.03), int(h * 0.16), int(w * 0.14), int(h * 0.215))).resize((int(w * 0.33), int(h * 0.165)))  # number row only
    if CONFIG.get("reader", "ocr") == "ocr":
        try:
            v = _digits(ocr_lines(crop))
            if v is not None:
                return v
            import numpy as np  # no digits: the red circle-slash means 0
            a = np.array(crop.convert("RGB")).astype(int)
            if ((a[:, :, 0] > 150) & (a[:, :, 1] < 60) & (a[:, :, 2] < 60)).sum() > 30:
                return 0
        except Exception:
            pass
    try:
        res = _points_ask(crop)
    except Exception:
        return None
    p = res.get("points")
    return int(p) if str(p).isdigit() else None


def read_level() -> int | None:
    """D4 character level from the gold diamond badge (top-left of the FULL skill tree)."""
    img = screenshot()
    w, h = img.size
    crop = img.crop((int(w * 0.015), int(h * 0.055), int(w * 0.05), int(h * 0.12)))
    crop = crop.resize((crop.width * 4, crop.height * 4))
    if CONFIG.get("reader", "ocr") == "ocr":
        try:  # greyscale: in colour the gold diamond makes OCR read "31" as "15"/"18"
            from PIL import ImageOps
            v = _digits(ocr_lines(ImageOps.grayscale(crop).convert("RGB")))
            if v and 1 <= v <= 100:
                return v
            # single-digit levels ("6"): the text detector skips a lone character. Tight crop, side by side twice
            # -> it reads it (10/9 Paladin lvl 6). "66" or "6" both mean 6.
            cw, ch = crop.size
            t = ImageOps.grayscale(crop.crop((int(cw * .25), int(ch * .2), int(cw * .75), int(ch * .8)))).convert("RGB")
            two = Image.new("RGB", (t.width * 2 + 20, t.height), "black")
            two.paste(t, (0, 0))
            two.paste(t, (t.width + 20, 0))
            s = re.sub(r"\D", "", "".join(x for x, _ in ocr_lines(two)).replace("Ø", "0").replace("ø", "0"))
            if s:
                if len(s) % 2 == 0 and s[:len(s) // 2] == s[len(s) // 2:]:
                    s = s[:len(s) // 2]
                if 1 <= int(s) <= 100:
                    return int(s)
        except Exception:
            pass
    try:
        res = ask_local('This badge shows a character level number. In this font a slashed zero (Ø) is the digit 0, '
                        'so "3Ø" means 30. Return {"level": <int>}', crop)
    except Exception:
        return None
    lv = res.get("level")
    return int(lv) if str(lv).isdigit() and 1 <= int(lv) <= 100 else None


def read_spent() -> int | None:
    """D4 'N points spent' line in the full skill tree's top-left panel."""
    img = screenshot()
    w, h = img.size
    crop = img.crop((int(w * 0.045), int(h * 0.098), int(w * 0.14), int(h * 0.135)))
    crop = crop.resize((crop.width * 3, crop.height * 3))
    if CONFIG.get("reader", "ocr") == "ocr":
        try:
            v = _digits(ocr_lines(crop))
            if v is not None:
                return v
        except Exception:
            pass
    try:
        res = ask_local('Read the number in this text (format "N points spent"). A slashed zero (Ø) is the digit 0. '
                        'Return {"spent": <int>}', crop)
    except Exception:
        return None
    v = res.get("spent")
    return int(v) if str(v).isdigit() else None
