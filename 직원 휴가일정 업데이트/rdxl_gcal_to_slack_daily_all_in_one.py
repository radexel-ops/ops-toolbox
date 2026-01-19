
# -*- coding: utf-8 -*-
"""
RDXL | Google Calendar -> Slack Daily Digest (All-in-One)
- 사용자 OAuth(데스크톱) 사용: 최초 1회 브라우저 동의 필요
- OAuth Client ID/Secret, Slack 토큰, 캘린더/채널 ID 모두 스크립트에 내장
- OAuth access/refresh token은 같은 폴더의 token.json 에 저장/갱신

설치
  pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 requests

실행
  python rdxl_gcal_to_slack_daily_all_in_one.py
  (첫 실행 시 브라우저에서 캘린더 읽기 권한 동의 1회)

스케줄링
  Windows 작업 스케줄러에 매일 07:00 등록
"""
from __future__ import annotations

import os
import re
import sys
import json
import argparse
import logging
import datetime as dt
from pathlib import Path
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import requests
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleAuthRequest

# ----------------- 내장 설정 (환경변수에서 로드) -----------------
CALENDAR_ID   = os.getenv("GOOGLE_CALENDAR_ID", "c_a691b5b6d11b9c1717fdc1a4ef2bf106b9a5cd76c90605337bd5dca7546ce3ad@group.calendar.google.com")
SLACK_TOKEN   = os.getenv("SLACK_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ATTENDANCE", "C06PZGY59S6")   #리얼 - 근태 채널
# SLACK_CHANNEL = "D06NS3K1N5N"   #개인dm 수현
# SLACK_CHANNEL = "C08V9CA0UPM"   #automation 테스트 계정



TZNAME        = "Asia/Seoul"

# OAuth (Desktop) – 환경변수에서 로드
CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
TOKEN_PATH = Path(__file__).with_name("token.json")  # 저장 위치

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s | %(message)s")

# ----------------------------- 유틸 -----------------------------
def tz_now() -> dt.datetime:

    # print((dt.datetime.now() + dt.timedelta(days=1)))
    # return dt.datetime.now() + dt.timedelta(days=1)
    return dt.datetime.now(ZoneInfo(TZNAME))
    # return dt.datetime(2025, 10, 1, 9, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))

def to_kst_time(s: str) -> dt.datetime:
    dt_obj = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt_obj.astimezone(ZoneInfo(TZNAME))

def parse_event_type(summary: str) -> tuple[str, str]:
    """
    캘린더 실제 사용 패턴에 맞춘 분류 규칙:
    - 우선순위 1) [휴가]/[재택]/[외근]/[출장] 브라켓 태그가 있으면 그대로 사용
    - 우선순위 2) 키워드 탐지
        휴가계열: 휴가, 연차, 반차, 오전 반차, 오후 반차, 대휴/대체휴무
        재택계열: 재택, 재택근무, WFH, work from home, 원격근무
        외근/출장계열: 외근, 출장, 방문, 미팅, 컨설팅, 설명회, 세미나/워크숍, 교육, 발표, 점검/설치/시연, 현장, 검진/검사 등
    - 우선순위 3) 장소/기관 패턴(대학/병원/연구원/센터/공단/연구소/KBSI/KTL/원자력 등)이 들어가면 외근으로 간주
    - 그 외는 '기타'
    반환: (type, display_title)
    """
    import re
    s = (summary or "").strip()

    # 1) 브라켓 태그 우선
    m = re.match(r"^\s*\[(휴가|재택|외근|출장)\]\s*(.+)$", s)
    if m:
        return m.group(1), m.group(2).strip()

    s_no_space = re.sub(r"\s+", "", s).lower()

    # 2) 키워드 탐지
    vac_kw = [
        "휴가", "연차", "반차", "오전반차", "오후반차",
        "대휴", "대체휴무", "대체휴가"
    ]
    wfh_kw = [
        "재택", "재택근무", "wfh", "workfromhome", "원격근무"
    ]
    trip_kw = [
        "외근", "출장", "방문", "미팅", "컨설팅", "면담", "면접",
        "설명회", "세미나", "워크숍", "워크샵", "교육", "발표",
        "점검", "설치", "시연", "현장", "검진", "검사"
    ]

    if any(k in s_no_space for k in [k.lower() for k in vac_kw]):
        return "휴가", s
    if any(k in s_no_space for k in [k.lower() for k in wfh_kw]):
        return "재택", s
    if any(k in s_no_space for k in [k.lower() for k in trip_kw]):
        return "외근", s  # build_slack_blocks에서 '외근·출장'으로 병합됨

    # 3) 장소/기관 힌트가 있으면 외근으로 간주 (내부 회의와 구분 위해 장소어휘 위주)
    place_hint_patterns = [
        r"병원", r"대학병원", r"대학교", r"대학(?!원)", r"연구원", r"연구소",
        r"센터", r"공단", r"공사", r"기관", r"학회", r"박람회",
        r"KBSI", r"KTL", r"원자력", r"의료기기", r"산단", r"고객사"
    ]
    if any(re.search(p, s, flags=re.IGNORECASE) for p in place_hint_patterns):
        return "외근", s

    # 4) 기본값
    return "기타", s


