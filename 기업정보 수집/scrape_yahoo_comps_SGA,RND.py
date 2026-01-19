# scrape_yahoo_opex_final.py
# -*- coding: utf-8 -*-

import time
import sys
import os
import traceback
import logging
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# ==== 설정 ====
BASE_URL = "https://finance.yahoo.com/quote/"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 타임아웃 설정
PAGE_LOAD_TIMEOUT = 20
TICKER_TOTAL_TIMEOUT = 40  # 시간을 조금 더 넉넉히

# 수집할 항목 컬럼명
COL_SGA = "Selling General and Administrative"
COL_RND = "Research & Development"


# --------- Logging Setup ---------
def setup_logging():
    log_path = os.path.join(LOG_DIR, f"scrape_opex_{datetime.now().strftime('%Y%m%d_%H%M')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


# --------- Selenium Driver ---------
def start_driver(headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(3)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


def try_accept_cookies(driver):
    try:
        btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.NAME, "agree"))
        )
        btn.click()
    except:
        pass


# --------- Extraction Logic ---------

def get_value_from_row_element(row_element):
    """
    행 요소(div)를 받아서 TTM(보통 2번째 컬럼) 값을 추출
    구조: [Label, TTM, Year1, Year2...]
    """
    try:
        # 자식 div들(컬럼들)을 모두 찾음
        cols = row_element.find_elements(By.XPATH, "./div")

        if len(cols) > 1:
            # 인덱스 1번이 TTM 값인 경우가 일반적
            val = cols[1].text.strip()
            if val == "-" or val == "":
                return "0"
            return val
        else:
            # div 구조가 아닐 경우 텍스트 파싱 시도 (비추천하지만 예비책)
            full_text = row_element.text.split('\n')
            if len(full_text) > 1:
                # 보통 라벨 다음 숫자가 옴
                val = full_text[1].strip()
                if val == "-": return "0"
                return val

        return "0"
    except Exception:
        return "0"


def find_row_by_text_content(driver, text_keywords):
    """
    특정 텍스트 키워드들을 포함하는 행(div)을 찾음.
    span, div 등 태그에 상관없이 텍스트를 포함하는 상위 'row' div를 반환.
    """
    # 1. contains(text(), 'A') and contains(text(), 'B') ...
    conditions = " and ".join([f"contains(text(), '{kw}')" for kw in text_keywords])

    # 2. 해당 텍스트를 가진 요소의 조상 중 class가 'row'인 것을 찾음
    #    Yahoo Finance는 보통 class="row ... " 또는 data-test="fin-row" 등을 사용
    xpath = f"//div[contains(@class, 'row') or contains(@class, 'fin-row') or contains(@class, 'tbr')][.//*[{conditions}]]"

    try:
        rows = driver.find_elements(By.XPATH, xpath)
        if rows:
            return rows[0]  # 첫 번째 매칭되는 행 반환
    except:
        pass
    return None


