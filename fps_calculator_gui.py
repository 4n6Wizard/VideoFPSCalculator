#!/usr/bin/env python3
"""
fps_calculator_gui.py  —  Compact GUI for fps_calculator.py
Run with: python fps_calculator_gui.py
"""

import ctypes
import os
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from fps_calculator import find_videos, probe_video, build_html, VIDEO_EXTENSIONS

# ── Colors ────────────────────────────────────────────────────────────────────
BG       = "#1e2130"
SURFACE  = "#2a2f45"
SURFACE2 = "#242838"
BORDER   = "#3a4060"
TEXT     = "#c8cfe0"
MUTED    = "#8892a4"
ACCENT   = "#5b8dee"
STATUS_FG = "#6b7b99"
ERROR_FG  = "#f87171"

DOT_READY = "#4ade80"
DOT_BUSY  = "#f59e0b"
DOT_ERROR = "#f87171"

BTN_OK_FG  = "#4ade80"
BTN_OK_BD  = "#1d6a3a"
BTN_OK_DIM = "#2a3a2e"

RADIUS = 8

FONT       = ("Segoe UI", 9)
FONT_BOLD  = ("Segoe UI", 9, "bold")
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_LABEL = ("Segoe UI", 8, "bold")

VIDEO_TYPES = [
    ("Video files", " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))),
    ("All files", "*.*"),
]
DEFAULT_SAVE = str(Path.home() / "Desktop" / "fps_report.html")


# ── Rounded-corner helpers ────────────────────────────────────────────────────

def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
           x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
           x1,y2, x1,y2-r, x1,y1+r, x1,y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class RoundedEntry(tk.Canvas):
    """A tk.Entry wrapped in a Canvas that draws a rounded border."""
    H = 30

    def __init__(self, parent, var, parent_bg=BG, **kw):
        super().__init__(parent, bg=parent_bg, highlightthickness=0,
                         height=self.H, **kw)
        self._entry = tk.Entry(self, textvariable=var, font=FONT,
                               bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                               relief="flat", bd=0, highlightthickness=0)
        self._win = self.create_window(RADIUS + 4, self.H // 2,
                                       window=self._entry, anchor="w")
        self.bind("<Configure>", lambda e: self._draw())
        self._entry.bind("<FocusIn>",  lambda e: self._draw(ACCENT))
        self._entry.bind("<FocusOut>", lambda e: self._draw(BORDER))

    def _draw(self, outline=BORDER):
        self.delete("bg")
        w = self.winfo_width() or 200
        _round_rect(self, 0, 0, w - 1, self.H - 1, RADIUS,
                    fill=SURFACE, outline=outline, width=1, tags="bg")
        self.tag_lower("bg")
        self.itemconfig(self._win, width=w - RADIUS * 2 - 8)

    def get(self):
        return self._entry.get()


class RoundedButton(tk.Canvas):
    """A Canvas that looks and acts like a rounded button."""

    def __init__(self, parent, text, command, *,
                 bg=SURFACE, fg=MUTED, outline=BORDER,
                 hover_bg=BORDER, hover_fg=TEXT,
                 disabled_fg="#3a4060",
                 padx=10, pady=5,
                 font=FONT, parent_bg=BG, **kw):
        self._bg       = bg
        self._fg       = fg
        self._outline  = outline
        self._hover_bg = hover_bg
        self._hover_fg = hover_fg
        self._dis_fg   = disabled_fg
        self._text     = text
        self._font     = font
        self._cmd      = command
        self._state    = "normal"

        # Size to fit text
        probe = tk.Label(parent, text=text, font=font, padx=padx, pady=pady)
        probe.update_idletasks()
        w, h = probe.winfo_reqwidth(), probe.winfo_reqheight()
        probe.destroy()

        super().__init__(parent, width=w, height=h,
                         bg=parent_bg, highlightthickness=0,
                         cursor="hand2", **kw)
        self._draw()
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self, fill=None, fg=None, outline=None):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        f  = fill    or self._bg
        o  = outline or self._outline
        fc = fg or (self._dis_fg if self._state == "disabled" else self._fg)
        _round_rect(self, 0, 0, w - 1, h - 1, RADIUS,
                    fill=f, outline=o, width=1)
        self.create_text(w // 2, h // 2, text=self._text,
                         font=self._font, fill=fc)

    def _on_enter(self, _):
        if self._state == "normal":
            self._draw(fill=self._hover_bg, fg=self._hover_fg)

    def _on_leave(self, _):
        self._draw()

    def _on_click(self, _):
        if self._state == "normal" and self._cmd:
            self._cmd()

    def config(self, **kw):
        if "state" in kw:
            self._state = kw["state"]
            self["cursor"] = "hand2" if self._state == "normal" else ""
        if "text" in kw:
            self._text = kw["text"]
        if "fg" in kw:
            self._fg = kw["fg"]
        if "outline" in kw:
            self._outline = kw["outline"]
        self._draw()


