# -*- coding: utf-8 -*-
"""
간단 프롬프터 (Teleprompter) v5
- 다크 모드 전용
- 대사 / 행동지시 두 패널을 드래그로 비율 조절 가능(Panedwindow)
- 두 패널은 항상 같은 줄 수를 유지하도록 자동으로 맞춰서(빈 줄 패딩) 완전히 동기화된 스크롤 보장
- 둥근 버튼 UI, 섹션 라벨은 굵게/밝게 표시해 구분 쉬움
- 기본 폰트: 프리텐다드 Bold(대사) / 프리텐다드 Regular(행동지시), fonts 폴더로 설치 없이 자동 로드
- 앱/창 아이콘 적용
"""

import os
import sys
import ctypes
import tkinter as tk
from tkinter import ttk, font as tkfont, simpledialog, messagebox

MAIN_FONT_KEYWORDS = ["Pretendard", "Paperlogy", "맑은 고딕", "Malgun Gothic"]
UI_FONT = "맑은 고딕"
AUTOSCROLL_TICK_MS = 40

COLORS = dict(
    bg="#121317",
    panel="#1b1c22",
    panel2="#24252d",
    text_bg="#0f1013",
    text_fg="#f1f2f6",
    instr_fg="#4fc3f7",
    accent="#5b8def",
    hover="#33445c",
    label_fg="#9aa0ae",
    title_fg="#e7e9f0",
)

TEXT_COLORS = {"연두": "#b6ff3c", "노랑": "#ffe14d", "흰색": "#ffffff"}
HILITE_COLORS = {"노랑": "#fff59d", "초록": "#c8e6c9", "분홍": "#f8bbd0", "하늘": "#bbdefb"}

DEFAULT_SCRIPT = "안녕하세요\n뭐뭐입니다\n날씨 참 덥죠?\n\n왼쪽엔 대사, 오른쪽엔 같은 줄에 행동지시를 적어보세요."
DEFAULT_INSTR = "꾸벅 화면에 인사하기\n\n손 부채질하기\n\n"


# ---------------------------------------------------------------- 리소스 경로
def _bundled_resource_path(*parts):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def _external_resource_dir(*parts):
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


ICON_PNG_PATH = _bundled_resource_path("assets", "icon.png")
FONTS_DIR = _external_resource_dir("fonts")


def _load_bundled_fonts():
    if sys.platform != "win32" or not os.path.isdir(FONTS_DIR):
        return
    FR_PRIVATE = 0x10
    try:
        gdi32 = ctypes.windll.gdi32
        for fname in os.listdir(FONTS_DIR):
            if fname.lower().endswith((".ttf", ".otf", ".ttc")):
                path = os.path.join(FONTS_DIR, fname)
                gdi32.AddFontResourceExW(ctypes.c_wchar_p(path), FR_PRIVATE, 0)
    except Exception:
        pass


def _find_font_family(families, must_include):
    must_include = must_include.lower()
    for f in families:
        if must_include in f.lower():
            return f
    return None


def pick_default_family():
    families = tkfont.families()
    for keyword in MAIN_FONT_KEYWORDS:
        match = _find_font_family(families, keyword)
        if match:
            return match
    return families[0] if families else "TkDefaultFont"


