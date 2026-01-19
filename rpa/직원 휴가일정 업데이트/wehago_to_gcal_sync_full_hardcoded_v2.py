# -*- coding: utf-8 -*-
"""
WEHAGO → Google Calendar Sync (Vacations, GROUPED, Nickname) – FULL(종일) 통일판
- ALD(올데이)와 FD(시간형 종일)를 내부적으로 "FULL" 하나로 통일
- 수기 이벤트(올데이/시간형 혼재)도 안전 매칭/정리
- 멱등성 보장: 동일 내용이면 PATCH 생략, 404/410 삭제 오류 무시

사용 예시:
  python wehago_to_gcal_sync_full.py --dry-run
  python wehhago_to_gcal_sync_full.py
"""
from __future__ import annotations


import os, re, json, argparse, logging, hashlib, datetime as dt
import sys, traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Iterable
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

from zoneinfo import ZoneInfo

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.auth.exceptions import RefreshError

import urllib.request, urllib.error

# ------------- 환경 설정 -------------
DOWNLOAD_DIR = Path.cwd() / "wehago_downloads"          # WEHAGO 엑셀 폴더
# CALENDAR_ID  = "c_30a180676d3193946924d3f0c107988c686830f4ba28c49952eb832b68d60476@group.calendar.google.com" #테스트용. 채용일정 캘린더
CALENDAR_ID  = "c_a691b5b6d11b9c1717fdc1a4ef2bf106b9a5cd76c90605337bd5dca7546ce3ad@group.calendar.google.com"
TZNAME       = "Asia/Seoul"

SHEETS_SPREADSHEET_ID = "1bQA0tYIa-jU3DG_t29KWjvYDxQCN6EAj70adGD315zo"
SHEETS_RANGE = "'직원 정보'!A:Z"  # 이름 / 닉네임

# OAuth (Desktop) - 환경변수에서 로드
CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
TOKEN_PATH = Path(__file__).with_name("token.json")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s | %(message)s")

