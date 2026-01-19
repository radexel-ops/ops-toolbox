
"""
mgmt_number.py
--------------
관리번호 자동부여 헬퍼 모듈.

요구사항 요약
- "관리번호 앞자리"에 의존하지 말고, **카테고리 (필수)** 와 **구매일**만으로 생성
- 카테고리 → 알파벳 코드 매핑은
  1) 자산현황 시트의 기존 데이터(실사용 값)에서 **우선 학습**
  2) "카테고리번호 리스트" 시트를 **보조 소스**로 로드
  (절대 하드코딩 금지)
- 최종 관리번호 포맷: "<알파벳코드><YYYY>-<MM><순번2자리><알파벳2자리>"
  예) T-EQ-RDE2024-1201AA

Public API
- fill_management_numbers_for_rows(sheets, spreadsheet_id, assets_sheet_name, category_sheet_name, rows_to_insert, default_alpha="AA")
- bulk_assign_management_numbers(...)  # 래퍼(호환): 4 또는 5개 인자 호출/구버전(2개 인자) 모두 수용

주의
- 매핑 실패시 UNDEF 등을 쓰지 않고 **값을 비워둠**
- 순번은 동일 prefix 내 기존 + 이번 배치 예약을 모두 고려해 01..99 중 미사용 선택
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple, Any

# 패턴들
PAT_ALPHA_CODE = re.compile(r"^[A-Z](?:-[A-Z]{2,4}){2,6}$")  # 예: T-PD-SMD, I-SW-SUB
PAT_FULL_MGMT = re.compile(
    r"^(?P<alpha>[A-Z](?:-[A-Z]{2,4}){2,6})(?P<yyyy>\d{4})-(?P<mm>\d{2})(?P<seq>\d{2})(?P<aa>[A-Z]{2})$"
)

def _excel_serial_to_date_str(serial: int) -> Optional[str]:
    """엑셀 일련값(1900 system) → 'YYYY-MM-DD' 문자열. 잘못된 경우 None."""
    try:
        # Excel 1900 date system: day 1 is 1899-12-31, but Excel incorrectly treats 1900 as leap.
        # Python correct base: 1899-12-30 to reproduce Excel serial (incl. 1900-02-29 bug position)
        base = datetime(1899, 12, 30)
        d = base + timedelta(days=int(serial))
        return d.strftime("%Y-%m-%d")
    except Exception:
        return None

def _yyyymm_from_date(date_val: Any) -> Optional[Tuple[str, str]]:
    """
    입력이 'YYYY-MM-DD' 또는 엑셀 일련값(문자열 숫자 포함)일 때 ('YYYY','MM') 반환.
    실패 시 None.
    """
    if date_val is None:
        return None
    s = str(date_val).strip()
    if not s:
        return None

    # 엑셀 일련값 추정
    if s.isdigit() and len(s) <= 5:
        ds = _excel_serial_to_date_str(int(s))
        if ds:
            y, m, _ = ds.split("-")
            return (y, m)

    # 일반 날짜 포맷: YYYY[-./]MM[-./]DD
    s = s.replace(".", "-").replace("/", "-")
    parts = s.split("-")
    try:
        if len(parts) >= 2:
            y = int(parts[0])
            m = int(parts[1])
            if 1900 <= y <= 2100 and 1 <= m <= 12:
                return (f"{y:04d}", f"{m:02d}")
    except Exception:
        pass
    return None

def _rows_from_values(values: List[List[str]]) -> List[Dict[str, str]]:
    """A1:ZZ로 가져온 values를 헤더 기반 dict 리스트로 변환."""
    if not values:
        return []
    header = values[0]
    rows: List[Dict[str, str]] = []
    for line in values[1:]:
        row = {}
        for i, key in enumerate(header):
            if not key:
                continue
            row[key] = line[i] if i < len(line) else ""
        rows.append(row)
    return rows

def _learn_category_map_from_assets(existing_rows: List[Dict[str, str]]) -> Dict[str, str]:
    """
    자산현황의 기존 데이터에서 '카테고리 (필수)' → 알파벳코드(T-PD-SMD...) 매핑을 학습.
    """
    mapping: Dict[str, str] = {}
    for r in existing_rows:
        cat = str(r.get("카테고리 (필수)", "")).strip()
        mgmt = str(r.get("관리번호 (필수)", "")).strip()
        if not cat or not mgmt:
            continue
        m = PAT_FULL_MGMT.match(mgmt)
        if not m:
            continue
        alpha = m.group("alpha")
        if PAT_ALPHA_CODE.match(alpha):
            # 이미 있다면 최초 학습값 유지(현행 사용 규칙을 우선 신뢰)
            mapping.setdefault(cat, alpha)
    return mapping

def _load_category_map_from_sheet(sheets, spreadsheet_id: str, category_sheet_name: str) -> Dict[str, str]:
    """
    '카테고리번호 리스트' 시트에서 카테고리→알파벳코드 매핑을 보조 로드.
    - 구조를 확정할 수 없으므로 A7:Z 범위를 긁고, I열(0-index 8)을 카테고리로 보되
      각 행의 나머지 셀들 중 알파벳코드 패턴에 맞는 첫 값을 코드로 사용.
    """
    mapping: Dict[str, str] = {}
    # 가급적 많은 범위를 커버
    rng = f"{category_sheet_name}!A7:Z"
    res = sheets.values_get(spreadsheet_id, rng)
    vals: List[List[str]] = res.get("values", []) if isinstance(res, dict) else []
    for line in vals:
        cat = ""
        if len(line) > 8:
            cat = str(line[8]).strip()
        if not cat:
            continue
        alpha = None
        for i, cell in enumerate(line):
            if i == 8:
                continue  # 카테고리 열 제외
            s = str(cell).strip()
            if PAT_ALPHA_CODE.match(s):
                alpha = s
                break
        if cat and alpha:
            mapping.setdefault(cat, alpha)
    return mapping

def _merge_maps(primary: Dict[str, str], secondary: Dict[str, str]) -> Dict[str, str]:
    merged = dict(secondary or {})
    merged.update(primary or {})  # primary 우선
    return merged

def _collect_existing_numbers(sheets, spreadsheet_id: str, assets_sheet_name: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """자산현황 시트 전체를 읽어 기존 관리번호 목록과 행 dict를 반환."""
    res = sheets.values_get(spreadsheet_id, f"{assets_sheet_name}!A1:ZZ")
    values: List[List[str]] = res.get("values", []) if isinstance(res, dict) else []
    rows = _rows_from_values(values)
    existing_numbers = [str(r.get("관리번호 (필수)", "")).strip() for r in rows if r.get("관리번호 (필수)")]
    return existing_numbers, rows

def _prefix_from(cat_to_alpha: Dict[str, str], category: str, y: str, m: str) -> Optional[str]:
    alpha = cat_to_alpha.get(category.strip(), "")
    if not alpha:
        return None
    return f"{alpha}{y}-{m}"  # 예: T-PD-SMD2025-06

def _collect_used_sequences(existing_numbers: Iterable[str], prefix: str, also_reserved: Optional[Set[str]] = None) -> Set[int]:
    used: Set[int] = set()
    pat = re.compile(re.escape(prefix) + r"(?P<seq>\d{2})(?P<alpha>[A-Z]{2})$", re.IGNORECASE)
    for num in existing_numbers:
        if not isinstance(num, str):
            continue
        m = pat.match(num.strip())
        if not m:
            continue
        try:
            used.add(int(m.group("seq")))
        except Exception:
            continue
    if also_reserved:
        for n in list(also_reserved):
            m = pat.match(n)
            if m:
                try:
                    used.add(int(m.group("seq")))
                except Exception:
                    pass
    return used

def _next_sequence(existing_numbers: Iterable[str], prefix: str, reserved: Set[str]) -> Optional[int]:
    used = _collect_used_sequences(existing_numbers, prefix, reserved)
    for i in range(1, 100):
        if i not in used:
            return i
    return None

def _build_mgmt(prefix: str, seq: int, alpha2: str = "AA") -> str:
    return f"{prefix}{seq:02d}{alpha2}"

def fill_management_numbers_for_rows(
    sheets,
    spreadsheet_id: str,
    assets_sheet_name: str,
    category_sheet_name: str,
    rows_to_insert: List[Dict[str, Any]],
    default_alpha: str = "AA",
) -> List[Dict[str, Any]]:
    """
    신규 업로드 대상 rows_to_insert에 대해 '관리번호 (필수)' 자동 생성(비어있는 행만).
    - 카테고리/구매일 기반, 맵 실패시 비워둠
    - 중복 방지(기존 + 이번 배치 예약)
    """
    # 1) 기존 관리번호/행 로드
    existing_numbers, existing_rows = _collect_existing_numbers(sheets, spreadsheet_id, assets_sheet_name)

    # 2) 카테고리→코드 맵 학습/로드
    learned = _learn_category_map_from_assets(existing_rows)
    from_sheet = _load_category_map_from_sheet(sheets, spreadsheet_id, category_sheet_name)
    cat_map = _merge_maps(learned, from_sheet)

    reserved: Set[str] = set()
    for r in rows_to_insert:
        cur = str(r.get("관리번호 (필수)", "") or "").strip()
        if cur:  # 이미 있으면 스킵(충돌만 방지)
            reserved.add(cur)
            continue

        category = str(r.get("카테고리 (필수)", "") or "").strip()
        yymm = _yyyymm_from_date(r.get("구매일"))
        if not category or not yymm:
            # 필수 정보 없으면 생략
            continue

        y, m = yymm
        prefix = _prefix_from(cat_map, category, y, m)
        if not prefix:
            # 매핑 실패 → 비워둠
            continue

        seq = _next_sequence(existing_numbers, prefix, reserved)
        if seq is None:
            # 99개 초과 → 여기선 실패 처리(비워둠)
            continue
        candidate = _build_mgmt(prefix, seq, default_alpha)
        r["관리번호 (필수)"] = candidate
        reserved.add(candidate)
        existing_numbers.append(candidate)  # 이후 항목들이 참고

    return rows_to_insert

# -------------------------
# 호환용 래퍼
# -------------------------

def bulk_assign_management_numbers(*args, **kwargs):
    """
    호출 호환성 유지를 위한 래퍼.
    지원 형태:
    1) (sheets, spreadsheet_id, assets_sheet_name, rows_to_insert)
       + kw: category_sheet_name="카테고리번호 리스트"
    2) (sheets, spreadsheet_id, assets_sheet_name, category_sheet_name, rows_to_insert)
    3) (rows, existing_numbers)  # 구버전: '관리번호 앞자리' 기반 (비권장) → 최소동작만 제공
    """
    # 형태 2)  또는 1)
    if len(args) >= 4 and not (len(args) == 2 and isinstance(args[0], list)):
        sheets = args[0]
        spreadsheet_id = args[1]
        assets_sheet_name = args[2]
        if len(args) == 4:
            # 형태 1) rows가 4번째
            rows_to_insert = args[3]
            category_sheet_name = kwargs.get("category_sheet_name", "카테고리번호 리스트")
        else:
            # 형태 2)
            category_sheet_name = args[3]
            rows_to_insert = args[4]
        default_alpha = kwargs.get("default_alpha", "AA")
        return fill_management_numbers_for_rows(
            sheets, spreadsheet_id, assets_sheet_name, category_sheet_name, rows_to_insert, default_alpha
        )

    # 형태 3) 구버전 최소 지원
    if len(args) == 2 and isinstance(args[0], list):
        rows = args[0]
        existing_numbers = [str(x).strip() for x in args[1] if x]
        reserved: Set[str] = set()

        # 구버전은 '관리번호 앞자리'를 사용(가능하면), 없으면 스킵
        def _ensure_prefix_has_yyyymm(prefix: str, date_val: Any) -> Optional[str]:
            yymm = _yyyymm_from_date(date_val)
            if not yymm:
                return None
            y, m = yymm
            if re.search(r"\d{4}-\d{2}$", prefix):
                return prefix
            if prefix and prefix[-1].isdigit():
                return f"{prefix}-{y}-{m}"
            return f"{prefix}{y}-{m}"

        for r in rows:
            if r.get("관리번호 (필수)"):
                continue
            front = str(r.get("관리번호 앞자리", "") or "").strip()
            if not front:
                continue
            front = _ensure_prefix_has_yyyymm(front, r.get("구매일"))
            if not front:
                continue
            # 순번 찾기
            pat = re.compile(re.escape(front) + r"(?P<seq>\d{2})(?P<aa>[A-Z]{2})$")
            used = set()
            for ex in existing_numbers:
                m = pat.match(str(ex).strip())
                if m:
                    try:
                        used.add(int(m.group("seq")))
                    except Exception:
                        pass
            for n in list(reserved):
                m = pat.match(n)
                if m:
                    try:
                        used.add(int(m.group("seq")))
                    except Exception:
                        pass
            seq = None
            for i in range(1, 100):
                if i not in used:
                    seq = i
                    break
            if seq is None:
                continue
            candidate = f"{front}{seq:02d}AA"
            r["관리번호 (필수)"] = candidate
            reserved.add(candidate)
            existing_numbers.append(candidate)
        return rows

    raise TypeError("bulk_assign_management_numbers: unsupported call signature")
