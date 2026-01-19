# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
from datetime import datetime, date, timedelta
from collections import Counter

from config import STOPWORDS_IN_TITLE, AP_COL_ALIASES

# ────────────────────────── 공통 유틸 ──────────────────────────
def normalize_header_map(headers: List[str]) -> Dict[str, int]:
    return {h.strip(): i for i, h in enumerate(headers)}

def find_header(headers: List[str], candidates: List[str]) -> Optional[str]:
    lower = {h.replace(" ", "").lower(): h for h in headers}
    for c in candidates:
        key = c.replace(" ", "").lower()
        if key in lower:
            return lower[key]
    for c in candidates:
        key = c.replace(" ", "").lower()
        for k, v in lower.items():
            if key in k:
                return v
    return None

def to_ymd(s: Any) -> str:
    if s is None or s == "":
        return ""
    if isinstance(s, (datetime, date)):
        return s.strftime("%Y-%m-%d")
    t = str(s).strip()

    m = re.search(r"^(20\d{6})(?!\d)", t)  # 맨 앞 8자리
    if m:
        ymd = m.group(1)
        return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(20\d{2})[./-]?(\d{1,2})[./-]?(\d{1,2})", t)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ""

def to_int(s: Any) -> Optional[int]:
    if s is None or s == "":
        return None
    t = str(s).replace(",", "").replace(" ", "")
    m = re.search(r"-?\d+", t)
    try:
        return int(m.group()) if m else None
    except Exception:
        return None

def detect_rental(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ["임차","렌탈","구독","월 결제","월과금","lease", "rent"])

def detect_brand_from_item(item: str) -> str:
    if not item:
        return ""
    m = re.match(r"\s*\[([^\]]+)\]", item)
    return m.group(1).strip() if m else ""

def clean_asset_title(name: str) -> str:
    if not name: return ""
    s = str(name)
    for w in STOPWORDS_IN_TITLE: s = s.replace(w, " ")
    s = re.sub(r"[\[\]{}()]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -_/\\\t\r\n")
    return s

def parse_model_and_detail(raw_title: str) -> Tuple[str, str]:
    if not raw_title:
        return "", ""
    s = re.sub(r'^\s*\[[^\]]+\]\s*', "", str(raw_title))
    for w in STOPWORDS_IN_TITLE: s = s.replace(w, " ")
    s = s.replace('"',' ').replace("'", " ")
    s = re.sub(r"[\[\]{}()]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -_/\\\t\r\n")

    parts = re.split(r"\s[-—:|]\s|[-—:|]", s, maxsplit=1)
    model, detail = (parts[0].strip(), parts[1].strip()) if len(parts)==2 else (s, "")

    def _tokens(text): return [t for t in re.split(r"[ \t]+", (text or "").strip()) if t]
    toks = _tokens(s)
    modelish = [t for t in toks if re.search(r"[A-Za-z].*\d|\d.*[A-Za-z]", t)]
    if (len(model) <= 2) or (model in {"서", "문서", "기안", "경비", "기기"}):
        model = max(modelish, key=len) if modelish else (max(toks, key=len) if toks else model)

    detail = detail.replace('"',' ').replace("'"," ")
    detail = re.sub(r"\s{2,}", " ", detail).strip(" -_/\\\t\r\n")
    if len(detail) == 1: detail = ""
    return model, detail

def infer_payment_method(notes: str, has_account: bool, row_text: str) -> str:
    t = f"{notes or ''} {row_text or ''}".lower()
    if "연구비계좌이체(데모)".lower() in t: return "연구(데)-계좌이체"
    if has_account or re.search(r"\d{2,}[- ]?\d{2,}[- ]?\d{2,}", t): return "운영-계좌이체"
    for pat in [r"법인카드[- ]?\d{4}", r"카드[- ]?\d{4}", r"신한카드", r"국민카드", r"삼성카드", r"현대카드", r"BC카드"]:
        mm = re.search(pat, t, re.I)
        if mm: return mm.group(0)
    return ""

