# -*- coding: utf-8 -*-
"""
간단 프롬프터(Teleprompter)
- 글자크기 변경
- 시스템 폰트 선택 (기본값: 페이퍼로지 고딕, 없으면 자동 대체)
- 내용 편집
- 창 크기 자유 조절 / 전체화면
- 항상 위(상단 고정)
- 탭으로 여러 원고 구분
- 원고 내 하이라이트(형광펜/글자색)
- 행동지시(▶ 로 시작하는 줄)는 원고에서 숨겨지고 오른쪽 패널에 표시,
  현재 읽고 있는 위치에 맞춰 자동으로 강조됨
- 자동 스크롤 속도 및 간격(스텝) 조정
"""

import tkinter as tk
from tkinter import ttk, font as tkfont, simpledialog, messagebox

DEFAULT_FONT_CANDIDATES = ["Paperlogy", "PaperlogyGothic", "Paperlogy Gothic", "맑은 고딕", "Malgun Gothic"]
NOTE_MARK = "▶"

HILITE_COLORS = {
    "노랑": "#fff59d",
    "초록": "#c8e6c9",
    "분홍": "#f8bbd0",
    "하늘": "#bbdefb",
}
TEXT_COLORS = {
    "빨강": "#e53935",
    "파랑": "#1e88e5",
    "검정": "#000000",
}


class TabData:
    def __init__(self, notebook, title):
        self.frame = ttk.Frame(notebook)
        self.title = title

        paned = ttk.Panedwindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # ---- 원고 텍스트 ----
        left = ttk.Frame(paned)
        self.text = tk.Text(
            left, wrap="word", undo=True, spacing1=6, spacing3=6,
            padx=16, pady=16, borderwidth=0
        )
        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=yscroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        paned.add(left, weight=4)

        # ---- 행동지시 패널 ----
        right = ttk.Frame(paned)
        ttk.Label(right, text="행동지시", anchor="center",
                  font=("", 10, "bold")).pack(fill="x", pady=(4, 2))
        self.note_list = tk.Listbox(right, activestyle="none", exportselection=False)
        self.note_list.pack(fill="both", expand=True, padx=4, pady=4)
        paned.add(right, weight=1)

        # 태그: 행동지시 줄은 원고에서 숨김(elide)
        self.text.tag_configure("action", elide=True)
        self.notes = []  # [(line_no, note_text)]

        self.note_list.bind("<<ListboxSelect>>", self._jump_to_note)

    def _jump_to_note(self, _evt=None):
        sel = self.note_list.curselection()
        if not sel:
            return
        line_no, _ = self.notes[sel[0]]
        self.text.see(f"{line_no}.0")


class PrompterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("간단 프롬프터")
        self.root.geometry("1100x700")

        self.autoscroll_on = False
        self.tabs = []
        self.tab_counter = 0

        self._build_toolbar()
        self._build_notebook()
        self.add_tab()

        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.root.bind("<Up>", lambda e: self._manual_scroll(-1))
        self.root.bind("<Down>", lambda e: self._manual_scroll(1))

    # ---------------------------------------------------------- 툴바
    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(side="top", fill="x")

        # 폰트
        ttk.Label(bar, text="폰트:").pack(side="left")
        families = sorted(tkfont.families())
        default_family = next((f for f in DEFAULT_FONT_CANDIDATES if f in families), families[0])
        self.font_family = tk.StringVar(value=default_family)
        fam_box = ttk.Combobox(bar, textvariable=self.font_family, values=families,
                                width=18, state="readonly")
        fam_box.pack(side="left", padx=(2, 10))
        fam_box.bind("<<ComboboxSelected>>", lambda e: self._apply_font())

        # 글자크기
        ttk.Label(bar, text="크기:").pack(side="left")
        self.font_size = tk.IntVar(value=32)
        size_spin = ttk.Spinbox(bar, from_=8, to=200, width=5, textvariable=self.font_size,
                                 command=self._apply_font)
        size_spin.pack(side="left", padx=(2, 10))
        size_spin.bind("<Return>", lambda e: self._apply_font())

        # 상단 고정
        self.topmost = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="항상 위", variable=self.topmost,
                         command=self._apply_topmost).pack(side="left", padx=(0, 10))

        # 전체화면
        ttk.Button(bar, text="전체화면(F11)", command=self._toggle_fullscreen).pack(side="left", padx=(0, 10))

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        # 하이라이트 (배경색)
        ttk.Label(bar, text="하이라이트:").pack(side="left")
        for name, color in HILITE_COLORS.items():
            b = tk.Button(bar, text="  ", bg=color, width=2,
                          command=lambda c=color: self._apply_highlight(bg=c))
            b.pack(side="left", padx=1)

        # 글자색
        ttk.Label(bar, text=" 글자색:").pack(side="left")
        for name, color in TEXT_COLORS.items():
            b = tk.Button(bar, text="  ", bg=color, width=2,
                          command=lambda c=color: self._apply_highlight(fg=c))
            b.pack(side="left", padx=1)

        ttk.Button(bar, text="서식지우기", command=self._clear_format).pack(side="left", padx=(6, 10))

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        # 자동 스크롤
        self.scroll_btn = ttk.Button(bar, text="▶ 자동스크롤", command=self._toggle_autoscroll)
        self.scroll_btn.pack(side="left", padx=(0, 6))

        ttk.Label(bar, text="속도:").pack(side="left")
        self.scroll_speed = tk.IntVar(value=50)  # ms 간격, 작을수록 빠름
        ttk.Scale(bar, from_=10, to=300, orient="horizontal", length=100,
                  variable=self.scroll_speed).pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="간격(줄):").pack(side="left")
        self.scroll_step = tk.IntVar(value=1)
        ttk.Spinbox(bar, from_=1, to=10, width=4, textvariable=self.scroll_step).pack(side="left", padx=(2, 10))

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(bar, text="+ 탭 추가", command=self.add_tab).pack(side="left", padx=2)
        ttk.Button(bar, text="탭 이름변경", command=self.rename_tab).pack(side="left", padx=2)
        ttk.Button(bar, text="탭 닫기", command=self.close_tab).pack(side="left", padx=2)

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

        data.text.insert("1.0", "여기에 원고 내용을 입력하세요.\n"
                                 f"{NOTE_MARK} 이 줄처럼 맨 앞에 '{NOTE_MARK}'를 붙이면 행동지시로 처리되어 "
                                 "원고에는 보이지 않고 오른쪽 패널에 표시됩니다.\n"
                                 "다음 대사를 이어서 입력하세요.")
        data.text.bind("<KeyRelease>", lambda e, d=data: self._refresh_notes(d))
        data.text.bind("<MouseWheel>", lambda e, d=data: self.root.after(10, self._refresh_note_highlight, d))
        data.text.bind("<ButtonRelease-1>", lambda e, d=data: self._refresh_note_highlight(d))
        self._apply_font()
        self._refresh_notes(data)

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
        for d in self.tabs:
            d.text.configure(font=f)

    def _apply_topmost(self):
        self.root.attributes("-topmost", self.topmost.get())

    def _toggle_fullscreen(self, _evt=None):
        cur = self.root.attributes("-fullscreen")
        self.root.attributes("-fullscreen", not cur)

    # ---------------------------------------------------------- 하이라이트
    def _apply_highlight(self, bg=None, fg=None):
        data = self._current_tab()
        if not data:
            return
        try:
            sel_range = data.text.tag_ranges("sel")
            if not sel_range:
                return
            tag_name = f"fmt_{bg}_{fg}"
            opts = {}
            if bg:
                opts["background"] = bg
            if fg:
                opts["foreground"] = fg
            data.text.tag_configure(tag_name, **opts)
            data.text.tag_add(tag_name, "sel.first", "sel.last")
        except tk.TclError:
            pass

    def _clear_format(self):
        data = self._current_tab()
        if not data:
            return
        try:
            for tag in data.text.tag_names():
                if tag.startswith("fmt_"):
                    data.text.tag_remove(tag, "sel.first", "sel.last")
        except tk.TclError:
            pass

    # ---------------------------------------------------------- 행동지시
    def _refresh_notes(self, data: TabData):
        text = data.text
        for tag in ("action",):
            text.tag_remove(tag, "1.0", "end")

        data.notes.clear()
        data.note_list.delete(0, "end")

        content = text.get("1.0", "end-1c")
        lines = content.split("\n")
        for i, line in enumerate(lines, start=1):
            if line.strip().startswith(NOTE_MARK):
                text.tag_add("action", f"{i}.0", f"{i}.end+1c")
                note_text = line.strip().lstrip(NOTE_MARK).strip()
                data.notes.append((i, note_text))
                data.note_list.insert("end", f"[{i}] {note_text}")

        self._refresh_note_highlight(data)

    def _refresh_note_highlight(self, data: TabData):
        if not data.notes:
            return
        try:
            top_index = data.text.index("@0,0")
            top_line = int(top_index.split(".")[0])
        except tk.TclError:
            return
        current = 0
        for i, (line_no, _) in enumerate(data.notes):
            if line_no <= top_line:
                current = i
        data.note_list.selection_clear(0, "end")
        data.note_list.selection_set(current)
        data.note_list.see(current)

    # ---------------------------------------------------------- 스크롤
    def _manual_scroll(self, direction):
        data = self._current_tab()
        if not data:
            return
        step = self.scroll_step.get()
        data.text.yview_scroll(direction * step, "units")
        self._refresh_note_highlight(data)

    def _toggle_autoscroll(self):
        self.autoscroll_on = not self.autoscroll_on
        self.scroll_btn.configure(text="⏸ 정지" if self.autoscroll_on else "▶ 자동스크롤")
        if self.autoscroll_on:
            self._autoscroll_tick()

    def _autoscroll_tick(self):
        if not self.autoscroll_on:
            return
        data = self._current_tab()
        if data:
            data.text.yview_scroll(self.scroll_step.get(), "units")
            self._refresh_note_highlight(data)
        self.root.after(self.scroll_speed.get(), self._autoscroll_tick)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except tk.TclError:
        pass
    app = PrompterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
