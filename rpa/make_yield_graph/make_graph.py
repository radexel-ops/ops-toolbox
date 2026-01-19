import pandas as pd
import matplotlib.pyplot as plt
from tkinter import *
from tkinter import filedialog, ttk
from datetime import timedelta, datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.dates import MonthLocator
from itertools import cycle
import matplotlib.font_manager as fm
import matplotlib.ticker as ticker
import calendar
import os
import numpy as np      # ← Sharpe·Sortino 계산용



"""
─────────────────────────────────────────────────────────────────────────────
 Bloomberg-style Graph Plotter with *Embedded* Calendar Date Picker
─────────────────────────────────────────────────────────────────────────────
★ NEW FEATURES (2025-05-14 UPDATE 2)
    1. ‘시작/종료 날짜’ 라벨 클릭 시, 별도 팝업이 아닌
       메인 UI 내부(frame_ctl) 에 달력 위젯이 바로 표시됩니다.
    2. 달력은 <, > 로 월 이동, <<, >> 로 연도 이동, 날짜 클릭으로 확정
       (기존 팝업과 동일한 조작법).
    3. 달력 위젯은 자동으로 크기가 조절되어 내용이 잘리지 않습니다.
    4. 나머지 모든 기능(파일 로드/추가, 색상 팔레트, Reset, 그래프 로직 등)
       은 *그대로 유지*됩니다.
─────────────────────────────────────────────────────────────────────────────
"""

plt.rcParams["axes.unicode_minus"] = False
plt.style.use("dark_background")  # Bloomberg-style dark theme

# ─────────────────────────────────────────────────────────────────────────────
# 색상 팔레트
# ─────────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# 한글 폰트 설정
# ─────────────────────────────────────────────────────────────────────────────
def set_korean_font():
    for f in fm.fontManager.ttflist:
        if "Malgun" in f.name:
            plt.rcParams["font.family"] = f.name
            break
    else:
        print("한글 폰트를 찾지 못했습니다. 한글이 깨질 수 있습니다.")

# ─────────────────────────────────────────────────────────────────────────────
# 전역: 최초 전체 날짜 범위 & 현재 선택 기간
# ─────────────────────────────────────────────────────────────────────────────
original_min_date: pd.Timestamp | None = None
original_max_date: pd.Timestamp | None = None
selected_start_date: pd.Timestamp | None = None
selected_end_date: pd.Timestamp | None = None

# 달력 위젯(임베디드) 핸들
calendar_frame = None   # type: Frame | None

# 빈 데이터프레임으로 초기화 (Reset 버튼 지원)
df = pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# 파일 읽기 / 유틸리티
# ─────────────────────────────────────────────────────────────────────────────
def _read_file(path: str) -> pd.DataFrame | None:
    try:
        data = pd.read_csv(path) if path.endswith(".csv") else pd.read_excel(path)
    except Exception as e:
        print("파일 읽기 오류:", e)
        return None
    if "date" in data.columns:
        data["date"] = pd.to_datetime(data["date"], format="%Y%m%d", errors="coerce")
    return data

def _unique(col: str, existing: set[str]):
    if col not in existing:
        return col
    i = 1
    while f"{col}_{i}" in existing:
        i += 1
    return f"{col}_{i}"

def _update_original_range():
    global original_min_date, original_max_date, selected_start_date, selected_end_date
    if "df" in globals() and not df.empty and "date" in df.columns:
        original_min_date = df["date"].min()
        original_max_date = df["date"].max()
        selected_end_date = original_max_date
        selected_start_date = original_max_date - timedelta(days=30)  # default 1M
    else:
        original_min_date = original_max_date = None
        selected_start_date = selected_end_date = None

