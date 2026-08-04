# -*- coding: utf-8 -*-
"""
간단 프롬프터 (Teleprompter) v3
- 라이트/다크 모드
- 행동지시: 오른쪽 분할 패널에 별도로 작성, 대사와 같은 줄(행) 높이로 맞춰 함께 스크롤
- 자동스크롤: 픽셀 단위 부드러운 스크롤 + 속도 슬라이더 (양쪽 패널 동시 이동)
- 마우스휠 간격: 1줄 / 2줄 / 3줄 중 선택
- 탭: "+" 로 새 탭 생성 / 더블클릭으로 이름변경 / 우클릭으로 삭제
- 상단 툴바 2줄(항상 보이는 1줄 + 접고 펼 수 있는 1줄)
"""

import tkinter as tk
from tkinter import ttk, font as tkfont, simpledialog, messagebox

DEFAULT_FONT_CANDIDATES = ["Paperlogy", "PaperlogyGothic", "Paperlogy Gothic", "맑은 고딕", "Malgun Gothic"]
AUTOSCROLL_TICK_MS = 40  # 고정 틱 간격(ms). 속도는 틱당 이동 픽셀 수로 조절.

THEMES = {
    "light": dict(
        bg="#f5f6fa", fg="#20222a", toolbar_bg="#ffffff",
        text_bg="#ffffff", text_fg="#20222a", instr_fg="#b5651d",
        select_bg="#d7e8ff", muted="#8a8f9c", accent="#5b8def",
    ),
    "dark": dict(
        bg="#16171c", fg="#e8e9ee", toolbar_bg="#1f2026",
        text_bg="#121218", text_fg="#f0f0f5", instr_fg="#4fc3f7",
        select_bg="#33445c", muted="#9096a5", accent="#5b8def",
    ),
}

TEXT_COLOR_SETS = {
    "light": {"빨강": "#e53935", "파랑": "#1e88e5", "검정": "#000000"},
    "dark":  {"연두": "#b6ff3c", "노랑": "#ffe14d", "흰색": "#ffffff"},
}

HILITE_COLORS = {
    "노랑": "#fff59d",
    "초록": "#c8e6c9",
    "분홍": "#f8bbd0",
    "하늘": "#bbdefb",
}

DEFAULT_SCRIPT = "안녕하세요\n뭐뭐입니다\n날씨 참 덥죠?\n\n왼쪽엔 대사, 오른쪽엔 같은 줄에 행동지시를 적어보세요."
DEFAULT_INSTR = "꾸벅 화면에 인사하기\n\n손 부채질하기\n\n"


class TabData:
    """스크립트(대사) + 행동지시 두 패널을 같은 줄 높이로 동기화."""

    def __init__(self, notebook, title):
        self.title = title
        self.frame = ttk.Frame(notebook)
        self._sync_guard = False

        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True)
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=7)
        container.columnconfigure(2, weight=3)

        self.script_label = ttk.Label(container, text="대사 (원고)", font=("", 9, "bold"))
        self.script_label.grid(row=0, column=0, sticky="w", padx=(16, 0), pady=(8, 4))
        self.instr_label = ttk.Label(container, text="행동지시", font=("", 9, "bold"))
        self.instr_label.grid(row=0, column=2, sticky="w", padx=(10, 0), pady=(8, 4))

        self.text = tk.Text(container, wrap="none", undo=True, spacing1=6, spacing3=6,
                             padx=18, pady=10, borderwidth=0, highlightthickness=0)
        self.text.grid(row=1, column=0, sticky="nsew")

        sep = ttk.Separator(container, orient="vertical")
        sep.grid(row=1, column=1, rowspan=2, sticky="ns", padx=4)

        self.instr_text = tk.Text(container, wrap="none", undo=True, spacing1=6, spacing3=6,
                                   padx=12, pady=10, borderwidth=0, highlightthickness=0)
        self.instr_text.grid(row=1, column=2, sticky="nsew")

        self.vsb = ttk.Scrollbar(container, orient="vertical", command=self._on_scrollbar)
        self.vsb.grid(row=1, column=3, sticky="ns")

        script_hsb = ttk.Scrollbar(container, orient="horizontal", command=self.text.xview)
        script_hsb.grid(row=2, column=0, sticky="ew")
        instr_hsb = ttk.Scrollbar(container, orient="horizontal", command=self.instr_text.xview)
        instr_hsb.grid(row=2, column=2, sticky="ew")

        self.text.configure(xscrollcommand=script_hsb.set, yscrollcommand=self._make_yscroll_cb("text"))
        self.instr_text.configure(xscrollcommand=instr_hsb.set, yscrollcommand=self._make_yscroll_cb("instr"))

    def _on_scrollbar(self, *args):
        self.text.yview(*args)
        self.instr_text.yview(*args)

    def _make_yscroll_cb(self, which):
        def cb(first, last):
            self.vsb.set(first, last)
            if self._sync_guard:
                return
            self._sync_guard = True
            try:
                other = self.instr_text if which == "text" else self.text
                other.yview_moveto(float(first))
            finally:
                self._sync_guard = False
        return cb

    def scroll_both(self, amount, kind):
        self.text.yview_scroll(amount, kind)
        self.instr_text.yview_scroll(amount, kind)


class PrompterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("간단 프롬프터")
        self.root.geometry("1200x720")

        self.theme_name = tk.StringVar(value="light")
        self.autoscroll_on = False
        self._scroll_accum = 0.0
        self.tabs = []
        self.tab_counter = 0
        self.row2_visible = tk.BooleanVar(value=True)

        self._build_toolbar()
        self._build_notebook()
        self.add_tab()
        self._apply_theme()

        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<Up>", lambda e: self._manual_scroll(-1))
        self.root.bind("<Down>", lambda e: self._manual_scroll(1))

    # ---------------------------------------------------------- 툴바
    def _build_toolbar(self):
        self.shell = ttk.Frame(self.root, padding=(10, 8))
        self.shell.pack(side="top", fill="x")

        row1 = ttk.Frame(self.shell)
        row1.pack(side="top", fill="x")

        ttk.Label(row1, text="테마:").pack(side="left")
        ttk.Button(row1, text="라이트", width=6,
                   command=lambda: self._set_theme("light")).pack(side="left", padx=1)
        ttk.Button(row1, text="다크", width=6,
                   command=lambda: self._set_theme("dark")).pack(side="left", padx=(1, 12))

        ttk.Label(row1, text="폰트:").pack(side="left")
        families = sorted(tkfont.families())
        default_family = next((f for f in DEFAULT_FONT_CANDIDATES if f in families), families[0])
        self.font_family = tk.StringVar(value=default_family)
        fam_box = ttk.Combobox(row1, textvariable=self.font_family, values=families,
                                width=16, state="readonly")
        fam_box.pack(side="left", padx=(2, 12))
        fam_box.bind("<<ComboboxSelected>>", lambda e: self._apply_font())

        ttk.Label(row1, text="크기:").pack(side="left")
        self.font_size = tk.IntVar(value=32)
        size_spin = ttk.Spinbox(row1, from_=8, to=200, width=5, textvariable=self.font_size,
                                 command=self._apply_font)
        size_spin.pack(side="left", padx=(2, 12))
        size_spin.bind("<Return>", lambda e: self._apply_font())

        self.topmost = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="항상 위", variable=self.topmost,
                         command=self._apply_topmost).pack(side="left", padx=(0, 12))

        ttk.Button(row1, text="전체화면(F11)", command=self._toggle_fullscreen).pack(side="left")

        self.toggle_btn = ttk.Button(row1, text="▲ 접기", width=10, command=self._toggle_row2)
        self.toggle_btn.pack(side="right")

        self.row2 = ttk.Frame(self.shell)
        self.row2.pack(side="top", fill="x", pady=(6, 0))

        ttk.Label(self.row2, text="하이라이트:").pack(side="left")
        for color in HILITE_COLORS.values():
            tk.Button(self.row2, text="  ", bg=color, width=2, relief="flat", bd=0,
                      command=lambda c=color: self._apply_highlight(bg=c)).pack(side="left", padx=1)

        ttk.Label(self.row2, text=" 글자색:").pack(side="left")
        self.text_color_frame = ttk.Frame(self.row2)
        self.text_color_frame.pack(side="left")
        self._build_text_color_buttons()

        ttk.Button(self.row2, text="서식지우기", command=self._clear_format).pack(side="left", padx=(6, 12))

        ttk.Separator(self.row2, orient="vertical").pack(side="left", fill="y", padx=6)

        self.scroll_btn = ttk.Button(self.row2, text="▶ 자동스크롤", command=self._toggle_autoscroll)
        self.scroll_btn.pack(side="left", padx=(0, 6))

        ttk.Label(self.row2, text="속도:").pack(side="left")
        self.scroll_speed = tk.DoubleVar(value=1.2)
        speed_scale = tk.Scale(self.row2, from_=0.2, to=6.0, resolution=0.1, orient="horizontal",
                                length=110, showvalue=False, variable=self.scroll_speed,
                                bd=0, highlightthickness=0)
        speed_scale.pack(side="left", padx=(2, 12))

        ttk.Separator(self.row2, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Label(self.row2, text="휠 간격:").pack(side="left")
        self.wheel_step = tk.IntVar(value=1)
        for val, label in [(1, "1줄"), (2, "2줄"), (3, "3줄")]:
            tk.Radiobutton(self.row2, text=label, value=val, variable=self.wheel_step,
                           indicatoron=False, width=5, bd=0).pack(side="left", padx=1)

    def _toggle_row2(self):
        if self.row2_visible.get():
            self.row2.pack_forget()
            self.toggle_btn.configure(text="▼ 펼치기")
        else:
            self.row2.pack(side="top", fill="x", pady=(6, 0))
            self.toggle_btn.configure(text="▲ 접기")
        self.row2_visible.set(not self.row2_visible.get())

    def _build_text_color_buttons(self):
        for w in self.text_color_frame.winfo_children():
            w.destroy()
        colors = TEXT_COLOR_SETS[self.theme_name.get()]
        for color in colors.values():
            tk.Button(self.text_color_frame, text="  ", bg=color, width=2, relief="flat", bd=0,
                      command=lambda c=color: self._apply_highlight(fg=c)).pack(side="left", padx=1)

    # ---------------------------------------------------------- 노트북(탭)
    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.plus_frame = ttk.Frame(self.notebook)
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

        for widget in (data.text, data.instr_text):
            widget.bind("<MouseWheel>", lambda e, d=data: self._on_mousewheel(e, d))
            widget.bind("<Button-4>", lambda e, d=data: self._on_mousewheel_linux(e, d))
            widget.bind("<Button-5>", lambda e, d=data: self._on_mousewheel_linux(e, d))

        self._apply_font()
        self._apply_theme_to_tab(data)

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

        main_metrics = tkfont.Font(family=family, size=size).metrics("linespace")
        main_total = main_metrics + main_spacing * 2

        instr_size = max(8, int(size * 0.72))
        instr_metrics = tkfont.Font(family=family, size=instr_size, slant="italic").metrics("linespace")
        extra = max(0, main_total - instr_metrics)
        instr_spacing1 = extra // 2
        instr_spacing3 = extra - instr_spacing1

        for d in self.tabs:
            d.text.configure(font=(family, size), spacing1=main_spacing, spacing3=main_spacing)
            d.instr_text.configure(font=(family, instr_size, "italic"),
                                    spacing1=instr_spacing1, spacing3=instr_spacing3)

    def _apply_topmost(self):
        self.root.attributes("-topmost", self.topmost.get())

    def _toggle_fullscreen(self, _evt=None):
        cur = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not cur)

    # ---------------------------------------------------------- 테마
    def _set_theme(self, name):
        self.theme_name.set(name)
        self._apply_theme()

    def _apply_theme(self):
        t = THEMES[self.theme_name.get()]
        self.root.configure(bg=t["bg"])

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=t["toolbar_bg"])
        style.configure("TLabel", background=t["toolbar_bg"], foreground=t["fg"])
        style.configure("TCheckbutton", background=t["toolbar_bg"], foreground=t["fg"])
        style.configure("TButton", background=t["bg"], foreground=t["fg"], padding=(10, 5), relief="flat")
        style.map("TButton", background=[("active", t["select_bg"])])
        style.configure("TNotebook", background=t["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=t["toolbar_bg"], foreground=t["muted"],
                         padding=(14, 8))
        style.map("TNotebook.Tab",
                  background=[("selected", t["text_bg"])],
                  foreground=[("selected", t["fg"])])

        for d in self.tabs:
            self._apply_theme_to_tab(d)
        self._build_text_color_buttons()

    def _apply_theme_to_tab(self, data: TabData):
        t = THEMES[self.theme_name.get()]
        data.text.configure(bg=t["text_bg"], fg=t["text_fg"],
                             insertbackground=t["text_fg"], selectbackground=t["select_bg"])
        data.instr_text.configure(bg=t["text_bg"], fg=t["instr_fg"],
                                   insertbackground=t["instr_fg"], selectbackground=t["select_bg"])

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
        step = self.wheel_step.get()
        direction = -1 if event.delta > 0 else 1
        data.scroll_both(direction * step, "units")
        return "break"

    def _on_mousewheel_linux(self, event, data):
        step = self.wheel_step.get()
        direction = -1 if event.num == 4 else 1
        data.scroll_both(direction * step, "units")
        return "break"

    def _manual_scroll(self, direction):
        data = self._current_tab()
        if not data:
            return
        step = self.wheel_step.get()
        data.scroll_both(direction * step, "units")

    def _toggle_autoscroll(self):
        self.autoscroll_on = not self.autoscroll_on
        self.scroll_btn.configure(text="⏸ 정지" if self.autoscroll_on else "▶ 자동스크롤")
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
                self.scroll_btn.configure(text="▶ 자동스크롤")
                return
        self.root.after(AUTOSCROLL_TICK_MS, self._autoscroll_tick)


def main():
    root = tk.Tk()
    app = PrompterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
