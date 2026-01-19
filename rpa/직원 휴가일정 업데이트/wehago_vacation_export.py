# -*- coding: utf-8 -*-
import os
import time
from pathlib import Path
import shutil
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_root / '.env.shared')
load_dotenv(_root / '.env.local', override=True)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException


# -------------------- 고정 값 --------------------
LOGIN_URL = "https://www.wehago.com/#/login"
DAYOFF_URL = "https://www.wehago.com/attendance/#/orgInfo/dayOff"

CSS_ID = "#inputId"
CSS_PW = "#inputPw"
CSS_LOGIN_BTN = '#contnt > div.content_box.login_process > div > button'
CSS_DUP_CONFIRM = "#contnt > div:nth-child(9) > div:nth-child(2) > div > div > div.dialog_content > div > div > div.dialog_data_area > div > div > button:nth-child(2)"

CSS_TAB_DAYOFF = "#BODY_CLASS > div > div.container > div > div > div > div.content_bx > div > div > div > div > div > div.am_admin_content > div > div.right_section > div > div > div.LUX_basic_tabs.table_tabs > div > ul > li:nth-child(2) > a > span"

CSS_BTN_EXCEL = "#BODY_CLASS > div > div.container > div > div > div > div.content_bx > div > div > div > div > div > div.am_admin_content > div > div.right_section > div > div > div.sec_tit_wrap > div.calbtn_bx > div > button"
CSS_BTN_NEXT_MONTH = "#BODY_CLASS > div > div.container > div > div > div > div.content_bx > div > div > div > div > div > div.am_admin_content > div > div.right_section > div > div > div.sec_tit_wrap > div.date_control_bx > button.LUX_basic_btn.Image.next"
CSS_MONTH_LABEL = "#BODY_CLASS > div > div.container > div > div > div > div.content_bx > div > div > div > div > div > div.am_admin_content > div > div.right_section > div > div > div.sec_tit_wrap > div.date_control_bx > div > span:nth-child(2) > strong"

# 다운로드 확인 팝업
CSS_DOWNLOAD_CONFIRM = "#confirm"

# 보안상 기본값은 공란으로 두고, 환경변수로 주입
WEHAGO_ID = os.getenv("WEHAGO_ID", "")
WEHAGO_PW = os.getenv("WEHAGO_PW", "")

# 다운로드 폴더
DOWNLOAD_DIR = Path.cwd() / "wehago_downloads"

# 원하는 개월 수로 조절
MONTHS_TO_FETCH = int(os.getenv("WEHAGO_MONTHS", "6"))

# -------------------- 유틸 --------------------
def _rmtree(path: Path) -> None:
    """강제 삭제 (오류 무시)."""
    if not path.exists():
        return
    for p in path.glob("*"):
        try:
            if p.is_file() or p.is_symlink():
                p.unlink(missing_ok=True)
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            # 잠깐 사용 중인 파일이 있어도 전체 흐름 방해하지 않음
            pass

def reset_download_dir(path: Path, retries: int = 3) -> None:
    """
    다운로드 시작 전, 폴더를 '항상' 깨끗하게 초기화.
    - 삭제 실패 시 재시도
    - 여전히 실패하면 백업 폴더로 이름 변경 후 새 폴더 생성
    """
    for i in range(retries):
        try:
            if path.exists():
                _rmtree(path)
                # 혹시 상위가 잠깐 잠겨 있어 삭제가 안 되었을 수 있으니 한 텀 쉬었다가 확인
                time.sleep(0.2)
                # 폴더 자체를 비우는 보수적 조치
                try:
                    # 폴더가 비어 있다면 rmdir 가능
                    path.rmdir()
                except Exception:
                    pass
            # 깨끗한 폴더 재생성
            path.mkdir(parents=True, exist_ok=True)

            # 검증: 잔여물이 없으면 성공
            if not any(path.iterdir()):
                return
        except Exception:
            time.sleep(0.4)

    # 끝내 잔여가 있으면 백업 후 새로 생성
    backup = path.with_name(f"{path.name}_old_{int(time.time())}")
    try:
        path.rename(backup)
    except Exception:
        pass
    path.mkdir(parents=True, exist_ok=True)