# ─────────────────────────────────────────────────────────────────────────────
# Embedded Calendar Widget (Frame)
# ─────────────────────────────────────────────────────────────────────────────
class CalendarFrame(Frame):
    def __init__(self, master, init_date: datetime, callback):
        super().__init__(master, bg="#222", bd=1, relief="ridge")
        self.callback = callback
        self.curr_year = init_date.year
        self.curr_month = init_date.month
        self.build_widgets()
        self.draw_calendar()

    # ---------- UI ----------
    def build_widgets(self):
        frm_nav = Frame(self, bg="#222")
        frm_nav.pack(fill=X, pady=3)

        # ← 버튼 순서: <<, <, >, >>
        Button(frm_nav, text="<<", width=3, command=self.prev_year).pack(side=LEFT, padx=2)
        Button(frm_nav, text="<",  width=3, command=self.prev_month).pack(side=LEFT, padx=2)

        self.lbl_title = Label(frm_nav, text="", width=12, bg="#222", fg="white")
        self.lbl_title.pack(side=LEFT, expand=YES)

        # next_month '>' 을 먼저 pack, 그 다음 next_year '>>' 을 pack하여
        # 버튼 순서가 <<, <, >, >> 가 되도록 함
        Button(frm_nav, text=">",  width=3, command=self.next_month).pack(side=RIGHT, padx=2)
        Button(frm_nav, text=">>", width=3, command=self.next_year).pack(side=RIGHT, padx=2)

        self.frm_days = Frame(self, bg="#222")
        self.frm_days.pack(fill=BOTH, expand=YES, padx=4, pady=4)

    # ---------- Navigation ----------
    def prev_month(self):
        if self.curr_month == 1:
            self.curr_month = 12
            self.curr_year -= 1
        else:
            self.curr_month -= 1
        self.draw_calendar()

    def next_month(self):
        if self.curr_month == 12:
            self.curr_month = 1
            self.curr_year += 1
        else:
            self.curr_month += 1
        self.draw_calendar()

    def prev_year(self):
        self.curr_year -= 1
        self.draw_calendar()

    def next_year(self):
        self.curr_year += 1
        self.draw_calendar()

    # ---------- Calendar draw ----------
    def draw_calendar(self):
        for w in self.frm_days.winfo_children():
            w.destroy()
        cal = calendar.monthcalendar(self.curr_year, self.curr_month)
        self.lbl_title.config(text=f"{self.curr_year}-{self.curr_month:02d}")

        week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for i, wd in enumerate(week_days):
            Label(self.frm_days, text=wd, width=3, fg="#aaa", bg="#222").grid(row=0, column=i)

        for r, week in enumerate(cal, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    Label(self.frm_days, text="", width=3, bg="#222").grid(row=r, column=c)
                else:
                    btn = Button(
                        self.frm_days,
                        text=f"{day:02d}",
                        width=3,
                        command=lambda d=day: self._on_select(d),
                    )
                    btn.grid(row=r, column=c, padx=1, pady=1)

    # ---------- Date select ----------
    def _on_select(self, day):
        new_date = datetime(self.curr_year, self.curr_month, day)
        self.callback(pd.Timestamp(new_date))

# ─────────────────────────────────────────────────────────────────────────────
# Calendar helpers (show / hide in UI)
# ─────────────────────────────────────────────────────────────────────────────
def _hide_calendar():
    global calendar_frame
    if calendar_frame is not None:
        calendar_frame.destroy()
        calendar_frame = None

def _show_calendar(target: str):
    """
    target: "start" 또는 "end"
    달력을 클릭된 날짜 라벨 바로 아래에 임베디드로 표시합니다.
    """
    global calendar_frame
    _hide_calendar()  # 이전 달력 숨기기

    # 초기 날짜 결정
    init = {
        "start": selected_start_date or original_min_date or pd.Timestamp.now(),
        "end":   selected_end_date   or original_max_date or pd.Timestamp.now(),
    }[target]

    # 선택 콜백
    def _cb(date_val: pd.Timestamp):
        global selected_start_date, selected_end_date
        if target == "start":
            selected_start_date = date_val
            dur_combo.set("Custom")
        else:
            selected_end_date = date_val
            dur_combo.set("Custom")
        update_period_display()
        _hide_calendar()

    # 달력 프레임 생성
    calendar_frame = CalendarFrame(frame_ctl, init.to_pydatetime(), _cb)

    # 클릭한 라벨 바로 아래에 표시
    ref_widget = start_lbl if target == "start" else end_lbl
    calendar_frame.pack(after=ref_widget, fill=X, pady=2)

# ─────────────────────────────────────────────────────────────────────────────
# 기간 표시 & 변경
# ─────────────────────────────────────────────────────────────────────────────
def update_period_by_duration(event=None):
    global selected_start_date, selected_end_date
    if original_max_date is None:
        return
    sel = dur_combo.get()
    end = original_max_date
    if sel == "All":
        selected_start_date = original_min_date
    else:
        dur_map = {
            "1 Week":  timedelta(days=7),
            "1 Month": timedelta(days=30),
            "3 Months":timedelta(days=90),
            "6 Months":timedelta(days=180),
            "1 Year":  timedelta(days=365),
        }
        if sel in dur_map:
            selected_start_date = end - dur_map[sel]
        else:  # Custom → 기존 값 유지
            if selected_start_date is None:
                selected_start_date = end - timedelta(days=30)
    selected_end_date = end
    update_period_display()
    _hide_calendar()

def update_period_display():
    if selected_start_date and selected_end_date:
        start_label_var.set(selected_start_date.strftime("%Y-%m-%d"))
        end_label_var.set(selected_end_date.strftime("%Y-%m-%d"))
    else:
        start_label_var.set("-")
        end_label_var.set("-")

# ─────────────────────────────────────────────────────────────────────────────
# 데이터 로드 / 추가
# ─────────────────────────────────────────────────────────────────────────────
def load_file():
    global df
    path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Excel", "*.xls;*.xlsx")])
    if not path:
        return
    tmp = _read_file(path)
    if tmp is None or tmp.empty:
        return

    df = tmp.reset_index(drop=True)
    _update_original_range()
    _init_gui()
    update_period_display()
    _hide_calendar()

def add_file():
    global df
    if df.empty:
        return
    path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Excel", "*.xls;*.xlsx")])
    if not path:
        return
    new = _read_file(path)
    if new is None or new.empty:
        return

    # ---------- 컬럼 중복 처리 ----------
    rename = {}
    existing = set(df.columns)
    for c in new.columns:
        if c == "date":
            continue
        if c in existing:
            rename[c] = _unique(c, existing)
        existing.add(rename.get(c, c))
    if rename:
        new = new.rename(columns=rename)

    # ---------- 날짜 기준 병합 ----------
    if "date" in df.columns and "date" in new.columns:
        df = (
            pd.merge(df, new, on="date", how="outer", sort=True)
            .sort_values("date")
            .reset_index(drop=True)
        )
    else:
        df = pd.concat([df, new], axis=1)

    _update_original_range()
    _refresh_y_boxes()
    update_period_display()
    _hide_calendar()

    add_button.config(state=NORMAL)
    plot_button.config(state=NORMAL)
    print(os.path.basename(path), "추가 완료 → 전체 컬럼:", list(df.columns))

# ─────────────────────────────────────────────────────────────────────────────
# GUI helpers
# ─────────────────────────────────────────────────────────────────────────────
def _init_gui():
    cols = list(df.columns)
    x_axis_combobox["values"] = cols
    x_axis_combobox.set("date" if "date" in cols else cols[0])
    _refresh_y_boxes()
    add_button.config(state=NORMAL)
    plot_button.config(state=NORMAL)

def _refresh_y_boxes():
    cols = list(df.columns)
    for b in y_boxes:
        b["values"] = cols

def safe_interp(s: pd.Series):
    try:
        return s.astype(float).interpolate(method="polynomial", order=3)
    except ImportError:
        print("SciPy 미설치 → 선형 보간 대체")
        return s.astype(float).interpolate(method="linear")

# ─────────────────────────────────────────────────────────────────────────────
# 앱 초기화 (Reset)
# ─────────────────────────────────────────────────────────────────────────────
def reset_app():
    """모든 상태를 처음 실행한 상태로 되돌립니다."""
    global df, selected_start_date, selected_end_date
    df = pd.DataFrame()
    _update_original_range()

    x_axis_combobox.set("")
    x_axis_combobox["values"] = []
    for b in y_boxes:
        b.set("")
        b["values"] = []

    for w in frame_graph.winfo_children():
        w.destroy()

    dur_combo.set("1 Month")
    all_data_chk.set(False)
    diff_label.config(text="")
    start_label_var.set("-")
    end_label_var.set("-")

    add_button.config(state=DISABLED)
    plot_button.config(state=DISABLED)
    _hide_calendar()
    print("앱이 초기화되었습니다.")

# ─────────────────────────────────────────────────────────────────────────────
# 그래프 그리기 (이전 로직 그대로)
# ─────────────────────────────────────────────────────────────────────────────
def _first_valid_or_none(series: pd.Series):
    if series.dropna().empty:
        return None
    return series.dropna().iloc[0]

# ─────────────────────────────────────────────
# 그래프 그리기 (Sharpe · Sortino · IR 포함)
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 그래프 그리기 (Sharpe·Sortino·IR ― 표준식)
# ─────────────────────────────────────────────
def plot_graph():
    if df.empty:
        return

    # 1) 선택 항목
    x_axis = x_axis_combobox.get()
    selected = [b.get() for i, b in enumerate(y_boxes)
                if b.get() and inc_flags[i].get()]
    if not selected:
        print("선택한 컬럼이 없습니다.")
        return

    work = df.copy()

    # 2) 기간 필터
    if x_axis == "date" and "date" in work.columns:
        if not pd.api.types.is_datetime64_any_dtype(work["date"]):
            work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date")

        if (
            not all_data_chk.get()
            and selected_start_date is not None
            and selected_end_date is not None
        ):
            work = work[(work["date"] >= selected_start_date) &
                        (work["date"] <= selected_end_date)]

    if work.empty:
        print("해당 구간에 데이터가 없습니다.")
        return

    # 3) 벤치마크(kqsm)
    bench_name = "kqsm"
    bench_r = None
    if bench_name in work.columns and pd.api.types.is_numeric_dtype(work[bench_name]):
        bench_r = work[bench_name].pct_change(fill_method=None).dropna()

    # 4) 캔버스 초기화
    for w in frame_graph.winfo_children():
        w.destroy()

    palette = cycle(COLOR_PALETTES.get(palette_combo.get(), DEFAULT_COLORS))
    fig, (ax, ax_d) = plt.subplots(
        2, 1, sharex=True,
        gridspec_kw={"height_ratios": [3, 1.2]},
    )
    ax2, ax_d2 = ax.twinx(), ax_d.twinx()

    # 5) 라인·스프레드
    for i, col in enumerate(selected):
        ser = safe_interp(work[col]) if pd.api.types.is_numeric_dtype(work[col]) else work[col]

        # Relative
        if rel_flags[selected.index(col)].get() and pd.api.types.is_numeric_dtype(ser):
            base = _first_valid_or_none(ser)
            if base not in (None, 0):
                ser = ser / base

        color = next(palette)
        lw = 2.5 if i == 0 else 1.5
        ax.plot(work[x_axis], ser, label=col, color=color, lw=lw)

        # 스프레드
        if i > 0 and pd.api.types.is_numeric_dtype(ser):
            base_ser = safe_interp(work[selected[0]])
            if rel_flags[0].get():
                b0 = _first_valid_or_none(base_ser)
                if b0 not in (None, 0):
                    base_ser = base_ser / b0
            ax_d.plot(work[x_axis], base_ser - ser, label=col, color=color, lw=1.3)

    # 6) 지표 계산 (표준식)
    rf_daily = 0.015 / 252    # 연 1.5 % 가정
    diff_txt = []

    if x_axis == "date" and not work.empty:
        diff_txt.append("[ Last ]")
        span_days = (work["date"].iloc[-1] - work["date"].iloc[0]).days
        span_years = span_days / 365.25 if span_days else 0

        for col in selected:
            if not pd.api.types.is_numeric_dtype(work[col]):
                continue

            st = _first_valid_or_none(work[col])
            ed = _first_valid_or_none(work[col].iloc[::-1])
            if st in (None, 0) or ed is None:
                continue

            tot_ret = ed / st - 1
            cagr = (ed / st) ** (1 / span_years) - 1 if span_years else 0

            r = work[col].pct_change(fill_method=None).dropna()
            if r.empty:
                continue
            excess = r - rf_daily

            # Sharpe (표본σ, ddof=1)
            sharpe = np.sqrt(252) * excess.mean() / excess.std(ddof=1)

            # Sortino (다운사이드 세미편차)
            downside_sq = np.square(np.minimum(excess, 0.0))
            semi_dev = np.sqrt(downside_sq.mean())
            sortino = np.sqrt(252) * excess.mean() / semi_dev if semi_dev else np.nan

            # Downside Risk (참고용: σ_neg, ddof=1)
            d_risk = np.sqrt(downside_sq.mean()) * np.sqrt(252)

            # Information Ratio
            ir = np.nan
            if bench_r is not None and not bench_r.empty and col != bench_name:
                active = r.align(bench_r, join="inner")[0] - bench_r
                te = active.std(ddof=1)
                ir = np.sqrt(252) * active.mean() / te if te else np.nan

            diff_txt.append(
                f"{col:>10}: Return {tot_ret*100:6.2f}% (CAGR {cagr*100:6.2f}%)\n"
                f"           Downside {d_risk*100:6.2f}% | Sharpe {sharpe:5.2f}  "
                f"Sortino {sortino:5.2f}  IR {ir:5.2f}"
            )

    # 7) 축·포맷
    ax.legend()
    ax_d.legend(loc="upper left")
    ax.grid(True, ls="--", lw=0.4)
    ax_d.grid(True, ls="--", lw=0.4)
    ax.tick_params(axis="x", rotation=45)
    ax_d.tick_params(axis="x", rotation=45)
    if x_axis == "date":
        ax.xaxis.set_major_locator(MonthLocator())
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.2f}"))
    ax_d.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.2f}"))
    ax2.set_ylim(ax.get_ylim())
    ax_d2.set_ylim(ax_d.get_ylim())

    # 8) 제목
    if x_axis == "date":
        ax.set_title(f"{', '.join(selected)} (총 {span_days}일, {span_years:.1f}년)")
    else:
        ax.set_title(', '.join(selected))

    # 9) Tk 캔버스
    canvas = FigureCanvasTkAgg(fig, master=frame_graph)
    canvas.draw()
    NavigationToolbar2Tk(canvas, frame_graph).update()
    canvas.get_tk_widget().pack(fill=BOTH, expand=YES)

    diff_label.config(text='\n'.join(diff_txt))
    _hide_calendar()



