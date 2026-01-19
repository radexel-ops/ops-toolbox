import pandas as pd
import matplotlib.pyplot as plt
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# DeprecationWarning 방지 및 호환성 처리
try:
    from ttkbootstrap.widgets import ScrolledFrame
except ImportError:
    from ttkbootstrap.scrolled import ScrolledFrame

from tkinter import filedialog, messagebox
from datetime import timedelta, datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.dates import MonthLocator, DateFormatter
import matplotlib.font_manager as fm
import matplotlib.ticker as ticker
import calendar
import numpy as np
from itertools import cycle

# ─────────────────────────────────────────────────────────────────────────────
# 전역 설정
# ─────────────────────────────────────────────────────────────────────────────
plt.rcParams["axes.unicode_minus"] = False
# Chunksize 설정 (속도 최적화)
try:
    plt.rcParams['agg.path.chunksize'] = 10000
except KeyError:
    pass

DEFAULT_COLORS = [
    "#E53935", "#43A047", "#1E88E5", "#FFC107", "#8E24AA",
    "#FB8C00", "#00ACC1", "#E91E63", "#FDD835", "#64B5F6",
]

COLOR_PALETTES = {
    "Bloomberg": DEFAULT_COLORS,
    "Default": plt.rcParams["axes.prop_cycle"].by_key()["color"],
    "Pastel": [
        "#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99",
        "#e31a1c", "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a",
    ],
}


def set_korean_font():
    for f in fm.fontManager.ttflist:
        if "Malgun" in f.name:
            plt.rcParams["font.family"] = f.name
            break


# ─────────────────────────────────────────────────────────────────────────────
# [UI Component] Overlay Calendar (디자인 및 기능 개선)
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# [UI Component] Overlay Calendar (컴팩트 버전)
# ─────────────────────────────────────────────────────────────────────────────
class CalendarOverlay(ttk.Frame):
    def __init__(self, master, init_date, on_select, on_close):
        # padding을 줄여서 테두리 안쪽 여백 최소화
        super().__init__(master, bootstyle="dark", padding=1, relief="raised", borderwidth=1)
        self.on_select = on_select
        self.on_close = on_close

        if isinstance(init_date, (pd.Timestamp, datetime)):
            self.curr_year = init_date.year
            self.curr_month = init_date.month
        else:
            now = datetime.now()
            self.curr_year = now.year
            self.curr_month = now.month

        self.build_widgets()
        self.draw_calendar()

        self.focus_set()
        self.bind("<Escape>", lambda e: self.on_close())

    def build_widgets(self):
        # 1. 상단 헤더 (높이 줄임)
        header_frm = ttk.Frame(self, bootstyle="dark")
        header_frm.pack(fill=X, pady=(1, 2))

        # 닫기 버튼 (크기 축소 width=2)
        ttk.Button(header_frm, text="×", width=2, bootstyle="danger-link",
                   command=self.on_close).pack(side=RIGHT, padx=1)

        # 네비게이션 영역
        nav_frm = ttk.Frame(self, bootstyle="dark")
        nav_frm.pack(fill=X, pady=0)

        # 네비게이션 버튼 크기 축소 (width=2)
        # 스타일을 link로 변경하여 불필요한 테두리 공간 절약
        ttk.Button(nav_frm, text="«", width=2, bootstyle="secondary-link", command=self.prev_year).pack(side=LEFT)
        ttk.Button(nav_frm, text="‹", width=2, bootstyle="secondary-link", command=self.prev_month).pack(side=LEFT)

        # 제목 폰트 축소 (11 -> 9)
        self.lbl_title = ttk.Label(nav_frm, text="", anchor="center", font=("Arial", 9, "bold"),
                                   bootstyle="inverse-dark")
        self.lbl_title.pack(side=LEFT, expand=YES, fill=X)

        ttk.Button(nav_frm, text="›", width=2, bootstyle="secondary-link", command=self.next_month).pack(side=RIGHT)
        ttk.Button(nav_frm, text="»", width=2, bootstyle="secondary-link", command=self.next_year).pack(side=RIGHT)

        # 2. 요일 및 날짜 그리드
        self.days_frm = ttk.Frame(self, bootstyle="dark")
        self.days_frm.pack(fill=BOTH, expand=YES, padx=1, pady=1)

    def draw_calendar(self):
        for widget in self.days_frm.winfo_children(): widget.destroy()

        self.lbl_title.config(text=f"{self.curr_year}.{self.curr_month:02d}")
        weeks = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

        # 요일 헤더 (폰트 9 -> 8, 너비 4 -> 3)
        for i, w in enumerate(weeks):
            lbl = ttk.Label(self.days_frm, text=w, width=3, anchor="center", font=("Arial", 8),
                            bootstyle="inverse-dark")
            lbl.grid(row=0, column=i, sticky="ew", pady=(0, 2))

        # 날짜 배치
        cal = calendar.monthcalendar(self.curr_year, self.curr_month)
        for r, week in enumerate(cal, start=1):
            for c, day in enumerate(week):
                if day != 0:
                    # 날짜 버튼 (너비 3 -> 2, 작은 폰트 적용)
                    btn = ttk.Button(
                        self.days_frm,
                        text=str(day),
                        width=2,
                        bootstyle="light-outline",
                        command=lambda d=day: self.on_select(
                            pd.Timestamp(year=self.curr_year, month=self.curr_month, day=d))
                    )
                    # 버튼 내부 폰트 조절을 위해 style이나 grid 옵션 활용이 제한적이므로
                    # ttkbootstrap 기본 버튼은 폰트가 조금 큽니다.
                    # pack/grid padding을 최소화하여 밀집시킵니다.
                    btn.grid(row=r, column=c, padx=0, pady=0, sticky="nsew")

    def prev_month(self):
        self.curr_month -= 1
        if self.curr_month < 1: self.curr_month, self.curr_year = 12, self.curr_year - 1
        self.draw_calendar()

    def next_month(self):
        self.curr_month += 1
        if self.curr_month > 12: self.curr_month, self.curr_year = 1, self.curr_year + 1
        self.draw_calendar()

    def prev_year(self):
        self.curr_year -= 1; self.draw_calendar()

    def next_year(self):
        self.curr_year += 1; self.draw_calendar()

