"""
회계처리 분류 시스템 - AI 채팅 패널 모듈
========================================
AIChatPanel 클래스 - AI 회계 분류 분석 UI
"""

import os
import tkinter as tk
import tkinter.font as tk_font
from tkinter import filedialog, messagebox
from typing import Optional, Dict, List

import customtkinter as ctk

# 상수 임포트
try:
    from config import (
        BG_COLOR, SIDEBAR_COLOR, ACCENT_COLOR,
        SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR,
        FONT_FAMILY, SUPPORTED_FILE_TYPES
    )
except ImportError:
    BG_COLOR = "#18181C"
    SIDEBAR_COLOR = "#25262B"
    ACCENT_COLOR = "#3A76F0"
    SUCCESS_COLOR = "#50C878"
    WARNING_COLOR = "#FFB347"
    ERROR_COLOR = "#FF6B6B"
    FONT_FAMILY = "Malgun Gothic"
    SUPPORTED_FILE_TYPES = {
        "pdf": "PDF", "docx": "Word", "xlsx": "Excel",
        "png": "이미지", "jpg": "이미지", "jpeg": "이미지"
    }

# ManualClassifyDialog를 지연 임포트 (순환 참조 방지)
ManualClassifyDialog = None


def get_manual_classify_dialog():
    """ManualClassifyDialog 지연 로드"""
    global ManualClassifyDialog
    if ManualClassifyDialog is None:
        try:
            from dialogs import ManualClassifyDialog as MCD
            ManualClassifyDialog = MCD
        except ImportError:
            ManualClassifyDialog = None
    return ManualClassifyDialog


