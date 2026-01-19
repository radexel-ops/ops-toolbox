# scrape_yahoo_comps_optimized.py
# -*- coding: utf-8 -*-

import re
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# ==== 설정 ====
BASE_URL = "https://finance.yahoo.com/quote/"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 제한 시간 설정 (초)
PAGE_LOAD_TIMEOUT = 10  # 페이지 로딩 최대 대기 시간
ELEMENT_WAIT_TIMEOUT = 5  # 요소 찾기 최대 대기 시간
TICKER_TOTAL_TIMEOUT = 20  # 한 종목당 최대 허용 시간 (안전장치)

# 요청하신 환율 CSS
CURRENCY_CSS_USER = '#main-content-wrapper > section > div.top.yf-19hyiou > span > span:nth-child(3)'


# --------- Logging Setup ---------
def setup_logging():
    log_path = os.path.join(LOG_DIR, f"scrape_{datetime.now().strftime('%Y%m%d_%H%M')}.log")
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
    chrome_options.page_load_strategy = 'eager'

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(3)

    # [핵심 수정 1] 페이지 로딩이 10초 넘어가면 TimeoutException 발생시킴
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    return driver


def try_accept_cookies(driver):
    try:
        # 쿠키 팝업도 짧게 기다림
        btn = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.NAME, "agree"))
        )
        btn.click()
    except:
        pass


# --------- Parsing Logic (Batch) ---------

def get_currency_from_main(driver, ticker):
    try:
        try:
            el = driver.find_element(By.CSS_SELECTOR, CURRENCY_CSS_USER)
            return el.text.strip()
        except NoSuchElementException:
            el = driver.find_element(By.CSS_SELECTOR, 'section div.top span span:nth-child(3)')
            return el.text.strip()
    except Exception as e:
        logging.warning(f"[{ticker}] Currency 수집 실패: {e}")
        return None


def scrape_keystats_page(driver, ticker, target_headers):
    results = {}
    # [핵심 수정 2] 요소 로딩 대기 시간을 10초 -> 5초로 단축
    time.sleep(1)

    for header, label in target_headers.items():
        try:
            xpath = f"//tr[td[1]//text()[contains(., '{label}')]]/td[2]"
            val_el = driver.find_element(By.XPATH, xpath)
            val = val_el.text.strip()
            results[header] = val
            logging.info(f"    -> {label}: {val}")
        except NoSuchElementException:
            logging.warning(f"    -> {label}: 값 찾을 수 없음")
            results[header] = None
        except Exception:
            results[header] = None
    return results


def scrape_financials_page(driver, ticker, target_headers):
    results = {}
    # [핵심 수정 2] 요소 로딩 대기 시간을 10초 -> 5초로 단축
    time.sleep(1)

    for header, label in target_headers.items():
        try:
            row_xpath = f"//div[contains(@class, 'row') or contains(@class, 'tbr') or @data-test='fin-row'][.//span[text()='{label}'] or .//div[contains(text(), '{label}')]]"
            rows = driver.find_elements(By.XPATH, row_xpath)

            if not rows:
                rows = driver.find_elements(By.XPATH, f"//div[./div/span[text()='{label}']]")

            target_val = None
            if rows:
                row = rows[0]
                full_text = row.text.split('\n')
                cleaned_values = [
                    t.strip() for t in full_text
                    if t.strip() != "" and t.strip() != label and t.strip() != "-"
                ]
                if cleaned_values:
                    target_val = cleaned_values[0]
                else:
                    cols = row.find_elements(By.XPATH, "./div")
                    if len(cols) > 1:
                        target_val = cols[1].text.strip()

            results[header] = target_val

            if target_val:
                logging.info(f"    -> {label}: {target_val}")
            else:
                logging.warning(f"    -> {label}: 값 찾을 수 없음")

        except Exception:
            results[header] = None

    return results