# ---------------------------------------------------------------- 둥근 버튼(Canvas 기반)
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, width=90, height=32, radius=12,
                 bg=None, fg="#ffffff", font=None, parent_bg=None):
        parent_bg = parent_bg if parent_bg else COLORS["panel"]
        super().__init__(parent, width=width, height=height, bg=parent_bg,
                          highlightthickness=0, bd=0, cursor="hand2")
        self.command = command
        self.text_str = text
        self.radius = radius
        self.fg_color = fg
        self.font = font or (UI_FONT, 10)
        self.base_bg = bg or COLORS["panel2"]
        self.current_bg = self.base_bg
        self._render()
        self.bind("<ButtonRelease-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._set_bg(COLORS["hover"]))
        self.bind("<Leave>", lambda e: self._set_bg(self.base_bg))

    def _rounded_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _render(self):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        self._rounded_rect(1, 1, w - 1, h - 1, self.radius, fill=self.current_bg, outline="")
        self.create_text(w // 2, h // 2, text=self.text_str, fill=self.fg_color, font=self.font)

    def _set_bg(self, color):
        self.current_bg = color
        self._render()

    def _on_click(self, _evt):
        if self.command:
            self.command()

    def set_active(self, active):
        self.base_bg = COLORS["accent"] if active else COLORS["panel2"]
        self.current_bg = self.base_bg
        self._render()

    def set_text(self, text):
        self.text_str = text
        self._render()


def section_label(parent, text):
    return tk.Label(parent, text=text, bg=COLORS["panel"], fg=COLORS["label_fg"],
                     font=(UI_FONT, 10, "bold"))


# ---------------------------------------------------------------- 탭(대사+행동지시) 데이터
class TabData:
    def __init__(self, notebook, title):
        self.title = title
        self.frame = tk.Frame(notebook, bg=COLORS["bg"])
        self._sync_guard = False

        paned = ttk.Panedwindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # ---- 왼쪽: 대사 ----
        left = tk.Frame(paned, bg=COLORS["bg"])
        section_label(left, "대사 (원고)").pack(anchor="w", padx=14, pady=(8, 4))
        left_body = tk.Frame(left, bg=COLORS["bg"])
        left_body.pack(fill="both", expand=True)
        left_body.rowconfigure(0, weight=1)
        left_body.columnconfigure(0, weight=1)

        self.text = tk.Text(left_body, wrap="none", undo=True, spacing1=6, spacing3=6,
                             padx=18, pady=10, borderwidth=0, highlightthickness=0,
                             bg=COLORS["text_bg"], fg=COLORS["text_fg"],
                             insertbackground=COLORS["text_fg"], selectbackground=COLORS["hover"])
        self.text.grid(row=0, column=0, sticky="nsew")
        vsb1 = ttk.Scrollbar(left_body, orient="vertical")
        vsb1.grid(row=0, column=1, sticky="ns")
        hsb1 = ttk.Scrollbar(left_body, orient="horizontal", command=self.text.xview)
        hsb1.grid(row=1, column=0, sticky="ew")
        self.text.configure(xscrollcommand=hsb1.set, yscrollcommand=vsb1.set)

        paned.add(left, weight=7)

        # ---- 오른쪽: 행동지시 ----
        right = tk.Frame(paned, bg=COLORS["bg"])
        section_label(right, "행동지시").pack(anchor="w", padx=12, pady=(8, 4))
        right_body = tk.Frame(right, bg=COLORS["bg"])
        right_body.pack(fill="both", expand=True)
        right_body.rowconfigure(0, weight=1)
        right_body.columnconfigure(0, weight=1)

        self.instr_text = tk.Text(right_body, wrap="none", undo=True, spacing1=6, spacing3=6,
                                   padx=12, pady=10, borderwidth=0, highlightthickness=0,
                                   bg=COLORS["text_bg"], fg=COLORS["instr_fg"],
                                   insertbackground=COLORS["instr_fg"], selectbackground=COLORS["hover"])
        self.instr_text.grid(row=0, column=0, sticky="nsew")
        vsb2 = ttk.Scrollbar(right_body, orient="vertical")
        vsb2.grid(row=0, column=1, sticky="ns")
        hsb2 = ttk.Scrollbar(right_body, orient="horizontal", command=self.instr_text.xview)
        hsb2.grid(row=1, column=0, sticky="ew")
        self.instr_text.configure(xscrollcommand=hsb2.set, yscrollcommand=vsb2.set)

        paned.add(right, weight=3)

        # 두 스크롤바 모두 "양쪽을 동시에" 움직이는 같은 핸들러를 사용
        def on_vscroll(*args):
            self.text.yview(*args)
            self.instr_text.yview(*args)

        vsb1.configure(command=on_vscroll)
        vsb2.configure(command=on_vscroll)
        self.text.configure(yscrollcommand=lambda a, b: vsb1.set(a, b))
        self.instr_text.configure(yscrollcommand=lambda a, b: vsb2.set(a, b))

    def line_count(self, widget):
        return int(widget.index("end-1c").split(".")[0])

    def sync_line_counts(self):
        """대사/행동지시 줄 수를 항상 똑같이 맞춰서, 두 패널이 물리적으로 동일한 높이만큼
        스크롤될 수 있도록(=완전히 같이 움직이도록) 짧은 쪽 끝에 빈 줄을 채워 넣는다."""
        n1 = self.line_count(self.text)
        n2 = self.line_count(self.instr_text)
        if n1 > n2:
            self.instr_text.insert("end", "\n" * (n1 - n2))
        elif n2 > n1:
            self.text.insert("end", "\n" * (n2 - n1))

    def scroll_both(self, amount, kind):
        self.text.yview_scroll(amount, kind)
        self.instr_text.yview_scroll(amount, kind)


# ---------------------------------------------------------------- 메인 앱
class PrompterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("간단 프롬프터")
        self.root.geometry("1200x720")
        self.root.configure(bg=COLORS["bg"])
        self._apply_icon()
        self._setup_ttk_style()

        self.autoscroll_on = False
        self._scroll_accum = 0.0
        self.tabs = []
        self.tab_counter = 0
        self.row2_visible = True

        self._build_toolbar()
        self._build_notebook()
        self.add_tab()
        self._apply_font()

        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<Up>", lambda e: self._manual_scroll(-1))
        self.root.bind("<Down>", lambda e: self._manual_scroll(1))

    def _apply_icon(self):
        try:
            icon_img = tk.PhotoImage(file=ICON_PNG_PATH)
            self.root.iconphoto(True, icon_img)
            self._icon_img_ref = icon_img
        except Exception:
            pass

    def _setup_ttk_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TPanedwindow", background=COLORS["bg"])
        style.configure("TCombobox", fieldbackground=COLORS["panel2"], background=COLORS["panel2"],
                         foreground=COLORS["text_fg"], arrowcolor=COLORS["text_fg"])
        style.map("TCombobox", fieldbackground=[("readonly", COLORS["panel2"])])
        style.configure("TSpinbox", fieldbackground=COLORS["panel2"], background=COLORS["panel2"],
                         foreground=COLORS["text_fg"], arrowcolor=COLORS["text_fg"])
        style.configure("Vertical.TScrollbar", background=COLORS["panel2"], troughcolor=COLORS["bg"],
                         arrowcolor=COLORS["text_fg"])
        style.configure("Horizontal.TScrollbar", background=COLORS["panel2"], troughcolor=COLORS["bg"],
                         arrowcolor=COLORS["text_fg"])
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["panel"], foreground=COLORS["label_fg"],
                         padding=(16, 9), font=(UI_FONT, 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", COLORS["panel2"])],
                  foreground=[("selected", COLORS["title_fg"])])

    # ---------------------------------------------------------- 툴바
    def _build_toolbar(self):
        self.shell = tk.Frame(self.root, bg=COLORS["panel"])
        self.shell.pack(side="top", fill="x")

        row1 = tk.Frame(self.shell, bg=COLORS["panel"])
        row1.pack(side="top", fill="x", padx=10, pady=(10, 6))

        section_label(row1, "폰트").pack(side="left")
        families = sorted(tkfont.families())
        default_family = pick_default_family()
        self.font_family = tk.StringVar(value=default_family)
        fam_box = ttk.Combobox(row1, textvariable=self.font_family, values=families,
                                width=16, state="readonly")
        fam_box.pack(side="left", padx=(6, 16))
        fam_box.bind("<<ComboboxSelected>>", lambda e: self._apply_font())

        section_label(row1, "크기").pack(side="left")
        self.font_size = tk.IntVar(value=32)
        size_spin = ttk.Spinbox(row1, from_=8, to=200, width=5, textvariable=self.font_size,
                                 command=self._apply_font)
        size_spin.pack(side="left", padx=(6, 16))
        size_spin.bind("<Return>", lambda e: self._apply_font())

        self.topmost_btn = RoundedButton(row1, text="항상 위", width=84, height=32,
                                          command=self._toggle_topmost, parent_bg=COLORS["panel"])
        self.topmost_btn.pack(side="left", padx=(0, 8))
        self.topmost_state = False

        RoundedButton(row1, text="전체화면 (F11)", width=126, height=32,
                      command=self._toggle_fullscreen, parent_bg=COLORS["panel"]).pack(side="left")

        self.toggle_btn = RoundedButton(row1, text="▲ 접기", width=90, height=32,
                                         command=self._toggle_row2, parent_bg=COLORS["panel"])
        self.toggle_btn.pack(side="right")

        self.row2 = tk.Frame(self.shell, bg=COLORS["panel"])
        self.row2.pack(side="top", fill="x", padx=10, pady=(0, 10))

        section_label(self.row2, "하이라이트").pack(side="left")
        for color in HILITE_COLORS.values():
            RoundedButton(self.row2, text="", width=30, height=30, radius=15, bg=color,
                          parent_bg=COLORS["panel"],
                          command=lambda c=color: self._apply_highlight(bg=c)).pack(side="left", padx=2)

        section_label(self.row2, "글자색").pack(side="left", padx=(16, 0))
        for color in TEXT_COLORS.values():
            RoundedButton(self.row2, text="", width=30, height=30, radius=15, bg=color,
                          parent_bg=COLORS["panel"],
                          command=lambda c=color: self._apply_highlight(fg=c)).pack(side="left", padx=2)

        RoundedButton(self.row2, text="서식지우기", width=96, height=32,
                      command=self._clear_format, parent_bg=COLORS["panel"]).pack(side="left", padx=(16, 20))

        section_label(self.row2, "자동스크롤").pack(side="left")
        self.scroll_btn = RoundedButton(self.row2, text="▶ 시작", width=84, height=32,
                                         command=self._toggle_autoscroll, parent_bg=COLORS["panel"])
        self.scroll_btn.pack(side="left", padx=(6, 12))

        section_label(self.row2, "속도").pack(side="left")
        self.scroll_speed = tk.DoubleVar(value=1.2)
        speed_scale = tk.Scale(self.row2, from_=0.2, to=6.0, resolution=0.1, orient="horizontal",
                                length=110, showvalue=False, variable=self.scroll_speed,
                                bd=0, highlightthickness=0, bg=COLORS["panel"],
                                troughcolor=COLORS["panel2"], fg=COLORS["text_fg"],
                                activebackground=COLORS["accent"])
        speed_scale.pack(side="left", padx=(6, 20))

        section_label(self.row2, "휠 간격").pack(side="left")
        self.wheel_step = 1
        self.wheel_buttons = []
        wheel_group = tk.Frame(self.row2, bg=COLORS["panel"])
        wheel_group.pack(side="left", padx=(6, 0))
        for val, label in [(1, "1줄"), (2, "2줄"), (3, "3줄")]:
            btn = RoundedButton(wheel_group, text=label, width=54, height=32,
                                 parent_bg=COLORS["panel"],
                                 command=lambda v=val: self._set_wheel_step(v))
            btn.pack(side="left", padx=2)
            self.wheel_buttons.append((val, btn))
        self._set_wheel_step(1)

    def _set_wheel_step(self, val):
        self.wheel_step = val
        for v, btn in self.wheel_buttons:
            btn.set_active(v == val)

    def _toggle_topmost(self):
        self.topmost_state = not self.topmost_state
        self.root.attributes("-topmost", self.topmost_state)
        self.topmost_btn.set_active(self.topmost_state)

    def _toggle_row2(self):
        if self.row2_visible:
            self.row2.pack_forget()
            self.toggle_btn.set_text("▼ 펼치기")
        else:
            self.row2.pack(side="top", fill="x", padx=10, pady=(0, 10))
            self.toggle_btn.set_text("▲ 접기")
        self.row2_visible = not self.row2_visible

    # ---------------------------------------------------------- 노트북(탭)
    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 10))

        self.plus_frame = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.plus_frame, text=" + ")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.notebook.bind("<Double-Button-1>", self._on_tab_double_click)
        self.notebook.bind("<Button-3>", self._on_tab_right_click)

    def add_tab(self):
        self.tab_counter += 1
        title = f"원고 {self.tab_counter}"
        data = TabData(self.notebook, title)

        insert_idx = self.notebook.index(self.plus_frame)
        self.notebook.insert(insert_idx, data.frame, text=title)
        self.notebook.select(data.frame)
        self.tabs.append(data)

        data.text.insert("1.0", DEFAULT_SCRIPT)
        data.instr_text.insert("1.0", DEFAULT_INSTR)
        data.sync_line_counts()

        for widget in (data.text, data.instr_text):
            widget.bind("<MouseWheel>", lambda e, d=data: self._on_mousewheel(e, d))
            widget.bind("<Button-4>", lambda e, d=data: self._on_mousewheel_linux(e, d))
            widget.bind("<Button-5>", lambda e, d=data: self._on_mousewheel_linux(e, d))
            widget.bind("<KeyRelease>", lambda e, d=data: d.sync_line_counts())

        self._apply_font()

    def _on_tab_changed(self, _evt=None):
        sel = self.notebook.select()
        if sel == str(self.plus_frame):
            self.add_tab()

    def _tab_index_at(self, event):
        try:
            return self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return None

    def _on_tab_double_click(self, event):
        idx = self._tab_index_at(event)
        if idx is None:
            return
        tab_id = self.notebook.tabs()[idx]
        if tab_id == str(self.plus_frame):
            return
        data = self._find_tab_by_id(tab_id)
        if not data:
            return
        new_name = simpledialog.askstring("탭 이름변경", "새 탭 이름:", initialvalue=data.title)
        if new_name:
            data.title = new_name
            self.notebook.tab(data.frame, text=new_name)

    def _on_tab_right_click(self, event):
        idx = self._tab_index_at(event)
        if idx is None:
            return
        tab_id = self.notebook.tabs()[idx]
        if tab_id == str(self.plus_frame):
            return
        data = self._find_tab_by_id(tab_id)
        if not data:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="원고 삭제", command=lambda: self._delete_tab(data))
        menu.tk_popup(event.x_root, event.y_root)

    def _find_tab_by_id(self, tab_id):
        for d in self.tabs:
            if str(d.frame) == tab_id:
                return d
        return None

    def _delete_tab(self, data):
        if len(self.tabs) <= 1:
            messagebox.showinfo("안내", "마지막 원고는 삭제할 수 없습니다.")
            return
        if messagebox.askyesno("원고 삭제", f"'{data.title}' 원고를 삭제할까요?"):
            self.notebook.forget(data.frame)
            self.tabs.remove(data)

    def _current_tab(self):
        if not self.tabs:
            return None
        sel = self.notebook.select()
        return self._find_tab_by_id(sel)

    # ---------------------------------------------------------- 폰트/창
    def _apply_font(self):
        family = self.font_family.get()
        size = self.font_size.get()
        main_spacing = 6

        main_metrics = tkfont.Font(family=family, size=size, weight="bold").metrics("linespace")
        main_total = main_metrics + main_spacing * 2

        instr_size = max(8, int(size * 0.72))
        instr_metrics = tkfont.Font(family=family, size=instr_size,
                                     weight="normal", slant="italic").metrics("linespace")
        extra = max(0, main_total - instr_metrics)
        instr_spacing1 = extra // 2
        instr_spacing3 = extra - instr_spacing1

        for d in self.tabs:
            d.text.configure(font=(family, size, "bold"), spacing1=main_spacing, spacing3=main_spacing)
            d.instr_text.configure(font=(family, instr_size, "normal italic"),
                                    spacing1=instr_spacing1, spacing3=instr_spacing3)

    def _toggle_fullscreen(self, _evt=None):
        cur = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not cur)

    # ---------------------------------------------------------- 하이라이트
    def _target_text(self, data):
        if data.text.tag_ranges("sel"):
            return data.text
        if data.instr_text.tag_ranges("sel"):
            return data.instr_text
        return None

    def _apply_highlight(self, bg=None, fg=None):
        data = self._current_tab()
        if not data:
            return
        target = self._target_text(data)
        if not target:
            return
        try:
            tag_name = f"fmt_{bg}_{fg}"
            opts = {}
            if bg:
                opts["background"] = bg
            if fg:
                opts["foreground"] = fg
            target.tag_configure(tag_name, **opts)
            target.tag_add(tag_name, "sel.first", "sel.last")
            target.tag_raise(tag_name)
        except tk.TclError:
            pass

    def _clear_format(self):
        data = self._current_tab()
        if not data:
            return
        target = self._target_text(data)
        if not target:
            return
        try:
            for tag in target.tag_names():
                if tag.startswith("fmt_"):
                    target.tag_remove(tag, "sel.first", "sel.last")
        except tk.TclError:
            pass

    # ---------------------------------------------------------- 스크롤
    def _on_mousewheel(self, event, data):
        direction = -1 if event.delta > 0 else 1
        data.scroll_both(direction * self.wheel_step, "units")
        return "break"

    def _on_mousewheel_linux(self, event, data):
        direction = -1 if event.num == 4 else 1
        data.scroll_both(direction * self.wheel_step, "units")
        return "break"

    def _manual_scroll(self, direction):
        data = self._current_tab()
        if not data:
            return
        data.scroll_both(direction * self.wheel_step, "units")

    def _toggle_autoscroll(self):
        self.autoscroll_on = not self.autoscroll_on
        self.scroll_btn.set_text("⏸ 정지" if self.autoscroll_on else "▶ 시작")
        self.scroll_btn.set_active(self.autoscroll_on)
        if self.autoscroll_on:
            self._scroll_accum = 0.0
            self._autoscroll_tick()

    def _autoscroll_tick(self):
        if not self.autoscroll_on:
            return
        data = self._current_tab()
        if data:
            self._scroll_accum += self.scroll_speed.get()
            move = int(self._scroll_accum)
            if move >= 1:
                data.scroll_both(move, "pixels")
                self._scroll_accum -= move
            _, last = data.text.yview()
            if last >= 0.999:
                self.autoscroll_on = False
                self.scroll_btn.set_text("▶ 시작")
                self.scroll_btn.set_active(False)
                return
        self.root.after(AUTOSCROLL_TICK_MS, self._autoscroll_tick)


def main():
    _load_bundled_fonts()
    root = tk.Tk()
    app = PrompterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