# ─────────────────────────────────────────────────────────────────────────────
# [UI Component] Y-Axis Slot
# ─────────────────────────────────────────────────────────────────────────────
class YAxisSlot(ttk.Frame):
    def __init__(self, master, index):
        super().__init__(master)
        self.pack(fill=X, pady=1)
        ttk.Label(self, text=f"Y{index + 1}", width=4, font=("Arial", 9, "bold")).pack(side=LEFT)
        self.combo = ttk.Combobox(self, state="readonly", width=15)
        self.combo.pack(side=LEFT, fill=X, expand=YES, padx=2)
        self.var_inc = ttk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Inc", variable=self.var_inc, bootstyle="round-toggle").pack(side=RIGHT, padx=2)
        self.var_rel = ttk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Rel", variable=self.var_rel, bootstyle="square-toggle").pack(side=RIGHT, padx=2)

    def set_items(self, items): self.combo['values'] = items

    def get_selection(self): return self.combo.get()

    def set_selection(self, value):
        if value in self.combo['values'] or value == "": self.combo.set(value)

    def is_included(self): return self.var_inc.get()

    def is_relative(self): return self.var_rel.get()

    def reset(self):
        self.combo.set("")
        self.combo['values'] = []
        self.var_inc.set(True)
        self.var_rel.set(True)


# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────
class BloombergApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="cyborg")
        self.title("High-Performance Quantitative Plotter (Final Fixed)")
        self.geometry("1400x900")
        set_korean_font()

        self.df = pd.DataFrame()
        self.original_min_date = None
        self.original_max_date = None
        self.selected_start_date = None
        self.selected_end_date = None

        self.calendar_widget = None
        self.y_slots = []

        self._init_layout()

    def _init_layout(self):
        # 전체를 좌우로 나누는 메인 분할창
        main_paned = ttk.Panedwindow(self, orient=HORIZONTAL)
        main_paned.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # 1. 왼쪽 패널 (컨트롤 영역)
        self.frm_ctl = ttk.Frame(main_paned, padding=5)
        main_paned.add(self.frm_ctl, weight=0)  # weight=0: 고정 크기 유지 시도

        # 2. 오른쪽 패널 (컨텐츠 영역)
        self.frm_content = ttk.Frame(main_paned)
        main_paned.add(self.frm_content, weight=4)

        # ─────────────────────────────────────────────────────────────
        # [핵심 수정] 오른쪽 영역을 다시 '상하'로 분할 (Graph vs Table)
        # ─────────────────────────────────────────────────────────────
        right_splitter = ttk.Panedwindow(self.frm_content, orient=VERTICAL)
        right_splitter.pack(fill=BOTH, expand=YES)

        # (1) 위쪽: 그래프 영역 (비중 3)
        self.frm_graph = ttk.Frame(right_splitter)
        right_splitter.add(self.frm_graph, weight=3)

        # (2) 아래쪽: 통계 표 영역 (비중 1) -> 무조건 공간 확보됨
        self.frm_stats = ttk.Frame(right_splitter)
        right_splitter.add(self.frm_stats, weight=1)
        # ─────────────────────────────────────────────────────────────

        # ─── Left Panel 구성 (기존과 동일) ───
        lf_file = ttk.Labelframe(self.frm_ctl, text="Data Source", padding=5)
        lf_file.pack(fill=X, pady=5)
        btn_grid = ttk.Frame(lf_file)
        btn_grid.pack(fill=X)
        ttk.Button(btn_grid, text="Open", command=self.load_file, bootstyle="primary").pack(side=LEFT, fill=X,
                                                                                            expand=YES, padx=1)
        self.btn_add = ttk.Button(btn_grid, text="Add", command=self.add_file, state=DISABLED, bootstyle="info")
        self.btn_add.pack(side=LEFT, fill=X, expand=YES, padx=1)
        ttk.Button(lf_file, text="Reset App", command=self.reset_app, bootstyle="danger-outline").pack(fill=X, pady=4)

        lf_period = ttk.Labelframe(self.frm_ctl, text="Period Settings", padding=5)
        lf_period.pack(fill=X, pady=5)
        self.dur_var = ttk.StringVar(value="1 Month")
        self.cbo_dur = ttk.Combobox(lf_period, textvariable=self.dur_var, state="readonly",
                                    values=["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "All", "Custom"])
        self.cbo_dur.bind("<<ComboboxSelected>>", self.update_period_by_duration)
        self.cbo_dur.pack(fill=X, pady=2)
        self.chk_all_data = ttk.BooleanVar(value=False)
        ttk.Checkbutton(lf_period, text="Show All Data (No Filter)", variable=self.chk_all_data).pack(anchor="w")

        date_frm = ttk.Frame(lf_period)
        date_frm.pack(fill=X, pady=5)
        self.lbl_start = ttk.Label(date_frm, text="-", foreground="#4fc3f7", cursor="hand2",
                                   font=("Arial", 10, "underline"))
        self.lbl_start.pack(anchor="w")
        self.lbl_start.bind("<Button-1>", lambda e: self.show_calendar("start"))

        ttk.Label(date_frm, text=" ~ ").pack(anchor="w")
        self.lbl_end = ttk.Label(date_frm, text="-", foreground="#4fc3f7", cursor="hand2",
                                 font=("Arial", 10, "underline"))
        self.lbl_end.pack(anchor="w")
        self.lbl_end.bind("<Button-1>", lambda e: self.show_calendar("end"))

        lf_opt = ttk.Labelframe(self.frm_ctl, text="Graph Options", padding=5)
        lf_opt.pack(fill=X, pady=5)
        ttk.Label(lf_opt, text="X-Axis:").pack(anchor="w")
        self.cbo_xaxis = ttk.Combobox(lf_opt, state="readonly")
        self.cbo_xaxis.pack(fill=X, pady=2)
        ttk.Label(lf_opt, text="Palette:").pack(anchor="w")
        self.cbo_palette = ttk.Combobox(lf_opt, values=list(COLOR_PALETTES.keys()), state="readonly")
        self.cbo_palette.set("Bloomberg")
        self.cbo_palette.pack(fill=X, pady=2)

        lf_series = ttk.Labelframe(self.frm_ctl, text="Series Selection", padding=5)
        lf_series.pack(fill=BOTH, expand=YES, pady=5)
        sf = ScrolledFrame(lf_series, autohide=True)
        sf.pack(fill=BOTH, expand=YES)
        for i in range(10):
            slot = YAxisSlot(sf, i)
            self.y_slots.append(slot)
        ttk.Button(lf_series, text="Auto Fill (Bulk)", command=self.set_bulk, bootstyle="secondary-outline").pack(
            fill=X, pady=2)

        self.btn_plot = ttk.Button(self.frm_ctl, text="PLOT GRAPH", command=self.plot_graph, state=DISABLED,
                                   bootstyle="success")
        self.btn_plot.pack(fill=X, pady=10)

        # ─── Right Panel 내부 구성 (Treeview) ───
        # *주의* frm_graph는 plot_graph 함수에서 채워짐

        # frm_stats 내부 채우기
        cols = ["Asset", "Return", "CAGR", "Downside", "Sharpe", "Sortino", "IR"]
        self.tree = ttk.Treeview(self.frm_stats, columns=cols, show="headings", height=6, bootstyle="info",
                                 selectmode="extended")

        for c, w in zip(cols, [120, 80, 80, 80, 80, 80, 80]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")

        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)

        scrolly = ttk.Scrollbar(self.frm_stats, orient=VERTICAL, command=self.tree.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=scrolly.set)

        self.tree.bind("<Control-c>", self.copy_from_tree)

    def copy_from_tree(self, event):
        selected_items = self.tree.selection()
        if not selected_items: return
        headers = [self.tree.heading(col)['text'] for col in self.tree['columns']]
        copy_text_lines = ["\t".join(headers)]
        for item_id in selected_items:
            values = self.tree.item(item_id, 'values')
            copy_text_lines.append("\t".join(map(str, values)))
        self.clipboard_clear()
        self.clipboard_append("\n".join(copy_text_lines))
        print("Copied to clipboard!")

    # ─────────────────────────────────────────────────────────────────────────
    # [Data Logic]
    # ─────────────────────────────────────────────────────────────────────────
    def _read_file(self, path):
        try:
            data = pd.read_csv(path) if path.endswith(".csv") else pd.read_excel(path)
        except Exception as e:
            print("File Read Error:", e)
            return None

        # 날짜 파싱 강화 (yyyyMMdd 등 대응)
        if "date" in data.columns:
            temp_date = pd.to_datetime(data["date"], format="%Y%m%d", errors="coerce")
            if temp_date.isna().sum() > len(data) / 2:
                data["date"] = pd.to_datetime(data["date"], errors="coerce")
            else:
                data["date"] = temp_date
        return data

    def _safe_interp(self, series):
        # 3차 보간(Polynomial) 복구
        if not series.isnull().any(): return series
        try:
            return series.astype(float).interpolate(method="polynomial", order=3)
        except:
            return series.astype(float).interpolate(method="linear")

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Excel", "*.xls;*.xlsx")])
        if not path: return
        tmp = self._read_file(path)
        if tmp is None or tmp.empty: return

        self.df = tmp.reset_index(drop=True)
        self._post_data_update()

    def add_file(self):
        if self.df.empty: return
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Excel", "*.xls;*.xlsx")])
        if not path: return
        new = self._read_file(path)
        if new is None or new.empty: return

        rename = {}
        existing = set(self.df.columns)
        for c in new.columns:
            if c == "date": continue
            if c in existing:
                i = 1
                while f"{c}_{i}" in existing: i += 1
                rename[c] = f"{c}_{i}"
            existing.add(rename.get(c, c))
        if rename: new = new.rename(columns=rename)

        if "date" in self.df.columns and "date" in new.columns:
            self.df = pd.merge(self.df, new, on="date", how="outer", sort=True).sort_values("date").reset_index(
                drop=True)
        else:
            self.df = pd.concat([self.df, new], axis=1)

        self._post_data_update()

    def _post_data_update(self):
        if "date" in self.df.columns:
            self.original_min_date = self.df["date"].min()
            self.original_max_date = self.df["date"].max()
            self.selected_end_date = self.original_max_date
            self.selected_start_date = self.original_max_date - timedelta(days=30)
        else:
            self.original_min_date = self.original_max_date = None

        cols = list(self.df.columns)
        self.cbo_xaxis["values"] = cols
        self.cbo_xaxis.set("date" if "date" in cols else cols[0])
        for slot in self.y_slots: slot.set_items(cols)

        self.btn_add.config(state=NORMAL)
        self.btn_plot.config(state=NORMAL)
        self.update_period_display()
        self.hide_calendar()

    def set_bulk(self):
        if self.df.empty: return
        cols = [c for c in self.df.columns if c != "date"]
        for i, slot in enumerate(self.y_slots):
            slot.set_selection(cols[i] if i < len(cols) else "")

    def reset_app(self):
        self.df = pd.DataFrame()
        self._post_data_update()
        for slot in self.y_slots: slot.reset()
        for w in self.frm_graph.winfo_children(): w.destroy()
        self.tree.delete(*self.tree.get_children())
        self.dur_var.set("1 Month")
        self.chk_all_data.set(False)
        self.update_period_display()
        self.btn_add.config(state=DISABLED)
        self.btn_plot.config(state=DISABLED)

    # ─────────────────────────────────────────────────────────────────────────
    # [Calendar Logic] 닫기 버튼 및 ESC 지원
    # ─────────────────────────────────────────────────────────────────────────
    def hide_calendar(self):
        if self.calendar_widget:
            self.calendar_widget.destroy()
            self.calendar_widget = None

    def show_calendar(self, target):
        self.hide_calendar()
        base = self.selected_start_date if target == "start" else self.selected_end_date
        if base is None: base = pd.Timestamp.now()

        def on_select(dt):
            if target == "start":
                self.selected_start_date = dt
            else:
                self.selected_end_date = dt
            self.dur_var.set("Custom")
            self.update_period_display()
            self.hide_calendar()

        def on_close():
            self.hide_calendar()

        ref = self.lbl_start if target == "start" else self.lbl_end

        self.calendar_widget = CalendarOverlay(self.frm_ctl, base, on_select, on_close)

        # 위치 계산
        x = ref.winfo_rootx() - self.frm_ctl.winfo_rootx()
        y = ref.winfo_y() + ref.winfo_height() + 2  # 간격 조금 줄임

        # [수정됨] 달력 전체 크기를 대폭 줄임 (내부 요소가 작아졌으므로 가능)
        # Width: 240, Height: 230 정도로 설정
        cal_width = 290
        cal_height = 250

        # 화면 아래로 잘리는 경우 위로 띄우기 로직
        if y + cal_height > self.frm_ctl.winfo_height():
            y -= (cal_height + ref.winfo_height() + 4)

        self.calendar_widget.place(x=x, y=y, width=cal_width, height=cal_height)
    def update_period_by_duration(self, event=None):
        if self.original_max_date is None: return
        sel = self.dur_var.get()
        end = self.original_max_date
        dur_map = {
            "1 Week": timedelta(days=7), "1 Month": timedelta(days=30),
            "3 Months": timedelta(days=90), "6 Months": timedelta(days=180),
            "1 Year": timedelta(days=365),
        }
        if sel == "All":
            self.selected_start_date = self.original_min_date
        elif sel in dur_map:
            self.selected_start_date = end - dur_map[sel]
        self.selected_end_date = end
        self.update_period_display()
        self.hide_calendar()

    def update_period_display(self):
        s_txt = self.selected_start_date.strftime("%Y-%m-%d") if self.selected_start_date else "-"
        e_txt = self.selected_end_date.strftime("%Y-%m-%d") if self.selected_end_date else "-"
        self.lbl_start.config(text=s_txt)
        self.lbl_end.config(text=e_txt)

    # ─────────────────────────────────────────────────────────────────────────
    # [Plot Logic] 전체 데이터 그리기 (계단현상 해결)
    # ─────────────────────────────────────────────────────────────────────────
    def plot_graph(self):
        # 1. 필수 모듈 임포트
        from matplotlib.dates import YearLocator, MonthLocator, DayLocator, DateFormatter
        import matplotlib.ticker as ticker
        import numpy as np

        if self.df.empty: return

        # 2. 사용자 선택 값 가져오기
        x_col = self.cbo_xaxis.get()
        selected_slots = []
        for i, slot in enumerate(self.y_slots):
            col = slot.get_selection()
            if col and slot.is_included():
                selected_slots.append((i, col, slot.is_relative()))

        if not selected_slots: return

        # 3. 데이터 복사 및 전처리
        work = self.df.copy()

        # 날짜 컬럼 처리
        if x_col == "date" and "date" in work.columns:
            work["date"] = pd.to_datetime(work["date"], errors="coerce")
            work = work.dropna(subset=["date"]).sort_values("date")
            if not self.chk_all_data.get() and self.selected_start_date and self.selected_end_date:
                work = work[(work["date"] >= self.selected_start_date) &
                            (work["date"] <= self.selected_end_date)]

        if work.empty:
            print("No data in range")
            return

        plot_data = work.copy()

        # 4. UI 초기화 (이전 그래프/표 삭제)
        for w in self.frm_graph.winfo_children(): w.destroy()
        self.tree.delete(*self.tree.get_children())

        # 5. 그래프 설정
        plt.style.use("dark_background")
        fig, (ax, ax_d) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1.2]}, figsize=(8, 5))
        fig.patch.set_facecolor('#2e2e2e')
        ax.set_facecolor('#222222')
        ax_d.set_facecolor('#222222')

        palette = cycle(COLOR_PALETTES.get(self.cbo_palette.get(), DEFAULT_COLORS))

        # 6. 통계 기준값 준비
        rf_daily = 0.015 / 252
        span_days = 0
        span_years = 0
        if x_col == "date" and not work.empty:
            span_days = (work["date"].iloc[-1] - work["date"].iloc[0]).days
            span_years = span_days / 365.25 if span_days else 0

        # 벤치마크 데이터 처리 (콤마 제거 포함)
        bench_r = None
        if "kqsm" in work.columns:
            try:
                temp_kq = work["kqsm"].astype(str).str.replace(',', '')
                bench_r = pd.to_numeric(temp_kq, errors='coerce').pct_change(fill_method=None).dropna()
            except:
                bench_r = None

        # [참고선]
        if x_col == "date" and not plot_data.empty:
            try:
                start_date = plot_data["date"].iloc[0]
                t_years = (plot_data["date"] - start_date).dt.days / 365.0
                ref_curve = 1.0 * (1.03 ** t_years)
                ax.plot(plot_data["date"], ref_curve, color="gray", linestyle="--", linewidth=1.2, alpha=0.6,
                        label="Ref 3%")
            except:
                pass

        base_plot_series = None

        # 7. 시리즈별 루프 (여기가 핵심)
        for idx, (slot_idx, col, is_rel) in enumerate(selected_slots):

            # [1] 데이터 강제 숫자 변환 (콤마 제거)
            try:
                if work[col].dtype == 'object':
                    work[col] = work[col].astype(str).str.replace(',', '')
                work[col] = pd.to_numeric(work[col], errors='coerce')
                plot_data[col] = work[col]
            except:
                print(f"Data convert error: {col}")
                continue

            # [2] 변수 초기화 (계산 실패시 0으로 표기하기 위함)
            full_series = self._safe_interp(work[col])
            tot_ret = 0.0
            cagr = 0.0
            sharpe = 0.0
            sortino = 0.0
            ir = 0.0
            d_risk = 0.0

            # [3] 통계 계산 시도
            try:
                st_val = full_series.iloc[0] if not full_series.empty else 0
                ed_val = full_series.iloc[-1] if not full_series.empty else 0

                # 수익률
                if st_val != 0:
                    tot_ret = (ed_val / st_val - 1)
                    if span_years > 0:
                        cagr = ((abs(ed_val) / abs(st_val)) ** (1 / span_years) - 1)
                        if ed_val < st_val: cagr = -abs(cagr)

                # 리스크 지표
                r = full_series.pct_change(fill_method=None).dropna()
                if not r.empty:
                    excess = r - rf_daily
                    std = excess.std(ddof=1)
                    if std > 0:
                        sharpe = np.sqrt(252) * excess.mean() / std

                    downside = excess[excess < 0]
                    sortino_denom = np.sqrt((downside ** 2).mean())
                    if sortino_denom > 0:
                        sortino = np.sqrt(252) * excess.mean() / sortino_denom
                    d_risk = sortino_denom * np.sqrt(252)

                    if bench_r is not None and col != "kqsm":
                        r_aligned, b_aligned = r.align(bench_r, join="inner")
                        active = r_aligned - b_aligned
                        te = active.std(ddof=1)
                        if te > 0:
                            ir = np.sqrt(252) * active.mean() / te
            except Exception as e:
                print(f"Calc warning {col}: {e}")

            # [4] Treeview에 강제 삽입 (이 코드가 있어서 표가 나옵니다)
            # ─────────────────────────────────────────────────────────────
            self.tree.insert("", "end", values=(
                col,
                f"{tot_ret * 100:6.2f}%",
                f"{cagr * 100:6.2f}%",
                f"{d_risk * 100:6.2f}%",
                f"{sharpe:5.2f}",
                f"{sortino:5.2f}",
                f"{ir:5.2f}"
            ))
            # ─────────────────────────────────────────────────────────────

            # [5] 플로팅
            try:
                plot_ser = self._safe_interp(plot_data[col])
                if is_rel:
                    base_v = plot_ser.iloc[0] if not plot_ser.empty else 0
                    if base_v: plot_ser = plot_ser / base_v

                color = next(palette)
                lw = 2.0 if idx == 0 else 1.2
                ax.plot(plot_data[x_col], plot_ser, label=col, color=color, lw=lw)

                if idx == 0:
                    base_plot_series = plot_ser
                elif base_plot_series is not None:
                    # 길이 보정
                    s1, s2 = base_plot_series.align(plot_ser, join='inner')
                    diff = s1 - s2
                    # 날짜 인덱스 매칭
                    diff_x = plot_data[x_col].loc[s1.index]
                    ax_d.plot(diff_x, diff, label=f"Diff({col})", color=color, lw=1.0)
            except Exception as e:
                print(f"Plot error {col}: {e}")

        # 8. 그래프 마무리
        ax.yaxis.tick_right()
        ax_d.yaxis.tick_right()
        ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
        ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.2f}"))
        ax_d.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.2f}"))

        if x_col == "date":
            if span_days <= 60:
                interval = 1 if span_days <= 30 else 2
                ax.xaxis.set_major_locator(DayLocator(interval=interval))
                ax.xaxis.set_major_formatter(DateFormatter("%m-%d"))
            elif span_days < 365:
                ax.xaxis.set_major_locator(MonthLocator())
                ax.xaxis.set_major_formatter(DateFormatter("%Y-%m"))
            else:
                ax.xaxis.set_major_locator(YearLocator())
                ax.xaxis.set_major_formatter(DateFormatter("%Y"))
                ax.xaxis.set_minor_locator(MonthLocator())

            plt.setp(ax_d.xaxis.get_majorticklabels(), rotation=0 if span_days > 60 else 45)

        for a in [ax, ax_d]:
            a.grid(True, which='major', axis='x', ls='--', lw=0.5, alpha=0.5)
            a.grid(True, axis='y', ls='--', lw=0.4, alpha=0.4)

        ax.set_title(f"Performance Analysis ({span_days} days)", fontsize=10, color="white", pad=10)

        canvas = FigureCanvasTkAgg(fig, master=self.frm_graph)
        canvas.draw()
        toolbar = NavigationToolbar2Tk(canvas, self.frm_graph)
        toolbar.update()
        canvas.get_tk_widget().pack(fill=BOTH, expand=YES)
if __name__ == "__main__":
    app = BloombergApp()
    app.mainloop()