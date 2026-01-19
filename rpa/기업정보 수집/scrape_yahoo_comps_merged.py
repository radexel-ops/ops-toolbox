# scrape_yahoo_parallel_ultimate.py
# -*- coding: utf-8 -*-

import re
import time
import sys
import os
import traceback
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로세스 제어를 위한 psutil (없으면 pip install psutil)
try:
    import psutil
except ImportError:
    psutil = None

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException

# ==============================================================================
# [설정 영역: 절대 건드리지 마세요]
# ==============================================================================
BASE_URL = "https://finance.yahoo.com/quote/"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 병렬 처리 워커 수 (PC 성능에 맞춰 4개 유지)
MAX_WORKERS = 4

# 타임아웃 설정 (충분히 길게 설정하여 로딩 실패 방지)
PAGE_LOAD_TIMEOUT = 40
ELEMENT_WAIT_TIMEOUT = 15

# [중요] 사용자 제공 CSS Selector (우선순위 1위 적용)
CURRENCY_CSS_USER = '#main-content-wrapper > section > div.top.yf-19hyiou > span > span:nth-child(3)'

# 수집할 핵심 항목 컬럼명
COL_SGA = "Selling General and Administrative"
COL_RND = "Research & Development"

# ==============================================================================
# [유틸리티 함수: 로깅 및 프로세스 청소]
# ==============================================================================
def setup_logging():
    """상세 로그 설정을 초기화합니다."""
    log_path = os.path.join(LOG_DIR, f"scrape_ultimate_{datetime.now().strftime('%Y%m%d_%H%M')}.log")
    
    # 로거 인스턴스 확보
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 중복 핸들러 제거
    if logger.hasHandlers():
        logger.handlers.clear()

    # 포맷 설정
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    # 1. 콘솔 핸들러 (터미널 출력용)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 2. 파일 핸들러 (기록 보관용)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def kill_zombie_chrome():
    """
    작업 전후에 '자동화된' 좀비 크롬 프로세스만 골라서 사살합니다.
    사용자가 직접 띄운 인터넷 창(Chrome)은 절대 끄지 않습니다.
    """
    if psutil is None: return

    logging.info("🧹 [청소] 자동화된 좀비 크롬 프로세스만 정리 중 (사용자 브라우저 보호)...")
    count = 0
    
    # 실행 중인 모든 프로세스를 검사
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name'].lower()
            cmdline = proc.info['cmdline'] # 실행 명령어 인자 리스트
            
            # 명령행 인자가 없으면(권한 부족 등) 건너뜀
            if not cmdline:
                continue
            
            # 리스트를 문자열 하나로 합쳐서 검색하기 쉽게 만듦
            cmd_str = ' '.join(cmdline).lower()

            # [타겟 1] chromedriver.exe (이건 무조건 자동화 툴이므로 종료)
            is_chromedriver = 'chromedriver' in name
            
            # [타겟 2] chrome.exe 중 '자동화(Bot)' 흔적이 있는 녀석들
            # - --headless: 화면 없이 실행된 경우
            # - --test-type: 셀레니움이 브라우저 제어할 때 붙는 플래그
            # - automationcontrolled: 우리 스크립트가 추가한 옵션
            is_chrome_bot = False
            if 'chrome' in name:
                if ('--headless' in cmd_str) or \
                   ('--test-type' in cmd_str) or \
                   ('automationcontrolled' in cmd_str) or \
                   ('webdriver' in cmd_str):
                    is_chrome_bot = True

            # 타겟인 경우에만 종료 (Kill)
            if is_chromedriver or is_chrome_bot:
                proc.kill()
                count += 1
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    if count > 0:
        logging.info(f"    -> {count}개의 자동화 프로세스 정리 완료.")