# ----------------------------- OAuth -----------------------------
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
            creds.refresh(GoogleAuthRequest())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        else:
            client_config = {
                "installed": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds

# ----------------------------- Slack -----------------------------
def post_to_slack(channel: str, payload: Dict) -> None:
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json;charset=utf-8"}
    data = {"channel": channel, **payload}
    resp = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
    ok = False
    try: ok = resp.json().get("ok", False)
    except Exception: pass
    if not ok:
        logging.error("Slack API error: %s", resp.text)
        resp.raise_for_status()
    else:
        logging.info("Slack message posted to channel %s", channel)

# ----------------------------- 비즈니스 로직 -----------------------------
def fetch_todays_absences(svc, calendar_id: str) -> List[Dict]:
    today = tz_now().date()
    day_start = dt.datetime.combine(today, dt.time.min, tzinfo=ZoneInfo(TZNAME))
    day_end = day_start + dt.timedelta(days=1)

    logging.info("Loading events @ %s (%s ~ %s)", calendar_id, day_start, day_end)

    resp = svc.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=500,
    ).execute()

    items = resp.get("items", [])
    records: List[Dict] = []
    for ev in items:
        summary = ev.get("summary", "(제목 없음)")
        ev_type, body_title = parse_event_type(summary)

        start_raw = ev.get("start", {})
        end_raw = ev.get("end", {})
        all_day = "date" in start_raw

        if all_day:
            start_time, end_time = "종일", ""
        else:
            st = to_kst_time(start_raw["dateTime"])
            et = to_kst_time(end_raw["dateTime"])
            start_time, end_time = st.strftime("%H:%M"), et.strftime("%H:%M")

        # ---------- [추가] 이름/제목 정리 ----------
        # 끝 괄호 "(이름들)"을 우선적으로 사람 이름으로 인식
        m = re.search(r"\(([^()]*)\)\s*$", body_title)
        names = None
        title_clean = body_title
        if m:
            names_str = m.group(1).strip()
            # 쉼표 / · / 슬래시 구분자 지원
            parts = re.split(r"[,\u00b7/]+|\s*,\s*|\s*·\s*", names_str)
            parts = [p.strip() for p in parts if p.strip()]
            if parts:
                names = ", ".join(parts)
                # 괄호 제거한 제목으로 교체
                title_clean = body_title[:m.start()].strip(" -—–\u00a0\t")

        # 기존 대시 앞 토큰으로 이름 추정(보조 규칙)
        if not names:
            parts = re.split(r"[—\-–]\s*", body_title, maxsplit=1)
            if parts:
                cand = parts[0].strip()
                if re.fullmatch(r"[가-힣A-Za-z\s\.]+", cand) and len(cand) <= 20:
                    names = cand

        records.append({
            "summary": summary,
            "title": title_clean,      # 정리된 제목(괄호/불필요 공백 제거)
            "raw_title": body_title,   # 원본 본문 제목(필요시 디버그용)
            "type": ev_type,
            "names": names,            # "성준, 근우" 같은 문자열
            "all_day": all_day,
            "start": start_time,
            "end": end_time,
            "htmlLink": ev.get("htmlLink"),
        })

    logging.info("Fetched %d event(s)", len(records))
    return records


