# -*- coding: utf-8 -*-
"""
자동 실행 오케스트레이터 (재시도/타임아웃/건너뛰기 지원)

개선점
- wehago_vacation_export.py: 최대 3회 재시도 + 각 시도 타임아웃, 실패해도 다음 스크립트로 진행
- 다른 스크립트도 개별 타임아웃 설정 및 실패 시 계속 진행(옵션화)
- 표준 출력/에러 로그 남김
"""

import subprocess
import sys
import logging
import time
from typing import Dict, Tuple

# -------------------- 설정 --------------------
# 스크립트별 (재시도 횟수, 타임아웃(초), 실패 후 계속 진행 여부)
RETRY_POLICY: Dict[str, Tuple[int, int, bool]] = {
    "wehago_vacation_export.py": (3, int(float(
        # 환경변수로 조정 가능 (기본 240초)
        __import__("os").environ.get("WEHAGO_EXPORT_TIMEOUT", "240")
    )), True),
    "wehago_to_gcal_sync_full_hardcoded_v2.py": (1, int(float(
        __import__("os").environ.get("GCAL_SYNC_TIMEOUT", "180")
    )), True),
    "rdxl_gcal_to_slack_daily_all_in_one.py": (1, int(float(
        __import__("os").environ.get("SLACK_PUSH_TIMEOUT", "120")
    )), True),
}

SCRIPTS_IN_ORDER = [
    "wehago_vacation_export.py",
    "wehago_to_gcal_sync_full_hardcoded_v2.py",
    "rdxl_gcal_to_slack_daily_all_in_one.py",
]

# -------------------- 로깅 --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def run_once(script_name: str, timeout: int) -> bool:
    """단일 실행 (타임아웃 적용)"""
    logging.info(f"--- [{script_name}] 실행 (timeout={timeout}s) ---")
    try:
        proc = subprocess.run(
            [sys.executable, script_name],
            check=False,                 # 반환코드로 성공/실패 판단
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        if proc.stdout:
            logging.info(f"[{script_name}] STDOUT:\n{proc.stdout.strip()}")
        if proc.stderr:
            logging.warning(f"[{script_name}] STDERR:\n{proc.stderr.strip()}")
        if proc.returncode == 0:
            logging.info(f"--- [{script_name}] 성공 ---")
            return True
        else:
            logging.error(f"--- [{script_name}] 실패 (returncode={proc.returncode}) ---")
            return False

    except subprocess.TimeoutExpired as e:
        logging.error(f"--- [{script_name}] 타임아웃 발생({timeout}s). 프로세스를 중단합니다. ---")
        # e.stdout / e.stderr는 None일 수 있음
        if e.stdout:
            logging.error(f"[{script_name}] (timeout) STDOUT:\n{e.stdout}")
        if e.stderr:
            logging.error(f"[{script_name}] (timeout) STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        logging.error(f"오류: '{script_name}' 파일이 보이지 않습니다.")
        return False
    except Exception as e:
        logging.exception(f"[{script_name}] 예외 발생: {e}")
        return False


def run_with_retry(script_name: str, retries: int, timeout: int) -> bool:
    """재시도 래퍼"""
    for attempt in range(1, retries + 1):
        ok = run_once(script_name, timeout)
        if ok:
            return True
        if attempt < retries:
            backoff = min(10, 2 * attempt)  # 짧은 백오프
            logging.info(f"[{script_name}] 재시도 대기 {backoff}s (시도 {attempt}/{retries})")
            time.sleep(backoff)
    logging.error(f"[{script_name}] 모든 재시도({retries}) 실패")
    return False


def main():
    logging.info(">>> 전체 자동화 시작 <<<")
    overall_success = True

    for script in SCRIPTS_IN_ORDER:
        retries, timeout, continue_on_fail = RETRY_POLICY.get(script, (1, 120, True))
        success = run_with_retry(script, retries, timeout)
        overall_success = overall_success and success

        if not success and not continue_on_fail:
            logging.error(f"'{script}' 실패로 중단(continue_on_fail=False).")
            break
        elif not success and continue_on_fail:
            logging.warning(f"'{script}' 실패. 다음 스크립트로 진행합니다.")

    if overall_success:
        logging.info(">>> 모든 스크립트 성공 <<<")
        sys.exit(0)
    else:
        logging.warning(">>> 일부 스크립트 실패 <<<")
        # 일부 실패해도 오케이: 0이 아닌 종료코드
        sys.exit(2)


if __name__ == "__main__":
    main()
