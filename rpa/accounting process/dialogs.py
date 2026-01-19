"""
회계처리 분류 시스템 - 다이얼로그 모듈
=============================================
파일 로드 시 컬럼 매핑, 직접 분류 입력 등의 다이얼로그를 제공합니다.
"""

from typing import List, Optional, Dict, Any
import customtkinter as ctk
from tkinter import messagebox

from config import (
    BG_COLOR, SIDEBAR_COLOR, ACCENT_COLOR,
    FONT_FAMILY
)


class ColumnMappingDialog(ctk.CTkToplevel):
    """파일 로드 시 컬럼 역할 지정 다이얼로그"""

    def __init__(self, parent, columns: List[str]):
        super().__init__(parent)
        self.title("컬럼 설정")
        self.geometry("500x400")
        self.configure(fg_color=BG_COLOR)
        self.transient(parent)
        self.grab_set()

        self.columns = columns
        self.result = None

        self._setup_ui()
        self.wait_window()

    def _setup_ui(self):
        # 제목
        ctk.CTkLabel(
            self,
            text="컬럼 역할 설정",
            font=(FONT_FAMILY, 16, "bold")
        ).pack(pady=15)

        ctk.CTkLabel(
            self,
            text="기존 계정과목 분류가 있는 컬럼을 선택하세요.\n없으면 '없음'을 선택하세요.",
            font=(FONT_FAMILY, 11),
            text_color="gray"
        ).pack(pady=(0, 15))

        # 기존 분류 컬럼 선택
        frame1 = ctk.CTkFrame(self, fg_color=SIDEBAR_COLOR)
        frame1.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            frame1,
            text="기존 계정과목 컬럼:",
            font=(FONT_FAMILY, 12),
            width=150
        ).pack(side="left", padx=10, pady=10)

        options = ["(없음)"] + self.columns
        self.existing_col_var = ctk.StringVar(value="(없음)")

        # 자동 감지: 계정과목, 계정, 분류 등의 키워드가 있으면 선택
        for col in self.columns:
            if any(kw in col for kw in ["계정", "분류", "과목", "코드"]):
                self.existing_col_var.set(col)
                break

        self.existing_col_menu = ctk.CTkOptionMenu(
            frame1,
            values=options,
            variable=self.existing_col_var,
            width=250
        )
        self.existing_col_menu.pack(side="left", padx=10, pady=10)

        # 거래처 컬럼 선택 (선택사항)
        frame2 = ctk.CTkFrame(self, fg_color=SIDEBAR_COLOR)
        frame2.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            frame2,
            text="거래처 컬럼:",
            font=(FONT_FAMILY, 12),
            width=150
        ).pack(side="left", padx=10, pady=10)

        self.vendor_col_var = ctk.StringVar(value="(없음)")
        for col in self.columns:
            if any(kw in col for kw in ["거래처", "업체", "공급자", "매입처"]):
                self.vendor_col_var.set(col)
                break

        ctk.CTkOptionMenu(
            frame2,
            values=options,
            variable=self.vendor_col_var,
            width=250
        ).pack(side="left", padx=10, pady=10)

        # 금액 컬럼 선택 (선택사항)
        frame3 = ctk.CTkFrame(self, fg_color=SIDEBAR_COLOR)
        frame3.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            frame3,
            text="금액 컬럼:",
            font=(FONT_FAMILY, 12),
            width=150
        ).pack(side="left", padx=10, pady=10)

        self.amount_col_var = ctk.StringVar(value="(없음)")
        for col in self.columns:
            if any(kw in col for kw in ["금액", "공급가", "합계", "원가", "비용"]):
                self.amount_col_var.set(col)
                break

        ctk.CTkOptionMenu(
            frame3,
            values=options,
            variable=self.amount_col_var,
            width=250
        ).pack(side="left", padx=10, pady=10)

        # 설명
        ctk.CTkLabel(
            self,
            text="* 기존 분류가 있으면 AI가 검증하고, 없으면 새로 분류합니다",
            font=(FONT_FAMILY, 10),
            text_color="gray"
        ).pack(pady=15)

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)

        ctk.CTkButton(
            btn_frame,
            text="확인",
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=ACCENT_COLOR,
            width=120,
            command=self._confirm
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="취소",
            font=(FONT_FAMILY, 12),
            fg_color="#6B7280",
            width=120,
            command=self._cancel
        ).pack(side="left", padx=10)

    def _confirm(self):
        self.result = {
            "existing_classification_col": self.existing_col_var.get() if self.existing_col_var.get() != "(없음)" else None,
            "vendor_col": self.vendor_col_var.get() if self.vendor_col_var.get() != "(없음)" else None,
            "amount_col": self.amount_col_var.get() if self.amount_col_var.get() != "(없음)" else None
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class ManualClassifyDialog(ctk.CTkToplevel):
    """직접 분류 입력 다이얼로그"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("직접 분류 입력")
        self.geometry("450x350")
        self.configure(fg_color=BG_COLOR)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self._setup_ui()
        self.wait_window()

    def _setup_ui(self):
        # 제목
        ctk.CTkLabel(
            self,
            text="계정과목 직접 입력",
            font=(FONT_FAMILY, 16, "bold")
        ).pack(pady=15)

        ctk.CTkLabel(
            self,
            text="AI 분석 대신 직접 계정과목을 입력합니다.",
            font=(FONT_FAMILY, 11),
            text_color="gray"
        ).pack(pady=(0, 15))

        # 분류 입력
        frame1 = ctk.CTkFrame(self, fg_color=SIDEBAR_COLOR)
        frame1.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            frame1,
            text="계정과목:",
            font=(FONT_FAMILY, 12),
            width=100
        ).pack(side="left", padx=10, pady=10)

        self.classification_entry = ctk.CTkEntry(
            frame1,
            font=(FONT_FAMILY, 12),
            width=280,
            placeholder_text="예: 206 기계장치, 831 지급수수료"
        )
        self.classification_entry.pack(side="left", padx=10, pady=10)

        # 근거 입력
        frame2 = ctk.CTkFrame(self, fg_color=SIDEBAR_COLOR)
        frame2.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(
            frame2,
            text="분류 근거:",
            font=(FONT_FAMILY, 12),
            width=100
        ).pack(side="left", padx=10, pady=10, anchor="n")

        self.reasoning_textbox = ctk.CTkTextbox(
            frame2,
            font=(FONT_FAMILY, 11),
            width=280,
            height=100
        )
        self.reasoning_textbox.pack(side="left", padx=10, pady=10)

        # 설명
        ctk.CTkLabel(
            self,
            text="* 입력한 분류는 '검증완료' 상태로 저장됩니다",
            font=(FONT_FAMILY, 10),
            text_color="gray"
        ).pack(pady=10)

        # 버튼
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(
            btn_frame,
            text="확인",
            font=(FONT_FAMILY, 12, "bold"),
            fg_color=ACCENT_COLOR,
            width=120,
            command=self._confirm
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="취소",
            font=(FONT_FAMILY, 12),
            fg_color="#6B7280",
            width=120,
            command=self._cancel
        ).pack(side="left", padx=10)

    def _confirm(self):
        classification = self.classification_entry.get().strip()
        reasoning = self.reasoning_textbox.get("1.0", "end").strip()

        if not classification:
            messagebox.showwarning("입력 필요", "계정과목을 입력하세요")
            return

        self.result = {
            "classification": classification,
            "reasoning": reasoning if reasoning else "직접 입력"
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
