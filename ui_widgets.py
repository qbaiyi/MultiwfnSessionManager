"""Lightweight canvas controls for the desktop launcher."""

import math
import tkinter as tk
from localization import translate


def rounded(canvas, x1, y1, x2, y2, radius=6, **options):
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **options)


def line_icon(canvas, kind, x, y, color):
    """Outline geometry based on the Lucide folder-open, rotate-cw and x icons."""
    options = dict(fill=color, width=1.7, capstyle=tk.ROUND, joinstyle=tk.ROUND)
    if kind == "folder":
        canvas.create_line(x + 2, y + 15, x + 2, y + 3, x + 7, y + 3,
                           x + 10, y + 6, x + 18, y + 6, x + 18, y + 9, **options)
        canvas.create_line(x + 2, y + 15, x + 6, y + 9, x + 21, y + 9,
                           x + 18, y + 18, x + 3, y + 18, x + 2, y + 15, **options)
    elif kind == "restart":
        points = []
        for index in range(29):
            angle = math.radians(45 + index * 10)
            points.extend((x + 11 + 8 * math.cos(angle), y + 11 + 8 * math.sin(angle)))
        canvas.create_line(*points, **options)
        canvas.create_line(x + 19, y + 2, x + 19, y + 8, x + 13, y + 8, **options)
    elif kind == "close":
        canvas.create_line(x + 5, y + 5, x + 17, y + 17, **options)
        canvas.create_line(x + 17, y + 5, x + 5, y + 17, **options)


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, variant="secondary", icon=None, width=148):
        super().__init__(parent, width=width, height=36, bg="#f3f6f9",
                         highlightthickness=0, cursor="hand2", takefocus=True)
        self.text, self.command, self.variant, self.icon = text, command, variant, icon
        self.hover = False
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Enter>", lambda _: self.set_hover(True))
        self.bind("<Leave>", lambda _: self.set_hover(False))
        self.bind("<ButtonRelease-1>", self.click)
        self.bind("<Return>", lambda _: self.command())
        self.bind("<space>", lambda _: self.command())
        self.bind("<FocusIn>", lambda _: self.draw())
        self.bind("<FocusOut>", lambda _: self.draw())

    def click(self, event):
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.focus_set()
            self.command()

    def set_hover(self, hover):
        self.hover = hover
        self.draw()

    def draw(self):
        self.delete("all")
        colors = {
            "primary": ("#087f8c", "#066c77", "#ffffff", "#087f8c"),
            "secondary": ("#f8fafc", "#e9eff4", "#334155", "#d6dfe8"),
            "danger": ("#fff4f3", "#fde7e5", "#b44742", "#efd1ce"),
        }
        normal, active, foreground, border = colors[self.variant]
        rounded(self, 1, 1, self.winfo_width() - 1, 35,
                fill=active if self.hover else normal,
                outline="#087f8c" if self.focus_get() is self else border, width=1)
        if self.icon:
            line_icon(self, self.icon, 11, 7, foreground)
        self.create_text(40 if self.icon else self.winfo_width() / 2, 18, text=self.text,
                         anchor="w" if self.icon else "center", fill=foreground,
                         font=("Microsoft YaHei UI", 10))


class DropZone(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, height=96, bg="#f3f6f9", highlightthickness=0)
        self.active = False
        self.language = "zh"
        self.highlight_job = None
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Enter>", lambda _: self.highlight(True))
        self.bind("<Leave>", lambda _: self.highlight(False))

    def highlight(self, active):
        self.active = active
        self.draw()

    def draw(self):
        self.delete("all")
        width = max(100, self.winfo_width())
        self.create_rectangle(1, 1, width - 2, 94, dash=(5, 4),
                              width=2 if self.active else 1,
                              fill="#eaf6f7" if self.active else "#f5f8fa",
                              outline="#087f8c" if self.active else "#bfccd6")
        self.create_text(width / 2, 30, text=translate("释放以打开文件" if self.active else "文件拖放区", self.language),
                         fill="#087f8c" if self.active else "#334155",
                         font=("Microsoft YaHei UI", 11, "bold"))
        self.create_text(width / 2, 62, text=translate("仅在此处拖入一个或多个文件", self.language),
                         fill="#4a5568", font=("Microsoft YaHei UI", 8))