# ────────────────────────── 구성원 인덱스 ──────────────────────────
@dataclass
class MemberIndex:
    index: Dict[str, Dict[str, str]]

    @staticmethod
    def build_from_sheet(sheets_client, cfg) -> "MemberIndex":
        rng = f"'구성원'!1:1000"
        data = sheets_client.values_get(cfg["ASSETS_SPREADSHEET_ID"], rng)
        if not data: return MemberIndex({})
        header = data[0]; idx = normalize_header_map(header)
        def find(cands, default=None):
            h = find_header(header, cands) or default
            return h
        name_h = find(["이름","성명","Name"], "이름")
        nick_h = find(["닉네임","별명","Nick","Nickname","Handle"], None)
        email_h= find(["이메일","메일","Email"], "이메일")
        team_h = find(["팀","부서","Team"], None)
        loc_h  = find(["위치","근무지","Location","사무실","호수","룸","지점","site","Site","room","Room"], None)

        def get(row, h):
            if h is None: return ""
            j = idx.get(h, -1)
            return str(row[j]).strip() if 0 <= j < len(row) and row[j] is not None else ""

        def norm_keys(s: str) -> list:
            if not s: return []
            raw=s.strip(); low=raw.lower()
            compact = re.sub(r"[\s]+","", low)
            bare = re.sub(r"[\s\W_]+","", low)
            return list({raw, low, compact, bare})

        result = {}
        for row in data[1:]:
            if not any(row): continue
            rec = {"이름": get(row,name_h), "닉네임": get(row,nick_h), "이메일": get(row,email_h),
                   "팀": get(row,team_h), "위치": get(row,loc_h)}
            keys=set()
            keys.update(norm_keys(rec["이름"]))
            keys.update(norm_keys(rec["닉네임"]))
            keys.update(norm_keys(rec["이메일"]))
            for k in keys:
                result[k]=rec
        return MemberIndex(result)

    def resolve(self, requester_hint: str, cfg) -> Tuple[str,str]:
        if not requester_hint: return ("","")
        s = requester_hint.strip()
        cands=[]
        m = re.search(r"[\w\.-]+@[\w\.-]+", s)
        if m: cands.append(m.group(0).lower())
        parts = re.split(r"[\/ ,]|[()\[\]]", s); parts.append(s)
        for p in parts:
            p=p.strip()
            if not p: continue
            low=p.lower(); cands.extend([low, re.sub(r"[\s\W_]+","",low)])

        for c in cands:
            if c in self.index:
                rec=self.index[c]
                nick = rec.get("닉네임") or rec.get("이름") or ""
                loc  = rec.get("위치") or cfg.get("TEAM_TO_LOCATION",{}).get(rec.get("팀",""), rec.get("팀",""))
                return (nick, loc)
        for rec in self.index.values():
            for key in [rec.get("닉네임",""), rec.get("이름",""), rec.get("이메일","")]:
                if not key: continue
                k=key.lower()
                if any((len(c)>=2 and (k in c or c in k)) for c in cands):
                    nick = rec.get("닉네임") or rec.get("이름") or ""
                    loc  = rec.get("위치") or cfg.get("TEAM_TO_LOCATION",{}).get(rec.get("팀",""), rec.get("팀",""))
                    return (nick, loc)
        return ("","")

# ────────────────────────── 집계 / 매핑 ──────────────────────────
def aggregate_ap_rows(docno_display: str, rows: List[List[Any]], headers: List[str], ap_map: Dict[str,int], member_index: MemberIndex, cfg) -> Dict[str, Any]:
    def get_val(row, h):
        j = ap_map.get(h, -1)
        return row[j] if (j >= 0 and j < len(row)) else ""

    def pick(row, key):
        cand = AP_COL_ALIASES.get(key, [key])
        h = find_header(headers, cand) or key
        return get_val(row, h)

    items, payees, amounts = [], [], []
    dates_inv, dates_pay = [], []
    requesters, requester_emails = [], []
    banks, accts, notes = [], [], []
    h_note = find_header(headers, ["비고","메모","사유","설명","비고/메모"]) or None

    for r in rows:
        items.append(str(pick(r, "품목")))
        payees.append(str(pick(r, "수취인")))
        am = to_int(pick(r, "금액")); amounts.append(am or 0)
        d1 = to_ymd(pick(r, "세금계산서 수령"));  d2 = to_ymd(pick(r, "이체 날짜"))
        if d1: dates_inv.append(d1)
        if d2: dates_pay.append(d2)
        rq = str(pick(r, "요청자")).strip()
        if rq: requesters.append(rq)
        em = str(pick(r, "요청자이메일")).strip()
        if em: requester_emails.append(em)
        banks.append(str(pick(r, "은행"))); accts.append(str(pick(r, "계좌번호")))
        if h_note: notes.append(str(get_val(r, h_note)))

    def first_nonempty(seq):
        for x in seq:
            if str(x).strip(): return str(x).strip()
        return ""

    payees_clean = [p for p in payees if str(p).strip()]
    payee = Counter(payees_clean).most_common(1)[0][0] if payees_clean else first_nonempty(payees)

    inv_date = min(dates_inv) if dates_inv else ""
    pay_date = inv_date

    requester_hint = first_nonempty(requesters) or first_nonempty(requester_emails)
    nick, loc = member_index.resolve(requester_hint, cfg)

    cleaned_candidates = []
    for it in items:
        m, d = parse_model_and_detail(it)
        if m:
            cleaned_candidates.append((m, d, len(m)+len(d)))
    if cleaned_candidates:
        m, d, _ = max(cleaned_candidates, key=lambda x: x[2])
    else:
        m, d = "", ""

    brand = ""
    for it in items:
        b = detect_brand_from_item(it)
        if b: brand=b; break

    is_rent = any(detect_rental(str(x)) for x in items)

    notes_join = " / ".join([n for n in notes if n])
    has_account = any(bool(re.search(r"\d{2,}[- ]?\d{2,}[- ]?\d{2,}", x)) for x in accts)
    row_blob = " ".join(items + payees + banks + accts)
    pay_method = infer_payment_method(notes_join, has_account, row_blob)

    total_amount = sum(x for x in amounts if isinstance(x, int))

    ap_agg = {
        "문서번호": docno_display,
        "요청자": requester_hint,
        "수취인": payee,
        "금액합계": total_amount or "",
        "세금계산서 수령": inv_date,
        "이체 날짜": pay_date,
        "__prefill_model": m,
        "__prefill_detail": d,
        "__prefill_brand": brand,
        "__nick": nick,
        "__loc": loc,
        "__is_rent": is_rent,
        "__payment_method": pay_method,
        "__ap_notes": notes_join.strip(),
        "비고": (f"문서번호:{docno_display}" if docno_display else "문서번호:") + (f" | {notes_join.strip()}" if notes_join else "")
    }

    if brand: ap_agg["브랜드"] = brand
    if payee: ap_agg["구매처"] = payee
    if total_amount: ap_agg["구매 가격 (원)"] = total_amount
    if inv_date: ap_agg["구매일"] = inv_date
    if pay_date: ap_agg["지급일"] = pay_date
    if nick: ap_agg["기기 사용자 (없을 시 공란)"] = nick
    if loc: ap_agg["위치"] = loc
    if pay_method: ap_agg["결재수단"] = pay_method
    if is_rent:
        ap_agg["렌탈 공급자"] = payee
        ap_agg["렌탈 금액"] = total_amount
    return ap_agg


