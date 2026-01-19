# -*- coding: utf-8 -*-
"""
AP List 업데이트 프레임 (병렬 처리 적용)
"""

import threading
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

import pandas as pd

from config import (
    BASE_DIR,
    DEFAULT_GEMINI_API_KEY,
    DEFAULT_GEMINI_MODEL,
    COMPANY_NAME
)
from services.gemini_service import GeminiService
from utils.date_utils import extract_date
from utils.text_utils import (
    first_name,
    detect_product,
    is_travel_reimbursement,
    safe_payee
)
from utils.excel_utils import lookup_bank_account, load_accounts_sheet


class UpdateAPListFrame(ttk.Frame):
    """AP List 업데이트 UI 프레임"""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.ai_service: Optional[GeminiService] = None

        self.path_db = tk.StringVar(value=str(BASE_DIR / "db_temp.xlsx"))
        # AP List 파일 자동 탐색 (우선순위: 원본 > updated > merged)
        ap_candidates = ["AP List_RDXL.xlsx", "AP List_RDXL_updated.xlsx", "AP List_RDXL_merged.xlsx"]
        ap_path = ""
        for fname in ap_candidates:
            p = BASE_DIR / fname
            if p.is_file():
                ap_path = str(p)
                break
        self.path_ap = tk.StringVar(value=ap_path)

        self._build_file_ui()
        self._build_gemini_ui()
        self._build_buttons()
        self._build_log()

    def _build_file_ui(self):
        """파일 선택 UI 구성"""
        f = ttk.LabelFrame(self, text="엑셀 파일 지정")
        f.pack(fill="x", padx=6, pady=4)
        self._file_row(f, "db_temp.xlsx", self.path_db)
        self._file_row(f, "AP List_RDXL.xlsx", self.path_ap)

    def _file_row(self, parent, label: str, var: tk.StringVar):
        """파일 선택 행 추가"""
        r = len(parent.children) // 3
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="e", padx=2, pady=2)
        ttk.Entry(parent, textvariable=var, width=60).grid(row=r, column=1, sticky="w")
        ttk.Button(parent, text="찾기", command=lambda: self._browse(var)) \
            .grid(row=r, column=2, padx=2)

    def _browse(self, var: tk.StringVar):
        """파일 브라우저 열기"""
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if p:
            var.set(p)

    def _build_gemini_ui(self):
        """Gemini 설정 UI 구성"""
        frm = ttk.LabelFrame(self, text="Gemini 설정")
        frm.pack(fill="x", padx=6, pady=4)

        ttk.Label(frm, text="API Key").grid(row=0, column=0, sticky="e")
        self.ent_key = ttk.Entry(frm, width=70, show="*")
        self.ent_key.grid(row=0, column=1, sticky="w")
        self.ent_key.insert(0, DEFAULT_GEMINI_API_KEY)

        ttk.Label(frm, text="모델").grid(row=1, column=0, sticky="e")
        self.ent_model = ttk.Entry(frm, width=40)
        self.ent_model.grid(row=1, column=1, sticky="w")
        self.ent_model.insert(0, DEFAULT_GEMINI_MODEL)

    def _build_buttons(self):
        """버튼 UI 구성"""
        btn_bar = ttk.Frame(self)
        btn_bar.pack(pady=4)

        ttk.Button(btn_bar, text="6. 실행", command=self.run).pack(side="left", padx=(0, 4))
        ttk.Button(btn_bar, text="7. 세금계산서 추가하기", command=self.run_tax).pack(side="left")

    def _build_log(self):
        """로그 영역 구성"""
        self.log = scrolledtext.ScrolledText(self, height=18, state="disabled")
        self.log.pack(fill="both", expand=True, padx=6, pady=4)

    def _log(self, msg: str):
        """로그 메시지 추가"""
        self.log.configure(state="normal")
        now = datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{now}] {msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def run(self):
        """실행 버튼 클릭 처리"""
        for p, lbl in [(self.path_db.get(), "db_temp"),
                       (self.path_ap.get(), "AP List_RDXL")]:
            if not Path(p).is_file():
                messagebox.showerror("오류", f"{lbl} 경로를 확인하세요")
                return

        if not self.ent_key.get().strip():
            messagebox.showerror("오류", "API Key 입력 필요")
            return

        self.ai_service = GeminiService(
            api_key=self.ent_key.get().strip(),
            model=self.ent_model.get().strip()
        )
        threading.Thread(target=self._process, daemon=True).start()

    def run_tax(self):
        """세금계산서 추가하기 버튼 클릭 처리"""
        ok = messagebox.askokcancel(
            "세금계산서 추가하기",
            "작업을 시작하기 전에, 먼저 홈텍스에서 세금계산서목록을 다운받아 주세요. "
            "홈택스 > 전자세금계산서 조회 > 발급 목록조회 > 매입, '전송일자', 조회기간 설정 > 조회 > 내려받기"
        )
        if not ok:
            return

        script_path = BASE_DIR / "tax2aplist_ui.py"
        if not script_path.exists():
            messagebox.showerror("오류", f"'{script_path.name}' 파일을 찾을 수 없습니다.")
            return

        try:
            subprocess.Popen([sys.executable, str(script_path)])
        except Exception as e:
            messagebox.showerror("실행 실패", str(e))

    # 병렬 처리 워커 수
    MAX_WORKERS = 5

    def _parse_single_document(self, row_data: Dict) -> Dict:
        """
        단일 문서 AI 파싱 (병렬 처리용)

        Args:
            row_data: 문서 정보 dict

        Returns:
            파싱 결과 dict (원본 정보 + AI 파싱 결과)
        """
        body = row_data["body"]
        infos = self.ai_service.parse_multi_transfer(body)
        if not infos:
            infos = [self.ai_service.parse_single_transfer(body)]
        return {**row_data, "infos": infos}

    def _process(self):
        """핵심 처리 로직 (병렬 처리 적용)"""
        self._log("데이터 로딩...")

        db = pd.read_excel(self.path_db.get())
        ap = pd.read_excel(self.path_ap.get(), sheet_name="2025")
        accounts_df = load_accounts_sheet(self.path_ap.get())

        existing = set(ap["문서번호"].astype(str))

        # 1단계: 처리할 문서 필터링
        docs_to_process = []
        for _, row in db.iterrows():
            title, docno = str(row["제목"]), str(row["문서번호"])
            if docno in existing:
                self._log(f"{docno} 이미 존재 -> 건너뜀")
                continue
            docs_to_process.append({
                "row": row,
                "title": title,
                "docno": docno,
                "body": str(row["본문"])
            })

        if not docs_to_process:
            self._log("처리할 새 문서 없음")
            messagebox.showinfo("완료", "추가할 새 문서가 없습니다.")
            return

        # 2단계: AI 파싱 병렬 처리
        self._log(f"{len(docs_to_process)}건 병렬 파싱 시작 (워커 {self.MAX_WORKERS}개)...")
        parsed_results = []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_doc = {
                executor.submit(self._parse_single_document, doc): doc
                for doc in docs_to_process
            }

            for future in as_completed(future_to_doc):
                try:
                    result = future.result()
                    parsed_results.append(result)
                    self._log(f"{result['docno']} 파싱 완료")
                except Exception as e:
                    doc = future_to_doc[future]
                    self._log(f"{doc['docno']} 파싱 실패: {e}")

        # 3단계: 결과 처리 (순차)
        add_rows = []
        for result in parsed_results:
            row = result["row"]
            title = result["title"]
            docno = result["docno"]
            body = result["body"]
            infos = result["infos"]

            # 여비정산 전용 처리
            if is_travel_reimbursement(title, body):
                new_row = self._process_travel_reimbursement(
                    row, infos, accounts_df, title, docno
                )
                add_rows.append(new_row)
                self._log(f"{docno} -> 여비정산 처리 완료")
                continue

            # 일반 전자문서 처리
            if "지급 조건" in body and len(infos) > 1:
                self._log(f"{docno} -> 지급조건별 {len(infos)}건 분할")
            elif len(infos) > 1:
                self._log(f"{docno} -> 다중 이체 {len(infos)}건 분할")
            else:
                self._log(f"{docno} -> 단일 이체")

            for info in infos:
                new_row = self._process_general_document(row, info, title, docno, body)
                add_rows.append(new_row)

        # 4단계: 결과 저장
        if add_rows:
            self._log(f"추가 {len(add_rows)}행 완료")
            ap = pd.concat([ap, pd.DataFrame(add_rows)], ignore_index=True)
        else:
            self._log("추가할 행 없음")

        # 계좌·금액 열 문자열 고정
        ap["계좌번호"] = ap["계좌번호"].astype(str)
        ap["금액"] = ap["금액"].astype(int, errors="ignore")

        out = str(Path(self.path_ap.get()).with_stem(
            Path(self.path_ap.get()).stem + "_updated"
        ))
        self._log("엑셀 저장 중...")

        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            original = pd.ExcelFile(self.path_ap.get())
            for sheet in original.sheet_names:
                df = ap if sheet == "2025" else pd.read_excel(
                    self.path_ap.get(), sheet_name=sheet
                )
                df.to_excel(writer, sheet_name=sheet, index=False)

        self._log(f"저장 완료 -> {out}")
        messagebox.showinfo("완료", f"저장 완료:\n{out}")

    def _process_travel_reimbursement(
        self, row, infos, accounts_df, title, docno
    ) -> dict:
        """여비정산 처리"""
        info = infos[0] if infos else {}
        requester = first_name(row["기안자"])
        bank, account = lookup_bank_account(requester, accounts_df)

        # 수취인 보정
        payee = safe_payee(info.get("수취인", ""), requester)

        # 내부메모 재작성
        month = extract_date(row["작성일자"])[5:7] or datetime.now().strftime("%m")
        inner_memo = f"(여비정산){requester}{month}월여비정산"

        return {
            "기안 날짜": extract_date(row["작성일자"]),
            "세금계산서 수령": "필요없음",
            "이체 목표": "매월 2번째 금요일",
            "이체 날짜": "",
            "요청자": requester,
            "구분": "여비정산",
            "품목": title,
            "문서번호": docno,
            "비고": info.get("비고", ""),
            "은행": str(bank) if bank else "",
            "계좌번호": str(account) if account else "",
            "금액": info.get("금액", 0),
            "수취인": payee,
            "공란": "",
            "CMS코드(공란)": "",
            "받는분 통장 표시": COMPANY_NAME,
            "본인 통장표시내용": f"여비정산_{requester}",
            "내부 메모": inner_memo,
        }

    def _process_general_document(
        self, row, info, title, docno, body
    ) -> dict:
        """일반 전자문서 처리"""
        product = detect_product(f"{title} {body}") or info.get("제품", "")
        requester = first_name(row["기안자"])

        return {
            "기안 날짜": extract_date(row["작성일자"]),
            "세금계산서 수령": "",
            "이체 목표": info.get("이체_목표", "세금계산서 확인 후"),
            "이체 날짜": "",
            "요청자": requester,
            "구분": info.get("구분", "검토 필요"),
            "품목": title,
            "문서번호": docno,
            "비고": info.get("비고", ""),
            "은행": info.get("은행", ""),
            "계좌번호": info.get("계좌번호", ""),
            "금액": info.get("금액", ""),
            "수취인": info.get("수취인", ""),
            "공란": "",
            "CMS코드(공란)": "",
            "받는분 통장 표시": COMPANY_NAME,
            "본인 통장 표시": info.get("수취인", ""),
            "내부 메모": info.get(
                "내부메모",
                f"({info.get('구분', '구분없음')}){product or '내역 확인'}"
            ),
        }