# ------------- Slack 알림 설정 (환경변수에서 로드) -------------
SLACK_TOKEN   = os.getenv("SLACK_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "C08V9CA0UPM")  # 테스트 채널
# SLACK_CHANNEL = "D06NS3K1N5N"  # 테스트 채널



def _slack_enabled() -> bool:
    return bool(SLACK_TOKEN and SLACK_CHANNEL)

def slack_post(text_msg: str):
    if not _slack_enabled():
        return
    try:
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=json.dumps({"channel": SLACK_CHANNEL, "text": text_msg}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {SLACK_TOKEN}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                logging.warning("Slack post failed: %s", data)
    except Exception as e:
        logging.warning("Slack post error: %s", e)

def _fmt_dt_range(start_iso: str, end_iso: str) -> str:
    try:
        st = dt.datetime.fromisoformat(start_iso).astimezone(ZoneInfo(TZNAME))
        et = dt.datetime.fromisoformat(end_iso).astimezone(ZoneInfo(TZNAME))
        return f"{st.strftime('%Y-%m-%d %H:%M')}–{et.strftime('%H:%M')}"
    except Exception:
        return f"{start_iso} ~ {end_iso}"

def _slack_text(prefix: str, summary: str, start_iso: str, end_iso: str, extra: Optional[str]=None) -> str:
    t = _fmt_dt_range(start_iso, end_iso)
    msg = f"[WEHAGO→GCal Sync] {prefix}: {summary} | {t}"
    if extra:
        msg += f" | {extra}"
    return msg

# ------------- 문자열/제목 헬퍼 -------------
_title_space_re = re.compile(r"\s+")
_paren_map = str.maketrans({"（":"(", "）":")", "［":"[", "］":"]", "｛":"{", "｝":"}", "【":"[", "】":"]", "《":"<", "》":">"})

def normalize_title(title: str) -> str:
    s = (title or "").translate(_paren_map)
    s = re.sub(r"[\/·ㆍ・•&]+", ",", s)  # 구분자 통일
    s = _title_space_re.sub(" ", s).strip()
    return s

def timekey_from_title(title: str) -> Optional[str]:
    """
    제목으로 AM/PM/FULL 분류 (한글/괄호/구두점 환경에서 \b 경계 문제를 피하도록 단순 토큰 포함 규칙 채택)
    - '오전' 또는 '오후'가 보이고, '반차/휴가/연차/대휴/휴무' 등 휴가계 키워드가 함께 있으면 각각 AM/PM
    - 위 키워드만 있고 오전/오후 언급이 없으면 FULL
    """
    s = normalize_title(title)
    s_low = s.lower()

    # 오전/오후 힌트
    has_am = ("오전" in s) or (" am" in s_low) or s_low.startswith("am ") or s_low.endswith(" am") or (" am " in s_low)
    has_pm = ("오후" in s) or (" pm" in s_low) or s_low.startswith("pm ") or s_low.endswith(" pm") or (" pm " in s_low)

    # 휴가계 키워드 (필요시 추가 가능)
    vac_tokens = ("휴가", "연차", "반차", "대휴", "대체휴무", "휴무", "유급")
    has_vac = any(tok in s for tok in vac_tokens)

    if has_vac and has_pm:
        return "PM"
    if has_vac and has_am:
        return "AM"
    if has_vac and not (has_am or has_pm):
        return "FULL"
    return None


def names_from_title(title: str) -> List[str]:
    """제목에서 괄호 또는 하이픈/콜론 뒤 닉네임 리스트를 추출"""
    t = normalize_title(title)
    m = re.search(r"\(([^)]*)\)", t)
    seg = m.group(1) if m and m.group(1) else None
    if not seg:
        m2 = re.search(r"(?:-|:)\s*(.+)$", t)
        if m2: seg = m2.group(1)
    if not seg: return []
    parts = [p.strip() for p in re.split(r"\s*,\s*", seg) if p.strip()]
    stop = {"오전","오후","반차","종일","연차","휴가","유급","1일","0.5일"}
    return [p for p in parts if p not in stop]

# ------------- 공통 유틸 -------------

def _cleanup_timekey_duplicates(
    svc,
    calendar_id: str,
    date_: dt.date,
    timekey: str,
    keep_event_id: Optional[str],
    dry_run: bool,
    deleted_ids: set[str],
) -> int:
    """
    같은 날짜·같은 타임키(AM/PM/FULL)의 '휴가성' 이벤트 중에서
    keeper(업서트로 남길 1건)를 제외한 나머지를 일괄 정리.
    - 매칭 실패로 새 이벤트가 생겼더라도, 즉시 기존 수기 이벤트를 정리해 중복 방지.
    """
    cleaned = 0
    existing_now = list_events_by_day(svc, calendar_id, date_)

    for ev in existing_now:
        eid = ev.get("id")
        if not eid or eid == keep_event_id or eid in deleted_ids:
            continue
        if _looks_like_absence(ev) and _event_matches_timekey(ev, timekey):
            if dry_run:
                cleaned += 1
                logging.info("[DRY] Delete duplicate (by timekey): %s", ev.get("summary"))
            else:
                try:
                    start_iso = ev.get("start", {}).get("dateTime") or ((ev.get("start", {}) or {}).get("date", "") + "T00:00:00+09:00")
                    end_iso = ev.get("end", {}).get("dateTime") or ((ev.get("end", {}) or {}).get("date", "") + "T00:00:00+09:00")
                    slack_post(_slack_text("삭제(중복)", ev.get("summary", ""), start_iso, end_iso))
                except Exception:
                    pass
                _safe_delete(svc, calendar_id, eid)
                deleted_ids.add(eid)
                cleaned += 1
    return cleaned


def get_credentials(reset: bool=False) -> Credentials:
    creds = None
    if reset and TOKEN_PATH.exists():
        TOKEN_PATH.unlink(missing_ok=True)
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
                TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            except RefreshError:
                TOKEN_PATH.unlink(missing_ok=True)
                creds = None

        if not creds or not creds.valid:
            if CLIENT_ID and CLIENT_SECRET:
                client_config = {
                    "installed": {
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["http://localhost"]
                    }
                }
            else:
                with open(Path(__file__).with_name("client_secret.json"), "r", encoding="utf-8") as f:
                    client_config = json.load(f)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds

def canon_text(s: str) -> str:
    s = (s or "").strip().lower()
    return re.sub(r"[\s\[\]\(\)\/\-—–\.\·,]+", "", s)

def sha1_key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()

def to_time(s: str) -> Optional[dt.time]:
    s = (str(s) or "").strip()
    if not s or s == "-" or s.lower() == "nan": return None
    m = re.match(r"^(\d{1,2})(?::)?(\d{2})$", s)
    if not m: return None
    hh, mm = int(m.group(1)), int(m.group(2))
    return dt.time(hh, mm) if 0 <= hh < 24 and 0 <= mm < 60 else None

def detect_timekey_from_cells(sub: str, start: str, end: str) -> str:
    """엑셀 '신청구분/시작/종료'로 AM/PM/FULL 판정 – FULL 통일"""
    t = (sub or "").replace(" ", "")
    st, et = (start or "").strip(), (end or "").strip()
    stt, ett = to_time(st), to_time(et)

    if "오전" in t: return "AM"
    if "오후" in t: return "PM"
    if "종일" in t or "1일" in t: return "FULL"

    if stt and ett:
        if stt == dt.time(9,0)  and ett in (dt.time(13,0), dt.time(14,0)): return "AM"
        if stt in (dt.time(13,0), dt.time(14,0)) and ett == dt.time(18,0): return "PM"
        if stt == dt.time(9,0)  and ett == dt.time(18,0): return "FULL"
    return "FULL"

def label_of(timekey: str) -> str:
    return {"AM": "오전 반차", "PM": "오후 반차", "FULL": "휴가"}.get(timekey, "휴가")

def parse_year_month_from_filename(p: Path) -> Tuple[int, int]:
    m = re.search(r"(\d{4})\.(\d{2})\.", p.name)
    if not m: raise ValueError(f"연/월 파싱 실패: {p.name}")
    return int(m.group(1)), int(m.group(2))

def normalize_date_from_cell(year: int, month: int, day_str: str) -> Optional[dt.date]:
    m = re.search(r"(\d{1,2})/(\d{1,2})", str(day_str))
    if not m: return None
    dd = int(m.group(2))
    return dt.date(year, month, dd)

# ------------- 엑셀 읽기(헤더 스니핑) -------------
def _read_wehago_df_with_header_sniff(xlsx_path: Path) -> Optional[pd.DataFrame]:
    try:
        xls = pd.ExcelFile(xlsx_path, engine="openpyxl")
    except Exception as e:
        logging.warning("Skip %s (%s)", xlsx_path.name, e)
        return None

    def norm(v: str) -> str:
        return re.sub(r"\s+", "", str(v or "").strip().lower())

    date_tokens = ("일자", "날짜", "근태일자", "휴가일자", "기준일자")
    name_tokens = ("이름", "성명", "신청자", "신청자명")
    item_tokens = ("근태항목", "근태구분", "근태 구분", "구분", "근태코드")
    sub_tokens  = ("신청구분", "세부구분", "상세구분", "유형")
    stat_tokens = ("상태", "승인상태", "결재상태", "진행상태", "처리상태")

    for sheet in xls.sheet_names:
        try:
            raw = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=str)
        except Exception:
            raw = None
        if raw is None or raw.empty:
            continue

        max_probe = min(300, len(raw))
        for i in range(max_probe):
            row = [norm(v) for v in raw.iloc[i].tolist()]
            has_date = any(t in row for t in map(norm, date_tokens))
            has_name = any(t in row for t in map(norm, name_tokens))
            score = 0
            score += any(t in row for t in map(norm, item_tokens))
            score += any(t in row for t in map(norm, sub_tokens))
            score += any(t in row for t in map(norm, stat_tokens))
            if has_date and has_name and score >= 1:
                cols = raw.iloc[i].astype(str).tolist()
                if i + 1 < len(raw):
                    nxt = raw.iloc[i + 1].astype(str).tolist()
                    merged = []
                    for a, b in zip(cols, nxt):
                        a_c = (a or "").strip()
                        b_c = (b or "").strip()
                        if a_c and not a_c.lower().startswith("unnamed"):
                            merged.append(a_c)
                        elif b_c and not b_c.lower().startswith("unnamed"):
                            merged.append(b_c)
                        else:
                            merged.append(a_c or b_c or "")
                    cols = merged

                df = raw.iloc[i + 1:].copy()
                df.columns = cols
                df = df.dropna(how="all")

                for c in df.columns:
                    if df[c].dtype == object:
                        df[c] = df[c].map(lambda x: (x if not isinstance(x, str) else (x.strip() or None)))

                logging.info("Using sheet '%s' header row %s (sniff)", sheet, i)
                return df
    logging.warning("Header row not found by sniff (all sheets): %s", xlsx_path.name)
    return None

def find_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    flat = {c: canon_text(c) for c in cols}
    for cand in candidates:
        token = canon_text(cand)
        for k, v in flat.items():
            if token == v:
                return k
    for cand in candidates:
        token = canon_text(cand)
        for k, v in flat.items():
            if token in v:
                return k
    return None

# ------------- 액션(APPLY/CANCEL) 추출 -------------
def extract_actions_from_file(xlsx_path: Path) -> List[Dict]:
    df = _read_wehago_df_with_header_sniff(xlsx_path)
    if df is None or df.empty:
        logging.warning("File read failed: %s", xlsx_path.name)
        return []

    y, m = parse_year_month_from_filename(xlsx_path)
    c_date = find_col(df.columns.tolist(), ["일자","날짜","근태일자","휴가일자","기준일자"])
    c_name = find_col(df.columns.tolist(), ["이름","성명","신청자","신청자명"])
    c_item = find_col(df.columns.tolist(), ["근태항목","근태 구분","근태구분","구분","근태코드"])
    c_sub  = find_col(df.columns.tolist(), ["신청구분","세부구분","상세구분","유형"])
    c_s    = find_col(df.columns.tolist(), ["시작시간","시작","근태시작","시작시각"])
    c_e    = find_col(df.columns.tolist(), ["종료시간","종료","근태종료","종료시각"])
    if not all([c_date, c_name, c_item, c_sub]):
        logging.warning("필수 컬럼 누락: %s | cols=%s", xlsx_path.name, df.columns.tolist())
        return []

    rows: List[Dict] = []
    for _, r in df.iterrows():
        name = (r[c_name] or "").strip()
        date_ = normalize_date_from_cell(y, m, str(r[c_date]))
        if not name or not date_:
            continue

        item, sub = str(r[c_item] or ""), str(r[c_sub] or "")
        start_s, end_s = str(r[c_s]) if c_s else "", str(r[c_e]) if c_e else ""
        timekey = detect_timekey_from_cells(sub, start_s, end_s)  # AM/PM/FULL

        s_item, s_sub = canon_text(item), canon_text(sub)
        if "취소" in s_item or "취소" in s_sub:
            action = "CANCEL"
        elif ("휴가" in s_item) or any(k in s_sub for k in ("휴가","연차","반차","유급")):
            action = "APPLY"
        else:
            continue

        rows.append({
            "date": date_,
            "name": name,
            "timekey": timekey,     # AM/PM/FULL
            "action": action,
            "raw_item": item,
            "raw_sub": sub,
        })
    return rows

def extract_actions(folder: Path) -> List[Dict]:
    rows: List[Dict] = []
    for f in sorted(folder.glob("*.xlsx")):
        rows.extend(extract_actions_from_file(f))
    return rows

# ------------- NET → 개인 '활성' -------------
def reduce_to_active(rows: List[Dict]) -> List[Dict]:
    from collections import defaultdict
    counter = defaultdict(lambda: {"A":0, "C":0, "sample":None})
    for r in rows:
        key = (r["date"], r["name"], r["timekey"])
        if r["action"] == "APPLY":    counter[key]["A"] += 1
        elif r["action"] == "CANCEL": counter[key]["C"] += 1
        if counter[key]["sample"] is None:
            counter[key]["sample"] = r

    active: List[Dict] = []
    for (d, name, timekey), v in counter.items():
        if v["A"] - v["C"] > 0:
            s = v["sample"]
            active.append({
                "date": d,
                "name": name,
                "timekey": timekey,
                "item": s["raw_item"],
                "sub": s["raw_sub"],
            })
    return active

# ------------- 개인 → 그룹 -------------
def group_actives(actives: List[Dict]) -> List[Dict]:
    from collections import defaultdict
    box = defaultdict(lambda: {"names": set(), "sample": None})
    for x in actives:
        key = (x["date"], x["timekey"])
        box[key]["names"].add(x["name"])
        if box[key]["sample"] is None:
            box[key]["sample"] = x

    groups: List[Dict] = []
    for (d, timekey), v in box.items():
        s = v["sample"]
        groups.append({
            "date": d,
            "timekey": timekey,
            "names": sorted(v["names"]),
            "item": s.get("item", ""),
            "sub": s.get("sub", ""),
        })
    return groups

# ------------- 닉네임 매핑 -------------
def _norm_name(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())

def load_nickname_map(creds) -> Dict[str, str]:
    if not SHEETS_SPREADSHEET_ID:
        logging.warning("닉네임 시트 ID가 설정되지 않았습니다. 본명으로 진행합니다.")
        return {}
    try:
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        res = svc.spreadsheets().values().get(
            spreadsheetId=SHEETS_SPREADSHEET_ID, range=SHEETS_RANGE
        ).execute()
        values = res.get("values", [])
        if not values:
            logging.warning("시트에서 값을 읽지 못했습니다.")
            return {}

        header = [str(x).strip() for x in values[0]]

        def find_idx(names):
            for n in names:
                if n in header:
                    return header.index(n)
            for i, h in enumerate(header):
                if any(n in h for n in names):
                    return i
            return None

        idx_name = find_idx(["이름", "성명", "Name"])
        idx_nick = find_idx(["닉네임", "별명", "Nickname"])
        if idx_name is None or idx_nick is None:
            logging.warning("시트에서 '이름' 또는 '닉네임' 컬럼을 찾지 못했습니다. header=%s", header)
            return {}

        mapping: Dict[str, str] = {}
        raw_names: set[str] = set()
        for row in values[1:]:
            if idx_name >= len(row) or idx_nick >= len(row):
                continue
            name = (row[idx_name] or "").strip()
            nick = (row[idx_nick] or "").strip()
            if not name or not nick:
                continue
            mapping[name] = nick
            mapping[_norm_name(name)] = nick
            raw_names.add(name)
        logging.info("닉네임 매핑 로드 완료: %d명", len(raw_names))
        return mapping
    except Exception as e:
        logging.warning("닉네임 시트 로드 실패: %s", e)
        return {}

def display_name(name: str, nick_map: Optional[Dict[str, str]]) -> str:
    if not nick_map:
        return name
    if name in nick_map and nick_map[name]:
        return nick_map[name]
    nn = nick_map.get(_norm_name(name))
    return nn or name

# ------------- 캘린더 I/O -------------
def _std_time_range(timekey: str) -> Tuple[Optional[dt.time], Optional[dt.time]]:
    if timekey == "AM":   return dt.time(9, 0), dt.time(14, 0)
    if timekey == "PM":   return dt.time(14, 0), dt.time(18, 0)
    if timekey == "FULL": return dt.time(9, 0), dt.time(18, 0)  # 기본 시간형 종일
    return None, None

def _within(t: dt.time, lo: dt.time, hi: dt.time) -> bool:
    return (t >= lo) and (t <= hi)

def _times_of(ev: Dict) -> Tuple[Optional[dt.time], Optional[dt.time]]:
    try:
        if "dateTime" in ev.get("start", {}):
            st = dt.datetime.fromisoformat(ev["start"]["dateTime"].replace("Z","+00:00")).astimezone(ZoneInfo(TZNAME)).time()
            et = dt.datetime.fromisoformat(ev["end"]["dateTime"].replace("Z","+00:00")).astimezone(ZoneInfo(TZNAME)).time()
            return st, et
    except Exception:
        pass
    return None, None


def _event_time_equals(ev: Dict, desired_start_iso: str, desired_end_iso: str, tol_minutes: int = 1) -> bool:
    """이벤트의 시간(start/end)이 원하는 시간과 동일한지 비교.
    - ALL-DAY 이벤트는 False 반환(시간형으로 변환 필요)
    - tz: Asia/Seoul 기준 비교, tol_minutes 내 차이는 동일로 간주"""
    try:
        if _is_allday(ev):
            return False
        # 현재 이벤트 시간
        st_ev, et_ev = _times_of(ev)
        if not (st_ev and et_ev):
            return False
        # 원하는 시간
        dst = dt.datetime.fromisoformat(desired_start_iso).astimezone(ZoneInfo(TZNAME))
        det = dt.datetime.fromisoformat(desired_end_iso).astimezone(ZoneInfo(TZNAME))
        # 시간 차이 허용(tolerance)
        def _mins(t: dt.time) -> int:
            return t.hour*60 + t.minute
        ok = abs(_mins(st_ev) - (dst.hour*60 + dst.minute)) <= tol_minutes and              abs(_mins(et_ev) - (det.hour*60 + det.minute)) <= tol_minutes
        return ok
    except Exception:
        return False

def _is_allday(ev: Dict) -> bool:
    return "date" in ev.get("start", {}) and "date" in ev.get("end", {})

def _summary(ev: Dict) -> str:
    return (ev.get("summary") or "").strip()

def _looks_like_absence(ev: Dict) -> bool:
    s = normalize_title(_summary(ev))
    return bool(re.search(r"(휴가|반차|연차)", s))


def _event_matches_timekey(ev: Dict, timekey: str) -> bool:
    """
    제목 우선 + 시간/올데이 보정.
    - ALL-DAY라도 제목에 '오전/오후'가 명시되면 해당 반차로 간주 (FULL로 취급하지 않음)
    - 시간형 이벤트는 표준 범위 내(AM: 09~14/PM: 14~18/FULL: 09~18 유사)면 매칭
    """
    s = _summary(ev)
    tk = timekey_from_title(s)  # 안정화된 타이틀 판별

    # FULL
    if timekey == "FULL":
        if tk == "FULL":
            return True
        if _is_allday(ev):
            tnorm = normalize_title(s)
            # 제목에 오전/오후 명시 없을 때만 FULL로 인식
            if ("오전" not in tnorm) and ("오후" not in tnorm):
                return True
            return False
        st, et = _times_of(ev)
        return bool(st and et and _within(st, dt.time(8, 0), dt.time(10, 0)) and _within(et, dt.time(17, 0), dt.time(19, 0)))

    # AM
    if timekey == "AM":
        if tk == "AM":
            return True
        if _is_allday(ev):
            # 올데이 + 제목에 오전 표시가 있으면 AM으로 간주
            tnorm = normalize_title(s)
            if "오전" in tnorm:
                return True
        st, et = _times_of(ev)
        return bool(st and et and _within(st, dt.time(7, 0), dt.time(10, 30)) and _within(et, dt.time(12, 0), dt.time(15, 0)))

    # PM
    if timekey == "PM":
        if tk == "PM":
            return True
        if _is_allday(ev):
            # 올데이 + 제목에 오후 표시가 있으면 PM으로 간주
            tnorm = normalize_title(s)
            if "오후" in tnorm:
                return True
        st, et = _times_of(ev)
        return bool(st and et and _within(st, dt.time(12, 0), dt.time(15, 0)) and _within(et, dt.time(17, 0), dt.time(20, 0)))

    return False


def _safe_delete(svc, calendar_id: str, event_id: str):
    try:
        svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as e:
        status = getattr(e.resp, "status", None)
        if status in (404, 410):
            logging.info("Skip already deleted: %s", event_id)
        else:
            raise


def _needs_patch(existing: Dict, payload: Dict) -> bool:
    """제목/설명/확장속성/시간이 동일하면 PATCH 생략
    - 시간 동일성은 분 단위 허용오차로 비교
    - ALL-DAY → 시간형 변환이 필요하면 True"""
    if (_summary(existing) or "") != payload["summary"]:
        return True
    if (existing.get("description") or "") != payload["description"]:
        return True
    ep = existing.get("extendedProperties", {}).get("private", {}) or {}
    pp = payload.get("extendedProperties", {}).get("private", {}) or {}
    for k in ("wehago_group_key", "wehago_group_members", "wehago_timekey"):
        if ep.get(k) != pp.get(k):
            return True
    # 시간 비교(ALL-DAY 포함)
    if not _event_time_equals(existing, payload["start"]["dateTime"], payload["end"]["dateTime"]):
        return True
    return False


def build_group_event_payload(g: Dict, nick_map: Optional[Dict[str, str]] = None) -> Tuple[Dict, str]:
    date_, timekey, names = g["date"], g["timekey"], g["names"]
    disp_names = [display_name(n, nick_map) for n in names]
    summary = f"{label_of(timekey)}({', '.join(disp_names)})"

    st, et = _std_time_range(timekey)
    start_dt = dt.datetime.combine(date_, st, tzinfo=ZoneInfo(TZNAME))
    end_dt   = dt.datetime.combine(date_, et, tzinfo=ZoneInfo(TZNAME))
    body_time = {
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TZNAME},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TZNAME}
    }
    group_key = sha1_key(date_.isoformat(), "FULL" if timekey=="FULL" else timekey)

    desc = f"원본: WEHAGO | 유형:{label_of(timekey)} | 구성원:{', '.join(names)}"
    payload = {
        "summary": summary,
        "description": desc,
        **body_time,
        "extendedProperties": {
            "private": {
                "wehago_group_key": group_key,
                "wehago_group_members": ",".join(names),
                "wehago_timekey": timekey
            }
        }
    }
    # 캘린더 기본 알림 방지: 이벤트 단위로 알림 OFF
    payload["reminders"] = {"useDefault": False, "overrides": []}
    return payload, group_key