class AIChatPanel(ctk.CTkFrame):
    """AI 회계 분류 분석 채팅 패널"""

    def __init__(self, master, on_submit, on_reanalyze=None, on_file_analyze=None,
                 on_keep_existing=None, on_manual_classify=None, on_reset_chat=None,
                 on_save_attachment=None, on_get_attachments=None, on_start_ai=None,
                 on_approve_classification=None, on_remove_attachment=None,
                 on_link_changed=None, on_get_linked=None, **kwargs):
        super().__init__(master, fg_color=SIDEBAR_COLOR, **kwargs)
        self.on_submit = on_submit
        self.on_reanalyze = on_reanalyze
        self.on_file_analyze = on_file_analyze
        self.on_keep_existing = on_keep_existing
        self.on_manual_classify = on_manual_classify
        self.on_reset_chat = on_reset_chat
        self.on_save_attachment = on_save_attachment
        self.on_get_attachments = on_get_attachments
        self.on_start_ai = on_start_ai
        self.on_approve_classification = on_approve_classification
        self.on_remove_attachment = on_remove_attachment
        self.on_link_changed = on_link_changed
        self.on_get_linked = on_get_linked
        self.current_row_index: Optional[int] = None
        self.is_complete = False
        self.ai_started = False
        self.user_inputs: List[str] = []
        self.attached_files: List[str] = []
        self.linked_rows: List[int] = []
        self.existing_classification: Optional[str] = None
        self.message_widgets: List[Dict] = []
        self.message_counter: int = 0
        self.pending_classification: Optional[str] = None
        self.pending_reasoning: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self):
        # 헤더
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=10)

        self.title_label = ctk.CTkLabel(
            header, text="AI 회계 분류 분석",
            font=(FONT_FAMILY, 16, "bold")
        )
        self.title_label.pack(side="left")

        self.reset_chat_btn = ctk.CTkButton(
            header, text="대화 초기화", font=(FONT_FAMILY, 10),
            width=80, height=24, fg_color="#DC2626", hover_color="#B91C1C",
            command=self._reset_chat
        )
        self.reset_chat_btn.pack(side="right", padx=(5, 0))

        self.status_label = ctk.CTkLabel(
            header, text="행을 선택하세요",
            font=(FONT_FAMILY, 12), text_color="gray"
        )
        self.status_label.pack(side="right", padx=(0, 10))

        # 결과 프레임
        self.result_frame = ctk.CTkFrame(self, fg_color="#1E3A1E", corner_radius=8)
        self.result_label = ctk.CTkLabel(
            self.result_frame, text="", font=(FONT_FAMILY, 14, "bold"), wraplength=350
        )
        self.result_label.pack(padx=15, pady=10)

        # 메시지 영역
        self.message_frame = ctk.CTkScrollableFrame(self, fg_color=BG_COLOR, corner_radius=8)
        self.message_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 파일 첨부 영역
        self.file_frame = ctk.CTkFrame(self, fg_color="#1E1E24", corner_radius=8)
        self.file_frame.pack(fill="x", padx=10, pady=(0, 5))

        file_header = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        file_header.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            file_header, text="참고 문서 첨부",
            font=(FONT_FAMILY, 11, "bold"), text_color="#A0AEC0"
        ).pack(side="left")

        self.attach_btn = ctk.CTkButton(
            file_header, text="+ 파일 추가", font=(FONT_FAMILY, 10),
            width=80, height=24, fg_color=ACCENT_COLOR, command=self._attach_files
        )
        self.attach_btn.pack(side="right")

        self.files_list_frame = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        self.files_list_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.no_files_label = ctk.CTkLabel(
            self.files_list_frame, text="PDF, 이미지, Excel, Word 파일을 첨부하세요",
            font=(FONT_FAMILY, 9), text_color="gray"
        )
        self.no_files_label.pack(pady=5)

        # 연관 행 영역
        self.linked_frame = ctk.CTkFrame(self, fg_color="#1E1E24", corner_radius=8)
        self.linked_frame.pack(fill="x", padx=10, pady=(0, 5))

        linked_header = ctk.CTkFrame(self.linked_frame, fg_color="transparent")
        linked_header.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            linked_header, text="연관 거래 연결",
            font=(FONT_FAMILY, 11, "bold"), text_color="#A0AEC0"
        ).pack(side="left")

        self.link_btn = ctk.CTkButton(
            linked_header, text="+ 행 연결", font=(FONT_FAMILY, 10),
            width=80, height=24, fg_color="#6B7280", command=self._link_rows
        )
        self.link_btn.pack(side="right")

        self.linked_list_frame = ctk.CTkFrame(self.linked_frame, fg_color="transparent")
        self.linked_list_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.no_linked_label = ctk.CTkLabel(
            self.linked_list_frame, text="계약금/잔금 등 연관된 거래가 있으면 연결하세요",
            font=(FONT_FAMILY, 9), text_color="gray"
        )
        self.no_linked_label.pack(pady=5)

        # 입력 영역
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.input_textbox = ctk.CTkTextbox(
            self.input_frame, height=60, font=(FONT_FAMILY, 12), wrap="word"
        )
        self.input_textbox.pack(fill="x", pady=(0, 5))

        btn_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.start_ai_btn = ctk.CTkButton(
            btn_frame, text="AI 분석 시작", font=(FONT_FAMILY, 11, "bold"),
            width=110, fg_color="#8B5CF6", hover_color="#7C3AED",
            command=self._start_ai_analysis
        )
        self.start_ai_btn.pack(side="left", padx=(0, 5))

        self.submit_btn = ctk.CTkButton(
            btn_frame, text="전송", font=(FONT_FAMILY, 11, "bold"),
            fg_color=ACCENT_COLOR, command=self._submit
        )
        self.submit_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.manual_classify_btn = ctk.CTkButton(
            btn_frame, text="직접 입력", font=(FONT_FAMILY, 11),
            width=80, fg_color="#10B981", command=self._manual_classify
        )
        self.manual_classify_btn.pack(side="left")

        # 승인 버튼 프레임
        self.approval_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")

        self.approve_btn = ctk.CTkButton(
            self.approval_frame, text="✓ 분류 승인", font=(FONT_FAMILY, 12, "bold"),
            fg_color=SUCCESS_COLOR, hover_color="#2E7D32", height=40,
            command=self._approve_classification
        )
        self.approve_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.reject_btn = ctk.CTkButton(
            self.approval_frame, text="✗ 다시 분석", font=(FONT_FAMILY, 12),
            fg_color="#6B7280", hover_color="#4B5563", height=40,
            command=self._reject_classification
        )
        self.reject_btn.pack(side="left", fill="x", expand=True)

    def set_row(self, idx: int, row_data: str, is_reanalyze: bool = False,
                existing_classification: str = None, existing_status: str = None):
        """새로운 행 선택 시"""
        self.current_row_index = idx
        self.is_complete = False
        self.ai_started = False
        self.user_inputs = []
        self.attached_files = []
        self.linked_rows = []
        self.existing_classification = existing_classification
        self.message_widgets = []
        self.message_counter = 0
        self.pending_classification = None
        self.pending_reasoning = None
        self.status_label.configure(text=f"행 #{idx + 1}", text_color=WARNING_COLOR)
        self.result_frame.pack_forget()
        self.approval_frame.pack_forget()

        if hasattr(self, 'keep_existing_btn'):
            self.keep_existing_btn.pack_forget()
        if hasattr(self, 'reanalyze_btn'):
            self.reanalyze_btn.pack_forget()

        self.input_textbox.configure(state="normal")
        self.submit_btn.configure(state="normal", text="전송")
        self.start_ai_btn.configure(state="normal")
        self.attach_btn.configure(state="normal")
        self.link_btn.configure(state="normal")

        for widget in self.message_frame.winfo_children():
            widget.destroy()

        # 기존 첨부파일 로드
        if self.on_get_attachments:
            existing_attachments = self.on_get_attachments(idx)
            if existing_attachments:
                for att in existing_attachments:
                    saved_path = att.get('saved_path', '')
                    if saved_path and os.path.exists(saved_path):
                        self.attached_files.append(saved_path)

        # 기존 연관 거래 로드
        if self.on_get_linked:
            existing_links = self.on_get_linked(idx)
            if existing_links:
                self.linked_rows = existing_links.copy()

        self._refresh_files_list()
        self._refresh_linked_list()

        if is_reanalyze:
            self.add_message("System", "재분석을 시작합니다. 이전 분류가 초기화되었습니다.")

        if existing_classification and existing_status == "기존분류":
            self.add_message("System",
                f"이 항목에는 기존 분류가 있습니다:\n\n"
                f"  기존 분류: {existing_classification}\n\n"
                f"AI 검증을 진행하거나, '기존분류 유지' 버튼을 클릭하세요."
            )
            if not hasattr(self, 'keep_existing_btn'):
                self.keep_existing_btn = ctk.CTkButton(
                    self.input_frame, text="기존분류 유지 (검증완료)",
                    font=(FONT_FAMILY, 11), fg_color="#F59E0B", text_color="black",
                    command=self._keep_existing
                )
            self.keep_existing_btn.pack(fill="x", pady=(5, 0))

    def show_initial_suggestions(self, suggestions: Dict):
        """초기 분류 제안 표시"""
        status = suggestions.get("status", "need_info")
        primary = suggestions.get("primary", "")
        options = suggestions.get("options", [])
        available_info = suggestions.get("available_info", [])
        missing_info = suggestions.get("missing_info", [])
        reason = suggestions.get("reason", "")
        decision_step = suggestions.get("decision_step", "")
        required_questions = suggestions.get("required_questions", [])
        confidence_score = suggestions.get("confidence_score", 0.5)

        suggest_frame = ctk.CTkFrame(self.message_frame, fg_color="#1E293B", corner_radius=8)
        suggest_frame.pack(fill="x", padx=5, pady=5)

        header_frame = ctk.CTkFrame(suggest_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))

        if status == "confident":
            ctk.CTkLabel(header_frame, text="✓ 분류 제안",
                font=(FONT_FAMILY, 11, "bold"), text_color=SUCCESS_COLOR).pack(side="left")
            ctk.CTkLabel(header_frame, text=f"[정보 충분 - 신뢰도 {int(confidence_score*100)}%]",
                font=(FONT_FAMILY, 9), text_color=SUCCESS_COLOR).pack(side="left", padx=10)

            if available_info:
                info_frame = ctk.CTkFrame(suggest_frame, fg_color="#064E3B", corner_radius=5)
                info_frame.pack(fill="x", padx=10, pady=(5, 5))
                ctk.CTkLabel(info_frame, text=f"확인된 정보: {', '.join(available_info[:5])}",
                    font=(FONT_FAMILY, 9), text_color="#6EE7B7").pack(anchor="w", padx=8, pady=5)

            ctk.CTkLabel(suggest_frame, text=f"추천 계정과목: {primary}",
                font=(FONT_FAMILY, 12, "bold"), text_color="white").pack(anchor="w", padx=10, pady=5)

        elif status == "discretionary":
            ctk.CTkLabel(header_frame, text="◈ 분류 제안",
                font=(FONT_FAMILY, 11, "bold"), text_color="#A78BFA").pack(side="left")
            ctk.CTkLabel(header_frame, text="[회사 재량 선택]",
                font=(FONT_FAMILY, 9), text_color="#A78BFA").pack(side="left", padx=10)

            if available_info:
                info_frame = ctk.CTkFrame(suggest_frame, fg_color="#312E81", corner_radius=5)
                info_frame.pack(fill="x", padx=10, pady=(5, 5))
                ctk.CTkLabel(info_frame, text=f"확인된 정보: {', '.join(available_info[:5])}",
                    font=(FONT_FAMILY, 9), text_color="#C4B5FD").pack(anchor="w", padx=8, pady=5)

            ctk.CTkLabel(suggest_frame, text="회사의 회계정책에 따라 선택 가능한 계정과목입니다:",
                font=(FONT_FAMILY, 10), text_color="white").pack(anchor="w", padx=10, pady=(5, 2))

            self._create_options_buttons(suggest_frame, options, "#A78BFA")

        else:  # need_info
            ctk.CTkLabel(header_frame, text="⚠ 분류 제안",
                font=(FONT_FAMILY, 11, "bold"), text_color=WARNING_COLOR).pack(side="left")
            ctk.CTkLabel(header_frame, text=f"[추가 정보 필요 - 신뢰도 {int(confidence_score*100)}%]",
                font=(FONT_FAMILY, 9), text_color=WARNING_COLOR).pack(side="left", padx=10)

            if available_info:
                avail_frame = ctk.CTkFrame(suggest_frame, fg_color="#1E3A5F", corner_radius=5)
                avail_frame.pack(fill="x", padx=10, pady=(5, 3))
                ctk.CTkLabel(avail_frame, text="✓ 확인된 정보:",
                    font=(FONT_FAMILY, 10, "bold"), text_color="#60A5FA").pack(anchor="w", padx=8, pady=(5, 2))
                ctk.CTkLabel(avail_frame, text=f"  {', '.join(available_info[:5])}",
                    font=(FONT_FAMILY, 9), text_color="#93C5FD").pack(anchor="w", padx=8, pady=(0, 5))

            if missing_info:
                miss_frame = ctk.CTkFrame(suggest_frame, fg_color="#7C2D12", corner_radius=5)
                miss_frame.pack(fill="x", padx=10, pady=(3, 5))
                ctk.CTkLabel(miss_frame, text="✗ 부족한 정보:",
                    font=(FONT_FAMILY, 10, "bold"), text_color="#FED7AA").pack(anchor="w", padx=8, pady=(5, 2))
                for info in missing_info[:5]:
                    ctk.CTkLabel(miss_frame, text=f"  • {info}",
                        font=(FONT_FAMILY, 10), text_color="white").pack(anchor="w", padx=8, pady=1)

            if required_questions:
                self._create_questions_section(suggest_frame, required_questions)

            if options:
                ctk.CTkLabel(suggest_frame, text="📋 현재 정보로 가능한 분류 (클릭하여 선택):",
                    font=(FONT_FAMILY, 10, "bold"), text_color="white").pack(anchor="w", padx=10, pady=(5, 3))
                self._create_options_buttons(suggest_frame, options, "#60A5FA")
            else:
                ctk.CTkLabel(suggest_frame, text="💡 위 질문에 답변하면 정확한 분류가 가능합니다.",
                    font=(FONT_FAMILY, 10), text_color="#9CA3AF").pack(anchor="w", padx=10, pady=5)

        if reason:
            reason_frame = ctk.CTkFrame(suggest_frame, fg_color="#0F172A", corner_radius=3)
            reason_frame.pack(fill="x", padx=10, pady=(5, 10))
            ctk.CTkLabel(reason_frame, text=f"근거: {reason}",
                font=(FONT_FAMILY, 9), text_color="gray", wraplength=350, justify="left"
            ).pack(anchor="w", padx=8, pady=5)

        if decision_step:
            ctk.CTkLabel(suggest_frame, text=f"(의사결정 트리: {decision_step})",
                font=(FONT_FAMILY, 8), text_color="#6B7280").pack(anchor="e", padx=10, pady=(0, 5))

    def _create_options_buttons(self, parent, options, text_color):
        """옵션 버튼 생성"""
        options_frame = ctk.CTkFrame(parent, fg_color="#374151", corner_radius=5)
        options_frame.pack(fill="x", padx=10, pady=5)

        for i, opt in enumerate(options[:5]):
            opt_text = opt if isinstance(opt, str) else opt.get("account", "")
            opt_cond = "" if isinstance(opt, str) else opt.get("conditions", "")
            opt_desc = "" if isinstance(opt, str) else opt.get("description", "")

            opt_btn_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
            opt_btn_frame.pack(fill="x", pady=2)

            opt_btn = ctk.CTkButton(
                opt_btn_frame, text=f"  {i+1}. {opt_text}", font=(FONT_FAMILY, 10),
                fg_color="transparent", hover_color="#4B5563", text_color=text_color,
                anchor="w", height=24, command=lambda acc=opt_text: self._quick_select_option(acc)
            )
            opt_btn.pack(side="left", fill="x", expand=True, padx=5)

            condition_text = opt_cond or opt_desc
            if condition_text:
                ctk.CTkLabel(options_frame, text=f"     ({condition_text})",
                    font=(FONT_FAMILY, 9), text_color="#9CA3AF").pack(anchor="w", padx=10)

    def _create_questions_section(self, parent, questions):
        """질문 섹션 생성"""
        q_frame = ctk.CTkFrame(parent, fg_color="#1E40AF", corner_radius=5)
        q_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(q_frame, text="❓ 아래 질문에 답변해 주세요:",
            font=(FONT_FAMILY, 10, "bold"), text_color="#BFDBFE").pack(anchor="w", padx=8, pady=(8, 5))

        for q_idx, q in enumerate(questions[:3]):
            q_text = q.get("question", "") if isinstance(q, dict) else str(q)
            q_options = q.get("options", []) if isinstance(q, dict) else []
            q_impact = q.get("impact", "") if isinstance(q, dict) else ""

            question_frame = ctk.CTkFrame(q_frame, fg_color="#1E3A8A", corner_radius=4)
            question_frame.pack(fill="x", padx=8, pady=3)

            ctk.CTkLabel(question_frame, text=f"Q{q_idx+1}. {q_text}",
                font=(FONT_FAMILY, 10), text_color="white", wraplength=340, justify="left"
            ).pack(anchor="w", padx=8, pady=(5, 3))

            if q_options:
                btn_frame = ctk.CTkFrame(question_frame, fg_color="transparent")
                btn_frame.pack(fill="x", padx=8, pady=(0, 5))

                for opt in q_options[:4]:
                    opt_btn = ctk.CTkButton(
                        btn_frame, text=opt, font=(FONT_FAMILY, 9),
                        fg_color="#3B82F6", hover_color="#2563EB", text_color="white",
                        height=26, corner_radius=4,
                        command=lambda q=q_text, a=opt: self._answer_question(q, a)
                    )
                    opt_btn.pack(side="left", padx=2, pady=2)

            if q_impact:
                ctk.CTkLabel(question_frame, text=f"→ {q_impact}",
                    font=(FONT_FAMILY, 8), text_color="#93C5FD").pack(anchor="w", padx=8, pady=(0, 5))

    def _answer_question(self, question: str, answer: str):
        """질문 답변 처리"""
        answer_text = f"[{answer}]"
        current_text = self.input_textbox.get("1.0", "end-1c").strip()
        new_text = f"{current_text}\n{answer_text}" if current_text else answer_text
        self.input_textbox.delete("1.0", "end")
        self.input_textbox.insert("1.0", new_text)
        self.add_message("User", f"답변: {answer}")

    def _attach_files(self):
        """파일 첨부"""
        if self.current_row_index is None:
            messagebox.showinfo("안내", "먼저 행을 선택하세요.")
            return

        filetypes = [
            ("지원 파일", "*.pdf *.png *.jpg *.jpeg *.xlsx *.xls *.csv *.docx *.doc *.xml *.json"),
            ("모든 파일", "*.*")
        ]

        files = filedialog.askopenfilenames(filetypes=filetypes)
        if files:
            saved_count = 0
            for f in files:
                if f not in self.attached_files:
                    if self.on_save_attachment:
                        saved_path = self.on_save_attachment(self.current_row_index, f)
                        if saved_path:
                            self.attached_files.append(f)
                            saved_count += 1
                    else:
                        self.attached_files.append(f)
                        saved_count += 1

            if saved_count > 0:
                self._refresh_files_list()
                self.add_message("System", f"첨부파일 {saved_count}개가 프로젝트에 저장되었습니다.")

    def _refresh_files_list(self):
        """파일 목록 갱신"""
        for widget in self.files_list_frame.winfo_children():
            widget.destroy()

        if not self.attached_files:
            self.no_files_label = ctk.CTkLabel(
                self.files_list_frame, text="PDF, 이미지, Excel, Word 파일을 첨부하세요",
                font=(FONT_FAMILY, 9), text_color="gray"
            )
            self.no_files_label.pack(pady=5)
        else:
            for file_path in self.attached_files:
                self._create_file_chip(file_path)

    def _create_file_chip(self, file_path: str):
        """파일 칩 생성"""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower().lstrip('.')
        file_type = SUPPORTED_FILE_TYPES.get(ext, "파일")

        chip_frame = ctk.CTkFrame(self.files_list_frame, fg_color="#374151", corner_radius=4)
        chip_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(chip_frame, text=f"[{file_type}]", font=(FONT_FAMILY, 9),
            text_color="#60A5FA", width=60).pack(side="left", padx=5)

        ctk.CTkLabel(chip_frame, text=filename[:25] + "..." if len(filename) > 25 else filename,
            font=(FONT_FAMILY, 9), text_color="white").pack(side="left", fill="x", expand=True)

        ctk.CTkButton(chip_frame, text="X", width=20, height=20, font=(FONT_FAMILY, 9),
            fg_color="transparent", hover_color=ERROR_COLOR,
            command=lambda p=file_path: self._remove_file(p)).pack(side="right", padx=2)

    def _remove_file(self, file_path: str):
        """파일 제거"""
        if file_path in self.attached_files:
            file_index = self.attached_files.index(file_path)
            if self.on_remove_attachment and self.current_row_index is not None:
                success = self.on_remove_attachment(self.current_row_index, file_index)
                if success:
                    self.attached_files.remove(file_path)
                    self._refresh_files_list()
                    self.add_message("System", f"첨부파일 '{os.path.basename(file_path)}'이(가) 삭제되었습니다.")
            else:
                self.attached_files.remove(file_path)
                self._refresh_files_list()

    def _link_rows(self):
        """연관 행 연결"""
        if self.current_row_index is None:
            return

        dialog = ctk.CTkInputDialog(
            text="연결할 행 번호를 입력하세요\n(쉼표로 구분, 예: 3, 5, 7)",
            title="연관 거래 연결"
        )
        result = dialog.get_input()

        if result:
            try:
                rows = [int(r.strip()) - 1 for r in result.split(",")]
                new_links = []
                for r in rows:
                    if r >= 0 and r != self.current_row_index and r not in self.linked_rows:
                        self.linked_rows.append(r)
                        new_links.append(r)
                self._refresh_linked_list()

                if self.on_link_changed and new_links:
                    self.on_link_changed(self.current_row_index, self.linked_rows.copy())
                    self.add_message("System", f"연관 거래 연결이 저장되었습니다: 행 {[r+1 for r in new_links]}")
            except ValueError:
                messagebox.showerror("오류", "올바른 행 번호를 입력하세요")

    def _refresh_linked_list(self):
        """연관 행 목록 갱신"""
        for widget in self.linked_list_frame.winfo_children():
            widget.destroy()

        if not self.linked_rows:
            self.no_linked_label = ctk.CTkLabel(
                self.linked_list_frame, text="계약금/잔금 등 연관된 거래가 있으면 연결하세요",
                font=(FONT_FAMILY, 9), text_color="gray"
            )
            self.no_linked_label.pack(pady=5)
        else:
            for row_idx in self.linked_rows:
                self._create_linked_chip(row_idx)

    def _create_linked_chip(self, row_idx: int):
        """연관 행 칩 생성"""
        chip_frame = ctk.CTkFrame(self.linked_list_frame, fg_color="#374151", corner_radius=4)
        chip_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(chip_frame, text=f"행 #{row_idx + 1}",
            font=(FONT_FAMILY, 10), text_color="#F59E0B").pack(side="left", padx=10)

        ctk.CTkButton(chip_frame, text="X", width=20, height=20, font=(FONT_FAMILY, 9),
            fg_color="transparent", hover_color=ERROR_COLOR,
            command=lambda r=row_idx: self._remove_linked(r)).pack(side="right", padx=2)

    def _remove_linked(self, row_idx: int):
        """연관 행 제거"""
        if row_idx in self.linked_rows:
            self.linked_rows.remove(row_idx)
            self._refresh_linked_list()

            if self.on_link_changed and self.current_row_index is not None:
                self.on_link_changed(self.current_row_index, self.linked_rows.copy())
                self.add_message("System", f"행 #{row_idx + 1} 연결이 해제되었습니다.")

    def get_attached_files(self) -> List[str]:
        return self.attached_files.copy()

    def get_linked_rows(self) -> List[int]:
        return self.linked_rows.copy()

    def add_message(self, sender: str, text: str, is_question: bool = False):
        """메시지 추가"""
        if sender == "AI":
            bg = "#2D3748"
            text_color = "white"
        elif sender == "User":
            bg = ACCENT_COLOR
            text_color = "white"
        else:
            bg = "#374151"
            text_color = "#A0AEC0"

        msg_id = self.message_counter
        self.message_counter += 1

        msg_frame = ctk.CTkFrame(self.message_frame, fg_color=bg, corner_radius=8)
        msg_frame.pack(fill="x", pady=4, padx=4)

        self.message_widgets.append({"id": msg_id, "frame": msg_frame, "sender": sender, "text": text})

        header_frame = ctk.CTkFrame(msg_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(header_frame, text=sender, font=(FONT_FAMILY, 10, "bold"),
            text_color=text_color).pack(side="left")

        def delete_this_message(mid=msg_id):
            if messagebox.askyesno("메시지 삭제", "이 메시지를 삭제하시겠습니까?"):
                self.delete_message(mid)

        ctk.CTkButton(header_frame, text="✕", font=(FONT_FAMILY, 9), width=24, height=18,
            fg_color="transparent", hover_color="#DC2626", text_color="#9CA3AF",
            command=delete_this_message).pack(side="right", padx=(5, 0))

        def copy_text():
            self.clipboard_clear()
            self.clipboard_append(text)
            copy_btn.configure(text="복사됨!")
            self.after(1000, lambda: copy_btn.configure(text="복사"))

        copy_btn = ctk.CTkButton(header_frame, text="복사", font=(FONT_FAMILY, 9),
            width=40, height=18, fg_color="transparent", hover_color="#4A5568", command=copy_text)
        copy_btn.pack(side="right")

        text_widget = tk.Text(msg_frame, font=(FONT_FAMILY, 11), fg=text_color, bg=bg,
            wrap="word", height=1, relief="flat", borderwidth=0, highlightthickness=0, cursor="arrow")
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")
        text_widget.pack(fill="x", padx=10, pady=(2, 8))

        def adjust_height(event=None):
            text_widget.update_idletasks()
            num_lines = int(text_widget.index('end-1c').split('.')[0])
            widget_width = text_widget.winfo_width()
            if widget_width > 1:
                font = tk_font.Font(font=text_widget.cget("font"))
                avg_char_width = font.measure("가")
                chars_per_line = max(widget_width // avg_char_width, 1)
                total_lines = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in text.split('\n'))
                text_widget.configure(height=max(total_lines, 1))
            else:
                lines = text.count('\n') + 1
                chars = len(text)
                text_widget.configure(height=max(lines, chars // 40 + 1))

        text_widget.bind("<Configure>", adjust_height)
        self.after(10, adjust_height)

    def show_complete(self, classification: str, reasoning: str):
        """분류 완료 표시"""
        self.is_complete = True
        self.status_label.configure(text="분류 완료", text_color=SUCCESS_COLOR)
        self.approval_frame.pack_forget()

        self.result_frame.pack_forget()
        self.result_label.configure(text=f"최종 분류: {classification}")
        self.message_frame.pack_forget()
        self.result_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.message_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.input_textbox.configure(state="disabled")
        self.submit_btn.configure(state="disabled")
        self.start_ai_btn.configure(state="disabled")
        self.attach_btn.configure(state="disabled")
        self.link_btn.configure(state="disabled")

        if not hasattr(self, 'reanalyze_btn'):
            self.reanalyze_btn = ctk.CTkButton(
                self.input_frame, text="재분석 (수정)", font=(FONT_FAMILY, 12),
                fg_color=WARNING_COLOR, text_color="black", command=self._reanalyze
            )
        self.reanalyze_btn.pack(fill="x", pady=(5, 0))

        self.add_message("System", f"✓ 분류가 완료되었습니다.\n\n분류: {classification}\n근거: {reasoning}")

    def _reanalyze(self):
        if self.on_reanalyze and self.current_row_index is not None:
            self.on_reanalyze(self.current_row_index)

    def _keep_existing(self):
        if self.on_keep_existing and self.current_row_index is not None:
            self.on_keep_existing(self.current_row_index, self.existing_classification)

    def _quick_select_option(self, account: str):
        """옵션 빠른 선택"""
        if self.current_row_index is None:
            return

        if messagebox.askyesno("분류 선택 확인",
            f"'{account}'로 분류하시겠습니까?\n\n이 분류를 선택하면 해당 항목이 즉시 적용됩니다."):
            self.input_textbox.delete("1.0", "end")
            self.input_textbox.insert("1.0", f"이 항목을 '{account}'로 분류합니다.")
            self.add_message("User", f"선택한 분류: {account}")

            self.pending_classification = account
            self.pending_reasoning = "사용자 직접 선택"

            if hasattr(self, 'approve_btn'):
                self.approve_btn.pack(fill="x", pady=(5, 0))
                self.approve_btn.configure(text=f"✓ '{account}' 승인", state="normal")

            self.add_message("System",
                f"'{account}'가 선택되었습니다.\n\n"
                f"'승인' 버튼을 클릭하면 분류가 확정됩니다.\n"
                f"다른 정보를 추가하려면 입력창에 작성해주세요."
            )

    def _start_ai_analysis(self):
        if self.current_row_index is None:
            return
        self.ai_started = True
        self.start_ai_btn.configure(state="disabled", text="분석 중...")
        if self.on_start_ai:
            self.on_start_ai(self.current_row_index)

    def _manual_classify(self):
        """직접 분류 입력"""
        if self.current_row_index is None:
            return

        MCD = get_manual_classify_dialog()
        if MCD:
            dialog = MCD(self)
            if dialog.result:
                classification = dialog.result.get("classification", "")
                reasoning = dialog.result.get("reasoning", "")
                if classification and self.on_manual_classify:
                    self.on_manual_classify(self.current_row_index, classification, reasoning)
        else:
            # Fallback: 간단한 입력 다이얼로그
            dialog = ctk.CTkInputDialog(text="계정과목을 입력하세요:", title="직접 분류 입력")
            classification = dialog.get_input()
            if classification and self.on_manual_classify:
                self.on_manual_classify(self.current_row_index, classification, "사용자 직접 입력")

    def get_user_inputs_text(self) -> str:
        return " | ".join(self.user_inputs) if self.user_inputs else ""

    def show_loading(self, loading: bool):
        """로딩 상태 표시"""
        if loading:
            self.submit_btn.configure(text="분석 중...", state="disabled")
            self.start_ai_btn.configure(state="disabled", text="분석 중...")
            self.status_label.configure(text="AI 분석 중...", text_color="#F59E0B")
            self._loading = True
            self._loading_dots = 0
            self._animate_loading()
        else:
            self._loading = False
            self.submit_btn.configure(text="전송", state="normal")
            self.start_ai_btn.configure(state="disabled", text="분석 시작됨")
            if self.current_row_index is not None:
                self.status_label.configure(text=f"행 #{self.current_row_index + 1}", text_color="#A0AEC0")

    def _animate_loading(self):
        if not getattr(self, '_loading', False):
            return
        dots = "." * (self._loading_dots % 4)
        self.status_label.configure(text=f"AI 분석 중{dots}")
        self._loading_dots += 1
        self.after(500, self._animate_loading)

    def _submit(self):
        """답변 제출"""
        if self.is_complete or self.current_row_index is None:
            return

        text = self.input_textbox.get("1.0", "end").strip()
        has_files = len(self.attached_files) > 0

        if not text and not has_files:
            return

        if not self.ai_started:
            self.ai_started = True
            self.add_message("System", "AI 분석을 시작합니다...")
            self.start_ai_btn.configure(state="disabled", text="분석 중...")

        self.approval_frame.pack_forget()
        self.pending_classification = None
        self.pending_reasoning = None

        user_message_parts = []
        if text:
            user_message_parts.append(text)
            self.user_inputs.append(text)

        if has_files:
            file_names = [os.path.basename(f) for f in self.attached_files]
            user_message_parts.append(f"[첨부파일: {', '.join(file_names)}]")

        self.input_textbox.delete("1.0", "end")

        if user_message_parts:
            self.add_message("User", "\n".join(user_message_parts))

        self.on_submit(self.current_row_index, text, self.attached_files.copy())

    def _approve_classification(self):
        """분류 승인"""
        if self.pending_classification and self.current_row_index is not None:
            self.approval_frame.pack_forget()

            if self.on_approve_classification:
                self.on_approve_classification(
                    self.current_row_index,
                    self.pending_classification,
                    self.pending_reasoning,
                    getattr(self, 'pending_is_new_case', False),
                    getattr(self, 'pending_new_case_suggestion', "")
                )

            self.show_complete(self.pending_classification, self.pending_reasoning)

            self.pending_classification = None
            self.pending_reasoning = None
            self.pending_is_new_case = False
            self.pending_new_case_suggestion = ""

    def _reject_classification(self):
        """분류 거절"""
        self.approval_frame.pack_forget()
        self.pending_classification = None
        self.pending_reasoning = None
        self.add_message("System", "추가 정보를 입력하거나, 직접 분류를 입력해주세요.")

    def show_classification_recommendation(self, classification: str, reasoning: str,
                                           is_new_case: bool = False, new_case_suggestion: str = ""):
        """분류 추천 표시"""
        self.pending_classification = classification
        self.pending_reasoning = reasoning
        self.pending_is_new_case = is_new_case
        self.pending_new_case_suggestion = new_case_suggestion

        recommendation_msg = f"📋 AI 추천 분류:\n\n  {classification}\n\n📝 근거:\n  {reasoning}"
        self.add_message("AI", recommendation_msg)

        if is_new_case and new_case_suggestion:
            self.add_message("System",
                f"💡 이 거래는 기존 지침에 없는 새로운 케이스입니다.\n승인 시 실무지침에 추가할 수 있습니다.")

        self.approval_frame.pack(fill="x", pady=(10, 0))

    def _reset_chat(self):
        """대화 초기화"""
        if self.current_row_index is None:
            messagebox.showinfo("안내", "먼저 행을 선택하세요.")
            return

        if not messagebox.askyesno("대화 초기화",
            f"행 #{self.current_row_index + 1}의 대화 내역을 모두 삭제하시겠습니까?\n"
            "분류 결과는 유지되지만, 대화 기록은 삭제됩니다."):
            return

        for widget in self.message_frame.winfo_children():
            widget.destroy()
        self.message_widgets.clear()
        self.message_counter = 0
        self.user_inputs = []

        if self.on_reset_chat and self.current_row_index is not None:
            self.on_reset_chat(self.current_row_index)

        self.add_message("System", "대화 내역이 초기화되었습니다. 다시 분석을 시작할 수 있습니다.")

        self.is_complete = False
        self.ai_started = False
        self.pending_classification = None
        self.pending_reasoning = None
        self.input_textbox.configure(state="normal")
        self.submit_btn.configure(state="normal", text="전송")
        self.start_ai_btn.configure(state="normal", text="AI 분석 시작")
        self.status_label.configure(text=f"행 #{self.current_row_index + 1} 대화 초기화됨", text_color=WARNING_COLOR)

        self.approval_frame.pack_forget()
        if hasattr(self, 'reanalyze_btn'):
            self.reanalyze_btn.pack_forget()

    def delete_message(self, message_id: int):
        """메시지 삭제"""
        for i, msg_info in enumerate(self.message_widgets):
            if msg_info.get("id") == message_id:
                frame = msg_info.get("frame")
                if frame:
                    frame.destroy()
                self.message_widgets.pop(i)
                if self.on_reset_chat and self.current_row_index is not None:
                    self.on_reset_chat(self.current_row_index, delete_index=i)
                break

    def clear(self):
        """패널 초기화"""
        self.current_row_index = None
        self.is_complete = False
        self.ai_started = False
        self.user_inputs = []
        self.attached_files = []
        self.linked_rows = []
        self.pending_classification = None
        self.pending_reasoning = None
        self.status_label.configure(text="행을 선택하세요", text_color="gray")
        self.result_frame.pack_forget()
        self.approval_frame.pack_forget()

        if hasattr(self, 'reanalyze_btn'):
            self.reanalyze_btn.pack_forget()

        self.input_textbox.configure(state="normal")
        self.input_textbox.delete("1.0", "end")
        self.submit_btn.configure(state="normal", text="전송")
        self.start_ai_btn.configure(state="normal", text="AI 분석 시작")
        self.attach_btn.configure(state="normal")
        self.link_btn.configure(state="normal")

        self._refresh_files_list()
        self._refresh_linked_list()

        for widget in self.message_frame.winfo_children():
            widget.destroy()
