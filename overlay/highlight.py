"""Guide-mode overlay: a see-through, click-through, always-on-top window that draws a glowing ring + label on the
next node. The player clicks; the bot never sends input to the game (stays inside Blizzard's rules).

  python highlight.py 1280 720 "Next: Fortify (3/23)"     # quick test: ring at that screen spot for 8 s

Only visible when Diablo IV runs in Windowed or Borderless (Windowed Fullscreen) mode - exclusive fullscreen
draws over everything.
"""
import ctypes
import sys
import threading
import tkinter as tk

KEY = "#010203"  # this colour becomes fully transparent


class Overlay:
    def __init__(self):
        self.root = None
        self._ring_kind = None
        self._ring_items = None
        self._arrow_items = None
        self._banner_key = None
        self._banner_items = None
        self._flash_item = None
        self._flash_job = None
        self._flash_on = False
        self._flash_color = "#ff3030"
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def _run(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        r = self.root = tk.Tk()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.config(bg=KEY)
        r.attributes("-transparentcolor", KEY)
        w, h = r.winfo_screenwidth(), r.winfo_screenheight()
        r.geometry(f"{w}x{h}+0+0")
        self.c = tk.Canvas(r, width=w, height=h, bg=KEY, highlightthickness=0)
        self.c.pack()
        r.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(r.winfo_id())
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = -20, 0x80000, 0x20, 0x80
        st = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
        # the player sees the overlay, but the bot's own screenshots don't (so the ring can't fool the detectors)
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11)  # WDA_EXCLUDEFROMCAPTURE (Win10 2004+)
        self._ready.set()
        r.mainloop()

    def banner(self, text, sub="", color="#ffd34d", size=22, at=None, connect=None, flash=False):
        """Big instruction text, optionally attached to a screen position."""
        def draw():
            key = (text, sub, color, size, flash)
            w, h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            cx, top = (w // 2, 120) if at is None else at
            text_width = min(760, int(w * 0.72))
            cx = max(text_width // 2 + 20, min(cx, w - text_width // 2 - 20))
            items = self._banner_items
            if self._banner_key == key and items is not None:
                line, shadow, heading, sub_shadow, subtitle = items
                if line is not None:
                    node_x, node_y = connect
                    banner_y = top - 28 if top > node_y else top + 58
                    self.c.coords(line, node_x, node_y, cx, banner_y)
                self.c.coords(shadow, cx + 2, top + 2)
                self.c.coords(heading, cx, top)
                self.c.itemconfigure(shadow, width=text_width)
                self.c.itemconfigure(heading, width=text_width)
                if subtitle is not None:
                    self.c.coords(sub_shadow, cx + 2, top + 42)
                    self.c.coords(subtitle, cx, top + 40)
                    self.c.itemconfigure(sub_shadow, width=text_width)
                    self.c.itemconfigure(subtitle, width=text_width)
                return
            self.c.delete("banner")
            if self._flash_job is not None:
                self.root.after_cancel(self._flash_job)
                self._flash_job = None
            self._flash_item = None
            line = None
            if at is not None:
                top = max(55, min(top, h - 105))
                if connect is not None:
                    node_x, node_y = connect
                    banner_y = top - 28 if top > node_y else top + 58
                    line = self.c.create_line(node_x, node_y, cx, banner_y, fill=color, width=3, tags="banner")
            shadow = self.c.create_text(cx + 2, top + 2, text=text, fill="#000000", width=text_width,
                                        font=("Segoe UI", size, "bold"), tags="banner")
            heading = self.c.create_text(cx, top, text=text, fill=color, width=text_width,
                                         font=("Segoe UI", size, "bold"), tags="banner")
            sub_shadow = subtitle = None
            if sub:
                sub_shadow = self.c.create_text(cx + 2, top + 42, text=sub, fill="#000000", width=text_width,
                                                font=("Segoe UI", max(15, int(size * 0.6))), tags="banner")
                subtitle = self.c.create_text(cx, top + 40, text=sub, fill="#ffffff", width=text_width,
                                              font=("Segoe UI", max(15, int(size * 0.6))), tags="banner")
            self._banner_items = (line, shadow, heading, sub_shadow, subtitle)
            self._banner_key = key
            if flash:
                self._flash_item = heading
                self._flash_color = color
                self._flash_on = False
                self._flash_job = self.root.after(500, self._flash_banner)
        self.root.after(0, draw)

    def _flash_banner(self):
        if self._flash_item is None:
            return
        self._flash_on = not self._flash_on
        self.c.itemconfigure(self._flash_item, fill=self._flash_color if self._flash_on else "#ffffff")
        self._flash_job = self.root.after(500, self._flash_banner)

    def arrow(self, x, y, direction, label=""):
        """Big arrow at (x, y) pointing up/down/left/right (drag hint)."""
        def draw():
            d = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[direction]
            coords = (x - d[0] * 90, y - d[1] * 90, x + d[0] * 90, y + d[1] * 90)
            label_y = y + 130 if direction == "up" else y - 130
            if self._ring_kind != "arrow":
                self.c.delete("ring")
                self._ring_items = None
                line = self.c.create_line(*coords, fill="#ffd34d", width=12, arrow="last",
                                          arrowshape=(34, 40, 16), tags="ring")
                text = self.c.create_text(x, label_y, text=label, fill="#ffd34d",
                                          font=("Segoe UI", 18, "bold"), tags="ring")
                self._arrow_items = (line, text)
                self._ring_kind = "arrow"
            else:
                line, text = self._arrow_items
                self.c.coords(line, *coords)
                self.c.coords(text, x, label_y)
                self.c.itemconfigure(text, text=label)
        self.root.after(0, draw)

    def show(self, x, y, radius=28, label=""):
        """Ring centred on screen pixel (x, y). Thread-safe."""
        def draw():
            if self._ring_kind != "circle":
                self.c.delete("ring")
                self._arrow_items = None
                colors = ("#ffd34d", "#ff9d00", "#ff5a00")
                circles = [self.c.create_oval(0, 0, 0, 0, outline=col, width=4 - i, tags="ring")
                           for i, col in enumerate(colors)]
                shadow = self.c.create_text(0, 0, text="", fill="#000000", font=("Segoe UI", 16, "bold"),
                                            tags="ring")
                caption = self.c.create_text(0, 0, text="", fill="#ffd34d", font=("Segoe UI", 16, "bold"),
                                             tags="ring")
                self._ring_items = (*circles, shadow, caption)
                self._ring_kind = "circle"
            *circles, shadow, caption = self._ring_items
            for i, item in enumerate(circles):
                rr = radius + i * 5
                self.c.coords(item, x - rr, y - rr, x + rr, y + rr)
            self.c.coords(shadow, x + 1, y - radius - 25)
            self.c.coords(caption, x, y - radius - 26)
            self.c.itemconfigure(shadow, text=label)
            self.c.itemconfigure(caption, text=label)
        self.root.after(0, draw)

    def clear(self, what="all"):
        def draw():
            self.c.delete(what)
            if what in ("all", "ring"):
                self._ring_kind = None
                self._ring_items = None
                self._arrow_items = None
            if what in ("all", "banner"):
                self._banner_key = None
                self._banner_items = None
                self._flash_item = None
                if self._flash_job is not None:
                    self.root.after_cancel(self._flash_job)
                    self._flash_job = None
        self.root.after(0, draw)

    def close(self):
        self.root.after(0, self.root.destroy)
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=5)


if __name__ == "__main__":
    import time
    x, y = int(sys.argv[1]), int(sys.argv[2])
    o = Overlay()
    o.show(x, y, label=sys.argv[3] if len(sys.argv) > 3 else "Next node")
    time.sleep(8)
    o.close()