def build_slack_blocks(records: List[Dict]) -> Dict:
    today = tz_now().strftime("%m/%d (%a)")
    groups = {"휴가": [], "재택": [], "외근·출장": [], "기타": []}
    for r in records:
        key = r["type"]
        if key in ("외근", "출장"):
            key = "외근·출장"
        if key not in groups:
            key = "기타"
        groups[key].append(r)

    # 1. 구분선을 가장 먼저 추가하여 날짜 구분을 명확하게 함
    blocks = [{"type": "divider"}]

    # 2. 헤더 아이콘을 심플한 것으로 변경
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*🗓️ 오늘의 부재 일정: {today}*"}
    })

    category_map = [
        ("휴가", "휴가"),
        ("재택", "재택근무"),
        ("외근·출장", "외근·출장"),
        ("기타", "기타"),
    ]

    content_rows = []
    for key, title in category_map:
        items = groups.get(key, [])
        if not items:
            continue

        # 3. 각 카테고리의 내용을 한 줄로 압축하여 표시
        if key in ("휴가", "재택"):
            # 휴가/재택은 모든 인원을 한 줄에 묶어서 표시
            details = []
            for r in items:
                time_str = "종일" if r["all_day"] else f"{r['start']}–{r['end']}"
                display_name = r.get("names") or r.get("title") or r.get('summary', '')
                details.append(f"{display_name} ({time_str})")
            content_rows.append(f"*{title}* | • {' , • '.join(details)}")
        else:
            # 외근/기타는 각 일정을 별도 줄로 표시하여 명확성 유지
            details = []
            for r in items:
                time_str = "종일" if r["all_day"] else f"{r['start']}–{r['end']}"
                names = r.get("names")
                title_clean = r.get("title") or ""

                line = ""
                if names and title_clean:
                    line = f"{names} ({time_str}) - {title_clean}"
                else:
                    main_content = names or title_clean or r.get('summary', '')
                    line = f"{main_content} ({time_str})"
                details.append(line)
            content_rows.append(f"*{title}* | • {' | • '.join(details)}")

    if content_rows:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(content_rows)}
        })
    else:
        # 부재 인원이 없는 경우
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "✅ 오늘은 부재 인원이 없습니다."}
        })

    # ⬇⬇⬇ 추가: 하단 아주 작은 안내(context block)
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "_매일 07:00 RDXL_부재/외부일정 캘린더 기반 자동 발송_"
        }]
    })
    return {"blocks": blocks}

# ----------------------------- CLI -----------------------------
def main():
    ap = argparse.ArgumentParser(description="RDXL GCal -> Slack Daily Digest (All-in-One)")
    ap.add_argument("--calendar", default=CALENDAR_ID, help="Google Calendar ID")
    ap.add_argument("--channel", default=SLACK_CHANNEL, help="Slack Channel ID")
    ap.add_argument("--reset", action="store_true", help="저장된 OAuth token.json 삭제 후 재동의")
    ap.add_argument("--dry-run", action="store_true", help="슬랙 전송 없이 콘솔 미리보기")
    args = ap.parse_args()

    creds = get_credentials(reset=args.reset)
    svc = build("calendar", "v3", credentials=creds, cache_discovery=False)

    records = fetch_todays_absences(svc, args.calendar)
    payload = build_slack_blocks(records)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    post_to_slack(args.channel, payload)

if __name__ == "__main__":
    main()