# ==============================================================================
# [Selenium 드라이버 설정: 최적화 옵션 풀장착]
# ==============================================================================
def start_driver(worker_id, headless=True):
    """최적화된 크롬 드라이버를 생성합니다."""
    # logging.info(f"  🔧 [Worker-{worker_id}] 드라이버 초기화 중...")
    
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    
    # 시스템 안정성 옵션
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--log-level=3") # 불필요한 시스템 로그 숨김
    
    # 리소스 차단 (속도 향상)
    prefs = {
        "profile.managed_default_content_settings.images": 2, # 이미지 차단
        "profile.managed_default_content_settings.stylesheets": 2, # CSS 차단
        "profile.managed_default_content_settings.cookies": 1,
        "profile.managed_default_content_settings.javascript": 1, # JS 필수
        "profile.managed_default_content_settings.plugins": 1,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.media_stream": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.page_load_strategy = 'eager' # DOM 로드 시 즉시 반응

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(3) # 기본 대기 3초
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        return driver
    except Exception as e:
        logging.error(f"  ❌ [Worker-{worker_id}] 드라이버 생성 실패: {e}")
        raise e

def try_accept_cookies(driver):
    """쿠키 팝업 자동 수락"""
    try:
        btn = WebDriverWait(driver, 1.5).until(EC.element_to_be_clickable((By.NAME, "agree")))
        driver.execute_script("arguments[0].click();", btn)
    except:
        pass

# ==============================================================================
# [핵심 파싱 로직: 절대 누락 없는 3중 체크]
# ==============================================================================
def get_currency_ultimate(driver):
    """환율 정보를 3단계로 끝까지 찾아냅니다."""
    
    # 1. [최우선] 사용자 제공 CSS Selector
    try:
        el = driver.find_element(By.CSS_SELECTOR, CURRENCY_CSS_USER)
        txt = el.text.strip()
        # 'Currency in USD' 또는 'USD' 형태 추출
        match = re.search(r"(?:Currency in|In)\s+([A-Z]{3})", txt, re.IGNORECASE)
        if match: return match.group(1).upper()
        if len(txt) == 3 and txt.isupper(): return txt
    except: 
        pass

    # 2. [차선] 야후 파이낸스 표준 헤더 ID
    try:
        header_el = driver.find_element(By.CSS_SELECTOR, "#quote-header-info")
        match = re.search(r"Currency in\s+([A-Z]{3})", header_el.text, re.IGNORECASE)
        if match: return match.group(1).upper()
    except: 
        pass

    # 3. [최후 수단] 본문 전체 검색 (Regex)
    try:
        # 상단 8000자만 긁어서 검색 (속도 타협)
        body_text = driver.find_element(By.TAG_NAME, "body").text[:8000]
        match = re.search(r"Currency in\s+([A-Z]{3})", body_text, re.IGNORECASE)
        if match: return match.group(1).upper()
    except: 
        pass
    
    return None


def scrape_stats_table(driver, target_headers):
    """
    [수정됨] 텍스트가 비슷하다고 무조건 가져오지 않고,
    Enterprise Value가 Enterprise Value/EBITDA로 덮어써지는 문제를 방지합니다.
    """
    extracted = {}
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        rows = driver.find_elements(By.TAG_NAME, "tr")
        
        for r in rows:
            try:
                cols = r.find_elements(By.XPATH, ".//*[self::td or self::th]")
                if len(cols) >= 2:
                    label_raw = cols[0].text.strip()
                    val = cols[1].text.strip()
                    
                    # 라벨 뒤에 붙은 주석 숫자(1, 2, 3...) 제거
                    label_clean = re.sub(r'\s\d+$', '', label_raw).strip()
                    current_label_lower = label_clean.lower()

                    for h_key, h_search in target_headers.items():
                        target_clean = h_search.strip().lower()
                        
                        # [1단계] 완전 일치 (Exact Match) - 가장 우선!
                        # 예: "Enterprise Value" == "Enterprise Value"
                        if current_label_lower == target_clean:
                            extracted[h_key] = val
                            continue 

                        # [2단계] 부분 일치 (Partial Match) - 예외 처리 강화
                        if target_clean in current_label_lower:
                            # [핵심 수정] 타겟은 'Enterprise Value'인데, 
                            # 현재 라벨이 '/Revenue'나 '/EBITDA'를 포함하고 있다면 무시!
                            if "enterprise value" in target_clean:
                                if "revenue" in current_label_lower or "ebitda" in current_label_lower:
                                    continue
                            
                            # P/E 찾는데 PEG Ratio 가져오는 것 방지
                            if "p/e" in target_clean and "peg" in current_label_lower:
                                continue

                            # 안전하다고 판단되면 저장 (단, 완전 일치로 찾은 값이 없을 때만)
                            if h_key not in extracted:
                                extracted[h_key] = val

            except: continue
    except: pass
    return extracted


def scrape_financials_rows(driver):
    """
    재무제표 파싱: Expand All 버튼 클릭 후 숨겨진 SG&A, R&D 데이터 확보
    """
    extracted = {}
    try:
        # 1. 하단 스크롤 (Lazy Loading 데이터 활성화)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
        time.sleep(1)
        
        # 2. Expand All 버튼 강제 클릭
        try:
            expand_btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(), 'Expand All')]]")
            driver.execute_script("arguments[0].scrollIntoView(true);", expand_btn)
            driver.execute_script("arguments[0].click();", expand_btn)
            time.sleep(1.5) # 데이터 펼쳐지는 시간 대기
        except: 
            pass # 이미 펼쳐져 있거나 버튼이 없는 경우 패스

        # 3. 데이터 행 파싱
        rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'row')] | //tr")
        for r in rows:
            txt = r.text
            if '\n' not in txt: continue
            
            parts = txt.split('\n')
            label = parts[0].strip()
            
            # 값 추출 (숫자 또는 '-' 찾기)
            val = "0"
            for p in parts[1:]:
                # 숫자가 포함되거나 '-' 인 경우
                if re.search(r'\d', p) or p.strip() == '-':
                    val = p.strip()
                    break
            
            if val == "-": val = "0"
            extracted[label] = val
    except: 
        pass
    return extracted

