"""On-screen markers over the kiosk (Windows only). Click-through and hidden from capture."""

import os
import queue

# --------------------------------------------------------------------------
# Overlay (Windows): click-through, always on top, hidden from screen capture
# --------------------------------------------------------------------------

class Overlay:
    COLOURS = {"hover": "#28dc28", "inferred": "#00b4ff", "todo": "#ffaa00", "label": "#ffcf6a", "none": "#9aa6b2"}

    def __init__(self, W, H):
        import tkinter as tk
        import ctypes
        self.tk = tk
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{W}x{H}+0+0")
        self.root.attributes("-topmost", True)
        self.root.config(bg="#ff00ff")
        self.root.attributes("-transparentcolor", "#ff00ff")
        self.canvas = tk.Canvas(self.root, width=W, height=H, bg="#ff00ff", highlightthickness=0)
        self.canvas.pack()
        self.root.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        GWL_EXSTYLE = -20
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # layered | transparent (click-through) | toolwindow | noactivate
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | 0x80000 | 0x20 | 0x80 | 0x08000000)
        try:
            user32.SetWindowDisplayAffinity(hwnd, 0x11)   # exclude from screen capture
        except Exception:
            pass
        self.q = queue.Queue()
        self.W, self.H = W, H
        self.root.after(100, self._pump)

    def show(self, markers, status):
        self.q.put((markers, status))

    def _pump(self):
        latest = None
        while True:
            try:
                latest = self.q.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self._draw(*latest)
        self.root.after(100, self._pump)

    def _draw(self, markers, status):
        c = self.canvas
        c.delete("all")
        s = self.H / 2160
        for m in markers:
            kind, (x, y, w, h) = m[0], m[1]
            col = self.COLOURS[kind]
            if kind in ("label", "none"):
                # A short note under a shop item: what you already own
                t = c.create_text(x, y + h + 4 * s, text=m[2], anchor="nw", fill=col,
                                  font=("Segoe UI", max(9, int(17 * s)), "bold"))
                bx = c.bbox(t)
                if bx:
                    bg = c.create_rectangle(bx[0] - 6 * s, bx[1] - 3 * s, bx[2] + 6 * s, bx[3] + 3 * s,
                                            fill="#10151b", outline=col)
                    c.tag_lower(bg, t)
                continue
            if kind == "todo":
                c.create_rectangle(x + 8 * s, y + 8 * s, x + w - 8 * s, y + h - 8 * s, outline=col, width=max(2, int(4 * s)))
            else:
                r = 10 * s
                c.create_oval(x + 8 * s, y + 8 * s, x + 8 * s + 2 * r, y + 8 * s + 2 * r, fill=col, outline="")
        if status:
            c.create_text(int(2830 / 3840 * self.W), int(1915 * s), text=status, anchor="w",
                          fill="#ffaa00", font=("Segoe UI", max(10, int(20 * s)), "bold"))

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass


def beep(cfg, kind="capture"):
    if not cfg.get("sound") or os.name != "nt":
        return
    try:
        import winsound
        if kind == "capture":
            winsound.Beep(1500, 35)
        elif kind == "page":
            winsound.Beep(1200, 60)
            winsound.Beep(1700, 80)
        elif kind == "restart":
            winsound.Beep(600, 150)
            winsound.Beep(400, 200)
    except Exception:
        pass

