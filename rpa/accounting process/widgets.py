"""
회계처리 분류 시스템 - 위젯 모듈
================================
DataTableFrame, AIChatPanel 등 UI 위젯 클래스
"""

import os
import tkinter as tk
import tkinter.font as tk_font
from tkinter import filedialog, messagebox
from typing import Optional, Dict, List

import customtkinter as ctk
import pandas as pd

# 상수 임포트
try:
    from config import (
        BG_COLOR, SIDEBAR_COLOR, ACCENT_COLOR,
        SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR,
        FONT_FAMILY, SUPPORTED_FILE_TYPES, ClassificationStatus
    )
except ImportError:
    # config.py가 없는 경우 기본값 사용
    BG_COLOR = "#18181C"
    SIDEBAR_COLOR = "#25262B"
    ACCENT_COLOR = "#3A76F0"
    SUCCESS_COLOR = "#50C878"
    WARNING_COLOR = "#FFB347"
    ERROR_COLOR = "#FF6B6B"
    FONT_FAMILY = "Malgun Gothic"

    SUPPORTED_FILE_TYPES = {
        "pdf": "PDF", "docx": "Word", "doc": "Word",
        "xlsx": "Excel", "xls": "Excel", "csv": "CSV",
        "png": "이미지", "jpg": "이미지", "jpeg": "이미지",
        "gif": "이미지", "bmp": "이미지", "tiff": "이미지",
        "xml": "XML", "json": "JSON", "yaml": "YAML"
    }

    class ClassificationStatus:
        PENDING = "미분류"
        EXISTING = "기존분류"
        AI_CLASSIFIED = "AI분류"
        VERIFIED = "검증완료"
        NEEDS_REVIEW = "검토필요"


