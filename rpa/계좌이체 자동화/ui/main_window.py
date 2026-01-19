# -*- coding: utf-8 -*-
"""
메인 윈도우 - Wehago 스크래퍼 + AP List 업데이트
"""

import threading
import webbrowser
from pathlib import Path
from typing import List, Tuple

import tkinter as tk
from tkinter import ttk, messagebox

import pandas as pd

from config import BASE_DIR, DATA_DIR, UI_BASE_WIDTH, LINKS
from services.wehago_scraper import WehagoScraperService, DocumentInfo
from ui.update_aplist_frame import UpdateAPListFrame


class WehagoScraperWindow(tk.Tk):
    """메인 윈도우 클래스"""

    def __init__(self):
        super().__init__()
        self._show_start_popup()
        self.title("Wehago 자동화 + AP List")

        self.scraper = WehagoScraperService()
        self.rows: List[Tuple[str, str, str, str]] = []
        self.bodies: List[str] = []
        self.ap_frame = None

        self._setup_window()
        self._build_ui()
        self._bind_shortcuts()

    def _bind_shortcuts(self):
        """단축키 바인딩"""
        self.bind("<Control-period>", lambda e: self.collect_full())

    def _setup_window(self):
        """윈도우 초기 설정"""
        self.update_idletasks()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{UI_BASE_WIDTH}x{screen_h - 100}+0+0")

    def _show_start_popup(self):
        """시작 안내 팝업"""
        pop = tk.Toplevel(self)
        pop.title("시작 전 다운로드 안내")

        tk.Label(
            pop,
            text="먼저 아래 두 가지 파일을 다운로드 받아주세요.",
            font=("맑은 고딕", 11)
        ).pack(padx=20, pady=(15, 10))

        def link_label(parent, text, url):
            lbl = tk.Label(
                parent, text=text, fg="blue", cursor="hand2",
                font=("맑은 고딕", 10, "underline")
            )
            lbl.pack(anchor="w", padx=30, pady=2)
            lbl.bind("<Button-1>", lambda e: webbrowser.open(url))
            return lbl

        link_label(pop, "1. AP 리스트 파일  :  파일로 이동", LINKS["ap_list"])
        link_label(pop, "2. 홈택스  :  홈텍스 이동", LINKS["hometax"])

        tk.Button(pop, text="확인", command=pop.destroy).pack(pady=(10, 15))

        pop.resizable(False, False)
        pop.grab_set()
        pop.transient(self)

    def _build_ui(self):
        """UI 구성"""
        self.left = ttk.Frame(self, width=360)
        self.left.pack(side="left", fill="y", padx=10, pady=10)

        self.right_container = ttk.Frame(self)
        self.right_container.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self._build_login_section()
        self._build_tree_section()
        self._build_action_buttons()
        self._build_body_section()

    def _build_login_section(self):
        """로그인 영역 구성"""
        ttk.Label(self.left, text="아이디").pack(anchor="w")
        self.eid = ttk.Entry(self.left)
        self.eid.insert(0, "pop84268")
        self.eid.pack(fill="x")

        ttk.Label(self.left, text="패스워드").pack(anchor="w")
        self.epw = ttk.Entry(self.left, show="*")
        self.epw.insert(0, "term0814!@#")
        self.epw.pack(fill="x", pady=(0, 8))

        btnf = ttk.Frame(self.left)
        btnf.pack(fill="x", pady=(0, 12))
        ttk.Button(btnf, text="1. Login", command=self._login_thread) \
            .pack(side="left", expand=True, fill="x")
        ttk.Button(btnf, text="2. 서비스관리 이동", command=self._goto_service) \
            .pack(side="left", expand=True, fill="x", padx=4)

        ttk.Button(self.left, text="위하고 통장 거래 내역", command=self._goto_wehago_account) \
            .pack(fill="x", pady=(0, 12))

    def _build_tree_section(self):
        """트리뷰 구성"""
        cols = ("제목", "문서번호", "작성일자", "기안자")
        self.tree = ttk.Treeview(self.left, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=80, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._show_body)

    def _build_action_buttons(self):
        """액션 버튼 구성"""
        ttk.Button(self.left, text="3. 정보수집", command=self.collect) \
            .pack(fill="x", pady=(6, 4))
        ttk.Button(self.left, text="3-1. 전체수집 (첨부포함)", command=self.collect_full) \
            .pack(fill="x", pady=(0, 4))
        ttk.Button(self.left, text="4. 엑셀로 저장 (자동)", command=self._save_to_excel) \
            .pack(fill="x", pady=(0, 4))
        ttk.Button(self.left, text="선택 항목 삭제", command=self.delete_selected) \
            .pack(fill="x", pady=(0, 4))
        ttk.Button(self.left, text="5. AP LIST 업데이트", command=self._toggle_ap_ui) \
            .pack(fill="x")

    def _build_body_section(self):
        """본문 표시 영역 구성"""
        self.body_frame = ttk.Frame(self.right_container)
        self.body_frame.pack(side="left", fill="both", expand=True)
        self.body_text = tk.Text(self.body_frame, wrap="word")
        self.body_text.pack(fill="both", expand=True)

    def _login_thread(self):
        """로그인 쓰레드 시작"""
        self.update_idletasks()
        geom = self.geometry()
        size, pos = geom.split('+', 1)
        ui_width, ui_height = map(int, size.split('x'))
        ui_x, ui_y = map(int, pos.split('+'))
        screen_w = self.winfo_screenwidth()

        def run():
            self.scraper.login(
                user_id=self.eid.get(),
                password=self.epw.get(),
                window_position=(ui_x + ui_width, ui_y),
                window_size=(screen_w - (ui_x + ui_width), ui_height),
                on_complete=lambda: messagebox.showinfo(
                    "안내", "로그인 완료\n팝업을 연 뒤 '정보수집'을 누르세요."
                )
            )

        threading.Thread(target=run, daemon=True).start()

    def _goto_service(self):
        """서비스관리 페이지 이동"""
        if not self.scraper.is_connected():
            messagebox.showwarning("경고", "먼저 Login 하세요.")
            return
        self.scraper.goto_service_management()

    def _goto_wehago_account(self):
        """위하고 통장 거래내역 페이지 이동"""
        if not self.scraper.is_connected():
            messagebox.showwarning("경고", "먼저 Login 하세요.")
            return
        self.scraper.goto_account_history()

    def collect(self):
        """문서 정보 수집"""
        if not self.scraper.is_connected():
            messagebox.showwarning("경고", "먼저 Login 하세요.")
            return

        try:
            doc = self.scraper.collect_document()
            self.rows.append((doc.title, doc.docno, doc.date, doc.writer))
            self.bodies.append(doc.body)
            self.tree.insert("", "end", values=(doc.title, doc.docno, doc.date, doc.writer))
        except Exception as e:
            messagebox.showerror("수집 실패", str(e))

    def collect_full(self):
        """전체 문서 수집 (첨부 파일 포함)"""
        if not self.scraper.is_connected():
            messagebox.showwarning("경고", "먼저 Login 하세요.")
            return

        try:
            doc_info = self.scraper.collect_full_document(DATA_DIR)

            # 트리뷰에 추가
            self.rows.append((doc_info.title, doc_info.docno, doc_info.date, doc_info.writer))
            self.bodies.append(doc_info.body)
            self.tree.insert("", "end",
                             values=(doc_info.title, doc_info.docno, doc_info.date, doc_info.writer))
        except Exception as e:
            messagebox.showerror("수집 실패", str(e))

    def delete_selected(self):
        """선택 항목 삭제"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("경고", "삭제할 항목을 선택하세요.")
            return
        for item in reversed(sel):
            idx = self.tree.index(item)
            self.tree.delete(item)
            del self.rows[idx]
            del self.bodies[idx]

    def _save_to_excel(self):
        """엑셀로 저장"""
        if not self.rows:
            messagebox.showwarning("경고", "저장할 데이터가 없습니다.")
            return

        path = BASE_DIR / "db_temp.xlsx"
        df = pd.DataFrame(self.rows, columns=["제목", "문서번호", "작성일자", "기안자"])
        df["본문"] = self.bodies

        try:
            df.to_excel(path, index=False)
            messagebox.showinfo("완료", f"db_temp.xlsx 로 저장되었습니다:\n{path}")
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))

    def _show_body(self, _):
        """본문 표시"""
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", self.bodies[idx])

    def _toggle_ap_ui(self):
        """AP UI 토글"""
        if self.ap_frame and self.ap_frame.winfo_exists():
            self.ap_frame.destroy()
            self.ap_frame = None
            self._restore_window()
        else:
            self.ap_frame = UpdateAPListFrame(self.right_container)
            self.ap_frame.pack(side="left", fill="both", padx=(10, 0))
            self._expand_window()

    def _expand_window(self):
        """창 확장"""
        self.update_idletasks()
        total_needed = self.left.winfo_reqwidth() + \
                       self.right_container.winfo_reqwidth() + 40
        w, h, x, y = self._get_geometry()
        self.geometry(f"{total_needed}x{h}+{x}+{y}")

    def _restore_window(self):
        """창 복원"""
        w, h, x, y = self._get_geometry()
        self.geometry(f"{UI_BASE_WIDTH}x{h}+{x}+{y}")

    def _get_geometry(self) -> Tuple[int, int, int, int]:
        """현재 창 geometry 파싱"""
        geom = self.geometry()
        size, pos = geom.split('+', 1)
        w, h = map(int, size.split('x'))
        x, y = map(int, pos.split('+'))
        return w, h, x, y