# --------- Main Logic ---------
def main(input_csv="COMPS.csv", output_csv="COMPS_updated.csv", headless=True):
    setup_logging()

    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        logging.error(f"파일을 찾을 수 없습니다: {input_csv}")
        return

    cols_to_update = [c for c in df.columns if "Currency" in c or "/key-statistics/" in c or "/financials/" in c]
    for col in cols_to_update:
        df[col] = df[col].astype('object')

    headers_currency = []
    headers_stats = {}
    headers_financials = {}

    for col in df.columns:
        if "Currency" in col:
            headers_currency.append(col)
        elif "/key-statistics/" in col:
            label = col.split('-')[0].strip()
            headers_stats[col] = label
        elif "/financials/" in col:
            label = col.split('-')[0].strip()
            headers_financials[col] = label

    logging.info(f"수집 대상: 통계 {len(headers_stats)}개, 재무 {len(headers_financials)}개 항목")

    driver = start_driver(headless)

    try:
        total_rows = len(df)
        for i, row in df.iterrows():
            ticker = str(row['야후 티커']).strip()
            if not ticker or ticker.lower() == 'nan':
                continue

            logging.info(f"[{i + 1}/{total_rows}] '{ticker}' 수집 시작...")

            # [핵심 수정 3] 티커별 시간 제한 체크용 시작 시간
            ticker_start_time = time.time()

            try:
                # 1. Main Page (Currency)
                if headers_currency:
                    url = f"{BASE_URL}{ticker}"
                    driver.get(url)  # 여기서 10초 이상 걸리면 TimeoutException 발생
                    try_accept_cookies(driver)
                    curr_val = get_currency_from_main(driver, ticker)
                    for h in headers_currency:
                        df.at[i, h] = curr_val
                    logging.info(f"    -> Currency: {curr_val}")

                # [체크포인트] 시간 초과 검사
                if time.time() - ticker_start_time > TICKER_TOTAL_TIMEOUT:
                    raise TimeoutError("티커 전체 처리 시간 초과")

                # 2. Key Statistics Page
                if headers_stats:
                    url = f"{BASE_URL}{ticker}/key-statistics"
                    driver.get(url)  # 로딩 제한 10초
                    stats_data = scrape_keystats_page(driver, ticker, headers_stats)
                    for h, val in stats_data.items():
                        df.at[i, h] = val

                # [체크포인트] 시간 초과 검사
                if time.time() - ticker_start_time > TICKER_TOTAL_TIMEOUT:
                    raise TimeoutError("티커 전체 처리 시간 초과")

                # 3. Financials Page
                if headers_financials:
                    url = f"{BASE_URL}{ticker}/financials"
                    driver.get(url)  # 로딩 제한 10초
                    fin_data = scrape_financials_page(driver, ticker, headers_financials)
                    for h, val in fin_data.items():
                        df.at[i, h] = val

            except (TimeoutException, TimeoutError) as e:
                # Selenium의 PageLoad Timeout 혹은 우리가 설정한 시간 초과 발생 시
                logging.warning(f"!! [SKIP] '{ticker}' 시간 초과로 건너뜁니다. ({str(e)})")
                continue  # 다음 티커(for loop)로 즉시 이동

            except WebDriverException as e:
                logging.error(f"!! [ERROR] 브라우저 오류 발생: {e}")
                # 브라우저가 죽었을 수도 있으므로 재시작 로직을 넣거나, 일단 넘어가기
                continue

            # 중간 저장
            if (i + 1) % 1 == 0:
                df.to_csv(output_csv, index=False, encoding="utf-8-sig")

    except KeyboardInterrupt:
        logging.warning("사용자에 의해 중단됨.")
    except Exception as e:
        logging.error(f"치명적 오류 발생: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        logging.info(f"완료. 결과 저장됨: {output_csv}")


if __name__ == "__main__":
    HEADLESS_MODE = False
    INPUT_FILE = "COMPS.csv"
    OUTPUT_FILE = "COMPS_updated.csv"

    main(INPUT_FILE, OUTPUT_FILE, headless=HEADLESS_MODE)