def list_events_by_day(svc, calendar_id: str, date_: dt.date) -> List[Dict]:
    day_start = dt.datetime.combine(date_, dt.time.min, tzinfo=ZoneInfo(TZNAME))
    day_end   = day_start + dt.timedelta(days=1)
    resp = svc.events().list(calendarId=calendar_id, timeMin=day_start.isoformat(),
                             timeMax=day_end.isoformat(), singleEvents=True,
                             orderBy="startTime", maxResults=2500).execute()
    return resp.get("items", [])

# ------------- 업서트 -------------
def upsert_groups(
    svc,
    calendar_id: str,
    groups: List[Dict],
    dry_run: bool=False,
    nick_map: Optional[Dict[str, str]] = None,
    extra_dates: Optional[Iterable[dt.date]] = None,
) -> Tuple[int,int,int]:
    created = updated = cleaned = 0
    deleted_ids: set[str] = set()

    by_date: Dict[dt.date, List[Dict]] = {}
    for g in groups:
        by_date.setdefault(g["date"], []).append(g)

    if extra_dates:
        for d in extra_dates:
            by_date.setdefault(d, [])

    ALL_TIMEKEYS = ("FULL", "AM", "PM")

    for d, lst in sorted(by_date.items(), key=lambda kv: kv[0]):
        existing = list_events_by_day(svc, calendar_id, d)

        todays_keys = set()
        todays_timekeys = {g["timekey"] for g in lst}

        # 1) 그룹별 업서트
        for g in lst:
            payload, gkey = build_group_event_payload(g, nick_map=nick_map)
            todays_keys.add(gkey)

            # 1-a. wehago_group_key -> 정확 매칭
            matches = [ev for ev in existing
                       if ev.get("extendedProperties", {}).get("private", {}).get("wehago_group_key") == gkey]

            # 1-b. fallback: 휴가성 + 타임키 일치(제목/올데이/시간형 포함 규칙)
            if not matches:
                label_prefix = f"{label_of(g['timekey'])}("
                matches = [ev for ev in existing
                           if (_summary(ev).startswith(label_prefix) or _looks_like_absence(ev))
                           and _event_matches_timekey(ev, g["timekey"])]

            keep_id: Optional[str] = None

            if matches:
                target = matches[0]
                if dry_run:
                    if _needs_patch(target, payload):
                        updated += 1
                        logging.info("[DRY] Patch: %s -> %s", target.get("summary"), payload["summary"])
                    # 중복 후보 정리(미리 계산)
                    for dup in matches[1:]:
                        cleaned += 1
                        logging.info("[DRY] Delete duplicate: %s", dup.get("summary"))
                    keep_id = target.get("id")
                else:
                    if _needs_patch(target, payload):
                        body = {
                            "summary": payload["summary"],
                            "description": payload["description"],
                            "extendedProperties": payload["extendedProperties"],
                            # 알림 OFF 유지
                            "reminders": {"useDefault": False, "overrides": []},
                        }
                        # 시간 차이 또는 올데이->시간형 전환 필요 시
                        time_changed = not _event_time_equals(target, payload["start"]["dateTime"], payload["end"]["dateTime"])
                        if time_changed:
                            body["start"] = {"dateTime": payload["start"]["dateTime"], "timeZone": TZNAME}
                            body["end"]   = {"dateTime": payload["end"]["dateTime"], "timeZone": TZNAME}

                        # update vs patch
                        if time_changed:
                            svc.events().update(calendarId=calendar_id, eventId=target["id"], body=body).execute()
                        else:
                            svc.events().patch(calendarId=calendar_id, eventId=target["id"], body=body).execute()
                        updated += 1

                        # ✅ 수정 알림 (무엇이 바뀌었는지 간단 표기)
                        try:
                            before = _summary(target) or ""
                            after  = payload["summary"]
                            chg = []
                            if before != after: chg.append("제목")
                            if time_changed:     chg.append("시간")
                            prefix = "수정" if not chg else f"수정({'+'.join(chg)})"
                            slack_post(_slack_text(prefix, after, payload["start"]["dateTime"], payload["end"]["dateTime"], extra=f"from='{before}'"))
                        except Exception:
                            pass

                    # 중복 정리(동일 그룹 매칭 안에서 잡힌 나머지)
                    for dup in matches[1:]:
                        try:
                            start_iso = dup.get("start", {}).get("dateTime") or ((dup.get("start", {}) or {}).get("date", "") + "T00:00:00+09:00")
                            end_iso   = dup.get("end", {}).get("dateTime")   or ((dup.get("end", {}) or {}).get("date", "") + "T00:00:00+09:00")
                            slack_post(_slack_text("삭제(중복)", dup.get("summary",""), start_iso, end_iso))
                        except Exception:
                            pass
                        if dup.get("id") and dup["id"] not in deleted_ids:
                            _safe_delete(svc, calendar_id, dup["id"])
                            deleted_ids.add(dup["id"])
                        cleaned += 1

                    keep_id = target.get("id")

                # ✅ 추가 안전망: 같은 타임키 중복(수기 잔여 포함) 일괄 정리
                cleaned += _cleanup_timekey_duplicates(svc, calendar_id, d, g["timekey"], keep_id, dry_run, deleted_ids)

            else:
                if dry_run:
                    created += 1
                    logging.info("[DRY] Insert: %s", payload["summary"])
                else:
                    new_ev = svc.events().insert(calendarId=calendar_id, body=payload).execute()
                    created += 1
                    keep_id = new_ev.get("id")
                    # 생성 알림
                    try:
                        slack_post(_slack_text(
                            "생성",
                            payload["summary"],
                            payload["start"]["dateTime"],
                            payload["end"]["dateTime"],
                            extra=f"key={payload['extendedProperties']['private']['wehago_group_key']}"
                        ))
                    except Exception:
                        pass

                # ✅ 생성 후에도 같은 타임키의 잔여 수기 이벤트가 있으면 일괄 정리
                cleaned += _cleanup_timekey_duplicates(svc, calendar_id, d, g["timekey"], keep_id, dry_run, deleted_ids)

        # 2) 잔존 삭제(오늘 그룹에 없는 타임키는 싹 정리)
        for tk in ALL_TIMEKEYS:
            if tk in todays_timekeys:
                continue
            leftovers = [ev for ev in existing if (_looks_like_absence(ev) and _event_matches_timekey(ev, tk))]
            for ev in leftovers:
                if dry_run:
                    cleaned += 1
                    logging.info("[DRY] Delete stale (no longer present %s): %s", tk, ev.get("summary"))
                else:
                    try:
                        start_iso = ev.get("start", {}).get("dateTime") or ((ev.get("start", {}) or {}).get("date", "") + "T00:00:00+09:00")
                        end_iso   = ev.get("end", {}).get("dateTime")   or ((ev.get("end", {}) or {}).get("date", "") + "T00:00:00+09:00")
                        slack_post(_slack_text("삭제(잔존)", ev.get("summary",""), start_iso, end_iso, extra=f"timekey={tk}"))
                    except Exception:
                        pass
                    if ev.get("id") and ev["id"] not in deleted_ids:
                        _safe_delete(svc, calendar_id, ev["id"])
                        deleted_ids.add(ev["id"])
                    cleaned += 1

        # 3) wehago_group_key 기반 안전망(키가 있는데 오늘 키와 불일치)
        leftovers_keys = [ev for ev in existing
                          if ev.get("extendedProperties", {}).get("private", {}).get("wehago_group_key")
                          and ev["extendedProperties"]["private"]["wehago_group_key"] not in todays_keys]
        for ev in leftovers_keys:
            if dry_run:
                cleaned += 1
                logging.info("[DRY] Delete stale by key: %s", ev.get("summary"))
            else:
                try:
                    start_iso = ev.get("start", {}).get("dateTime") or ((ev.get("start", {}) or {}).get("date", "") + "T00:00:00+09:00")
                    end_iso   = ev.get("end", {}).get("dateTime")   or ((ev.get("end", {}) or {}).get("date", "") + "T00:00:00+09:00")
                    key = ev.get("extendedProperties", {}).get("private", {}).get("wehago_group_key", "")
                    extra = f"key={key}" if key else None
                    slack_post(_slack_text("삭제(키 불일치)", ev.get("summary",""), start_iso, end_iso, extra=extra))
                except Exception:
                    pass
                if ev.get("id") and ev["id"] not in deleted_ids:
                    _safe_delete(svc, calendar_id, ev["id"])
                    deleted_ids.add(ev["id"])
                cleaned += 1

    return created, updated, cleaned