def map_rule_based_to_assets(ap_agg: Dict[str, Any], display_headers: List[str], cfg) -> Dict[str, Any]:
    """
    개선된 규칙기반 매핑:
    - '모델 (필수)'가 '지출 품의서' 등 일반명사일 경우, 세부제품명/비고에서 실질 키워드 추출
    - 카테고리 1차 추정(후보 리스트 기준으로 퍼지 매칭) → AI가 재검증하도록 힌트 제공
    """
    values = {h: "" for h in display_headers}
    values["카테고리 (필수)"] = ""

    def _clean_title(t: str) -> str:
        t = str(t or "").strip()
        t = re.sub(r"[\[\]{}()]", " ", t)
        t = re.sub(r"\s+", " ", t)
        t = t.replace("의 건", "").strip()
        return t

    def _pick_product_line(blob: str) -> str:
        b = (blob or "").upper()
        if "MAGSABER" in b or "SABER" in b:
            return "SABER"
        if "MAGSPACER" in b or "SPACER" in b:
            return "SPACER"
        if "VISION" in b:
            return "VISION"
        if "BLADE" in b:
            return "BLADE"
        return ""

    def _is_subscription(blob: str) -> bool:
        return bool(re.search(r"(임차|임대|구독|렌탈|subscription)", str(blob)))

    def _is_software(blob: str) -> bool:
        return bool(re.search(r"\b(CST|MATLAB|한컴|Adobe|Autodesk|Ansys|SolidWorks|Office|라이선스|소프트웨어)\b", str(blob), re.IGNORECASE))

    # ----- 모델 / 세부제품명 -----
    model  = (ap_agg.get("__prefill_model","") or "").strip()
    detail = (ap_agg.get("__prefill_detail","") or "").strip()
    generic_models = {"서","문서","경비","지출","지출 품의서"}

    if not model or model in generic_models:
        hint = _clean_title(detail) or _clean_title(ap_agg.get("__ap_notes",""))
        # 명시적 소프트웨어 패턴
        m = re.search(r"(CST\s*Studio\s*Suite\s*\d{4})", hint, flags=re.IGNORECASE)
        if m:
            model = m.group(1).replace("  "," ")
        else:
            line = _pick_product_line(hint)
            if line:
                model = f"Mag{line.title()}"
            else:
                tokens = [t for t in re.split(r"\s+", (_clean_title(ap_agg.get('구매처','')) + ' ' + hint).strip()) if t]
                model = " ".join(tokens[:3]) if tokens else "자산"
        # detail은 원문 유지 (너무 길면 빈칸)
        if len(detail) == 1:
            detail = ""

    model  = _clean_title(model)
    detail = _clean_title(detail)

    if "모델 (필수)" in values:
        values["모델 (필수)"] = model
    if "세부제품명" in values:
        values["세부제품명"] = detail

    # ----- 기본 복사 -----
    for k in ["브랜드","구매처","구매 가격 (원)","결재수단","위치",
              "렌탈 공급자","렌탈 금액","비고","기기 사용자 (없을 시 공란)"]:
        if k in values and ap_agg.get(k) not in (None,""):
            values[k]=ap_agg[k]

    buy_date = ap_agg.get("구매일","")
    if "구매일" in values: values["구매일"]=buy_date
    if "지급일" in values: values["지급일"]=buy_date

    if "자산상태 (필수)" in values: values["자산상태 (필수)"] = cfg.get("DEFAULT_ASSET_STATUS","사용")
    if "소유 유형" in values: values["소유 유형"] = "법인"

    if "자산 수정일" in values and not str(values["자산 수정일"]).strip():
        values["자산 수정일"] = datetime.now().strftime("%Y-%m-%d")

    # ----- 1차 카테고리 추정 -----
    blob = " ".join([
        str(ap_agg.get("__prefill_model","")),
        str(ap_agg.get("__prefill_detail","")),
        str(ap_agg.get("__ap_notes","")),
        str(values.get("세부제품명","")),
        str(values.get("모델 (필수)","")),
        str(ap_agg.get("구매처",""))
    ])

    def _ratio(a: str, b: str) -> float:
        try:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, a, b).ratio() if a and b else 0.0
        except Exception:
            return 0.0

    guess = ""
    if _is_software(blob):
        guess = "SW-구독 라이선스" if _is_subscription(blob) or ap_agg.get("__is_rent") else "SW-영구 라이선스"
    elif re.search(r"(모니터|monitor)", blob, re.IGNORECASE):
        guess = "IT-모니터"
    elif re.search(r"(랩탑|notebook|노트북)", blob, re.IGNORECASE):
        guess = "IT-랩탑"
    elif re.search(r"\bPC\b|본체|데스크탑", blob, re.IGNORECASE):
        guess = "IT-PC"
    elif re.search(r"서버", blob):
        guess = "IT-서버"
    elif re.search(r"의자|체어", blob):
        guess = "가구-의자"
    elif re.search(r"책상|데스크", blob):
        guess = "가구-책상"
    elif re.search(r"서랍", blob):
        guess = "가구-이동형 서랍"
    elif re.search(r"테이블", blob):
        guess = "가구-회의용 테이블"
    elif re.search(r"금형|사출|제작|양산|도금", blob):
        line = _pick_product_line(blob)
        guess = f"제품-{line} 제품" if line else "제품-기타 재고자산"

    if guess and cfg.get("CATEGORY_CHOICES"):
        best = ""
        best_r = -1.0
        for c in cfg["CATEGORY_CHOICES"]:
            r = _ratio(guess, c)
            if r > best_r:
                best_r, best = r, c
        if best and best_r >= float(cfg.get("CAT_FUZZY_MIN", 0.55)):
            values["카테고리 (필수)"] = best

    return values