def scrape_operating_expenses_breakdown(driver, ticker):
    data = {COL_SGA: "0", COL_RND: "0"}
    wait = WebDriverWait(driver, 5)

    try:
        # 1. 'Operating Expense' 행 찾기
        #    (Operating Expense 텍스트가 있는 행)
        opex_keywords = ["Operating", "Expense"]
        opex_row = find_row_by_text_content(driver, opex_keywords)

        if not opex_row:
            logging.warning("    -> 'Operating Expense' 행을 찾을 수 없음 (항목 부재 가능성)")
            return data

        # 2. 확장(Expand) 필요 여부 확인
        #    이미 SG&A가 보이는지 확인
        sga_row = find_row_by_text_content(driver, ["Selling", "General"])

        if not sga_row:
            logging.info("    -> 하위 항목 안보임. 화살표 클릭 시도...")
            try:
                # opex_row 안의 버튼 찾기
                expand_btn = opex_row.find_element(By.XPATH, ".//button")
                driver.execute_script("arguments[0].click();", expand_btn)

                # 클릭 후 로딩 대기 (중요: SG&A 텍스트가 나타날 때까지 대기)
                try:
                    wait.until(lambda d: find_row_by_text_content(d, ["Selling", "General"]))
                    logging.info("    -> 확장 성공 (항목 나타남)")
                except TimeoutException:
                    logging.warning("    -> 확장 클릭했으나 하위 항목이 나타나지 않음 (시간 초과)")
                    # 그래도 R&D는 있을 수 있으니 계속 진행
            except NoSuchElementException:
                logging.warning("    -> 화살표 버튼을 찾을 수 없음. 하위 항목이 없는 기업일 수 있음.")
            except Exception as e:
                logging.warning(f"    -> 클릭 중 에러: {e}")

        # 3. 데이터 수집 - SG&A
        #    (화면 갱신 후 다시 찾기)
        sga_row = find_row_by_text_content(driver, ["Selling", "General"])
        if sga_row:
            val = get_value_from_row_element(sga_row)
            data[COL_SGA] = val
            logging.info(f"    -> SG&A 수집값: {val}")
        else:
            logging.info("    -> SG&A 행 발견 못함 -> 0 처리")

        # 4. 데이터 수집 - R&D
        #    (Research & Development 또는 Research and Development)
        rnd_row = find_row_by_text_content(driver, ["Research", "Development"])
        if rnd_row:
            val = get_value_from_row_element(rnd_row)
            data[COL_RND] = val
            logging.info(f"    -> R&D 수집값: {val}")
        else:
            logging.info("    -> R&D 행 발견 못함 -> 0 처리")

    except Exception as e:
        logging.error(f"    -> 로직 수행 중 치명적 오류: {e}")
        # traceback.print_exc()

    return data


# --------- Main Logic ---------
def main(input_csv="COMPS_Opex_Updated.csv", output_csv="COMPS_Opex_Final.csv", headless=True):
    setup_logging()

    if not os.path.exists(input_csv):
        # 이전 파일이 없다면 원본(COMPS.csv)에서 시작
        if os.path.exists("COMPS.csv"):
            input_csv = "COMPS.csv"
        else:
            logging.error(f"입력 파일({input_csv} 또는 COMPS.csv)을 찾을 수 없습니다.")
            return

    logging.info(f"입력 파일 로드: {input_csv}")
    df = pd.read_csv(input_csv)

    # 컬럼 초기화 (없는 경우)
    if COL_SGA not in df.columns: df[COL_SGA] = None
    if COL_RND not in df.columns: df[COL_RND] = None

    # 티커 컬럼 확인
    if '야후 티커' not in df.columns:
        logging.error("'야후 티커' 컬럼이 없습니다.")
        return

    driver = start_driver(headless)

    try:
        total_rows = len(df)
        logging.info(f"총 {total_rows}개 종목 재수집 시작")

        for i, row in df.iterrows():
            ticker = str(row['야후 티커']).strip()
            if not ticker or ticker.lower() == 'nan':
                continue

            # (옵션) 이미 0이 아닌 값이 있으면 건너뛰려면 아래 주석 해제
            # current_sga = str(row[COL_SGA]).replace(',', '').replace('0', '').strip()
            # if current_sga: continue

            logging.info(f"[{i + 1}/{total_rows}] '{ticker}' 확인 중...")
            ticker_start_time = time.time()

            try:
                url = f"{BASE_URL}{ticker}/financials"
                driver.get(url)
                try_accept_cookies(driver)

                # 데이터 수집 함수 실행
                opex_data = scrape_operating_expenses_breakdown(driver, ticker)

                # 결과 저장
                df.at[i, COL_SGA] = opex_data[COL_SGA]
                df.at[i, COL_RND] = opex_data[COL_RND]

                if time.time() - ticker_start_time > TICKER_TOTAL_TIMEOUT:
                    raise TimeoutError("시간 초과")

            except (TimeoutException, TimeoutError):
                logging.warning(f"!! [SKIP] '{ticker}' 로딩 시간 초과")
            except Exception as e:
                logging.error(f"!! [ERROR] '{ticker}' 오류: {e}")

            # 중간 저장 (3개마다)
            if (i + 1) % 3 == 0:
                df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    except KeyboardInterrupt:
        logging.warning("사용자 중단")
    finally:
        driver.quit()
        df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        logging.info(f"최종 완료. 저장 파일: {output_csv}")


if __name__ == "__main__":
    # 테스트를 위해 헤드리스 끄고 싶으면 False로 변경
    main(headless=False)