class DataTableFrame(ctk.CTkFrame):
    """고성능 데이터 테이블 (ttk.Treeview 기반)"""

    def __init__(self, master, on_row_select, on_cell_edit=None, **kwargs):
        kwargs.pop('fg_color', None)
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_row_select = on_row_select
        self.on_cell_edit = on_cell_edit
        self.df: Optional[pd.DataFrame] = None
        self.selected_index: Optional[int] = None
        self.item_ids: List[str] = []
        self.current_filter: str = "all"
        self.column_mapping: Dict = {}

        self._setup_treeview()

    def _setup_treeview(self):
        """Treeview 및 스크롤바 설정"""
        import tkinter.ttk as ttk
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Custom.Treeview",
                        background="#25262B",
                        foreground="white",
                        fieldbackground="#25262B",
                        rowheight=28,
                        font=(FONT_FAMILY, 10))
        style.configure("Custom.Treeview.Heading",
                        background="#3A76F0",
                        foreground="white",
                        font=(FONT_FAMILY, 10, "bold"))
        style.map("Custom.Treeview",
                  background=[("selected", "#3A76F0")],
                  foreground=[("selected", "white")])

        style.configure("Custom.Vertical.TScrollbar",
                        background="#4A4A4A",
                        troughcolor="#25262B",
                        arrowcolor="white",
                        width=16)
        style.configure("Custom.Horizontal.TScrollbar",
                        background="#4A4A4A",
                        troughcolor="#25262B",
                        arrowcolor="white",
                        width=16)

        hsb = ttk.Scrollbar(self, orient="horizontal", style="Custom.Horizontal.TScrollbar")
        hsb.pack(side="bottom", fill="x")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical", style="Custom.Vertical.TScrollbar")
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(container, style="Custom.Treeview", selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.configure(command=self.tree.yview)
        hsb.configure(command=self.tree.xview)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.tag_configure("completed", background="#1E3A1E")
        self.tree.tag_configure("normal", background="#25262B")

        self.edit_entry = None
        self.editing_item = None
        self.editing_column = None

    def load_data(self, df: pd.DataFrame, column_mapping: Dict = None, highlighted_cells: set = None):
        """데이터프레임을 테이블에 로드"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_ids.clear()

        self.df = df.copy()
        self.column_mapping = column_mapping or {}
        self.highlighted_cells = highlighted_cells or set()
        self.highlighted_rows = {cell[0] for cell in self.highlighted_cells}

        if "분류_상태" not in self.df.columns:
            self.df["분류_상태"] = ClassificationStatus.PENDING
        if "최종_분류" not in self.df.columns:
            self.df["최종_분류"] = ""
        if "분류_근거" not in self.df.columns:
            self.df["분류_근거"] = ""
        if "사용자_입력" not in self.df.columns:
            self.df["사용자_입력"] = ""
        if "검토표시" not in self.df.columns:
            self.df["검토표시"] = ""

        existing_col = self.column_mapping.get("existing_classification_col")
        if existing_col and existing_col in self.df.columns:
            has_existing = self.df[existing_col].notna() & (self.df[existing_col].astype(str).str.strip() != "")
            self.df.loc[has_existing, "분류_상태"] = ClassificationStatus.EXISTING
            empty_final = self.df["최종_분류"].astype(str).str.strip() == ""
            copy_mask = has_existing & empty_final
            self.df.loc[copy_mask, "최종_분류"] = self.df.loc[copy_mask, existing_col].astype(str)

        if self.highlighted_rows:
            valid_rows = [r for r in self.highlighted_rows if r < len(self.df)]
            if valid_rows:
                self.df.loc[valid_rows, "검토표시"] = "★"

        columns = ["#", "검토", "상태"] + list(self.df.columns)
        self.tree["columns"] = columns
        self.tree["show"] = "headings"

        self.tree.heading("#", text="#")
        self.tree.column("#", width=45, minwidth=40, anchor="center")
        self.tree.heading("검토", text="검토")
        self.tree.column("검토", width=40, minwidth=35, anchor="center")
        self.tree.heading("상태", text="상태")
        self.tree.column("상태", width=70, minwidth=60, anchor="center")

        for col in self.df.columns:
            self.tree.heading(col, text=col)
            col_width = min(200, max(80, len(str(col)) * 10))
            self.tree.column(col, width=col_width, minwidth=60, anchor="w")

        self._refresh_display()

    def _refresh_display(self):
        """현재 필터에 따라 데이터 표시 갱신"""
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        self.item_ids.clear()

        if self.df is None:
            return

        self.tree.tag_configure("highlighted", background="#4A1E4A")
        self.tree.tag_configure("verified", background="#1E3A1E")
        self.tree.tag_configure("ai_classified", background="#1E3A3A")
        self.tree.tag_configure("existing", background="#3A3A1E")
        self.tree.tag_configure("needs_review", background="#3A1E1E")
        self.tree.tag_configure("normal", background="#25262B")

        status_col_idx = list(self.df.columns).index("분류_상태") if "분류_상태" in self.df.columns else -1
        review_col_idx = list(self.df.columns).index("검토표시") if "검토표시" in self.df.columns else -1

        for idx in range(len(self.df)):
            row = self.df.iloc[idx]
            status = str(row.iloc[status_col_idx]) if status_col_idx >= 0 else ClassificationStatus.PENDING
            review_mark = str(row.iloc[review_col_idx]) if review_col_idx >= 0 and pd.notna(row.iloc[review_col_idx]) else ""

            skip = False
            if self.current_filter == "pending" and status != ClassificationStatus.PENDING:
                skip = True
            elif self.current_filter == "classified" and status not in [ClassificationStatus.AI_CLASSIFIED, ClassificationStatus.VERIFIED]:
                skip = True
            elif self.current_filter == "existing" and status != ClassificationStatus.EXISTING:
                skip = True
            elif self.current_filter == "needs_review" and status != ClassificationStatus.NEEDS_REVIEW:
                skip = True
            elif self.current_filter == "highlighted" and idx not in self.highlighted_rows:
                skip = True

            if skip:
                self.item_ids.append(None)
                continue

            cell_values = []
            for col_idx in range(len(row)):
                v = row.iloc[col_idx]
                cell_str = str(v)[:50] if pd.notna(v) else ""
                if (idx, col_idx) in self.highlighted_cells:
                    cell_str = f"★{cell_str}"
                cell_values.append(cell_str)

            values = [idx + 1, review_mark, status] + cell_values

            is_highlighted = idx in self.highlighted_rows
            if is_highlighted:
                tag = "highlighted"
            elif status == ClassificationStatus.VERIFIED:
                tag = "verified"
            elif status == ClassificationStatus.AI_CLASSIFIED:
                tag = "ai_classified"
            elif status == ClassificationStatus.EXISTING:
                tag = "existing"
            elif status == ClassificationStatus.NEEDS_REVIEW:
                tag = "needs_review"
            else:
                tag = "normal"

            item_id = self.tree.insert("", "end", values=values, tags=(tag,))
            self.item_ids.append(item_id)

    def set_filter(self, filter_type: str):
        """필터 설정"""
        self.current_filter = filter_type
        self._refresh_display()

    def get_status_counts(self) -> Dict[str, int]:
        """상태별 건수 반환"""
        if self.df is None:
            return {"total": 0, "pending": 0, "existing": 0, "classified": 0, "verified": 0, "needs_review": 0, "highlighted": 0}

        counts = {
            "total": len(self.df),
            "pending": 0,
            "existing": 0,
            "classified": 0,
            "verified": 0,
            "needs_review": 0,
            "highlighted": len(self.highlighted_rows) if hasattr(self, 'highlighted_rows') else 0
        }

        for idx in range(len(self.df)):
            status = str(self.df.iloc[idx].get("분류_상태", ClassificationStatus.PENDING))
            if status == ClassificationStatus.PENDING:
                counts["pending"] += 1
            elif status == ClassificationStatus.EXISTING:
                counts["existing"] += 1
            elif status == ClassificationStatus.AI_CLASSIFIED:
                counts["classified"] += 1
            elif status == ClassificationStatus.VERIFIED:
                counts["verified"] += 1
            elif status == ClassificationStatus.NEEDS_REVIEW:
                counts["needs_review"] += 1

        return counts

    def _on_tree_select(self, event):
        """Treeview 선택 이벤트"""
        selection = self.tree.selection()
        if not selection:
            return

        item_id = selection[0]
        for idx, iid in enumerate(self.item_ids):
            if iid == item_id:
                self.selected_index = idx
                self.on_row_select(idx)
                break

    def _on_double_click(self, event):
        """더블클릭으로 셀 편집 시작"""
        if self.edit_entry:
            self._finish_edit()

        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        item_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)

        if not item_id or not column_id:
            return

        col_num = int(column_id.replace("#", ""))
        if col_num == 0:
            return

        columns = list(self.df.columns) if self.df is not None else []
        col_idx = col_num - 1
        if col_idx < 0 or col_idx >= len(columns):
            return

        column_name = columns[col_idx]

        readonly_columns = ["분류_상태"]
        if column_name in readonly_columns:
            return

        current_values = self.tree.item(item_id, "values")
        if col_idx >= len(current_values):
            return
        current_value = current_values[col_idx]

        bbox = self.tree.bbox(item_id, column_id)
        if not bbox:
            return

        x, y, width, height = bbox

        self.edit_entry = tk.Entry(self.tree, font=(FONT_FAMILY, 10))
        self.edit_entry.place(x=x, y=y, width=width, height=height)
        self.edit_entry.insert(0, current_value if current_value else "")
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus_set()

        self.editing_item = item_id
        self.editing_column = col_idx

        self.edit_entry.bind("<Return>", lambda e: self._finish_edit())
        self.edit_entry.bind("<Escape>", lambda e: self._cancel_edit())
        self.edit_entry.bind("<FocusOut>", lambda e: self._finish_edit())

    def _finish_edit(self):
        """편집 완료 및 값 저장"""
        if not self.edit_entry or self.editing_item is None:
            return

        new_value = self.edit_entry.get()

        row_idx = None
        for idx, iid in enumerate(self.item_ids):
            if iid == self.editing_item:
                row_idx = idx
                break

        if row_idx is not None and self.df is not None:
            col_name = list(self.df.columns)[self.editing_column]
            old_value = self.df.at[row_idx, col_name]

            if str(new_value) != str(old_value if pd.notna(old_value) else ""):
                self.df.at[row_idx, col_name] = new_value

                if col_name == "최종_분류" and new_value:
                    self.df.at[row_idx, "분류_상태"] = ClassificationStatus.VERIFIED
                    self.df.at[row_idx, "분류_근거"] = "사용자 직접 입력"

                self._update_tree_item(row_idx)

                if self.on_cell_edit:
                    self.on_cell_edit(row_idx, col_name, new_value)

        self._cleanup_edit()

    def _cancel_edit(self):
        """편집 취소"""
        self._cleanup_edit()

    def _cleanup_edit(self):
        """편집 상태 정리"""
        if self.edit_entry:
            self.edit_entry.destroy()
            self.edit_entry = None
        self.editing_item = None
        self.editing_column = None

    def _update_tree_item(self, row_idx: int):
        """단일 행의 트리뷰 표시 업데이트"""
        if row_idx >= len(self.item_ids):
            return

        item_id = self.item_ids[row_idx]
        if item_id is None:
            return

        row = self.df.iloc[row_idx]
        values = [str(v) if pd.notna(v) else "" for v in row.values]
        self.tree.item(item_id, values=values)

        status = str(row.get("분류_상태", ""))
        if status in [ClassificationStatus.AI_CLASSIFIED, ClassificationStatus.VERIFIED]:
            self.tree.item(item_id, tags=("completed",))
        else:
            self.tree.item(item_id, tags=("normal",))

    def update_row(self, idx: int, classification: str, reasoning: str, user_inputs: str = "",
                   status: str = None):
        """행 데이터 업데이트"""
        if self.df is not None and idx < len(self.df):
            self.df.at[idx, "최종_분류"] = classification
            self.df.at[idx, "분류_근거"] = reasoning
            if user_inputs:
                self.df.at[idx, "사용자_입력"] = user_inputs
            if status:
                self.df.at[idx, "분류_상태"] = status

            if idx < len(self.item_ids) and self.item_ids[idx] is not None:
                item_id = self.item_ids[idx]
                row = self.df.iloc[idx]
                current_status = str(row.get("분류_상태", ClassificationStatus.PENDING))
                review_mark = str(row.get("검토표시", "")) if pd.notna(row.get("검토표시")) else ""

                cell_values = []
                for col_idx, v in enumerate(row):
                    cell_str = str(v)[:50] if pd.notna(v) else ""
                    if hasattr(self, 'highlighted_cells') and (idx, col_idx) in self.highlighted_cells:
                        cell_str = f"★{cell_str}"
                    cell_values.append(cell_str)

                values = [idx + 1, review_mark, current_status] + cell_values

                is_highlighted = hasattr(self, 'highlighted_rows') and idx in self.highlighted_rows

                if is_highlighted:
                    tag = "highlighted"
                elif current_status == ClassificationStatus.VERIFIED:
                    tag = "verified"
                elif current_status == ClassificationStatus.AI_CLASSIFIED:
                    tag = "ai_classified"
                elif current_status == ClassificationStatus.EXISTING:
                    tag = "existing"
                elif current_status == ClassificationStatus.NEEDS_REVIEW:
                    tag = "needs_review"
                else:
                    tag = "normal"

                self.tree.item(item_id, values=values, tags=(tag,))

    def verify_row(self, idx: int):
        """행 분류 검증 완료 처리"""
        if self.df is not None and idx < len(self.df):
            self.df.at[idx, "분류_상태"] = ClassificationStatus.VERIFIED
            self._update_single_row_display(idx)

    def _update_single_row_display(self, idx: int):
        """단일 행 표시 업데이트"""
        if idx < len(self.item_ids) and self.item_ids[idx] is not None:
            item_id = self.item_ids[idx]
            row = self.df.iloc[idx]
            status = str(row.get("분류_상태", ClassificationStatus.PENDING))
            review_mark = str(row.get("검토표시", "")) if pd.notna(row.get("검토표시")) else ""

            cell_values = []
            for col_idx, v in enumerate(row):
                cell_str = str(v)[:50] if pd.notna(v) else ""
                if hasattr(self, 'highlighted_cells') and (idx, col_idx) in self.highlighted_cells:
                    cell_str = f"★{cell_str}"
                cell_values.append(cell_str)

            values = [idx + 1, review_mark, status] + cell_values

            is_highlighted = hasattr(self, 'highlighted_rows') and idx in self.highlighted_rows

            if is_highlighted:
                tag = "highlighted"
            elif status == ClassificationStatus.VERIFIED:
                tag = "verified"
            elif status == ClassificationStatus.AI_CLASSIFIED:
                tag = "ai_classified"
            elif status == ClassificationStatus.EXISTING:
                tag = "existing"
            elif status == ClassificationStatus.NEEDS_REVIEW:
                tag = "needs_review"
            else:
                tag = "normal"

            self.tree.item(item_id, values=values, tags=(tag,))

    def clear_row_classification(self, idx: int):
        """행 분류 초기화"""
        if self.df is not None and idx < len(self.df):
            self.df.at[idx, "최종_분류"] = ""
            self.df.at[idx, "분류_근거"] = ""
            self.df.at[idx, "분류_상태"] = ClassificationStatus.PENDING

            self._update_single_row_display(idx)

    def get_dataframe(self) -> Optional[pd.DataFrame]:
        return self.df

    def select_row(self, idx: int):
        """특정 행 선택"""
        if self.df is None or idx < 0 or idx >= len(self.df):
            return

        if idx < len(self.item_ids) and self.item_ids[idx] is not None:
            item_id = self.item_ids[idx]
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self.tree.see(item_id)
            self.selected_index = idx