# ─────────────────────────────────────────────────────────────────────────────
# Y-axis bulk set
# ─────────────────────────────────────────────────────────────────────────────

def set_bulk():
    if df.empty:                       # ← df.empty() → df.empty 로 수정
        return
    cols = [c for c in df.columns if c != "date"]
    for i, b in enumerate(y_boxes):
        b.set(cols[i] if i < len(cols) else "")

# ─────────────────────────────────────────────────────────────────────────────
# GUI BUILD
# ─────────────────────────────────────────────────────────────────────────────
set_korean_font()
root = Tk()
root.title("Graph Plotter")

frame_ctl = Frame(root)
frame_ctl.pack(side=LEFT, padx=20, pady=20)
frame_graph = Frame(root)
frame_graph.pack(side=RIGHT, fill=BOTH, expand=YES, padx=20, pady=20)

Button(frame_ctl, text="파일 선택", command=load_file).pack(pady=10)
add_button = Button(frame_ctl, text="파일 추가", state=DISABLED, command=add_file)
add_button.pack(pady=4)

Button(frame_ctl, text="초기화", command=reset_app).pack(pady=4)

Label(frame_ctl, text="Duration:").pack(anchor="w")
DUR_OPTS = ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "All", "Custom"]
dur_combo = ttk.Combobox(frame_ctl, values=DUR_OPTS, state="readonly")
dur_combo.set("1 Month")
dur_combo.bind("<<ComboboxSelected>>", update_period_by_duration)
dur_combo.pack(fill="x", pady=2)

