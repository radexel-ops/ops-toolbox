import os
import datetime
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sys
import subprocess
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / '.env.shared')
load_dotenv(_root / '.env.local', override=True)

def send_message_to_slack(channel_id, message, token):
    client = WebClient(token=token)
    try:
        # 슬랙에 메시지 전송
        response = client.chat_postMessage(channel=channel_id, text=message)
        assert response["message"]  # 이 구문이 예외를 발생시키지 않으면 API 호출이 성공한 것입니다
        print("Message sent successfully.")
    except SlackApiError as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    #뉴스 스크래핑 실행
    try :
        subprocess.call([sys.executable,  'radexel_news_scraping_legacy_exact_fixcap_time.py'])
    except :
        time.sleep(5)
        subprocess.call([sys.executable,  'radexel_news_scraping_legacy_exact_fixcap_time.py'])

    # if datetime.datetime.today().weekday() == 4:

    ##뉴스 보내기
    # 슬랙 설정 (환경변수에서 로드)
    slack_token = os.getenv('SLACK_TOKEN', '')
    # slack_channel_id = 'C08V9CA0UPM'  # 메시지를 보낼 채널 ID로 교체하세요
    slack_channel_id = os.getenv('SLACK_CHANNEL_NEWS', 'C07H9MB8JQ4')  # 뉴스 채널

    # 오늘 날짜에 맞춰 파일 이름 결정
    today = datetime.datetime.now().strftime("%Y%m%d")
    filename = f"slack/slack_{today}.txt"

    # 파일 존재 여부 확인 및 메시지로 보내기
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            file_content = file.read()
            # 메시지 길이가 슬랙의 메시지 길이 제한을 초과할 수 있으므로, 필요한 경우 메시지를 적절히 나누거나 줄일 것
            send_message_to_slack(slack_channel_id, file_content, slack_token)
            print(datetime.datetime.today().weekday(), "슬랙 - 뉴스 전송 / 월요일")

    else:
        print("File does not exist.")




    ##논문 보내기
    # 슬랙 설정 (환경변수에서 로드)
    slack_token = os.getenv('SLACK_TOKEN', '')
    slack_channel_id = os.getenv('SLACK_CHANNEL_PUBMED', 'C07HJ4RQGAC')  # 논문 채널

    # 오늘 날짜에 맞춰 파일 이름 결정
    today = datetime.datetime.now().strftime("%Y%m%d")
    filename = f"pub_med/pub_med_{today}.txt"

    # 파일 존재 여부 확인 및 메시지로 보내기
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            file_content = file.read()
            # 메시지 길이가 슬랙의 메시지 길이 제한을 초과할 수 있으므로, 필요한 경우 메시지를 적절히 나누거나 줄일 것
            send_message_to_slack(slack_channel_id, file_content, slack_token)
            print(datetime.datetime.today().weekday(), "슬랙 - 논문 전송")

    else:
        print("File does not exist.")