# ------------- 실행부 -------------
def main():
    ap = argparse.ArgumentParser(description="Sync WEHAGO vacation excels to Google Calendar (GROUPED + Nickname) – FULL unified")
    ap.add_argument("--download-dir", default=str(DOWNLOAD_DIR), help="WEHAGO 엑셀 폴더")
    ap.add_argument("--calendar", default=CALENDAR_ID, help="대상 캘린더 ID")
    ap.add_argument("--reset", action="store_true", help="OAuth 재동의(token.json 초기화)")
    ap.add_argument("--dry-run", action="store_true", help="쓰기 없이 계획만 출력")
    args = ap.parse_args()

    folder = Path(args.download_dir)
    if not folder.exists():
        logging.error("Download folder not found: %s", folder)
        return

    actions = extract_actions(folder)
    if not actions:
        logging.warning("엑셀에서 처리할 행을 찾지 못했습니다: %s", folder)
        return

    action_dates = {r["date"] for r in actions}

    actives = reduce_to_active(actions)
    groups  = group_actives(actives)
    logging.info("그룹 개수: %d (개인 활성 %d행)", len(groups), len(actives))

    creds = get_credentials(reset=args.reset)
    nick_map = load_nickname_map(creds)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    created, updated, cleaned = upsert_groups(
        svc,
        args.calendar,
        groups,
        dry_run=args.dry_run,
        nick_map=nick_map,
        extra_dates=action_dates,
    )
    logging.info("완료. 생성=%d, 수정=%d, 정리삭제=%d", created, updated, cleaned)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 로그에 전체 스택 남기기
        logging.exception("Uncaught fatal error")
        # 슬랙에는 마지막 10~12줄 정도만 전송(메시지 길이 안전)
        tb = traceback.format_exc()
        tail = "\n".join(tb.strip().splitlines()[-12:])
        slack_post(
            "[WEHAGO→GCal Sync][FAIL] "
            f"{e.__class__.__name__}: {e}\n```{tail}```"
        )
        sys.exit(1)
