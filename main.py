import tkinter as tk
from tkinter import ttk
import pyautogui
import keyboard
import random
from PIL import ImageGrab, Image, ImageTk
import threading
import time


# ---------------------------------------------------------------------------
# Color palette — Catppuccin Mocha base, kept consistent throughout
# ---------------------------------------------------------------------------
COLORS = {
    "base":      "#1e1e2e",   # window background
    "mantle":    "#181825",   # deeper background (canvas, text areas)
    "crust":     "#11111b",   # darkest surface
    "surface0":  "#313244",   # card background
    "surface1":  "#45475a",   # card border / divider
    "surface2":  "#585b70",   # muted text / placeholder
    "overlay0":  "#6c7086",   # secondary muted
    "overlay1":  "#7f849c",   # tertiary muted
    "text":      "#cdd6f4",   # primary text
    "subtext1":  "#bac2de",   # secondary text
    "subtext0":  "#a6adc8",   # tertiary text
    "lavender":  "#b4befe",   # accent 1
    "mauve":     "#cba6f7",   # accent 2 / titles
    "blue":      "#89b4fa",   # info
    "sapphire":  "#74c7ec",   # highlight
    "sky":       "#89dceb",   # secondary info
    "green":     "#a6e3a1",   # success / set
    "yellow":    "#f9e2af",   # warning
    "peach":     "#fab387",   # caution
    "red":       "#f38ba8",   # error / unset
    "pink":      "#f5c2e7",   # accent 3
    "teal":      "#94e2d5",   # accent 4
}

FONT_FAMILY = "맑은 고딕"


class HoverButton(tk.Canvas):
    """
    A fully custom Canvas-based button that supports:
    - Rounded rectangle shape
    - Smooth hover / active colour transitions
    - Optional leading icon (Unicode character)
    - Keyboard focus ring
    """

    def __init__(self, parent, text, command=None, icon="",
                 bg_normal=COLORS["surface0"],
                 bg_hover=COLORS["surface1"],
                 bg_active=COLORS["surface2"],
                 fg=COLORS["text"],
                 font_size=10, bold=False,
                 radius=8, width=160, height=36,
                 border_color=COLORS["surface1"],
                 border_hover=COLORS["lavender"],
                 **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"] if hasattr(parent, "__getitem__") else COLORS["base"],
                         highlightthickness=0, **kwargs)

        self.command = command
        self.radius = radius
        self.w = width
        self.h = height

        self.bg_normal = bg_normal
        self.bg_hover = bg_hover
        self.bg_active = bg_active
        self.fg = fg
        self.border_color = border_color
        self.border_hover = border_hover

        weight = "bold" if bold else "normal"
        self.font = (FONT_FAMILY, font_size, weight)
        self.label = (icon + "  " + text).strip() if icon else text
        self._state = "normal"

        self._draw(self.bg_normal, self.border_color)

        self.bind("<Enter>",          self._on_enter)
        self.bind("<Leave>",          self._on_leave)
        self.bind("<ButtonPress-1>",  self._on_press)
        self.bind("<ButtonRelease-1>",self._on_release)
        self.bind("<FocusIn>",        self._on_focus)
        self.bind("<FocusOut>",       self._on_blur)
        self.bind("<Return>",         lambda e: self._invoke())
        self.bind("<space>",          lambda e: self._invoke())

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        """Draw a rounded rectangle on this canvas."""
        self.create_arc(x1,     y1,     x1+2*r, y1+2*r, start= 90, extent=90, **kw)
        self.create_arc(x2-2*r, y1,     x2,     y1+2*r, start=  0, extent=90, **kw)
        self.create_arc(x1,     y2-2*r, x1+2*r, y2,     start=180, extent=90, **kw)
        self.create_arc(x2-2*r, y2-2*r, x2,     y2,     start=270, extent=90, **kw)
        self.create_rectangle(x1+r, y1,   x2-r, y2,   **kw)
        self.create_rectangle(x1,   y1+r, x2,   y2-r, **kw)

    def _draw(self, bg, border):
        self.delete("all")
        pad = 1          # border padding
        r   = self.radius
        self._rounded_rect(pad, pad, self.w-pad, self.h-pad, r,
                           fill=border, outline="")
        self._rounded_rect(pad+1, pad+1, self.w-pad-1, self.h-pad-1, max(r-1, 2),
                           fill=bg, outline="")
        self.create_text(self.w // 2, self.h // 2,
                         text=self.label, fill=self.fg,
                         font=self.font, anchor="center")

    def _on_enter(self, _=None):
        self._state = "hover"
        self._draw(self.bg_hover, self.border_hover)
        self.configure(cursor="hand2")

    def _on_leave(self, _=None):
        self._state = "normal"
        self._draw(self.bg_normal, self.border_color)
        self.configure(cursor="")

    def _on_press(self, _=None):
        self._state = "active"
        self._draw(self.bg_active, self.border_hover)

    def _on_release(self, _=None):
        self._draw(self.bg_hover, self.border_hover)
        self._invoke()

    def _on_focus(self, _=None):
        # Draw a subtle focus ring
        self.create_rectangle(3, 3, self.w-3, self.h-3,
                              outline=self.border_hover,
                              dash=(3, 3), width=1, tags="focus_ring")

    def _on_blur(self, _=None):
        self.delete("focus_ring")

    def _invoke(self):
        if self.command:
            self.command()

    def set_parent_bg(self, color):
        """Call this after the widget is placed so the transparent edges look correct."""
        self.configure(bg=color)


