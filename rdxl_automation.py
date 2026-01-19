# rdxl_automation.py
import subprocess, sys, os
from pathlib import Path
from datetime import datetime
import time
import json, urllib.request
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env')

# ── Slack 설정 (환경변수에서 로드) ──
SLACK_TOKEN = os.getenv("SLACK_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "C08V9CA0UPM")

def run_vacation_run_all():
    print("휴가 자동 업데이트 시작")
    script = BASE / 'rpa' / '직원 휴가일정 업데이트' / 'vacation_run_all.py'
    subprocess.run([sys.executable, str(script)], cwd=str(script.parent))

def run_news_bot():
    print("Running news_bot_suhyun for slack.py")
    script = BASE / 'rpa' / 'NEWS_SCRAPPING' / 'news_bot_suhyun for slack.py'
    subprocess.run([sys.executable, str(script)], cwd=str(script.parent))

def send_heartbeat():
    try:
        url = "https://slack.com/api/chat.postMessage"
        payload = {
            "channel": SLACK_CHANNEL,
            "text": f"✅ rdxl_automation alive: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        req.add_header("Authorization", f"Bearer {SLACK_TOKEN}")
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"[WARN] heartbeat send failed: {e}")

def check_time():
    now = datetime.now()

    # 작동확인: 매일 06:00, 18:00
    if datetime.today().weekday() not in (5, 6):
        if (now.hour in (0, 2, 4, 6, 18, 20, 22)) and now.minute == 0 and 0 <= now.second <= 1:
            send_heartbeat()
    else :
        if (now.hour in (0, 2, 4, 6,8,10,12,14,16, 18, 20, 22)) and now.minute == 0 and 0 <= now.second <= 1:
            send_heartbeat()

    # 뉴스봇: 평일 08:00
    if (now.hour == 8) and now.minute == 0 and 0 <= now.second <= 3:
        if datetime.today().weekday() not in (5, 6):  # 토,일 제외
            run_news_bot()

    # 휴가봇: 평일 07:00, 19:00
    if (now.hour == 7) and now.minute == 0 and 0 <= now.second <= 3:
        if datetime.today().weekday() not in (5, 6):  # 토,일 제외
            run_vacation_run_all()

while True:
    check_time()
    time.sleep(1)