# ==============================================================================
# [병렬 처리 워커(Worker) 로직]
# ==============================================================================
def process_batch(worker_id, ticker_indices, full_df):
    """
    각 워커(브라우저)가 맡은 티커 리스트를 처리하는 함수입니다.
    상세한 로그를 출력하여 사용자가 진행 상황을 알 수 있게 합니다.
    """
    logging.info(f"👷 [Worker-{worker_id}] 작업 시작! (할당량: {len(ticker_indices)}개)")
    
    # 드라이버 시작
    try:
        driver = start_driver(worker_id, headless=True)
    except Exception:
        logging.critical(f"❌ [Worker-{worker_id}] 브라우저 실행 실패. 해당 배치 건너뜀.")
        return {}

    batch_results = {}
    
    # 필요한 컬럼 및 헤더 매핑 준비
    cols_currency = [c for c in full_df.columns if "Currency" in c]
    cols_stats = [c for c in full_df.columns if "/key-statistics/" in c]
    cols_fin = [c for c in full_df.columns if "/financials/" in c]
    
    headers_stats_map = {c: c.split('-')[0].strip() for c in cols_stats}
    headers_fin_map = {c: c.split('-')[0].strip() for c in cols_fin}

    try:
        count = 0
        total = len(ticker_indices)
        
        for idx in ticker_indices:
            count += 1
            row = full_df.loc[idx]
            ticker = str(row['야후 티커']).strip()
            
            if not ticker or ticker.lower() == 'nan': continue

            # [Skip Logic] 데이터가 이미 완벽하게 있으면 건너뜀
            has_sga = pd.notna(row.get(COL_SGA)) and str(row.get(COL_SGA)) not in ['0', 'nan', '']
            has_curr = cols_currency and pd.notna(row.get(cols_currency[0]))
            
            if has_sga and has_curr:
                logging.info(f"   ⏩ [Worker-{worker_id}] ({count}/{total}) '{ticker}' 완료된 데이터 -> Skip")
                continue

            logging.info(f"🚀 [Worker-{worker_id}] ({count}/{total}) '{ticker}' 수집 중...")
            data_collected = {}

            # --- [Step 1] Key Statistics & Currency ---
            try:
                driver.get(f"{BASE_URL}{ticker}/key-statistics")
                try_accept_cookies(driver)
                
                # 환율 수집 (3중 체크)
                curr = get_currency_ultimate(driver)
                if curr:
                    for c in cols_currency: data_collected[c] = curr
                    logging.info(f"      -> [Worker-{worker_id}] 환율 발견: {curr}")
                
                # 통계 데이터 수집
                stats_data = scrape_stats_table(driver, headers_stats_map)
                data_collected.update(stats_data)
                
            except Exception as e:
                logging.warning(f"      ⚠️ [Worker-{worker_id}] {ticker} Stats 오류: {e}")

            # --- [Step 2] Financials (SG&A, R&D) ---
            try:
                driver.get(f"{BASE_URL}{ticker}/financials")
                
                # Step 1에서 환율 놓쳤으면 재시도
                if not data_collected.get(cols_currency[0] if cols_currency else ""):
                    curr = get_currency_ultimate(driver)
                    if curr:
                         for c in cols_currency: data_collected[c] = curr
                
                # 재무 데이터 파싱 (Expand All 포함)
                fin_raw = scrape_financials_rows(driver)
                
                # 일반 재무 항목 매핑
                for h_key, h_search in headers_fin_map.items():
                    for extracted_label, extracted_val in fin_raw.items():
                        if h_search.lower() in extracted_label.lower():
                             data_collected[h_key] = extracted_val
                             break
                
                # 특수 항목 매핑 (SG&A, R&D)
                for extracted_label, extracted_val in fin_raw.items():
                    label_lower = extracted_label.lower()
                    if "selling" in label_lower and "general" in label_lower:
                        data_collected[COL_SGA] = extracted_val
                    elif "research" in label_lower and "development" in label_lower:
                        data_collected[COL_RND] = extracted_val
                        
            except Exception as e:
                logging.warning(f"      ⚠️ [Worker-{worker_id}] {ticker} Fin 오류: {e}")

            # 결과 임시 저장
            batch_results[idx] = data_collected
            
    except Exception as e:
        logging.error(f"❌ [Worker-{worker_id}] 치명적 오류 발생: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        logging.info(f"👋 [Worker-{worker_id}] 할당 작업 종료.")
    
    return batch_results

# ==============================================================================
# [메인 실행부]
# ==============================================================================
def main(input_csv="COMPS.csv", output_csv="COMPS_updated_final.csv"):
    setup_logging()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(base_dir, input_csv)
    output_path = os.path.join(base_dir, output_csv)
    
    if not os.path.exists(input_path):
        logging.error(f"입력 파일을 찾을 수 없습니다: {input_path}")
        return

    # CSV 로드
    df = pd.read_csv(input_path)
    
    # 필요한 컬럼 생성 및 초기화
    if COL_SGA not in df.columns: df[COL_SGA] = None
    if COL_RND not in df.columns: df[COL_RND] = None
    
    # 데이터 타입 변환 (오류 방지)
    cols_to_convert = [c for c in df.columns if "Currency" in c or "/key-statistics/" in c or "/financials/" in c]
    cols_to_convert += [COL_SGA, COL_RND]
    for col in cols_to_convert:
        if col in df.columns: df[col] = df[col].astype('object')

    # 인덱스 분할 (작업 배분)
    df_indices = df.index.tolist()
    chunks = np.array_split(df_indices, MAX_WORKERS)
    
    logging.info(f"🔥 [메인] 병렬 수집 시작 (총 {len(df)}개 종목 / {MAX_WORKERS}개 브라우저)")
    start_time = time.time()

    # 병렬 실행 (Executor)
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i, chunk in enumerate(chunks):
            if len(chunk) == 0: continue
            # Worker ID는 1부터 시작하도록 전달
            futures.append(executor.submit(process_batch, i+1, chunk, df))
        
        # 결과 수집
        for future in as_completed(futures):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                logging.error(f"메인 루프에서 워커 오류 감지: {e}")

    # 데이터 병합
    logging.info("💾 [메인] 수집된 데이터 병합 및 저장 중...")
    count_updates = 0
    for batch_res in results:
        for idx, data_map in batch_res.items():
            for key, val in data_map.items():
                if val:
                    df.at[idx, key] = val
                    count_updates += 1

    # 최종 저장
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    duration = time.time() - start_time
    
    logging.info(f"✅ [완료] 총 {count_updates}개 셀 업데이트 완료. (소요시간: {duration:.1f}초)")
    logging.info(f"📁 파일 저장됨: {output_path}")
    
    kill_zombie_chrome()

if __name__ == "__main__":
    # 시작 전 청소
    kill_zombie_chrome()
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("🛑 사용자 중단 명령(Ctrl+C) 감지!")
        kill_zombie_chrome()
    except Exception as e:
        logging.critical(f"🛑 알 수 없는 치명적 오류: {e}")
        traceback.print_exc()
        kill_zombie_chrome()