all_data_chk = BooleanVar()
Checkbutton(frame_ctl, text="Show all data", variable=all_data_chk).pack(anchor="w")

Label(frame_ctl, text="X-axis:").pack(anchor="w")
x_axis_combobox = ttk.Combobox(frame_ctl, state="readonly")
x_axis_combobox.pack(fill="x", pady=2)

Label(frame_ctl, text="Color Palette:").pack(anchor="w")
palette_combo = ttk.Combobox(frame_ctl, values=list(COLOR_PALETTES.keys()), state="readonly")
palette_combo.set("Bloomberg")
palette_combo.pack(fill="x", pady=2)

Label(frame_ctl, text="Start Date / End Date:").pack(anchor="w", pady=(8, 0))
start_label_var = StringVar(value="-")
end_label_var   = StringVar(value="-")
start_lbl = Label(frame_ctl, textvariable=start_label_var, fg="#00ACC1", cursor="hand2")
end_lbl   = Label(frame_ctl, textvariable=end_label_var,   fg="#00ACC1", cursor="hand2")
start_lbl.pack(anchor="w")
end_lbl.pack(anchor="w", pady=(0, 4))
start_lbl.bind("<Button-1>", lambda e: _show_calendar("start"))
end_lbl.bind("<Button-1>",   lambda e: _show_calendar("end"))

y_boxes, inc_flags, rel_flags = [], [], []
for i in range(10):
    fr = Frame(frame_ctl)
    fr.pack(fill="x", pady=2)
    Label(fr, text=f"Y{i+1}:").pack(side=LEFT)
    cbo = ttk.Combobox(fr, state="readonly")
    cbo.pack(side=LEFT, fill="x", expand=YES)
    y_boxes.append(cbo)
    inc = BooleanVar(value=True)
    Checkbutton(fr, text="Include", variable=inc).pack(side=RIGHT)
    inc_flags.append(inc)
    rel = BooleanVar(value=True)
    Checkbutton(fr, text="Relative", variable=rel).pack(side=RIGHT)
    rel_flags.append(rel)

plot_button = Button(frame_ctl, text="그래프 그리기", state=DISABLED, command=plot_graph)
plot_button.pack(pady=10)
Button(frame_ctl, text="y축 일괄 입력", command=set_bulk).pack(pady=4)

diff_label = Label(frame_ctl, fg="red", justify=LEFT)
diff_label.pack(fill="x", pady=8)

root.mainloop()