def new_chrome(download_dir: Path) -> webdriver.Chrome:
    download_dir.mkdir(parents=True, exist_ok=True)
    opts = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        # 아래 2~3줄이 저장 완료까지의 내부 검사 지연을 줄여줍니다
        "safebrowsing.enabled": False,
        "download.safebrowsing.enabled": False,
        # "safebrowsing.disable_download_protection": True,  # 더 과감히 줄이고 싶으면 주석 해제(보안↓)
    }
    opts.add_experimental_option("prefs", prefs)
    # 필요하면 헤드리스로 약간 더 빠르게
    # opts.add_argument("--headless=new")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.maximize_window()
    return driver


def wait_click(driver: webdriver.Chrome, css: str, timeout: int = 15):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
    el.click()
    return el

def click_if_present(driver: webdriver.Chrome, css: str, timeout_short: int = 4) -> bool:
    try:
        el = WebDriverWait(driver, timeout_short).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
        el.click()
        return True
    except Exception:
        return False

def wait_new_download(before_files: set[str], timeout: int = 90) -> str:
    end = time.time() + timeout
    while time.time() < end:
        current = {f.name for f in DOWNLOAD_DIR.glob("*")}
        new_files = [n for n in current - before_files if not n.endswith(".crdownload")]
        if new_files:
            # 잔여 .crdownload가 없어지는 걸 빠르게 체크
            while any(x.name.endswith(".crdownload") for x in DOWNLOAD_DIR.glob("*")):
                time.sleep(0.05)  # 0.30s → 0.05s
            return str(DOWNLOAD_DIR / sorted(new_files)[-1])
        time.sleep(0.05)  # 0.30s → 0.05s
    return ""

def wait_download_started(before_files: set[str], timeout: int = 6) -> str:
    """
    새 다운로드가 '시작'됐는지만 빠르게 확인 (.crdownload/.tmp/.part 생성 기준)
    시작된 파일명(임시 포함)을 반환, 시작 감지 실패 시 "" 반환
    """
    end = time.time() + timeout
    while time.time() < end:
        current = {f.name for f in DOWNLOAD_DIR.glob("*")}
        new = list(current - before_files)
        for n in new:
            low = n.lower()
            if low.endswith(".crdownload") or low.endswith(".tmp") or low.endswith(".part"):
                return n
            # 어떤 환경에선 임시확장자 없이 완성본이 바로 생기기도 함
            if not (low.endswith(".crdownload") or low.endswith(".tmp") or low.endswith(".part")):
                return n
        time.sleep(0.05)
    return ""

def wait_all_downloads_complete(expected_count: int, timeout_per_file: int = 45) -> None:
    """
    전체 다운로드 완료까지 기다림: 임시확장자(.crdownload/.tmp/.part)가 모두 사라질 때까지
    expected_count 개의 '완성본'이 생기면 종료
    """
    deadline = time.time() + max(15, expected_count * timeout_per_file)

    def is_temp(path: Path) -> bool:
        low = path.name.lower()
        return low.endswith(".crdownload") or low.endswith(".tmp") or low.endswith(".part")

    while time.time() < deadline:
        files = list(DOWNLOAD_DIR.glob("*"))
        temps = [p for p in files if is_temp(p)]
        finals = [p for p in files if not is_temp(p)]
        if len(finals) >= expected_count and not temps:
            return
        time.sleep(0.1)

    # 타임아웃이지만 흐름을 막진 않음(로그만 남기고 계속)
    print(f"[경고] 다운로드 완료 대기 타임아웃: 기대 {expected_count}개, 현재 완성 {len([p for p in DOWNLOAD_DIR.glob('*') if not p.name.lower().endswith(('.crdownload','.tmp','.part'))])}개")


# -------------------- 플로우 --------------------
def login(driver: webdriver.Chrome):
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, CSS_ID))).send_keys(WEHAGO_ID)
    driver.find_element(By.CSS_SELECTOR, CSS_PW).send_keys(WEHAGO_PW)
    wait_click(driver, CSS_LOGIN_BTN, timeout=10)
    # (랜덤) 중복 로그인 팝업
    if click_if_present(driver, CSS_DUP_CONFIRM, timeout_short=5):
        time.sleep(1.0)

