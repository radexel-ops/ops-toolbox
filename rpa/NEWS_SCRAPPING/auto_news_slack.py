import schedule
import time
import subprocess
import sys
from datetime import datetime

def run_script():
    print("Running news_bot_suhyun for slack.py")
    subprocess.call([sys.executable, 'news_bot_suhyun for slack.py'])


def check_time():
    now = datetime.now()
    # 매일 오전 8시 0분 0초에서 3초 사이일 때만 스크립트를 실행, 금요일에 실행하면 뉴스도 보내짐 주의

    if datetime.today().weekday() == 5 or datetime.today().weekday() == 6:
        pass
    else :
        if now.hour == 8 and now.minute == 0 and 0 <= now.second <= 3:
            run_script()

while True:
    check_time()
    time.sleep(1)  # 1초마다 시간을 확인
