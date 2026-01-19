# -*- coding: utf-8 -*-
"""
Wehago 웹 스크래핑 서비스
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Callable, List
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

from config import (
    WEHAGO_LOGIN_URL,
    WEHAGO_SERVICE_URL,
    WEHAGO_ACCOUNT_URL,
    SEL_BODY_IFRAME,
    SEL_TITLE,
    SEL_DOCNO,
    SEL_DATE,
    SEL_WRITER,
    SEL_DIALOG_CONTENT,
    SEL_ATTACHMENT_ZONE,
    SEL_ATTACHMENT_SAVE_ALL_BTN
)
from utils.date_utils import format_raw_date


@dataclass
class DocumentInfo:
    """수집된 문서 정보"""
    title: str
    docno: str
    date: str
    writer: str
    body: str


@dataclass
class FullDocumentInfo:
    """전체 문서 정보 (첨부 파일 포함)"""
    title: str
    docno: str
    date: str
    writer: str
    body: str
    full_text: str                          # 팝업 전체 텍스트
    attachments: List[str] = field(default_factory=list)  # 다운로드된 파일 목록
    save_path: Optional[Path] = None        # 저장 경로


class WehagoScraperService:
    """Wehago 플랫폼 웹 스크래핑 서비스"""

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None

    def is_connected(self) -> bool:
        """드라이버 연결 상태 확인"""
        return self.driver is not None

    def login(
        self,
        user_id: str,
        password: str,
        window_position: Tuple[int, int] = (0, 0),
        window_size: Tuple[int, int] = (1200, 800),
        on_complete: Optional[Callable] = None
    ) -> None:
        """
        Wehago 로그인 수행

        Args:
            user_id: 사용자 ID
            password: 비밀번호
            window_position: 브라우저 창 위치 (x, y)
            window_size: 브라우저 창 크기 (width, height)
            on_complete: 완료 시 호출할 콜백
        """
        self.driver = webdriver.Chrome()
        self.driver.set_window_position(*window_position)
        self.driver.set_window_size(*window_size)
        self.driver.get(WEHAGO_LOGIN_URL)
        self.driver.find_element(By.CSS_SELECTOR, "#inputId").send_keys(user_id)
        self.driver.find_element(By.CSS_SELECTOR, "#inputPw").send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, "#contnt button span").click()

        if on_complete:
            on_complete()

    def goto_service_management(self) -> None:
        """서비스관리 페이지로 이동"""
        if not self.driver:
            raise RuntimeError("먼저 Login 하세요.")
        self.driver.get(WEHAGO_SERVICE_URL)

    def goto_account_history(self) -> None:
        """위하고 통장 거래내역 페이지로 이동"""
        if not self.driver:
            raise RuntimeError("먼저 Login 하세요.")
        self.driver.get(WEHAGO_ACCOUNT_URL)

    def _execute_live_text(self, selector: str) -> str:
        """JavaScript로 DOM 요소 텍스트 추출"""
        return self.driver.execute_script("""
            const e = document.querySelector(arguments[0]);
            if (!e) return '';
            const t = e.innerText.trim();
            if (t) return t;
            const img = e.querySelector('img[alt]');
            return img ? img.alt.trim() : '';
        """, selector)

    def _parse_body_html(self) -> str:
        """iframe 내 본문 HTML 파싱"""
        iframe = self.driver.find_element(By.CSS_SELECTOR, SEL_BODY_IFRAME)
        self.driver.switch_to.frame(iframe)
        body_html = self.driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
        self.driver.switch_to.default_content()

        soup = BeautifulSoup(body_html, "lxml")
        table = soup.select_one("table")
        if not table:
            return soup.get_text(" ", strip=True)

        lines = []
        for tr in table.select("tr"):
            cols = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
            if len(cols) == 2:
                lines.append(f"{cols[0]} : {cols[1]}")
            elif cols:
                lines.append(" | ".join(cols))
        return "\n".join(lines)

    def collect_document(self) -> DocumentInfo:
        """
        현재 열린 팝업에서 문서 정보 수집

        Returns:
            DocumentInfo 객체

        Raises:
            RuntimeError: 팝업이 열려 있지 않거나 셀렉터 오류
        """
        if not self.driver:
            raise RuntimeError("먼저 Login 하세요.")

        # 마지막 윈도우로 전환
        self.driver.switch_to.window(self.driver.window_handles[-1])

        title = self._execute_live_text(SEL_TITLE)
        docno = self._execute_live_text(SEL_DOCNO)
        raw_date = self._execute_live_text(SEL_DATE)
        writer = self._execute_live_text(SEL_WRITER)

        if not any((title, docno, raw_date, writer)):
            raise RuntimeError("팝업이 열려 있지 않거나 셀렉터가 달라졌습니다.")

        date = format_raw_date(raw_date)
        body = self._parse_body_html()

        return DocumentInfo(
            title=title,
            docno=docno,
            date=date,
            writer=writer,
            body=body
        )

    def close(self) -> None:
        """브라우저 닫기"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    # ────────────────────────────────────────────────────────
    # 전체 문서 수집 (첨부 파일 포함)
    # ────────────────────────────────────────────────────────

    def collect_full_document(self, data_dir: Path) -> FullDocumentInfo:
        """
        팝업 전체 내용 수집 + 첨부 파일 다운로드

        Args:
            data_dir: 데이터 저장 기본 경로 (예: ./data)

        Returns:
            FullDocumentInfo 객체
        """
        # 1. 기본 문서 정보 수집
        basic_info = self.collect_document()

        # 2. 문서번호로 저장 폴더 생성 (특수문자 제거)
        safe_docno = self._sanitize_filename(basic_info.docno)
        doc_folder = data_dir / safe_docno
        attachments_folder = doc_folder / "attachments"
        attachments_folder.mkdir(parents=True, exist_ok=True)

        # 3. 팝업 전체 텍스트 수집
        full_text = self._collect_full_popup_text()

        # 4. 첨부 파일 다운로드
        downloaded_files = self._download_attachments(attachments_folder)

        # 5. 메타데이터 JSON 저장
        self._save_metadata(doc_folder, basic_info, full_text, downloaded_files)

        return FullDocumentInfo(
            title=basic_info.title,
            docno=basic_info.docno,
            date=basic_info.date,
            writer=basic_info.writer,
            body=basic_info.body,
            full_text=full_text,
            attachments=downloaded_files,
            save_path=doc_folder
        )

    def _sanitize_filename(self, name: str) -> str:
        """파일명에 사용할 수 없는 문자 제거"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name.strip()

    def _collect_full_popup_text(self) -> str:
        """팝업 창 전체 텍스트 수집"""
        try:
            dialog = self.driver.find_element(By.CSS_SELECTOR, SEL_DIALOG_CONTENT)
            return dialog.text
        except Exception:
            return ""

    def _download_attachments(self, save_folder: Path) -> List[str]:
        """
        첨부 파일 다운로드 (모두저장 버튼 클릭)

        Args:
            save_folder: 첨부 파일 저장 폴더

        Returns:
            다운로드된 파일명 리스트
        """
        # Chrome 다운로드 경로 동적 변경
        self._set_download_path(str(save_folder.resolve()))

        try:
            # 첨부 파일 영역 확인
            attachment_zone = self.driver.find_elements(
                By.CSS_SELECTOR, SEL_ATTACHMENT_ZONE
            )
            if not attachment_zone:
                return []  # 첨부 파일 없음

            # "모두저장" 버튼 찾기
            save_btns = self.driver.find_elements(
                By.CSS_SELECTOR, SEL_ATTACHMENT_SAVE_ALL_BTN
            )

            for btn in save_btns:
                btn_text = btn.text.strip()
                if "모두저장" in btn_text or "저장" in btn_text:
                    btn.click()

                    # 다운로드 완료 대기
                    time.sleep(2)  # 기본 대기
                    self._wait_for_downloads(save_folder, timeout=30)
                    break

            # 다운로드된 파일 목록 반환
            return [f.name for f in save_folder.iterdir() if f.is_file()]

        except Exception as e:
            print(f"첨부 파일 다운로드 실패: {e}")
            return []

    def _set_download_path(self, path: str) -> None:
        """Chrome 다운로드 경로 동적 변경 (CDP 명령)"""
        try:
            self.driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": path}
            )
        except Exception as e:
            print(f"다운로드 경로 설정 실패: {e}")

    def _wait_for_downloads(self, folder: Path, timeout: int = 30) -> bool:
        """
        다운로드 완료 대기 (.crdownload 파일 사라질 때까지)

        Args:
            folder: 다운로드 폴더
            timeout: 최대 대기 시간 (초)

        Returns:
            완료 여부
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            # 다운로드 중인 파일 확인
            downloading = list(folder.glob("*.crdownload")) + list(folder.glob("*.tmp"))
            if not downloading:
                return True
            time.sleep(1)
        return False

    def _save_metadata(
        self,
        doc_folder: Path,
        basic_info: DocumentInfo,
        full_text: str,
        attachments: List[str]
    ) -> None:
        """메타데이터 JSON 저장"""
        metadata = {
            "title": basic_info.title,
            "docno": basic_info.docno,
            "date": basic_info.date,
            "writer": basic_info.writer,
            "body": basic_info.body,
            "full_text": full_text,
            "attachments": attachments,
            "collected_at": datetime.now().isoformat()
        }

        metadata_path = doc_folder / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
