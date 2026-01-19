import os
import time
import json
import gzip
import logging
from datetime import datetime
from openpyxl import Workbook
from seleniumwire import webdriver  # 일반 selenium이 아닌 seleniumwire 사용
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==============================================================================
# 1. 설정
# ==============================================================================
TARGET_URL = "https://www.wehago.com/#/eapprovals/menu/servicemanagement"
TARGET_YEAR = "2025"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, "결재문서_데이터")
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# 로깅 설정
logger = logging.getLogger("PACKET_SNIFFER")
logger.setLevel(logging.INFO)
if logger.hasHandlers(): logger.handlers.clear()
formatter = logging.Formatter('%(asctime)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==============================================================================
# 2. 브라우저 설정
# ==============================================================================
options = webdriver.ChromeOptions()
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--start-maximized")
options.add_argument('--ignore-certificate-errors')  # HTTPS 감청 허용

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 20)


# ==============================================================================
# 3. 데이터 추출 함수
# ==============================================================================
def decode_response(request):
    """서버 응답(JSON)을 사람이 읽을 수 있게 해독"""
    try:
        data = request.response.body
        try:
            data = gzip.decompress(data)  # 압축 해제
        except:
            pass

        return json.loads(data.decode('utf-8'))
    except:
        return None


def main():
    wb = Workbook()
    ws = wb.active
    ws.append(["작성일자", "양식명", "문서번호", "제목", "기안자", "상태", "데이터출처"])

    try:
        # 1. 로그인
        driver.get("https://www.wehago.com/")
        logger.info(">>> 로그인을 완료하고 메인 화면에서 엔터키를 누르세요.")
        input()

        # 2. 페이지 이동 (이제부터 네트워크 감시 시작)
        logger.info("네트워크 패킷 감시 중... 페이지로 이동합니다.")
        driver.get(TARGET_URL)
        time.sleep(5)

        # 3. 데이터 로딩 유도 (탭 클릭)
        try:
            logger.info("목록 갱신을 위해 탭을 클릭합니다...")
            tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), '전체문서조회')]")))
            tab.click()

            # 연도 변경 시도 (옵션)
            try:
                driver.find_element(By.ID, "inputElement").click()
                time.sleep(1)
                driver.find_element(By.XPATH,
                                    f"//li[contains(., '{TARGET_YEAR}')] | //div[contains(text(), '{TARGET_YEAR}')]").click()
            except:
                pass

            logger.info("데이터가 서버에서 도착하기를 기다립니다 (10초)...")
            time.sleep(10)

        except Exception as e:
            logger.warning(f"화면 조작 중 오류 (상관없음): {e}")

        # 4. 낚아챈 패킷 분석 (핵심!)
        logger.info("수집된 통신 내용을 분석합니다...")
        found_count = 0

        for request in driver.requests:
            if request.response:
                # API 주소에 'list', 'grid', 'document' 등이 포함된 요청만 필터링
                if 'json' in request.response.headers.get('Content-Type', '') and \
                        any(x in request.url for x in ['list', 'grid', 'select', 'retrieve']):

                    json_data = decode_response(request)
                    if not json_data: continue

                    # 데이터가 들어있을 만한 키 탐색
                    # 위하고는 보통 result_data, response, dataList 등에 담겨있음
                    rows = []
                    if isinstance(json_data, dict):
                        for key in ['result', 'resultData', 'response', 'data']:
                            if key in json_data and isinstance(json_data[key], list):
                                rows = json_data[key]
                                break

                    if rows:
                        logger.info(f" -> 유효한 데이터 패킷 발견! ({len(rows)}건)")
                        # 엑셀 저장
                        for row in rows:
                            # 필드명은 추정 (실제론 다를 수 있으나, 보통 영어 이니셜임)
                            # date, form_nm, doc_no, doc_title, user_nm...
                            w_date = row.get('draft_date') or row.get('appro_date') or row.get('reg_dt', '')
                            w_form = row.get('form_nm', '')
                            w_no = row.get('doc_no', '')
                            w_title = row.get('doc_title') or row.get('subject', '')
                            w_user = row.get('drafter_nm') or row.get('user_nm', '')
                            w_sts = row.get('doc_sts_nm', '')

                            if w_title and w_no:
                                ws.append([w_date, w_form, w_no, w_title, w_user, w_sts, request.url])
                                found_count += 1

        logger.info(f"🎉 총 {found_count}개의 결재 정보를 추출했습니다!")

    except Exception as e:
        logger.error(f"오류: {e}")
        traceback.print_exc()

    finally:
        wb.save(os.path.join(BASE_DIR, "결재문서_패킷_추출.xlsx"))
        logger.info("엑셀 저장 완료.")
        # driver.quit()


if __name__ == "__main__":
    main()