def group_by_docno(ap_data: List[List[Any]], headers: List[str]) -> Dict[str, List[List[Any]]]:
    hm = normalize_header_map(headers)
    doc_h = find_header(headers, AP_COL_ALIASES["문서번호"]) or None
    doc_idx = hm.get(doc_h, None) if doc_h else None

    groups: Dict[str, List[List[Any]]] = {}
    for i, r in enumerate(ap_data):
        raw = ""
        if doc_idx is not None and doc_idx < len(r):
            raw = str(r[doc_idx]).strip()
        key = raw if raw else f"__row_{i+2}"
        groups.setdefault(key, []).append(r)
    return groups

def is_suspect_duplicate(candidate: Dict[str, Any], existing_rows: List[Dict[str,Any]], rule: Dict[str,Any]) -> bool:
    try:
        wnd = int(rule.get("DATE_WINDOW_DAYS", 5))
        tol = int(rule.get("AMOUNT_TOLERANCE", 0))
        fields = list(rule.get("FIELDS", ["구매처","구매 가격 (원)"]))
        cand_date = candidate.get("구매일","")
        cdt = datetime.strptime(cand_date, "%Y-%m-%d") if cand_date else None

        for rec in existing_rows:
            ok = True
            for f in fields:
                if str(candidate.get(f,"")).strip() != str(rec.get(f,"")).strip():
                    ok=False; break
            if not ok: continue

            if cdt:
                rdt = rec.get("구매일","")
                rdt = datetime.strptime(rdt, "%Y-%m-%d") if rdt else None
                if rdt:
                    if abs((cdt - rdt).days) > wnd:
                        continue
            ca = candidate.get("구매 가격 (원)")
            ra = rec.get("구매 가격 (원)")
            if ca is not None and ra is not None:
                try:
                    if abs(int(ca) - int(ra)) > tol:
                        continue
                except:
                    pass
            return True
        return False
    except Exception:
        return False
