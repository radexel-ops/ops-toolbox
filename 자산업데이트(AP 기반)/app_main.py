# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, threading, uuid, re
from typing import Any, Dict, List, Tuple
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog


from config import DEFAULT_CONFIG, AP_COL_ALIASES, AP_SIMPLY_HEADERS
from gsheets_client import SheetsClient, A1, col_letter
from mapping_rules import (
    normalize_header_map, find_header,
    aggregate_ap_rows, map_rule_based_to_assets,
    MemberIndex, is_suspect_duplicate, clean_asset_title,
    group_by_docno
)
from mgmt_number import bulk_assign_management_numbers
from ai_enrich import enrich_selected_item



CONFIG_PATH = "config.json"


def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(cfg)
        return merged
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class StagedItem:
    def __init__(self, ap_key: str, ap_row: Dict[str, Any], values: Dict[str, Any]):
        self.ap_key = ap_key
        self.ap_row = ap_row
        self.values = values
        self.valid = False
        self.deleted = False
        self.suspect = False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AP → 자산현황 매핑")
        self.geometry("1500x940")

        self.cfg = load_config()
        self.cfg.setdefault("AI_DEBUG_LOG", True)
        self.cfg.setdefault("AI_LOG_PROMPT", True)
        self.cfg.setdefault("AI_MAX_LOG_CHARS", 6000)
        self.cfg.setdefault("AI_CONFIDENCE_IF_MISSING", 0.95)
        self.cfg.setdefault("ASSETS_CONTEXT_MAX_ROWS", 120)
        self.cfg.setdefault("CATEGORY_FUZZY_MIN_SCORE", 0.65)
        self.cfg.setdefault("ALLOW_CATEGORY_FALLBACK", False)
        self.cfg.setdefault("CATEGORY_FALLBACK_VALUE", "미분류")
        self.cfg.setdefault("OPENAI_MODEL", "gpt-5-mini")
        self.cfg.setdefault("CONFIDENCE_THRESHOLD", 0.90)
        self.cfg.setdefault("AI_ALLOW_OVERWRITE", True)

        self.sheets = SheetsClient()
        self.assets_headers: List[str] = []
        self.assets_header_map: Dict[str, int] = {}
        self.assets_total_cols: int = 0
        self.assets_formula_cols: List[int] = []
        self.assets_display_headers: List[str] = []
        self.category_candidates: List[str] = []
        self.member_index: MemberIndex | None = None
        self.existing_rows: List[Dict[str, Any]] = []

        self.staged: List[StagedItem] = []
        self.status = tk.StringVar(value="초기화…")

        self.edit_widgets: Dict[str, Any] = {}
        self.edit_vars: Dict[str, tk.StringVar] = {}
        self._suspend_edit_events = False
        self._current_edit_idx: int | None = None

        self._build_top()
        self._build_center()
        threading.Thread(target=self._init_connect, daemon=True).start()


    def _build_top(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))

        left = ttk.Frame(top)
        left.pack(side="left", fill="x", expand=True)
        right = ttk.Frame(top)
        right.pack(side="right")

        ttk.Label(left, text="OpenAI API Key").pack(side="left")
        self.ent_api = ttk.Entry(left, width=48, show="*")
        self.ent_api.pack(side="left", padx=6)
        self.ent_api.insert(0, os.getenv("OPENAI_API_KEY", ""))

        ttk.Button(left, text="저장", command=self._save_openai_key).pack(side="left", padx=(0, 10))

        ttk.Label(left, text="모델").pack(side="left")
        self.cmb_model = ttk.Combobox(left, width=14, state="readonly")
        self.cmb_model["values"] = ["gpt-5-mini"]
        self.cmb_model.set(self.cfg.get("OPENAI_MODEL", "gpt-5-mini"))
        self.cmb_model.pack(side="left", padx=6)

        ttk.Label(left, text="임계값").pack(side="left", padx=(8, 2))
        self.var_threshold = tk.DoubleVar(value=float(self.cfg.get("CONFIDENCE_THRESHOLD", 0.90)))
        ttk.Spinbox(left, from_=0.50, to=0.99, increment=0.01, textvariable=self.var_threshold, width=5).pack(side="left")

        self.var_debug = tk.BooleanVar(value=bool(self.cfg.get("AI_DEBUG_LOG", True)))
        ttk.Checkbutton(left, text="디버그", variable=self.var_debug).pack(side="left", padx=8)

        self.var_overwrite = tk.BooleanVar(value=bool(self.cfg.get("AI_ALLOW_OVERWRITE", True)))
        ttk.Checkbutton(left, text="수정 허용", variable=self.var_overwrite).pack(side="left", padx=8)

        ttk.Button(right, text="OAuth 재인증", command=self.reset_oauth).pack(side="right", padx=6)
        ttk.Button(right, text="선택행 삭제", command=self.delete_selected).pack(side="right", padx=6)
        ttk.Button(right, text="삭제 취소", command=self.undelete_selected).pack(side="right", padx=6)
        ttk.Button(right, text="선택행 AI 보강", command=self.enrich_selected_with_ai).pack(side="right", padx=6)
        ttk.Button(right, text="1차 규칙기반 분류", command=self.run_rule_first_pass).pack(side="right", padx=(0, 6))
        ttk.Button(right, text="행 추가", command=self.add_manual_row).pack(side="right", padx=6)
        ttk.Button(right, text="자산 나누기", command=self.split_selected_asset).pack(side="right", padx=6)

        ttk.Label(right, textvariable=self.status).pack(side="right", padx=10)

    def add_manual_row(self):
        """
        수동으로 한 줄 추가하여 트리뷰와 스테이징에 반영.
        - 업로드는 self.staged 기반이라 자동으로 포함됨.
        """
        # 문서번호(ap_key) 대체값 생성
        ap_key = f"MANUAL-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:4]}"

        # 표시 대상 헤더들로 빈 값 dict 생성
        values = {h: "" for h in self.assets_display_headers}

        # 기본값: 자산상태(필수) 있으면 config 첫 항목
        allowed_status = list(self.cfg.get("ALLOWED_STATUS", []))
        if "자산상태 (필수)" in values and allowed_status:
            values["자산상태 (필수)"] = allowed_status[0]

        # 스테이징에 추가
        it = StagedItem(ap_key=ap_key, ap_row={}, values=values)
        self.staged.append(it)
        new_idx = len(self.staged) - 1

        # 트리에 삽입
        self._insert_tree_item(new_idx)

        # 새 행 선택 + 편집 패널 반영
        self.tree.selection_set(f"row-{new_idx}")
        self.tree.see(f"row-{new_idx}")
        self._current_edit_idx = new_idx
        self._suspend_edit_events = True
        try:
            for h in self.assets_display_headers:
                self.edit_vars[h].set(str(values.get(h, "") or ""))
        finally:
            self._suspend_edit_events = False

        # 관리번호 중복 색상 갱신
        self._refresh_mgmt_duplicates()

        # 상태바/로그
        self._set_status("새 행 추가")
        self._log(f"수동 행 추가: {ap_key}")

    def _is_float_like(self, s: str) -> bool:
        t = str(s or "").strip().replace(",", "").replace("₩", "")
        try:
            float(t)
            return True
        except Exception:
            return False

    def _parse_amount(self, s: str) -> Tuple[float, bool]:
        """
        문자열 금액 → float 변환, 정수형 표시 여부 반환
        - 쉼표/원화기호 제거
        """
        raw = str(s or "").strip()
        t = raw.replace(",", "").replace("₩", "").replace("원", "")
        is_int_style = re.match(r"^-?\d+$", t) is not None  # 정수 스타일 표기였는지
        v = float(t) if t else 0.0
        return v, is_int_style

    def _format_amount(self, v: float, int_style: bool) -> str:
        """
        원래 표기 스타일을 최대한 보존:
        - int_style=True면 정수로 반올림 후 천단위 콤마
        - 아니면 소수점 2자리까지
        """
        if int_style:
            n = int(round(v))
            return f"{n:,}"
        else:
            return f"{v:.2f}".rstrip("0").rstrip(".")

    def _suffix_codes(self, n: int) -> List[str]:
        """
        AA, AB, ..., AZ, BA, ..., ZZ 순서로 n개 생성 (n<=676 가정)
        """
        letters = [chr(ord('A') + i) for i in range(26)]
        out = []
        for i in range(n):
            a = letters[(i // 26) % 26]
            b = letters[i % 26]
            out.append(a + b)
        return out

    def _split_mgmt_prefix(self, mgmt: str) -> Tuple[str, str]:
        """
        관리번호에서 접두/접미(마지막 2 영문자) 분리
        - 예: T-PD-SMD2025-0601AA -> ('T-PD-SMD2025-0601', 'AA')
        - 영문자 2글자 미존재 시 ('', '')
        """
        m = re.match(r"^(.*?)([A-Z]{2})$", str(mgmt or "").strip())
        if m:
            return m.group(1), m.group(2)
        return "", ""

    def split_selected_asset(self):
        # 1) 선택 검증
        sels = self.tree.selection()
        if not sels or len(sels) != 1:
            messagebox.showinfo("안내", "자산 나누기를 하려면 한 행만 선택하세요.")
            return
        idx = int(self.tree.set(sels[0], "__index__"))
        it = self.staged[idx]

        # 2) 몇 개로 나눌지 입력받기
        try:
            n = simpledialog.askinteger("자산 나누기", "몇 개로 나눌까요? (2~26*26)", minvalue=2, maxvalue=676, parent=self)
        except Exception:
            n = None
        if not n:
            return

        # 3) 금액 필드 탐색 (우선순위로 존재하는 첫 필드 사용)
        amount_headers_priority = [
            "금액", "지급금액", "지급액", "총액", "청구금액",
            "공급가액", "합계", "매입금액", "취득가액", "구매 가격 (원)",
        ]
        amount_field = next((h for h in amount_headers_priority if h in self.assets_display_headers), None)
        if not amount_field:
            messagebox.showwarning("경고", "금액 필드를 찾을 수 없습니다. config의 금액 헤더명을 확인하세요.")
            return

        amt_raw = it.values.get(amount_field, "")
        if not self._is_float_like(amt_raw):
            messagebox.showwarning("경고", f"금액 필드에 수치가 없습니다: {amount_field}")
            return

        total, was_int_style = self._parse_amount(amt_raw)
        if total == 0:
            messagebox.showwarning("경고", "금액이 0입니다. 나누기를 진행할 수 없습니다.")
            return

        # 4) 관리번호 기반 접두분리/생성
        mgmt_orig = str(it.values.get("관리번호 (필수)", "") or "").strip()
        prefix, _suf = self._split_mgmt_prefix(mgmt_orig)

        # 관리번호가 없으면 카테고리/구매일 기반으로 한번 생성 시도
        if not prefix:
            self._current_edit_idx = idx
            self._maybe_fill_mgmt_number_for_current()
            mgmt_new = str(it.values.get("관리번호 (필수)", "") or "").strip()
            prefix, _suf = self._split_mgmt_prefix(mgmt_new)

        # 그래도 못 뽑으면 접두 비어있음 → 접미만 부여 불가. 경고 후 진행(관리번호는 비워둠)
        if not prefix:
            proceed = messagebox.askyesno("관리번호 없음",
                                          "관리번호 패턴을 확인할 수 없습니다.\n금액만 N등분하여 복제할까요? (관리번호는 비워둡니다)")
            if not proceed:
                return

        # 5) 금액 1/N 계산(총합 보존: 정수면 몫/나머지 배분, 아니면 소수2자리 반올림 배분)
        parts = []
        if was_int_style:
            per = int(total // n)
            rem = int(round(total - per * n))
            for i in range(n):
                parts.append(per + (1 if i < rem else 0))
        else:
            per = round(total / n, 2)
            # 합계 보정: 마지막 항목에 잔차 몰아주기
            running = 0.0
            for i in range(n - 1):
                parts.append(per)
                running += per
            parts.append(round(total - running, 2))

        # 6) 원본 대체: n개의 새 아이템 만들고, 원본은 삭제 처리(혹은 대체)
        #    - UX상 깔끔하게: 원본 위치에 첫 조각을 덮어쓰고, 나머지 n-1개는 그 뒤에 삽입
        # 관리번호 접미사 시퀀스
        sufs = self._suffix_codes(n)

        # 첫 조각: 원본 it에 덮어쓰기
        first_amt = self._format_amount(parts[0], was_int_style)
        it.values[amount_field] = first_amt
        if prefix:
            it.values["관리번호 (필수)"] = f"{prefix}{sufs[0]}"

        self._refresh_tree_row(idx)

        # 나머지 조각들 삽입
        insert_after = idx
        new_items = []
        for k in range(1, n):
            nv = dict(it.values)  # 현재 첫 조각 상태를 기준 복제(같은 값)
            # 금액/관리번호만 덮어쓰기
            nv[amount_field] = self._format_amount(parts[k], was_int_style)
            if prefix:
                nv["관리번호 (필수)"] = f"{prefix}{sufs[k]}"

            new_it = StagedItem(ap_key=f"{it.ap_key}-SPLIT-{k + 1}", ap_row=dict(it.ap_row), values=nv)
            new_items.append(new_it)

        # 스테이징 리스트/트리뷰에 실제로 삽입
        # 리스트에 끼워넣기
        self.staged[insert_after + 1:insert_after + 1] = new_items

        # 트리뷰 재번호 및 전체 리프레시
        for i in self.tree.get_children():
            self.tree.delete(i)
        for i in range(len(self.staged)):
            self._insert_tree_item(i)

        # 선택 이동: 첫 조각 선택
        self.tree.selection_set(f"row-{idx}")
        self.tree.see(f"row-{idx}")
        self._current_edit_idx = idx
        # 편집 패널 값도 첫 조각으로 로드
        self._suspend_edit_events = True
        try:
            for h in self.assets_display_headers:
                self.edit_vars[h].set(str(self.staged[idx].values.get(h, "") or ""))
        finally:
            self._suspend_edit_events = False

        # 중복 관리번호 색상 갱신
        self._refresh_mgmt_duplicates()

        # 로그
        self._log(f"자산 나누기: idx={idx}, N={n}, amount_field='{amount_field}', total={amt_raw} -> parts={parts}")

    def _resolve_amount_key(self) -> str | None:
        """
        금액 컬럼 키 탐색 우선순위:
        1) config.AMOUNT_HEADERS 후보들 중에서 self.assets_headers(전체 헤더)에 존재하는 이름
        2) 현재 선택된 staged.values에 실제 키로 존재하는 이름
        """
        cand = [s.strip() for s in self.cfg.get("AMOUNT_HEADERS", []) if str(s).strip()]
        if not cand:
            cand = ["구매 가격 (원)", "금액", "구매금액", "총액"]  # 최후 폴백

        headers_all = set(self.assets_headers or [])
        # 1) 시트 전체 헤더 기준으로 1차 선택
        for name in cand:
            if name in headers_all:
                return name

        # 2) 현재 선택 행의 values에 실제 키가 있으면 그걸 사용
        if self._current_edit_idx is not None:
            vals = self.staged[self._current_edit_idx].values
            for name in cand:
                if name in vals:
                    return name
        return None

    def _build_center(self):
        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main)
        main.add(left, weight=5)
        self.tree = ttk.Treeview(left, show="headings", selectmode="extended")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)
        self.tree.tag_configure("deleted", foreground="#9B9B9B")
        self.tree.tag_configure("suspect", background="#FFF2B2")
        self.tree.tag_configure("dup_mgmt", background="#FFD6D6")

        right = ttk.Frame(main)
        main.add(right, weight=1)

        self.edit_frame = ttk.LabelFrame(right, text="편집")
        self.edit_frame.pack(fill="both", expand=True)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(6, 0))
        ttk.Button(bottom, text="검증", command=self.validate_all).pack(side="left")
        ttk.Button(bottom, text="최종 업로드", command=self.commit_upload).pack(side="right")

        logf = ttk.LabelFrame(right, text="로그")
        logf.pack(fill="both", expand=False, pady=(8, 0))
        self.log = scrolledtext.ScrolledText(logf, height=16, state="disabled")
        self.log.pack(fill="both", expand=True)

    # App 클래스에 유틸 추가
    def _refresh_mgmt_duplicates(self):
        """
        트리(스테이징) 내 '관리번호 (필수)' 중복을 빨간색 음영으로 표시.
        (ttk.Treeview는 셀 단위 색칠이 제한되어 '행' 음영으로 대체)
        """
        by_num = {}
        for i, it in enumerate(self.staged):
            if it.deleted:
                continue
            mg = str(it.values.get("관리번호 (필수)", "") or "").strip()
            if mg:
                by_num.setdefault(mg, []).append(i)

        # 우선 모두 태그 제거
        for i in range(len(self.staged)):
            tags = list(self.tree.item(f"row-{i}", "tags") or [])
            tags = [t for t in tags if t != "dup_mgmt"]
            self.tree.item(f"row-{i}", tags=tuple(tags))

        # 중복만 표시
        for mg, idxs in by_num.items():
            if len(idxs) >= 2:
                for i in idxs:
                    tags = list(self.tree.item(f"row-{i}", "tags") or [])
                    if "dup_mgmt" not in tags:
                        tags.append("dup_mgmt")
                    self.tree.item(f"row-{i}", tags=tuple(tags))

    def _init_connect(self):
        try:
            self._set_status("Google 연결…")
            self.sheets.connect()

            self._set_status("자산현황 헤더 로딩…")
            head = self.sheets.values_get(self.cfg["ASSETS_SPREADSHEET_ID"], A1(self.cfg["ASSETS_SHEET_NAME"], "1:1"))
            self.assets_headers = head[0] if head else []
            self.assets_header_map = normalize_header_map(self.assets_headers)
            self.assets_total_cols = len(self.assets_headers)

            row2 = self.sheets.values_get(
                self.cfg["ASSETS_SPREADSHEET_ID"],
                A1(self.cfg["ASSETS_SHEET_NAME"], "2:2"),
                value_render_option="FORMULA"
            )
            self.assets_formula_cols = [i for i, v in enumerate(row2[0]) if isinstance(v, str) and v.startswith("=")] if row2 else []

            excluded = set(self.cfg["EXCLUDED_HEADERS"] + ["관리번호 검증"])
            self.assets_display_headers = [
                h for i, h in enumerate(self.assets_headers) if h not in excluded and i not in self.assets_formula_cols
            ]

            self._load_categories()
            self.member_index = MemberIndex.build_from_sheet(self.sheets, self.cfg)
            self._load_existing_rows()
            self._setup_tree()

            self._set_status("연결 완료. 1차 규칙기반 분류를 실행하세요.")
            self._log("Google Sheets 연결 완료.")
        except Exception as e:
            self._set_status("연결 실패")
            self._log(f"[오류] 연결 실패: {e}")
            messagebox.showerror("연결 실패", str(e))

    def _load_categories(self):
        """
        카테고리 후보 + 카테고리→알파코드(T-PD-SMD 등) 맵을 동시 로드
        - 후보: I7:I
        - 코드: '카테고리번호 리스트'!A7:Z에서 I열(카테고리) + 나머지 셀 중 정규식에 맞는 첫 값
        """
        try:
            cat_sheet = self.cfg.get("CATEGORY_SHEET_NAME", "카테고리번호 리스트")

            # 후보(중복 제거)
            rng_cand = A1(cat_sheet, "I7:I")
            vals = self.sheets.values_get(self.cfg["ASSETS_SPREADSHEET_ID"], rng_cand)
            flat = [str(r[0]).strip() for r in vals if r and str(r[0]).strip()]
            seen = set();
            out = []
            for c in flat:
                if c not in seen:
                    seen.add(c);
                    out.append(c)
            self.category_candidates = out

            # 카테고리 → 알파코드 맵
            self._cat_alpha_map = {}
            rng_full = f"'{cat_sheet}'!A7:Z"
            full = self.sheets.values_get(self.cfg["ASSETS_SPREADSHEET_ID"], rng_full)
            pat_alpha = re.compile(r"^[A-Z](?:-[A-Z]{2,4}){2,6}$")  # 예: T-PD-SMD, I-SW-SUB
            for row in full[1:] if full else []:
                cat = row[8].strip() if len(row) > 8 and row[8] else ""
                if not cat:
                    continue
                alpha = None
                for i, cell in enumerate(row):
                    if i == 8:
                        continue
                    s = str(cell or "").strip()
                    if pat_alpha.match(s):
                        alpha = s;
                        break
                if cat and alpha:
                    self._cat_alpha_map.setdefault(cat, alpha)

            self._log(f"카테고리 후보 {len(out)}건 + 코드맵 {len(getattr(self, '_cat_alpha_map', {}))}건 로딩")
        except Exception:
            self.category_candidates = []
            self._cat_alpha_map = {}

    def _load_existing_rows(self):
        data = self.sheets.values_get(self.cfg["ASSETS_SPREADSHEET_ID"], A1(self.cfg["ASSETS_SHEET_NAME"], "1:10000"))
        if not data or len(data) < 2:
            self.existing_rows = []
            return
        header = data[0]
        idx = normalize_header_map(header)
        body = data[1:]
        rows = []
        for r in body:
            rec = {}
            for h in self.assets_display_headers:
                j = idx.get(h, -1)
                if 0 <= j < len(r):
                    rec[h] = str(r[j]).strip() if r[j] is not None else ""
                else:
                    rec[h] = ""
            rows.append(rec)
        self.existing_rows = rows

    def _setup_tree(self):
        cols = ["__index__", "문서번호"] + self.assets_display_headers
        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            w = 140
            if c == "__index__":
                w = 60
            elif c in ("모델 (필수)", "세부제품명", "비고", "구매처"):
                w = 220
            elif c in ("카테고리 (필수)", "자산상태 (필수)", "결재수단", "소유 유형", "위치"):
                w = 140
            elif c in ("구매일", "지급일", "렌탈 시작일", "렌탈 종료일"):
                w = 120
            self.tree.column(c, width=w, stretch=False)
        for i in self.tree.get_children():
            self.tree.delete(i)
        # _setup_tree 끝부분에 있는 우측 편집 그리드 구성부 교체
        for w in self.edit_widgets.values():
            try:
                w.destroy()
            except Exception:
                pass
        self.edit_widgets.clear()
        self.edit_vars.clear()

        grid = ttk.Frame(self.edit_frame)
        grid.pack(fill="both", expand=True, padx=8, pady=8)

        def _choices_for_header(h: str) -> list[str]:
            if h == "카테고리 (필수)":
                return list(self.category_candidates or [])
            if h == "자산상태 (필수)":
                return list(self.cfg.get("ALLOWED_STATUS", []))
            if h == "소유 유형":
                return list(self.cfg.get("ALLOWED_OWNERSHIP", []))
            # 필요하면 추가: 렌탈 결제주기/수단 등
            if h in ("렌탈 결제주기", "렌탈 주기"):
                return list(self.cfg.get("ALLOWED_RENTAL_CYCLE", []))
            if h in ("렌탈 결제수단", "렌탈 결제 방식"):
                return list(self.cfg.get("ALLOWED_RENTAL_PAY", []))
            return []

        # 3열 배치로 세로 길이 최소화
        r, c = 0, 0
        MAX_COLS = 3  # (기존 2 →) 3열로 바꿈
        for h in self.assets_display_headers:
            v = tk.StringVar()
            self.edit_vars[h] = v

            ttk.Label(grid, text=h).grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=2)
            choices = _choices_for_header(h)

            if choices:
                w = ttk.Combobox(grid, textvariable=v, state="readonly", values=choices, width=24)
                # 카테고리/구매일 연동: 관리번호 자동 채움
                if h in ("카테고리 (필수)",):
                    w.bind("<<ComboboxSelected>>", lambda e: self._maybe_fill_mgmt_number_for_current())
            else:
                w = ttk.Entry(grid, textvariable=v, width=28)
                if h in ("구매일",):
                    # 구매일 타이핑 시에도 관리번호 후보 갱신
                    v.trace_add("write", lambda *args: self._maybe_fill_mgmt_number_for_current())

            self.edit_widgets[h] = w
            w.grid(row=r, column=c * 2 + 1, sticky="ew", padx=(0, 8), pady=2)
            grid.grid_columnconfigure(c * 2 + 1, weight=1)

            v.trace_add("write", self._on_edit_var_changed)
            c += 1
            if c >= MAX_COLS:
                c = 0
                r += 1

    def _maybe_fill_mgmt_number_for_current(self):
        """
        규칙:
        - 카테고리(필수), 구매일이 있으면 카테고리코드 + YYYY-MM + '01AA' 자동 입력
          (동월 다건 순번 자동증가 로직은 '사용자 수동 정렬'을 위해 생략)
        - 이후 좌측 트리뷰의 중복 관리번호는 빨간색 음영 처리
        """
        if self._current_edit_idx is None:
            return
        it = self.staged[self._current_edit_idx]

        cat = str(self.edit_vars.get("카테고리 (필수)", tk.StringVar()).get()).strip()
        buy = str(self.edit_vars.get("구매일", tk.StringVar()).get()).strip()
        if not cat or not buy:
            return

        # YYYY-MM 추출
        t = re.sub(r"[./]", "-", buy)
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t) or re.match(r"^(\d{4})(\d{2})(\d{2})$", t)
        if not m:
            return
        if len(m.groups()) == 3:
            y, mo, d = m.groups()
        else:
            y, mo, d = m.group(1), m.group(2), m.group(3)
        y = f"{int(y):04d}";
        mo = f"{int(mo):02d}"

        # 카테고리 → 알파코드
        alpha = (getattr(self, "_cat_alpha_map", {}) or {}).get(cat, "")
        if not alpha:
            return

        mgmt = f"{alpha}{y}-{mo}01AA"  # 예: T-PD-SMD2025-0601AA
        it.values["관리번호 (필수)"] = mgmt
        if "관리번호 (필수)" in self.edit_vars:
            self.edit_vars["관리번호 (필수)"].set(mgmt)

        # 트리뷰 갱신 + 중복 검사
        self._refresh_tree_row(self._current_edit_idx)
        self._refresh_mgmt_duplicates()

    def _on_edit_var_changed(self, *args):
        if self._suspend_edit_events:
            return
        if self._current_edit_idx is None:
            return
        it = self.staged[self._current_edit_idx]
        for h, v in self.edit_vars.items():
            it.values[h] = v.get()
        self._refresh_tree_row(self._current_edit_idx)
        self._refresh_mgmt_duplicates()  # ← 추가

    def on_select_row(self, event=None):
        sels = self.tree.selection()
        if not sels:
            return
        item_id = sels[0]
        idx = int(self.tree.set(item_id, "__index__"))
        self._current_edit_idx = idx
        it = self.staged[idx]
        self._suspend_edit_events = True
        try:
            for h in self.assets_display_headers:
                self.edit_vars[h].set(str(it.values.get(h, "") or ""))
        finally:
            self._suspend_edit_events = False

    def _insert_tree_item(self, idx: int):
        it = self.staged[idx]
        values = [idx, it.ap_key]
        for h in self.assets_display_headers:
            values.append(str(it.values.get(h, "") or ""))
        tags = []
        if it.deleted:
            tags.append("deleted")
        if it.suspect:
            tags.append("suspect")
        self.tree.insert("", "end", iid=f"row-{idx}", values=values, tags=tuple(tags))

    def _refresh_tree_row(self, idx: int):
        it = self.staged[idx]
        values = [idx, it.ap_key]
        for h in self.assets_display_headers:
            values.append(str(it.values.get(h, "") or ""))
        tags = []
        if it.deleted:
            tags.append("deleted")
        if it.suspect:
            tags.append("suspect")
        self.tree.item(f"row-{idx}", values=values, tags=tuple(tags))

    def _save_openai_key(self):
        key = self.ent_api.get().strip()
        os.environ["OPENAI_API_KEY"] = key
        self.cfg["OPENAI_MODEL"] = self.cmb_model.get().strip() or "gpt-5-mini"
        self.cfg["CONFIDENCE_THRESHOLD"] = float(self.var_threshold.get())
        self.cfg["AI_ALLOW_OVERWRITE"] = bool(self.var_overwrite.get())
        save_config(self.cfg)
        self._log("OpenAI 설정 저장 완료")

    def reset_oauth(self):
        path = "token.json"
        try:
            if os.path.exists(path):
                os.remove(path)
                self._log("OAuth 토큰 삭제 완료")
            else:
                self._log("OAuth 토큰 파일이 없습니다")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    def delete_selected(self):
        sels = self.tree.selection()
        if not sels:
            return
        for sid in sels:
            idx = int(self.tree.set(sid, "__index__"))
            self.staged[idx].deleted = True
            self._refresh_tree_row(idx)

    def undelete_selected(self):
        sels = self.tree.selection()
        if not sels:
            return
        for sid in sels:
            idx = int(self.tree.set(sid, "__index__"))
            self.staged[idx].deleted = False
            self._refresh_tree_row(idx)

    def run_rule_first_pass(self):
        threading.Thread(target=self._first_pass_rule_thread, daemon=True).start()

    def _first_pass_rule_thread(self):
        try:
            self._set_status("AP 로딩…")
            ap_id = self.cfg["AP_SPREADSHEET_ID"]
            ap_sheet = self.cfg["AP_SHEET_NAME"]
            if not ap_id or not ap_sheet:
                messagebox.showwarning("설정 필요", "AP 스프레드시트 설정을 확인하세요.")
                return
            ap_all = self.sheets.values_get(ap_id, A1(ap_sheet, "1:50000"))
            if not ap_all or len(ap_all) < 2:
                messagebox.showinfo("안내", "AP 시트에 데이터가 없습니다.")
                return
            ap_headers = ap_all[0]
            ap_body = ap_all[1:]
            idx_map = normalize_header_map(ap_headers)
            mark_h = find_header(ap_headers, AP_SIMPLY_HEADERS)
            mark_j = idx_map.get(mark_h, None) if mark_h else None
            filtered = []
            for r in ap_body:
                ok = False
                if mark_j is not None and mark_j < len(r):
                    val = str(r[mark_j]).strip().lower()
                    ok = val in ("o", "y", "1", "true", "yes")
                if ok:
                    filtered.append(r)
            if not filtered:
                self._log("심플리 표시된 행이 없습니다.")
                return

            groups = group_by_docno(filtered, ap_headers)
            self._set_status(f"집계 {len(groups)}건…")

            staged_new: List[StagedItem] = []
            for key, rows in groups.items():
                ap_map = normalize_header_map(ap_headers)
                ap_agg = aggregate_ap_rows(key, rows, ap_headers, ap_map, self.member_index, self.cfg)
                values = map_rule_based_to_assets(ap_agg, self.assets_display_headers, self.cfg)
                self._fixup_model_from_ap(values, ap_agg)
                suspect = is_suspect_duplicate(values, self.existing_rows, {"DATE_WINDOW_DAYS": 5, "AMOUNT_TOLERANCE": 0})
                si = StagedItem(key, ap_agg, values)
                si.suspect = suspect
                staged_new.append(si)

            self.staged = staged_new
            for i in self.tree.get_children():
                self.tree.delete(i)
            for i in range(len(self.staged)):
                self._insert_tree_item(i)
            self._refresh_mgmt_duplicates()  # ← 여기 추가

            self._set_status(f"규칙기반 분류 완료: {len(self.staged)}건")
            self._log(f"규칙기반 분류 완료: {len(self.staged)}건")
        except Exception as e:
            self._set_status("1차 분류 실패")
            self._log(f"[오류] 1차 분류 실패: {e}")
            messagebox.showerror("오류", str(e))

    def _ensure_yyyy_mm_dd(self, s: str) -> str:
        t = str(s or "").strip()
        t = re.sub(r"[./]", "-", t)
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
        if m:
            y, mo, d = m.groups()
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", t)
        if m:
            y, mo, d = m.groups()
            return f"{y}-{mo}-{d}"
        return t

    def enrich_selected_with_ai(self):
        key = self.ent_api.get().strip()
        if not key:
            messagebox.showwarning("경고", "OpenAI API Key를 먼저 입력/저장하세요.")
            return
        sels = self.tree.selection()
        if not sels:
            messagebox.showinfo("안내", "AI로 보강할 행을 선택하세요.")
            return
        idxs = [int(self.tree.set(i, "__index__")) for i in sels]
        threading.Thread(target=self._ai_enrich_selected_worker, args=(idxs,), daemon=True).start()

    def _ai_enrich_selected_worker(self, idxs: List[int]):
        try:
            self._set_status("AI 보강…")
            api_key = self.ent_api.get().strip()
            model = self.cmb_model.get().strip() or "gpt-5-mini"
            thr = float(self.var_threshold.get())
            allow_over = bool(self.var_overwrite.get())
            ctx = self._build_assets_context()
            required_headers = ["카테고리 (필수)", "모델 (필수)"]

            self._log(f"[AI] 설정: model={model} thr={thr} overwrite={allow_over}")

            for idx in idxs:
                it = self.staged[idx]
                before_cat = str(it.values.get("카테고리 (필수)", "") or "")
                before_model = str(it.values.get("모델 (필수)", "") or "")

                rsp = enrich_selected_item(
                    api_key=api_key,
                    model=model,
                    current_values=it.values,
                    ap_aggregate=it.ap_row,
                    assets_context=ctx,
                    category_candidates=self.category_candidates,
                    required_headers=required_headers,
                    threshold=thr,
                    allow_overwrite=allow_over,
                    timeout_s=30.0,
                    log_prompt=True
                )

                used_model = rsp.get("_used_model", model)
                trace_id = rsp.get("_trace_id", "-")
                conf = rsp.get("confidence", 0.0)
                missing = rsp.get("missing_required", []) or []
                diag = rsp.get("diag", {}) or {}
                ai_raw = diag.get("ai_values_raw", {}) or {}
                cat_diag = diag.get("category", {}) or {}
                reasons = diag.get("reasons_count", {}) or {}
                apply_log = diag.get("apply_log", {}) or {}

                new_vals = rsp.get("values", {}) or {}

                # (중요) 무조건 대입으로 변경 — 키 존재 조건 삭제
                applied_keys = []
                for k, v in new_vals.items():
                    prev = it.values.get(k, None)
                    it.values[k] = v
                    if prev != v:
                        applied_keys.append(k)

                after_cat = str(it.values.get("카테고리 (필수)", "") or "")
                after_model = str(it.values.get("모델 (필수)", "") or "")

                # 상세 로그
                self._log(
                    "[AI][rsp] "
                    f"row={it.ap_key} used_model={used_model} trace={trace_id} "
                    f"conf={conf:.3f} thr={thr:.3f} "
                    f"missing={missing}"
                )
                # 원인 추정에 필요한 핵심 지표
                self._log(
                    "[AI][diag] "
                    f"before_cat='{before_cat}' -> after_cat='{after_cat}', "
                    f"before_model='{before_model}' -> after_model='{after_model}'"
                )
                self._log(
                    "[AI][diag] "
                    f"ai_raw.cat='{ai_raw.get('카테고리 (필수)', '')}', "
                    f"cat.norm='{cat_diag.get('normalized','')}', "
                    f"cat.matched={cat_diag.get('matched', False)}, "
                    f"cat.matched_value='{cat_diag.get('matched_value','')}'"
                )
                self._log(
                    "[AI][diag] reasons={}".format(
                        ", ".join([f"{k}:{v}" for k, v in reasons.items() if v])
                    )
                )
                # 필드별 적용/미적용 사유 상위 6개만 샘플
                sample_keys = list(apply_log.keys())[:6]
                for sk in sample_keys:
                    self._log(f"[AI][apply] {sk} -> {apply_log[sk]}")

                self._refresh_tree_row(idx)

            self._set_status("AI 보강 완료")
            self._log(f"AI 보강 완료: {len(idxs)}건")

        except Exception as e:
            self._set_status("AI 보강 실패")
            self._log(f"[오류] AI 보강 실패: {e}")
            messagebox.showerror("AI 보강 실패", str(e))

    def dlog(self, m: str):
        if self.cfg.get("AI_DEBUG_LOG", True):
            self._log(m)

    def _build_assets_context(self) -> Dict[str, Any]:
        data = self.sheets.values_get(self.cfg["ASSETS_SPREADSHEET_ID"], A1(self.cfg["ASSETS_SHEET_NAME"], "1:10000"))
        if not data or len(data) < 2:
            return {}
        header = data[0]
        body = data[1:]
        idx = normalize_header_map(header)
        fields = [
            "브랜드", "구매처", "결재수단", "소유 유형", "자산상태 (필수)",
            "위치", "모델 (필수)", "세부제품명", "구매일", "카테고리 (필수)"
        ]
        col = {f: idx[f] for f in fields if f in idx}
        samples = []
        for r in body[-int(self.cfg.get("ASSETS_CONTEXT_MAX_ROWS", 120)):]:
            row = {}
            for f, j in col.items():
                if j < len(r) and str(r[j]).strip():
                    row[f] = str(r[j]).strip()
            if row:
                samples.append(row)
        from collections import Counter
        pattern = {f: Counter([s.get(f) for s in samples if s.get(f)]) for f in fields}
        topk = {f: [x for x, _ in pattern[f].most_common(8)] for f in pattern}
        return {"top_values": topk, "examples": samples[:60]}

    def _fixup_model_from_ap(self, values: Dict[str, Any], ap_agg: Dict[str, Any]) -> None:
        m = str(values.get("모델 (필수)", "") or "").strip()
        generic_tokens = ["지출 품의서", "지출품의서", "품의서", "세금계산서", "계약서", "견적서"]
        looks_generic = (not m) or any(tok in m for tok in generic_tokens)
        if not looks_generic:
            return
        text_parts = [
            str(ap_agg.get("품목명", "")),
            str(ap_agg.get("__ap_notes", "")),
            str(ap_agg.get("비고", "")),
            str(values.get("비고", "")),
        ]
        from mapping_rules import clean_asset_title
        cleaned = clean_asset_title(" ".join([t for t in text_parts if t]).strip())
        if cleaned:
            values["모델 (필수)"] = cleaned

    def add(self, it: StagedItem):
        self.staged.append(it)
        self._insert_tree_item(len(self.staged) - 1)

    def _validate_required(self, rec: Dict[str, Any], required: List[str]) -> List[str]:
        miss = []
        for h in required:
            v = str(rec.get(h, "") or "").strip()
            if not v:
                miss.append(h)
        return miss

    def validate_all(self):
        required = list(self.cfg.get("REQUIRED_HEADERS", ["관리번호 (필수)", "카테고리 (필수)", "모델 (필수)", "자산상태 (필수)"]))
        ok = 0
        fail = 0
        for i, it in enumerate(self.staged):
            if it.deleted:
                continue
            miss = self._validate_required(it.values, required)
            it.valid = not bool(miss)
            tag = []
            if it.deleted:
                tag.append("deleted")
            if it.suspect:
                tag.append("suspect")
            self.tree.item(f"row-{i}", tags=tuple(tag))
            if it.valid:
                ok += 1
            else:
                fail += 1
        self._log(f"검증 완료: 유효 {ok}건, 누락 {fail}건")

    def commit_upload(self):
        threading.Thread(target=self._commit_thread, daemon=True).start()

    def _commit_thread(self):
        try:
            self._set_status("업로드 준비…")
            to_push = [it for it in self.staged if (not it.deleted)]
            if not to_push:
                messagebox.showinfo("안내", "업로드할 항목이 없습니다.")
                return
            required = list(self.cfg.get("REQUIRED_HEADERS", ["관리번호 (필수)", "카테고리 (필수)", "모델 (필수)", "자산상태 (필수)"]))
            invalid = [it for it in to_push if self._validate_required(it.values, required)]
            if invalid:
                messagebox.showwarning("검증 필요", f"필수값 누락 {len(invalid)}건이 있습니다.")
                return

            rows_dicts = [{h: str(it.values.get(h, "") or "") for h in self.assets_display_headers} for it in to_push]
            rows_dicts = bulk_assign_management_numbers(
                self.sheets,
                self.cfg["ASSETS_SPREADSHEET_ID"],
                self.cfg["ASSETS_SHEET_NAME"],
                rows_dicts,
                category_sheet_name=self.cfg.get("CATEGORY_SHEET_NAME", "카테고리번호 리스트")
            )

            count = len(rows_dicts)
            start_row, end_row = self.sheets.insert_rows_copy_template(
                self.cfg["ASSETS_SPREADSHEET_ID"],
                self.cfg["ASSETS_SHEET_NAME"],
                count,
                self.assets_total_cols,
                int(self.cfg.get("ASSETS_TEMPLATE_ROW_INDEX_1_BASED", 2))
            )

            col_payloads = []
            for i, h in enumerate(self.assets_headers):
                if h not in self.assets_display_headers:
                    continue
                if i in self.assets_formula_cols:
                    continue
                col_letter_str = col_letter(i)
                rng = A1(self.cfg["ASSETS_SHEET_NAME"], f"{col_letter_str}{start_row}:{col_letter_str}{end_row}")
                col_vals = [[rows_dicts[r].get(h, "")] for r in range(count)]
                col_payloads.append({"range": rng, "values": col_vals})
            if col_payloads:
                self.sheets.values_batch_update_columns(self.cfg["ASSETS_SPREADSHEET_ID"], col_payloads)

            self._set_status("업로드 완료")
            self._log(f"업로드 완료: {count}건")
            messagebox.showinfo("완료", f"업로드 완료: {count}건")
        except Exception as e:
            self._set_status("업로드 실패")
            self._log(f"[오류] 업로드 실패: {e}")
            messagebox.showerror("업로드 실패", str(e))

    def _set_status(self, s: str):
        self.status.set(s)
        self.update_idletasks()

    def _log(self, s: str):
        self.log.configure(state="normal")
        self.log.insert("end", f"{datetime.now().strftime('%H:%M:%S')} {s}\n")
        self.log.configure(state="disabled")
        self.log.see("end")


if __name__ == "__main__":
    App().mainloop()