def go_dayoff_and_open_tab(driver: webdriver.Chrome):
    driver.get(DAYOFF_URL)
    # 탭 클릭 시도(있으면 빠르게, 없어도 통과)
    click_if_present(driver, CSS_TAB_DAYOFF, timeout_short=5)
    # 엑셀 버튼이 '클릭 가능' 상태가 될 때까지 대기(바로 되면 바로 진행)
    WebDriverWait(driver, 6).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_BTN_EXCEL))
    )


def confirm_download_if_popup(driver: webdriver.Chrome):
    """엑셀 다운로드 버튼 후 뜨는 확인 팝업 처리"""
    # DOM 팝업(#confirm) 우선 처리
    if click_if_present(driver, CSS_DOWNLOAD_CONFIRM, timeout_short=5):
        return
    # 혹시 JS alert로 뜨는 경우도 커버
    try:
        WebDriverWait(driver, 3).until(EC.alert_is_present())
        driver.switch_to.alert.accept()
        time.sleep(0.3)
    except Exception:
        pass

def download_month_excel(driver: webdriver.Chrome, timeout_click: int = 15, timeout_download: int = 90) -> str:
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}
    wait_click(driver, CSS_BTN_EXCEL, timeout=timeout_click)
    confirm_download_if_popup(driver)
    path = wait_new_download(before, timeout=timeout_download)
    if not path:
        raise RuntimeError("엑셀 파일 다운로드를 확인하지 못했습니다.")
    return path

def next_month(driver: webdriver.Chrome):
    # 현재 달 텍스트 확보(없으면 빈 문자열로 진행)
    try:
        old_text = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CSS_MONTH_LABEL))
        ).text.strip()
    except TimeoutException:
        old_text = ""

    # 다음 달 클릭
    wait_click(driver, CSS_BTN_NEXT_MONTH, timeout=2)

    # 라벨이 바뀌면 즉시 다음 단계로 진행
    if old_text:
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.CSS_SELECTOR, CSS_MONTH_LABEL).text.strip() != old_text
            )
            return
        except TimeoutException:
            pass  # 라벨 텍스트 변경 감지 실패 시, 아래 Fallback으로

    # Fallback: 페이지 안정화만 짧게 확인(Timeout이어도 흐름 계속)
    try:
        WebDriverWait(driver, 2).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        pass

def main():
    reset_download_dir(DOWNLOAD_DIR)
    driver = new_chrome(DOWNLOAD_DIR)
    try:
        if not WEHAGO_ID or not WEHAGO_PW:
            raise RuntimeError("환경변수 WEHAGO_ID / WEHAGO_PW 를 설정하세요.")
        login(driver)
        go_dayoff_and_open_tab(driver)

        started = 0
        for idx in range(MONTHS_TO_FETCH):
            if idx > 0:
                next_month(driver)

            # ▼ 이전 파일 목록 캡처
            before = {f.name for f in DOWNLOAD_DIR.glob("*")}

            # ▼ 클릭(시작만 확인)
            try:
                wait_click(driver, CSS_BTN_EXCEL, timeout=15 if idx == 0 else 2)
                confirm_download_if_popup(driver)
                started_name = wait_download_started(before, timeout=8 if idx == 0 else 4)
                if started_name:
                    started += 1
                    print(f"[시작] {idx+1}/{MONTHS_TO_FETCH}개월차: {started_name}")
                else:
                    print(f"[경고] {idx+1}/{MONTHS_TO_FETCH}개월차: 시작 감지 실패(계속 진행)")
            except Exception as e:
                print(f"[실패] {idx+1}/{MONTHS_TO_FETCH}개월차 시작: {e}")

        # ▼ 모두 큐에 넣은 뒤, 한 번만 완료 대기
        if started > 0:
            wait_all_downloads_complete(started, timeout_per_file=40)
            # 완료된 파일 로그 출력
            finals = [p for p in DOWNLOAD_DIR.glob("*") if not p.name.lower().endswith((".crdownload",".tmp",".part"))]
            for i, p in enumerate(sorted(finals), 1):
                print(f"[완료] {i}/{len(finals)}: {p}")
        else:
            print("[알림] 감지된 시작이 없습니다.")

        print("\n자동화 완료 ✔")
    finally:
        time.sleep(0.5)
        try: driver.quit()
        except Exception: pass


if __name__ == "__main__":
    main()