# ── App ───────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video FPS Calculator")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.after(10, self._clear_titlebar_icon)
        self._report_path = None
        self._build_ui()
        self._center()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        title_row = tk.Frame(self, bg=BG)
        title_row.pack(fill="x", padx=14, pady=(14, 10))

        logo = tk.Canvas(title_row, width=20, height=20,
                         bg=BG, highlightthickness=0)
        logo.pack(side="left", padx=(0, 7))
        _round_rect(logo, 1, 3, 19, 17, 2, fill=SURFACE, outline=ACCENT, width=1)
        for y in (5, 9, 13):
            logo.create_rectangle(1, y, 3, y + 2, fill=ACCENT, outline="")
            logo.create_rectangle(17, y, 19, y + 2, fill=ACCENT, outline="")
        logo.create_polygon(8, 7, 8, 13, 14, 10, fill=ACCENT, outline="")

        tk.Label(title_row, text="Video FPS Calculator",
                 font=FONT_TITLE, bg=BG, fg=TEXT).pack(side="left")

        tk.Frame(self, height=1, bg=BORDER).pack(fill="x")

        # Body
        body = tk.Frame(self, bg=BG)
        body.pack(fill="x", padx=14, pady=0)

        # Video source
        self._section_label(body, "V I D E O   S O U R C E")
        src_row = tk.Frame(body, bg=BG)
        src_row.pack(fill="x", pady=(3, 0))

        self._path_var = tk.StringVar()
        RoundedEntry(src_row, self._path_var).pack(
            side="left", fill="x", expand=True)
        RoundedButton(src_row, "File",   self._browse_file,
                      padx=10).pack(side="left", padx=(5, 0))
        RoundedButton(src_row, "Folder", self._browse_folder,
                      padx=10).pack(side="left", padx=(4, 0))

        self._count_lbl = tk.Label(body, text="", font=FONT, bg=BG, fg=ACCENT)
        self._count_lbl.pack(anchor="w", pady=(3, 0))

        # Save report
        self._section_label(body, "S A V E   R E P O R T   T O")
        save_row = tk.Frame(body, bg=BG)
        save_row.pack(fill="x", pady=(3, 14))

        self._save_var = tk.StringVar(value=DEFAULT_SAVE)
        RoundedEntry(save_row, self._save_var).pack(
            side="left", fill="x", expand=True)
        RoundedButton(save_row, "Browse", self._browse_save,
                      padx=10).pack(side="left", padx=(5, 0))

        # Progress bar
        self._prog = tk.Canvas(self, height=3, bg=SURFACE2, highlightthickness=0)
        self._prog.pack(fill="x")
        self._prog_bar = self._prog.create_rectangle(0, 0, 0, 3,
                                                     fill=ACCENT, outline="")

        # Footer
        tk.Frame(self, height=1, bg=BORDER).pack(fill="x")
        footer = tk.Frame(self, bg=SURFACE2)
        footer.pack(fill="x", ipady=7)

        # Status dot + label
        status_left = tk.Frame(footer, bg=SURFACE2)
        status_left.pack(side="left", padx=(12, 0))

        self._dot = tk.Canvas(status_left, width=8, height=8,
                              bg=SURFACE2, highlightthickness=0)
        self._dot.pack(side="left", padx=(0, 6))
        self._dot_id = self._dot.create_oval(1, 1, 7, 7,
                                             fill=BORDER, outline="")

        self._status_var = tk.StringVar(value="Ready")
        self._status_lbl = tk.Label(status_left, textvariable=self._status_var,
                                    font=FONT, bg=SURFACE2, fg=STATUS_FG)
        self._status_lbl.pack(side="left")

        self._auto_var = tk.BooleanVar(value=False)
        tk.Checkbutton(status_left, text="Auto-open",
                       variable=self._auto_var,
                       bg=SURFACE2, fg=MUTED,
                       selectcolor=SURFACE2,
                       activebackground=SURFACE2, activeforeground=TEXT,
                       font=FONT, bd=0, highlightthickness=0,
                       ).pack(side="left", padx=(14, 0))

        # Action buttons
        btn_right = tk.Frame(footer, bg=SURFACE2)
        btn_right.pack(side="right", padx=(0, 12))

        self._open_btn = RoundedButton(
            btn_right, "Open report", self._open_report,
            bg=SURFACE2, fg=BTN_OK_DIM, outline=BORDER,
            hover_bg="#1d6a3a", hover_fg=BTN_OK_FG,
            disabled_fg=BTN_OK_DIM,
            parent_bg=SURFACE2,
        )
        self._open_btn.config(state="disabled")
        self._open_btn.pack(side="left", padx=(0, 6))

        self._analyze_btn = RoundedButton(
            btn_right, "Analyze", self._start_analysis,
            bg=ACCENT, fg="#ffffff", outline=ACCENT,
            hover_bg="#4a7bde", hover_fg="#ffffff",
            font=FONT_BOLD,
            parent_bg=SURFACE2,
        )
        self._analyze_btn.pack(side="left")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_titlebar_icon(self):
        hwnd = self.winfo_id()
        # Clear window-instance icons
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, 0)  # WM_SETICON SMALL
        ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, 0)  # WM_SETICON BIG
        # Clear window-class icons so tkinter can't restore the feather
        GCL_HICON   = -14
        GCL_HICONSM = -34
        ctypes.windll.user32.SetClassLongPtrW(hwnd, GCL_HICONSM, 0)
        ctypes.windll.user32.SetClassLongPtrW(hwnd, GCL_HICON,   0)

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, font=FONT_LABEL,
                 bg=BG, fg=BORDER).pack(anchor="w", pady=(10, 0))

    def _center(self):
        self.update_idletasks()
        h = self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"540x{h}+{(sw - 540) // 2}+{(sh - h) // 2}")

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(title="Select a video file",
                                          filetypes=VIDEO_TYPES)
        if path:
            self._path_var.set(path)
            self._schedule_count_update(path)

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select a folder")
        if path:
            self._path_var.set(path)
            self._schedule_count_update(path)

    def _schedule_count_update(self, path):
        self._count_lbl.config(text="Counting…")
        threading.Thread(target=self._count_videos, args=(path,),
                         daemon=True).start()

    def _count_videos(self, path):
        videos = find_videos(path)
        n = len(videos)
        text = f"{n} video{'s' if n != 1 else ''} found" if n else "No video files found"
        self.after(0, self._count_lbl.config, {"text": text,
                                               "fg": ACCENT if n else ERROR_FG})

    def _browse_save(self):
        path = filedialog.asksaveasfilename(
            title="Save report as",
            defaultextension=".html",
            filetypes=[("HTML file", "*.html"), ("All files", "*.*")],
            initialfile="fps_report.html",
        )
        if path:
            self._save_var.set(path)

    # ── Analysis ──────────────────────────────────────────────────────────────

    def _start_analysis(self):
        target = self._path_var.get().strip()
        if not target:
            self._set_status("Please select a file or folder first.", "error")
            return
        if not Path(target).exists():
            self._set_status("Path not found. Check the path and try again.", "error")
            return

        save_path = self._save_var.get().strip() or DEFAULT_SAVE
        self._analyze_btn.config(state="disabled", text="Scanning...")
        self._open_btn.config(state="disabled", fg=BTN_OK_DIM, outline=BORDER)
        self._count_lbl.config(text="")
        self._set_status("Scanning for video files...", "busy")
        self._set_progress(0)
        threading.Thread(target=self._run, args=(target, save_path),
                         daemon=True).start()

    def _run(self, target, save_path):
        videos = find_videos(target)
        if not videos:
            self.after(0, self._set_status,
                       "No video files found at that path.", "error")
            self.after(0, lambda: self._analyze_btn.config(
                state="normal", text="Analyze"))
            return

        self.after(0, self._set_status,
                   f"Analyzing {len(videos)} file(s)...", "busy")
        self.after(0, lambda: self._analyze_btn.config(text="Analyzing..."))

        rows = []
        total_v = len(videos)
        for i, vp in enumerate(videos, 1):
            self.after(0, self._set_status,
                       f"Processing {i} of {total_v}: {vp.name}", "busy")
            self.after(0, self._set_progress, (i - 1) / total_v)
            info = probe_video(str(vp))
            info["name"] = vp.name
            info["path"] = str(vp)
            rows.append(info)
        self.after(0, self._set_progress, 1.0)

        html = build_html(rows, target)
        try:
            Path(save_path).write_text(html, encoding="utf-8")
        except OSError as exc:
            self.after(0, self._on_save_error, str(exc))
            return

        errors = sum(1 for r in rows if "error" in r)
        ok = len(rows) - errors
        total_frames = sum(r["total_frames"] for r in rows
                           if isinstance(r.get("total_frames"), int))

        msg = f"Done  —  {ok}/{len(rows)} file(s) analyzed.  {total_frames:,} total frames."
        if errors:
            msg += f"  {errors} error(s) in report."

        self._report_path = save_path
        self.after(0, self._on_done, msg)

    def _on_done(self, msg):
        self._set_status(msg, "done")
        self._analyze_btn.config(state="normal", text="Analyze")
        self._open_btn.config(state="normal", fg=BTN_OK_FG, outline=BTN_OK_BD)
        if self._auto_var.get():
            self._open_report()

    def _on_save_error(self, detail):
        self._analyze_btn.config(state="normal", text="Analyze")
        self._set_status("Could not save report — check the save path.", "error")
        messagebox.showerror("Save failed",
                             f"Could not write the report:\n\n{detail}")

    def _set_progress(self, frac):
        w = self._prog.winfo_width()
        self._prog.coords(self._prog_bar, 0, 0, int(w * frac), 3)

    def _set_status(self, msg, state="idle"):
        self._status_var.set(msg)
        dot_color = {"idle": BORDER, "done": DOT_READY,
                     "busy": DOT_BUSY, "error": DOT_ERROR}.get(state, BORDER)
        self._dot.itemconfig(self._dot_id, fill=dot_color)
        self._status_lbl.config(fg=ERROR_FG if state == "error" else STATUS_FG)

    def _open_report(self):
        if self._report_path and Path(self._report_path).exists():
            os.startfile(self._report_path)


if __name__ == "__main__":
    app = App()
    app.mainloop()
