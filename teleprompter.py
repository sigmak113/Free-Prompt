# -*- coding: utf-8 -*-
"""
간단 프롬프터 (Teleprompter) v2
- 라이트/다크 모드
- 행동지시: "대사 | 지시문" 형태로 같은 줄에 표시 (원고는 사라지지 않음)
- 자동스크롤: 픽셀 단위 부드러운 스크롤 + 속도 슬라이더
- 마우스휠 간격: 1줄 / 2줄 / 3줄 중 선택
- 상단 툴바 2줄 구성 + 접기/펼치기
"""

import tkinter as tk
from tkinter import ttk, font as tkfont, simpledialog, messagebox

DEFAULT_FONT_CANDIDATES = ["Paperlogy", "PaperlogyGothic", "Paperlogy Gothic", "맑은 고딕", "Malgun Gothic"]
INSTR_SEP = "|"
AUTOSCROLL_TICK_MS = 40  # 고정 틱 간격(ms). 속도는 틱당 이동 픽셀 수로 조절.

THEMES = {
    "light": dict(
        bg="#f4f4f4", fg="#1a1a1a", toolbar_bg="#e9e9e9",
        text_bg="#ffffff", text_fg="#1a1a1a", instr_fg="#b5651d",
        select_bg="#cfe8ff",
    ),
    "dark": dict(
        bg="#1e1e1e", fg="#e8e8e8", toolbar_bg="#262626",
        text_bg="#121212", text_fg="#f0f0f0", instr_fg="#4fc3f7",
        select_bg="#3a5772",
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

DEFAULT_SCRIPT = (
    f"안녕하세요 {INSTR_SEP} 꾸벅 화면에 인사하기\n"
    f"뭐뭐입니다 {INSTR_SEP}\n"
    f"날씨 참 덥죠? {INSTR_SEP} 손 부채질하기\n"
    "\n"
    f"'|' 기호 뒤에 지시문을 쓰면 대사 옆에 색이 다르게 표시됩니다."
)


class TabData:
    def __init__(self, notebook, title):
        self.frame = ttk.Frame(notebook)
        self.title = title
        self.text = tk.Text(
            self.frame, wrap="word", undo=True, spacing1=6, spacing3=6,
            padx=18, pady=16, borderwidth=0, highlightthickness=0
        )
        yscroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=yscroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")


class PrompterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("간단 프롬프터")
        self.root.geometry("1100x700")

        self.theme_name = tk.StringVar(value="light")
        self.autoscroll_on = False
        self._scroll_accum = 0.0
        self.tabs = []
        self.tab_counter = 0
        self.toolbar_expanded = tk.BooleanVar(value=True)

        self._build_toolbar_shell()
        self._build_toolbar_rows()
        self._build_notebook()
        self.add_tab()
        self._apply_theme()

        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<Up>", lambda e: self._manual_scroll(-1))
        self.root.bind("<Down>", lambda e: self._manual_scroll(1))

    # ---------------------------------------------------------- 툴바 뼈대(접기/펼치기)
    def _build_toolbar_shell(self):
        self.shell = ttk.Frame(self.root, padding=(6, 4))
        self.shell.pack(side="top", fill="x")

        header = ttk.Frame(self.shell)
        header.pack(side="top", fill="x")
        ttk.Label(header, text="메뉴", font=("", 9, "bold")).pack(side="left")
        self.toggle_btn = ttk.Button(header, text="▲ 접기", width=10, command=self._toggle_toolbar)
        self.toggle_btn.pack(side="right")

        self.controls = ttk.Frame(self.shell)
        self.controls.pack(side="top", fill="x", pady=(4, 0))

    def _toggle_toolbar(self):
        expanded = not self.toolbar_expanded.get()
        self.toolbar_expanded.set(expanded)
        if expanded:
            self.controls.pack(side="top", fill="x", pady=(4, 0))
            self.toggle_btn.configure(text="▲ 접기")
        else:
            self.controls.pack_forget()
            self.toggle_btn.configure(text="▼ 펼치기")

    # ---------------------------------------------------------- 툴바 내용 (2줄)
    def _build_toolbar_rows(self):
        row1 = ttk.Frame(self.controls)
        row1.pack(side="top", fill="x", pady=2)
        row2 = ttk.Frame(self.controls)
        row2.pack(side="top", fill="x", pady=2)

        # ---- Row1 : 테마 / 폰트 / 창 / 탭 ----
        ttk.Label(row1, text="테마:").pack(side="left")
        ttk.Button(row1, text="라이트", width=6,
                   command=lambda: self._set_theme("light")).pack(side="left", padx=1)
        ttk.Button(row1, text="다크", width=6,
                   command=lambda: self._set_theme("dark")).pack(side="left", padx=(1, 10))

        ttk.Label(row1, text="폰트:").pack(side="left")
        families = sorted(tkfont.families())
        default_family = next((f for f in DEFAULT_FONT_CANDIDATES if f in families), families[0])
        self.font_family = tk.StringVar(value=default_family)
        fam_box = ttk.Combobox(row1, textvariable=self.font_family, values=families,
                                width=16, state="readonly")
        fam_box.pack(side="left", padx=(2, 10))
        fam_box.bind("<<ComboboxSelected>>", lambda e: self._apply_font())

        ttk.Label(row1, text="크기:").pack(side="left")
        self.font_size = tk.IntVar(value=32)
        size_spin = ttk.Spinbox(row1, from_=8, to=200, width=5, textvariable=self.font_size,
                                 command=self._apply_font)
        size_spin.pack(side="left", padx=(2, 10))
        size_spin.bind("<Return>", lambda e: self._apply_font())

        self.topmost = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="항상 위", variable=self.topmost,
                         command=self._apply_topmost).pack(side="left", padx=(0, 10))

        ttk.Button(row1, text="전체화면(F11)", command=self._toggle_fullscreen).pack(side="left", padx=(0, 10))

        ttk.Separator(row1, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(row1, text="+ 탭", width=6, command=self.add_tab).pack(side="left", padx=1)
        ttk.Button(row1, text="탭 이름변경", command=self.rename_tab).pack(side="left", padx=1)
        ttk.Button(row1, text="탭 닫기", command=self.close_tab).pack(side="left", padx=1)

        # ---- Row2 : 하이라이트 / 글자색 / 자동스크롤 / 휠간격 ----
        ttk.Label(row2, text="하이라이트:").pack(side="left")
        for color in HILITE_COLORS.values():
            tk.Button(row2, text="  ", bg=color, width=2, relief="raised",
                      command=lambda c=color: self._apply_highlight(bg=c)).pack(side="left", padx=1)

        ttk.Label(row2, text=" 글자색:").pack(side="left")
        self.text_color_frame = ttk.Frame(row2)
        self.text_color_frame.pack(side="left")
        self._build_text_color_buttons()

        ttk.Button(row2, text="서식지우기", command=self._clear_format).pack(side="left", padx=(6, 10))

        ttk.Separator(row2, orient="vertical").pack(side="left", fill="y", padx=6)

        self.scroll_btn = ttk.Button(row2, text="▶ 자동스크롤", command=self._toggle_autoscroll)
        self.scroll_btn.pack(side="left", padx=(0, 6))

        ttk.Label(row2, text="속도:").pack(side="left")
        self.scroll_speed = tk.DoubleVar(value=1.2)
        speed_scale = tk.Scale(row2, from_=0.2, to=6.0, resolution=0.1, orient="horizontal",
                                length=110, showvalue=False, variable=self.scroll_speed)
        speed_scale.pack(side="left", padx=(2, 10))

        ttk.Separator(row2, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Label(row2, text="휠 간격:").pack(side="left")
        self.wheel_step = tk.IntVar(value=1)
        for val, label in [(1, "1줄"), (2, "2줄"), (3, "3줄")]:
            tk.Radiobutton(row2, text=label, value=val, variable=self.wheel_step,
                           indicatoron=False, width=5).pack(side="left", padx=1)

    def _build_text_color_buttons(self):
        for w in self.text_color_frame.winfo_children():
            w.destroy()
        colors = TEXT_COLOR_SETS[self.theme_name.get()]
        for color in colors.values():
            tk.Button(self.text_color_frame, text="  ", bg=color, width=2, relief="raised",
                      command=lambda c=color: self._apply_highlight(fg=c)).pack(side="left", padx=1)

    # ---------------------------------------------------------- 노트북(탭)
    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._apply_font())

    def add_tab(self):
        self.tab_counter += 1
        title = f"원고 {self.tab_counter}"
        data = TabData(self.notebook, title)
        self.notebook.add(data.frame, text=title)
        self.notebook.select(data.frame)
        self.tabs.append(data)

        data.text.insert("1.0", DEFAULT_SCRIPT)
        data.text.bind("<KeyRelease>", lambda e, d=data: self._refresh_instructions(d))
        data.text.bind("<MouseWheel>", self._on_mousewheel)      # Windows/Mac
        data.text.bind("<Button-4>", self._on_mousewheel_linux)  # Linux
        data.text.bind("<Button-5>", self._on_mousewheel_linux)
        self._apply_font()
        self._apply_theme_to_tab(data)
        self._refresh_instructions(data)

    def rename_tab(self):
        data = self._current_tab()
        if not data:
            return
        new_name = simpledialog.askstring("탭 이름변경", "새 탭 이름:", initialvalue=data.title)
        if new_name:
            data.title = new_name
            self.notebook.tab(data.frame, text=new_name)

    def close_tab(self):
        if len(self.tabs) <= 1:
            messagebox.showinfo("안내", "마지막 탭은 닫을 수 없습니다.")
            return
        data = self._current_tab()
        if not data:
            return
        if messagebox.askyesno("탭 닫기", f"'{data.title}' 탭을 닫을까요?"):
            self.notebook.forget(data.frame)
            self.tabs.remove(data)

    def _current_tab(self):
        if not self.tabs:
            return None
        idx = self.notebook.index(self.notebook.select())
        return self.tabs[idx]

    # ---------------------------------------------------------- 폰트/창
    def _apply_font(self):
        f = (self.font_family.get(), self.font_size.get())
        instr_f = (self.font_family.get(), max(8, int(self.font_size.get() * 0.72)), "italic")
        for d in self.tabs:
            d.text.configure(font=f)
            d.text.tag_configure("instr", font=instr_f)

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
        self.shell.configure(style="Toolbar.TFrame")
        self.controls.configure(style="Toolbar.TFrame")

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Toolbar.TFrame", background=t["toolbar_bg"])
        style.configure("TFrame", background=t["toolbar_bg"])
        style.configure("TLabel", background=t["toolbar_bg"], foreground=t["fg"])
        style.configure("TCheckbutton", background=t["toolbar_bg"], foreground=t["fg"])
        style.configure("TButton", background=t["bg"], foreground=t["fg"])
        style.map("TButton", background=[("active", t["select_bg"])])

        for d in self.tabs:
            self._apply_theme_to_tab(d)

        self._build_text_color_buttons()

    def _apply_theme_to_tab(self, data: TabData):
        t = THEMES[self.theme_name.get()]
        data.text.configure(
            bg=t["text_bg"], fg=t["text_fg"],
            insertbackground=t["text_fg"],
            selectbackground=t["select_bg"],
        )
        data.text.tag_configure("instr", foreground=t["instr_fg"])

    # ---------------------------------------------------------- 하이라이트
    def _apply_highlight(self, bg=None, fg=None):
        data = self._current_tab()
        if not data:
            return
        try:
            if not data.text.tag_ranges("sel"):
                return
            tag_name = f"fmt_{bg}_{fg}"
            opts = {}
            if bg:
                opts["background"] = bg
            if fg:
                opts["foreground"] = fg
            data.text.tag_configure(tag_name, **opts)
            data.text.tag_add(tag_name, "sel.first", "sel.last")
            data.text.tag_raise(tag_name)
        except tk.TclError:
            pass

    def _clear_format(self):
        data = self._current_tab()
        if not data:
            return
        try:
            if not data.text.tag_ranges("sel"):
                return
            for tag in data.text.tag_names():
                if tag.startswith("fmt_"):
                    data.text.tag_remove(tag, "sel.first", "sel.last")
        except tk.TclError:
            pass

    # ---------------------------------------------------------- 행동지시 (같은 줄 표시)
    def _refresh_instructions(self, data: TabData):
        text = data.text
        text.tag_remove("instr", "1.0", "end")
        content = text.get("1.0", "end-1c")
        for i, line in enumerate(content.split("\n"), start=1):
            idx = line.find(INSTR_SEP)
            if idx >= 0:
                text.tag_add("instr", f"{i}.{idx}", f"{i}.end")
        t = THEMES[self.theme_name.get()]
        text.tag_configure("instr", foreground=t["instr_fg"])

    # ---------------------------------------------------------- 스크롤
    def _on_mousewheel(self, event):
        data = self._current_tab()
        if not data:
            return "break"
        step = self.wheel_step.get()
        direction = -1 if event.delta > 0 else 1
        data.text.yview_scroll(direction * step, "units")
        return "break"

    def _on_mousewheel_linux(self, event):
        data = self._current_tab()
        if not data:
            return "break"
        step = self.wheel_step.get()
        direction = -1 if event.num == 4 else 1
        data.text.yview_scroll(direction * step, "units")
        return "break"

    def _manual_scroll(self, direction):
        data = self._current_tab()
        if not data:
            return
        step = self.wheel_step.get()
        data.text.yview_scroll(direction * step, "units")

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
                data.text.yview_scroll(move, "pixels")
                self._scroll_accum -= move
            # 끝까지 도달하면 자동 정지
            first, last = data.text.yview()
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