class MacroLoopApp:
    def __init__(self, root):
        self.root = root
        self.root.configure(bg=COLORS["base"])

        # ── State flags ──────────────────────────────────────────────────────
        self.is_running     = False
        self.waiting_input  = False

        # ── Stored coordinates / settings ────────────────────────────────────
        self.seat_axis     = []
        self.seat_class    = set()
        self.time_axis     = []
        self.pay_axis      = []
        self.need_seat_cnt = 2    # 연석 기본값

        # ── 자동 정지 색상 감지 ────────────────────────────────────
        self.stop_color    = None  # (R, G, B)

        # ESC 키로 매크로 취소
        keyboard.on_press_key("esc", lambda _: self._on_esc())
        # A 키로 매크로 시작
        keyboard.on_press_key("a", lambda _: self._on_start_key())

        # ── ttk style (kept minimal — most styling done via tk widgets) ───────
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame",   background=COLORS["base"])
        self.style.configure("Card.TFrame",
                             background=COLORS["surface0"],
                             relief="flat")
        self.style.configure("TLabel",
                             background=COLORS["base"],
                             foreground=COLORS["text"],
                             font=(FONT_FAMILY, 10))
        self.style.configure("Card.TLabel",
                             background=COLORS["surface0"],
                             foreground=COLORS["text"],
                             font=(FONT_FAMILY, 10))
        self.style.configure("CardMuted.TLabel",
                             background=COLORS["surface0"],
                             foreground=COLORS["subtext0"],
                             font=(FONT_FAMILY, 8))
        self.style.configure("Separator.TSeparator",
                             background=COLORS["surface1"])

        self.build_ui()

    # =========================================================================
    # UI BUILD
    # =========================================================================

    def build_ui(self):
        """Construct the entire UI layout."""

        # ── Scrollable shell ──────────────────────────────────────────────────
        self._scroll_canvas = tk.Canvas(self.root, bg=COLORS["base"],
                                        highlightthickness=0)
        self._scrollbar = tk.Scrollbar(self.root, orient="vertical",
                                       command=self._scroll_canvas.yview,
                                       bg=COLORS["surface1"],
                                       troughcolor=COLORS["base"], width=8)
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)

        outer = tk.Frame(self._scroll_canvas, bg=COLORS["base"])
        self._scroll_window = self._scroll_canvas.create_window(
            (0, 0), window=outer, anchor="nw")

        # Keep scroll region up-to-date
        def _on_configure(event):
            self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
        outer.bind("<Configure>", _on_configure)

        # Match inner frame width to canvas width
        def _on_canvas_configure(event):
            self._scroll_canvas.itemconfigure(self._scroll_window, width=event.width)
        self._scroll_canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.root.bind_all("<MouseWheel>", _on_mousewheel)

        # Add padding inside the scrollable frame
        outer_padded = tk.Frame(outer, bg=COLORS["base"])
        outer_padded.pack(fill="both", expand=True, padx=16, pady=16)
        outer = outer_padded

        # ── Header bar ───────────────────────────────────────────────────────
        self._build_header(outer)

        # ── Status bar (below header) ─────────────────────────────────────────
        self._build_status_bar(outer)

        # ── Log card ─────────────────────────────────────────────────────────
        self._build_log_card(outer)

        # ── Body: canvas (left) + right panel ────────────────────────────────
        body = tk.Frame(outer, bg=COLORS["base"])
        body.pack(fill="both", expand=True, pady=(10, 0))

        self._build_canvas_card(body)
        self._build_right_panel(body)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self, parent):
        hdr = tk.Frame(parent, bg=COLORS["base"])
        hdr.pack(fill="x", pady=(0, 10))

        # App icon dot
        dot_canvas = tk.Canvas(hdr, width=14, height=14,
                               bg=COLORS["base"], highlightthickness=0)
        dot_canvas.pack(side="left", padx=(0, 8), pady=4)
        dot_canvas.create_oval(1, 1, 13, 13, fill=COLORS["mauve"], outline="")

        tk.Label(hdr, text="Ticket Macro",
                 bg=COLORS["base"], fg=COLORS["mauve"],
                 font=(FONT_FAMILY, 16, "bold")).pack(side="left")

        tk.Label(hdr, text="v1.0",
                 bg=COLORS["base"], fg=COLORS["surface2"],
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(8, 0), pady=(5, 0))

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self, parent):
        card = self._card(parent, pady=(0, 8))

        left = tk.Frame(card, bg=COLORS["surface0"])
        left.pack(fill="x")

        # Coloured indicator dot
        self._status_dot = tk.Canvas(left, width=10, height=10,
                                     bg=COLORS["surface0"], highlightthickness=0)
        self._status_dot.pack(side="left", padx=(12, 6), pady=10)
        self._status_dot_id = self._status_dot.create_oval(1, 1, 9, 9,
                                                            fill=COLORS["green"],
                                                            outline="")

        self.status_var = tk.StringVar(value="대기 중")
        tk.Label(left, textvariable=self.status_var,
                 bg=COLORS["surface0"], fg=COLORS["text"],
                 font=(FONT_FAMILY, 10, "bold")).pack(side="left")

        # Right-side secondary info
        self._status_right_var = tk.StringVar(value="준비 완료")
        tk.Label(left, textvariable=self._status_right_var,
                 bg=COLORS["surface0"], fg=COLORS["subtext0"],
                 font=(FONT_FAMILY, 9)).pack(side="right", padx=12)

    # ── Log card ──────────────────────────────────────────────────────────────

    def _build_log_card(self, parent):
        # 로그 + 영역 정보를 좌우로 배치하는 컨테이너
        row = tk.Frame(parent, bg=COLORS["base"])
        row.pack(fill="x", pady=(0, 10))

        # ── 왼쪽: 로그 카드 ──
        left_outer = tk.Frame(row, bg=COLORS["surface1"], padx=1, pady=1, width=420)
        left_outer.pack(side="left", fill="y")
        left_outer.pack_propagate(False)
        card = tk.Frame(left_outer, bg=COLORS["surface0"])
        card.pack(fill="both", expand=True)

        hdr = tk.Frame(card, bg=COLORS["surface0"])
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(hdr, text="로그",
                 bg=COLORS["surface0"], fg=COLORS["blue"],
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")

        tk.Label(hdr, text="실시간 출력",
                 bg=COLORS["surface0"], fg=COLORS["surface2"],
                 font=(FONT_FAMILY, 8)).pack(side="left", padx=(6, 0))

        def _clear_log():
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")

        clear_btn = tk.Label(hdr, text="지우기",
                             bg=COLORS["surface0"], fg=COLORS["surface2"],
                             font=(FONT_FAMILY, 8), cursor="hand2")
        clear_btn.pack(side="right")
        clear_btn.bind("<Enter>", lambda e: clear_btn.configure(fg=COLORS["red"]))
        clear_btn.bind("<Leave>", lambda e: clear_btn.configure(fg=COLORS["surface2"]))
        clear_btn.bind("<ButtonRelease-1>", lambda e: _clear_log())

        div = tk.Frame(card, height=1, bg=COLORS["surface1"])
        div.pack(fill="x", padx=12)

        log_bg = tk.Frame(card, bg=COLORS["mantle"])
        log_bg.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log_text = tk.Text(
            log_bg, bg=COLORS["mantle"], fg=COLORS["green"],
            font=("Consolas", 9), height=2, bd=0, wrap="word",
            state="disabled", insertbackground=COLORS["text"],
            selectbackground=COLORS["surface1"],
            selectforeground=COLORS["text"], padx=10, pady=8,
        )
        self.log_text.pack(fill="both", expand=True)

        self.log_text.tag_configure("ts",      foreground=COLORS["surface2"])
        self.log_text.tag_configure("info",    foreground=COLORS["blue"])
        self.log_text.tag_configure("success", foreground=COLORS["green"])
        self.log_text.tag_configure("warn",    foreground=COLORS["yellow"])
        self.log_text.tag_configure("error",   foreground=COLORS["red"])

        sb = tk.Scrollbar(log_bg, command=self.log_text.yview,
                          bg=COLORS["surface1"], troughcolor=COLORS["mantle"],
                          bd=0, width=6)
        self.log_text.configure(yscrollcommand=sb.set)

        # ── 오른쪽: 영역 좌표 정보 카드 ──
        right_outer = tk.Frame(row, bg=COLORS["surface1"], padx=1, pady=1)
        right_outer.pack(side="left", fill="both", padx=(10, 0), ipadx=0)
        rcard = tk.Frame(right_outer, bg=COLORS["surface0"])
        rcard.pack(fill="both", expand=True)

        rhdr = tk.Frame(rcard, bg=COLORS["surface0"])
        rhdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(rhdr, text="영역 좌표",
                 bg=COLORS["surface0"], fg=COLORS["peach"],
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")

        self._area_count_var = tk.StringVar(value="0개")
        tk.Label(rhdr, textvariable=self._area_count_var,
                 bg=COLORS["surface0"], fg=COLORS["text"],
                 font=(FONT_FAMILY, 9, "bold")).pack(side="right")

        rdiv = tk.Frame(rcard, height=1, bg=COLORS["surface1"])
        rdiv.pack(fill="x", padx=12)

        list_bg = tk.Frame(rcard, bg=COLORS["mantle"])
        list_bg.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.area_listbox = tk.Listbox(
            list_bg, bg=COLORS["mantle"], fg=COLORS["text"],
            font=("Consolas", 9), selectbackground=COLORS["surface1"],
            selectforeground=COLORS["peach"], highlightthickness=0,
            activestyle="none", bd=0, width=20,
        )
        self.area_listbox.pack(fill="both", expand=True, padx=6, pady=6)

    # ── Canvas card (seat preview) ────────────────────────────────────────────

    def _build_canvas_card(self, parent):
        wrap = tk.Frame(parent, bg=COLORS["base"])
        wrap.pack(side="left", fill="both", expand=True)

        card = self._card(wrap, padx=0, pady=0, fill="both", expand=True)

        # Header
        hdr = tk.Frame(card, bg=COLORS["surface0"])
        hdr.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(hdr, text="좌석 미리보기",
                 bg=COLORS["surface0"], fg=COLORS["lavender"],
                 font=(FONT_FAMILY, 9, "bold")).pack(side="left")
        tk.Label(hdr, text="영역 선택 시 자동 갱신",
                 bg=COLORS["surface0"], fg=COLORS["surface2"],
                 font=(FONT_FAMILY, 8)).pack(side="left", padx=(6, 0))

        div = tk.Frame(card, height=1, bg=COLORS["surface1"])
        div.pack(fill="x", padx=12, pady=(0, 6))

        canvas_wrap = tk.Frame(card, bg=COLORS["mantle"],
                               highlightthickness=1,
                               highlightbackground=COLORS["surface1"])
        canvas_wrap.pack(padx=12, pady=(0, 12))

        self.canvas = tk.Canvas(canvas_wrap, width=360, height=360,
                                bg=COLORS["mantle"], highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_text(180, 180,
                                text="좌석 영역을 선택하면\n여기에 미리보기가 표시됩니다",
                                fill=COLORS["surface2"],
                                font=(FONT_FAMILY, 10),
                                justify="center")

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        panel = tk.Frame(parent, bg=COLORS["base"])
        panel.pack(side="left", fill="both", padx=(10, 0))

        self._build_run_card(panel)
        self._build_setup_card(panel)
        self._build_stop_color_card(panel)
        self._build_color_card(panel)

    # ── Run card ──────────────────────────────────────────────────────────────

    def _build_run_card(self, parent):
        card = self._card(parent, pady=(0, 10))

        self._card_header(card, "매크로 실행", COLORS["green"], "실행 / 중지 제어")

        inner = tk.Frame(card, bg=COLORS["surface0"])
        inner.pack(fill="x", padx=12, pady=(4, 12))

        # ── Seat count radio group ────────────────────────────────────────────
        rc_frame = tk.Frame(inner, bg=COLORS["surface0"])
        rc_frame.pack(fill="x", pady=(0, 10))

        tk.Label(rc_frame, text="좌석 수",
                 bg=COLORS["surface0"], fg=COLORS["subtext0"],
                 font=(FONT_FAMILY, 8)).pack(side="left", padx=(0, 8))

        self.seat_cnt_var = tk.IntVar(value=2)
        for val, txt in [(1, "1석"), (2, "2석 (연석)")]:
            rb = tk.Radiobutton(
                rc_frame, text=txt,
                variable=self.seat_cnt_var, value=val,
                bg=COLORS["surface0"], fg=COLORS["text"],
                selectcolor=COLORS["surface1"],
                activebackground=COLORS["surface0"],
                activeforeground=COLORS["lavender"],
                font=(FONT_FAMILY, 9),
                command=self.on_seat_cnt_change,
                bd=0, highlightthickness=0,
                cursor="hand2",
            )
            rb.pack(side="left", padx=(0, 12))

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_data = [
            ("매크로 시작  (A)",   self.start_first_floor,
             COLORS["surface0"], COLORS["surface1"], COLORS["surface2"],
             COLORS["green"],    COLORS["green"],
             "▶"),
            ("매크로 중지  (ESC)",  self.stop_infinite_loop,
             COLORS["surface0"], COLORS["surface1"], COLORS["surface2"],
             COLORS["red"],      COLORS["red"],
             "■"),
        ]

        for label, cmd, bgn, bgh, bga, fg, border_h, icon in btn_data:
            b = HoverButton(
                inner, text=label, command=cmd, icon=icon,
                bg_normal=bgn, bg_hover=bgh, bg_active=bga,
                fg=fg,
                border_color=COLORS["surface1"],
                border_hover=border_h,
                font_size=9, bold=True,
                width=220, height=34,
                radius=7,
            )
            b.configure(bg=COLORS["surface0"])
            b.pack(pady=(0, 6), anchor="w")

    # ── Setup card ────────────────────────────────────────────────────────────

    def _build_setup_card(self, parent):
        card = self._card(parent, pady=(0, 10))
        self._card_header(card, "좌표 설정", COLORS["mauve"], "키보드로 좌표 지정")

        inner = tk.Frame(card, bg=COLORS["surface0"])
        inner.pack(fill="x", padx=12, pady=(4, 12))

        setup_items = [
            ("좌석 영역 선택",      self.get_axis,        "Z키: 좌상단  /  X키: 우하단"),
            ("좌석 등급(색상) 선택", self.get_color,       "Z키: 색상 추가  /  C키: 완료"),
            ("영역 선택 좌표",      self.get_time,        "Z키: 좌표 추가  /  C키: 완료"),
            ("선택 완료 좌표",      self.select_axis,     "Z키: 결제 버튼 위치"),
        ]

        self.setup_status_labels = {}

        for text, command, hint in setup_items:
            row = tk.Frame(inner, bg=COLORS["surface0"])
            row.pack(fill="x", pady=(0, 6))

            # Status dot (unset = red, set = green)
            dot = tk.Canvas(row, width=8, height=8,
                            bg=COLORS["surface0"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 6), pady=6)
            dot_id = dot.create_oval(1, 1, 7, 7, fill=COLORS["red"], outline="")

            col = tk.Frame(row, bg=COLORS["surface0"])
            col.pack(side="left", fill="x", expand=True)

            btn = HoverButton(
                col, text=text,
                command=lambda c=command: self.run_in_thread(c),
                bg_normal=COLORS["surface0"],
                bg_hover=COLORS["surface1"],
                bg_active=COLORS["surface2"],
                fg=COLORS["text"],
                border_color=COLORS["surface1"],
                border_hover=COLORS["mauve"],
                font_size=9, bold=False,
                width=210, height=28,
                radius=6,
            )
            btn.configure(bg=COLORS["surface0"])
            btn.pack(anchor="w")

            tk.Label(col, text=hint,
                     bg=COLORS["surface0"], fg=COLORS["sky"],
                     font=(FONT_FAMILY, 8)).pack(anchor="w")

            # Store dot reference so mark_setup can update it
            self.setup_status_labels[text] = (dot, dot_id)

    # ── Stop color card ──────────────────────────────────────────────────────

    def _build_stop_color_card(self, parent):
        card = self._card(parent, pady=(0, 10))
        self._card_header(card, "자동 정지 색상", COLORS["red"], "좌석 영역에서 감지 시 자동 중지")

        inner = tk.Frame(card, bg=COLORS["surface0"])
        inner.pack(fill="x", padx=12, pady=(4, 12))

        # 정지 색상 선택 버튼
        row = tk.Frame(inner, bg=COLORS["surface0"])
        row.pack(fill="x", pady=(0, 6))

        dot = tk.Canvas(row, width=8, height=8,
                        bg=COLORS["surface0"], highlightthickness=0)
        dot.pack(side="left", padx=(0, 6), pady=6)
        dot_id = dot.create_oval(1, 1, 7, 7, fill=COLORS["red"], outline="")

        col = tk.Frame(row, bg=COLORS["surface0"])
        col.pack(side="left", fill="x", expand=True)

        btn = HoverButton(
            col, text="정지 색상 선택",
            command=lambda: self.run_in_thread(self.get_stop_color),
            bg_normal=COLORS["surface0"],
            bg_hover=COLORS["surface1"],
            bg_active=COLORS["surface2"],
            fg=COLORS["text"],
            border_color=COLORS["surface1"],
            border_hover=COLORS["red"],
            font_size=9, bold=False,
            width=210, height=28,
            radius=6,
        )
        btn.configure(bg=COLORS["surface0"])
        btn.pack(anchor="w")

        tk.Label(col, text="Z키: 색상 지정",
                 bg=COLORS["surface0"], fg=COLORS["sky"],
                 font=(FONT_FAMILY, 8)).pack(anchor="w")

        self.setup_status_labels["정지 색상 선택"] = (dot, dot_id)

        # 정지 색상 미리보기
        preview_row = tk.Frame(inner, bg=COLORS["surface0"])
        preview_row.pack(fill="x", pady=(4, 0))
        tk.Label(preview_row, text="정지 색상",
                 bg=COLORS["surface0"], fg=COLORS["subtext0"],
                 font=(FONT_FAMILY, 8)).pack(side="left")
        self._stop_color_canvas = tk.Canvas(preview_row, width=30, height=18,
                                            bg=COLORS["surface1"],
                                            highlightthickness=1,
                                            highlightbackground=COLORS["surface1"])
        self._stop_color_canvas.pack(side="right", padx=(0, 4))
        self._stop_color_hex_var = tk.StringVar(value="미설정")
        tk.Label(preview_row, textvariable=self._stop_color_hex_var,
                 bg=COLORS["surface0"], fg=COLORS["text"],
                 font=("Consolas", 8)).pack(side="right", padx=(0, 4))

    # ── Color card ────────────────────────────────────────────────────────────

    def _build_color_card(self, parent):
        card = self._card(parent)
        self._card_header(card, "등록된 좌석 색상", COLORS["peach"], "클릭하면 색상 미리보기")

        inner = tk.Frame(card, bg=COLORS["surface0"])
        inner.pack(fill="x", padx=12, pady=(4, 12))

        # 색상 개수 표시
        count_row = tk.Frame(inner, bg=COLORS["surface0"])
        count_row.pack(fill="x", pady=(0, 6))
        tk.Label(count_row, text="등록 색상",
                 bg=COLORS["surface0"], fg=COLORS["subtext0"],
                 font=(FONT_FAMILY, 8)).pack(side="left")
        self._color_count_var = tk.StringVar(value="0개")
        tk.Label(count_row, textvariable=self._color_count_var,
                 bg=COLORS["surface0"], fg=COLORS["peach"],
                 font=(FONT_FAMILY, 10, "bold")).pack(side="left", padx=(8, 0))

        # 선택 색상 미리보기
        self.color_canvas = tk.Canvas(count_row, width=30, height=18,
                                      bg=COLORS["surface1"],
                                      highlightthickness=1,
                                      highlightbackground=COLORS["surface1"])
        self.color_canvas.pack(side="right", padx=(0, 4))
        self.color_hex_var = tk.StringVar(value="")
        tk.Label(count_row, textvariable=self.color_hex_var,
                 bg=COLORS["surface0"], fg=COLORS["text"],
                 font=("Consolas", 8)).pack(side="right", padx=(0, 4))

        # 색상 스와치 리스트 (Canvas로 컬러 블록 표시)
        self._color_swatch_frame = tk.Frame(inner, bg=COLORS["mantle"],
                                             highlightthickness=1,
                                             highlightbackground=COLORS["surface1"])
        self._color_swatch_frame.pack(fill="x")
        self.color_listbox = None  # 호환용

    # =========================================================================
    # UI HELPER UTILITIES
    # =========================================================================

    def _card(self, parent, padx=0, pady=0, fill="x", expand=False):
        """Create a card-style frame with border and rounded feel."""
        outer = tk.Frame(parent,
                         bg=COLORS["surface1"],   # 1 px border colour
                         padx=1, pady=1)
        outer.pack(fill=fill, expand=expand,
                   padx=padx if padx else 0,
                   pady=pady if pady else 0)

        inner = tk.Frame(outer, bg=COLORS["surface0"])
        inner.pack(fill="both", expand=True)
        return inner

    def _card_header(self, card, title, accent_color, subtitle=""):
        """Render a consistent card header with accent underline."""
        hdr = tk.Frame(card, bg=COLORS["surface0"])
        hdr.pack(fill="x", padx=12, pady=(10, 0))

        # Accent dot
        dot = tk.Canvas(hdr, width=8, height=8,
                        bg=COLORS["surface0"], highlightthickness=0)
        dot.pack(side="left", padx=(0, 6), pady=3)
        dot.create_oval(1, 1, 7, 7, fill=accent_color, outline="")

        tk.Label(hdr, text=title,
                 bg=COLORS["surface0"], fg=COLORS["text"],
                 font=(FONT_FAMILY, 10, "bold")).pack(side="left")

        if subtitle:
            tk.Label(hdr, text=subtitle,
                     bg=COLORS["surface0"], fg=COLORS["surface2"],
                     font=(FONT_FAMILY, 8)).pack(side="left", padx=(8, 0))

        # Hairline divider
        div = tk.Frame(card, height=1, bg=COLORS["surface1"])
        div.pack(fill="x", padx=12, pady=(6, 0))

    # =========================================================================
    # STATUS & LOG
    # =========================================================================

    def log(self, message, level="info"):
        """
        Append a timestamped message to the log.
        level: "info" | "success" | "warn" | "error"
        """
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")

        start = self.log_text.index("end")
        self.log_text.insert("end", f"[{timestamp}] ", "ts")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def set_status(self, message, mode="idle"):
        """
        Update the status bar.
        mode: "idle" | "running" | "warning" | "error" | "success"
        """
        self.status_var.set(message)

        dot_colors = {
            "idle":    COLORS["green"],
            "running": COLORS["yellow"],
            "warning": COLORS["peach"],
            "error":   COLORS["red"],
            "success": COLORS["teal"],
        }
        color = dot_colors.get(mode, COLORS["green"])
        self._status_dot.itemconfigure(self._status_dot_id, fill=color)

        right_text = {
            "idle":    "준비 완료",
            "running": "실행 중",
            "warning": "주의",
            "error":   "오류 발생",
            "success": "완료",
        }
        self._status_right_var.set(right_text.get(mode, ""))

    def mark_setup(self, name, done=True):
        """Toggle the status dot next to a setup button."""
        if name in self.setup_status_labels:
            dot, dot_id = self.setup_status_labels[name]
            color = COLORS["green"] if done else COLORS["red"]
            dot.itemconfigure(dot_id, fill=color)

    # =========================================================================
    # CORE LOGIC (unchanged from original)
    # =========================================================================

    def run_in_thread(self, func):
        threading.Thread(target=func, daemon=True).start()

    def on_seat_cnt_change(self):
        self.need_seat_cnt = self.seat_cnt_var.get()
        self.log(f"좌석 수 변경: {self.need_seat_cnt}석")

    def create_buttons(self):
        pass  # build_ui에서 처리

    def _on_esc(self):
        """ESC 키로 매크로 취소"""
        if self.is_running:
            self.stop_infinite_loop()

    def _on_start_key(self):
        """A 키로 매크로 시작"""
        if not self.is_running and not self.waiting_input:
            self.start_first_floor()

    def start_floor_loop(self, floor_function):
        if not self.is_running:
            self.is_running = True
            self.set_status("매크로 실행 중...", "running")
            threading.Thread(target=floor_function, daemon=True).start()

    def start_first_floor(self):
        self.log("매크로 시작", "success")
        self.start_floor_loop(self.first_loop)

    def stop_infinite_loop(self):
        self.is_running = False
        self.set_status("대기 중", "idle")
        self.log("매크로 중지됨", "warn")

    def first_loop(self):
        self.run_macro(self.search_seat)

    def run_macro(self, search_function):
        # 영역 클릭 스레드: 일정 간격으로 영역을 순환하며 클릭
        def area_click_loop():
            area_index = 0
            while self.is_running:
                try:
                    if self.time_axis:
                        pos = self.time_axis[area_index % len(self.time_axis)]
                        self.log(f"영역 #{area_index % len(self.time_axis) + 1} 클릭: ({pos.x}, {pos.y})", "info")
                        self.double_click(pos.x, pos.y)
                        area_index += 1
                    time.sleep(1.1)
                except Exception as e:
                    self.is_running = False
                    self.log(f"영역 클릭 Error: {e}", "error")
                    self.set_status("오류 발생", "error")
                    return

        # 정지 색상 감지 스레드
        def stop_color_watch_loop():
            while self.is_running:
                try:
                    if self.check_stop_color():
                        self.is_running = False
                        self.set_status("정지 색상 감지 — 매크로 자동 중지", "error")
                        self.log("정지 색상이 감지되어 매크로가 자동 중지되었습니다", "error")
                        return
                    time.sleep(0.2)
                except Exception as e:
                    self.log(f"정지 색상 감지 Error: {e}", "error")
                    return

        # 좌석 스캔 스레드: 쉬지 않고 계속 스캔
        def seat_scan_loop():
            while self.is_running:
                try:
                    found = search_function()
                    if found:
                        return
                except Exception as e:
                    self.is_running = False
                    self.log(f"좌석 스캔 Error: {e}", "error")
                    self.set_status("오류 발생", "error")
                    return
            self.set_status("대기 중", "idle")
            self.log("매크로 루프 종료", "warn")

        # 세 스레드 동시 실행
        threading.Thread(target=area_click_loop, daemon=True).start()
        if self.seat_axis and self.stop_color:
            threading.Thread(target=stop_color_watch_loop, daemon=True).start()
        seat_scan_loop()  # 현재 스레드에서 스캔 실행

    def get_position(self, key="z", label="좌표"):
        self.set_status(f"'{key.upper()}' 키를 눌러 {label} 지정...", "warning")
        self.log(f"대기 중: '{key.upper()}' 키를 눌러 {label}을 지정하세요", "warn")
        while True:
            if keyboard.read_key() == key:
                pos = pyautogui.position()
                self.log(f"'{key.upper()}' 키 입력 감지 → ({pos.x}, {pos.y})", "success")
                time.sleep(0.2)
                return pos

    def get_axis(self):
        self.waiting_input = True
        self.set_status("좌석 영역 선택 모드", "warning")
        left_top     = self.get_position("z", "좌상단 좌표")
        right_bottom = self.get_position("x", "우하단 좌표")
        self.seat_axis = [left_top, right_bottom]
        self.log(f"좌석 영역 설정 완료: ({left_top.x},{left_top.y}) ~ ({right_bottom.x},{right_bottom.y})",
                 "success")
        self.set_status("대기 중", "idle")
        self.mark_setup("좌석 영역 선택")
        self.capture_region(left_top, right_bottom)
        self.waiting_input = False

    def capture_region(self, left_top, right_bottom):
        captured_image = ImageGrab.grab(bbox=(left_top[0], left_top[1],
                                              right_bottom[0], right_bottom[1]))
        captured_image = captured_image.resize((360, 360))
        tk_image = ImageTk.PhotoImage(captured_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
        self.canvas.image_names = tk_image  # prevent GC

    def update_listbox(self):
        # 기존 스와치 삭제
        for w in self._color_swatch_frame.winfo_children():
            w.destroy()

        for color in self.seat_class:
            hex_c = "#{:02X}{:02X}{:02X}".format(*color)
            row = tk.Frame(self._color_swatch_frame, bg=COLORS["mantle"])
            row.pack(fill="x", padx=6, pady=2)

            # 색상 블록
            swatch = tk.Canvas(row, width=28, height=16, highlightthickness=0, bg=COLORS["mantle"])
            swatch.pack(side="left", padx=(0, 8))
            swatch.create_rectangle(0, 0, 28, 16, fill=hex_c, outline=COLORS["surface1"])

            # RGB 텍스트
            lbl = tk.Label(row, text=f"{hex_c}  RGB({color[0]}, {color[1]}, {color[2]})",
                           bg=COLORS["mantle"], fg=COLORS["text"],
                           font=("Consolas", 9), cursor="hand2")
            lbl.pack(side="left")

            # 클릭 시 미리보기
            lbl.bind("<ButtonRelease-1>", lambda e, c=color: self.draw_color_rectangle(c))
            swatch.bind("<ButtonRelease-1>", lambda e, c=color: self.draw_color_rectangle(c))

        self._color_count_var.set(f"{len(self.seat_class)}개")

        # 첫 번째 색상 자동 미리보기
        if self.seat_class:
            self.draw_color_rectangle(list(self.seat_class)[0])

    def draw_color_rectangle(self, rgb_values):
        self.color_canvas.delete("all")
        hex_color = "#{:02X}{:02X}{:02X}".format(*rgb_values)
        self.color_canvas.create_rectangle(0, 0, 30, 18, fill=hex_color, outline="")
        self.color_hex_var.set(f"{hex_color}")

    def get_color(self):
        self.waiting_input = True
        self.set_status("색상 선택 모드: Z=추가, C=완료", "warning")
        self.log("색상 선택 모드 진입 — Z키: 색상 추가  /  C키: 완료", "warn")
        my_class_list   = []
        count           = 0
        while True:
            key = keyboard.read_key()
            if key == "z":
                screen = ImageGrab.grab()
                x, y = pyautogui.position()
                rgb  = screen.getpixel((x, y))
                my_class_list.append(rgb)
                count += 1
                self.log(f"색상 #{count} 추가: RGB({rgb[0]}, {rgb[1]}, {rgb[2]}) at ({x}, {y})",
                         "success")
                time.sleep(0.2)
            elif key == "c":
                self.seat_class = set(my_class_list)
                self.update_listbox()
                self.log(f"색상 선택 완료: {len(self.seat_class)}개 등록됨", "success")
                self.set_status("대기 중", "idle")
                self.mark_setup("좌석 등급(색상) 선택")
                self.waiting_input = False
                break

    def _update_area_list(self):
        """영역 좌표 리스트 UI 업데이트"""
        self.area_listbox.delete(0, tk.END)
        for idx, pos in enumerate(self.time_axis):
            self.area_listbox.insert(tk.END, f"  #{idx + 1}  ({pos.x}, {pos.y})")
        self._area_count_var.set(f"{len(self.time_axis)}개")

    def get_time(self):
        self.waiting_input = True
        self.time_axis = []
        self.set_status("영역 좌표 선택: Z키=추가, C키=완료", "warning")
        self.log("영역 좌표 선택 모드 — Z키: 좌표 추가 / C키: 완료", "warn")
        count = 0
        while True:
            key = keyboard.read_key()
            if key == "z":
                pos = pyautogui.position()
                self.time_axis.append(pos)
                count += 1
                self.log(f"영역 #{count} 추가: ({pos.x}, {pos.y})", "success")
                self._update_area_list()
                time.sleep(0.2)
            elif key == "c":
                self.log(f"영역 좌표 설정 완료: {len(self.time_axis)}개 등록됨", "success")
                self.set_status("대기 중", "idle")
                self.mark_setup("영역 선택 좌표")
                self.waiting_input = False
                break

    def select_axis(self):
        self.waiting_input = True
        self.pay_axis = self.get_position("z", "선택 완료 좌표")
        self.log(f"선택 완료 좌표 설정 완료: ({self.pay_axis.x}, {self.pay_axis.y})", "success")
        self.set_status("대기 중", "idle")
        self.mark_setup("선택 완료 좌표")
        self.waiting_input = False

    def get_stop_color(self):
        self.waiting_input = True
        self.set_status("정지 색상 선택: Z키로 색상 지정", "warning")
        self.log("정지 색상 선택 모드 — Z키: 마우스 위치의 색상 지정", "warn")
        while True:
            key = keyboard.read_key()
            if key == "z":
                screen = ImageGrab.grab()
                x, y = pyautogui.position()
                rgb = screen.getpixel((x, y))
                self.stop_color = rgb
                hex_c = "#{:02X}{:02X}{:02X}".format(*rgb)
                self._stop_color_canvas.delete("all")
                self._stop_color_canvas.create_rectangle(0, 0, 30, 18, fill=hex_c, outline="")
                self._stop_color_hex_var.set(f"{hex_c}  RGB({rgb[0]}, {rgb[1]}, {rgb[2]})")
                self.log(f"정지 색상 설정: {hex_c} RGB({rgb[0]}, {rgb[1]}, {rgb[2]}) at ({x}, {y})",
                         "success")
                self.set_status("대기 중", "idle")
                self.mark_setup("정지 색상 선택")
                self.waiting_input = False
                time.sleep(0.2)
                break

    def check_stop_color(self):
        """좌석 영역에서 정지 색상이 감지되면 True 반환"""
        if not self.seat_axis or not self.stop_color:
            return False
        delta_error = 10
        screen = ImageGrab.grab()
        lt, rb = self.seat_axis
        for y in range(lt[1], rb[1], 7):
            for x in range(lt[0], rb[0], 7):
                rgb = screen.getpixel((x, y))
                if all(abs(rgb[k] - self.stop_color[k]) <= delta_error for k in range(3)):
                    return True
        return False

    def click(self, x, y):
        pyautogui.click(x, y)

    def double_click(self, x, y):
        pyautogui.doubleClick(x, y)

    def press_key(self, key):
        pyautogui.press(key)

    def search_seat(self):
        delta_error = 10
        screen = ImageGrab.grab()
        for j in range(self.seat_axis[0][1], self.seat_axis[1][1], 7):
            if not self.is_running:
                return False
            for i in range(self.seat_axis[0][0], self.seat_axis[1][0], 7):
                if not self.is_running:
                    return False
                rgb = screen.getpixel((i, j))
                for r, g, b in self.seat_class:
                    if all(abs(rgb[k] - color) <= delta_error
                           for k, color in enumerate((r, g, b))):
                        if self.need_seat_cnt == 2:
                            rgb2 = screen.getpixel((i + 10, j))
                            if all(abs(rgb2[k] - color) <= delta_error
                                   for k, color in enumerate((r, g, b))):
                                self.is_running = False
                                self.click(i, j)
                                time.sleep(0.08)
                                self.click(i + 10, j)
                                time.sleep(0.08)
                                self.click(*self.pay_axis)
                                self.set_status("좌석 발견! 클릭 완료", "success")
                                self.log(f"좌석 발견: ({i}, {j}) — 자동 클릭 완료", "success")
                                return True
                        elif self.need_seat_cnt == 1:
                            self.is_running = False
                            self.click(i, j)
                            time.sleep(0.08)
                            self.click(*self.pay_axis)
                            self.set_status("좌석 발견! 클릭 완료", "success")
                            self.log(f"좌석 발견: ({i}, {j}) — 자동 클릭 완료", "success")
                            return True
        return False


# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Ticket Macro")

    # 화면 크기에 맞게 창 크기 조정
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w = min(680, screen_w - 40)
    win_h = min(890, screen_h - 80)
    root.geometry(f"{win_w}x{win_h}")
    root.resizable(False, True)
    root.minsize(win_w, 400)

    app = MacroLoopApp(root)
    root.mainloop()
