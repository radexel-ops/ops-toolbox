"""
프로젝트 관리 모듈
==================
프로젝트 디렉토리 관리, 첨부파일 저장, 연관 거래 링크 등을 담당합니다.

주요 기능:
- 프로젝트 생성/로드/저장
- 행별 첨부파일 관리
- 연관 거래(linked_transactions) 연결 및 저장
- 분류 작업 데이터 영속성
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from config import SCRIPT_DIR


class ProjectManager:
    """
    프로젝트 디렉토리 관리자

    각 Excel/CSV 파일에 대해 프로젝트 디렉토리를 생성하고,
    첨부파일과 연관 거래를 행별로 연결하여 저장/관리합니다.

    디렉토리 구조:
    projects/
    ├── {프로젝트명_YYYYMMDD_HHMMSS}/
    │   ├── source.xlsx (원본 파일 복사본)
    │   ├── attachments/
    │   │   ├── row_001_001_filename.pdf
    │   │   └── ...
    │   ├── project.json (메타데이터)
    │   └── classification_data.json (분류 작업 데이터)
    """

    PROJECTS_DIR = os.path.join(SCRIPT_DIR, "projects")

    def __init__(self, source_file_path: str = None):
        self.source_file_path = source_file_path
        self.project_dir = None
        self.attachments_dir = None
        self.metadata = {
            "project_name": "",
            "source_file": "",
            "source_file_path": "",
            "created_at": "",
            "last_modified": "",
            "attachments": {},  # {row_key: [{file_info}, ...]}
            "linked_transactions": {},  # {row_key: [linked_row_indices]}
            "row_notes": {}  # {row_key: "메모"}
        }

        # 프로젝트 디렉토리 생성
        os.makedirs(self.PROJECTS_DIR, exist_ok=True)

    def create_project(self, source_file_path: str) -> bool:
        """새 프로젝트 생성"""
        self.source_file_path = source_file_path
        file_name = os.path.basename(source_file_path)
        base_name = os.path.splitext(file_name)[0]

        # 프로젝트명 생성 (파일명_날짜시간)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = f"{base_name}_{timestamp}"

        # 디렉토리 생성
        self.project_dir = os.path.join(self.PROJECTS_DIR, project_name)
        self.attachments_dir = os.path.join(self.project_dir, "attachments")

        try:
            os.makedirs(self.project_dir, exist_ok=True)
            os.makedirs(self.attachments_dir, exist_ok=True)

            # 원본 파일 복사
            dest_file = os.path.join(self.project_dir, f"source{os.path.splitext(file_name)[1]}")
            shutil.copy2(source_file_path, dest_file)

            # 메타데이터 초기화
            self.metadata = {
                "project_name": project_name,
                "source_file": file_name,
                "source_file_path": source_file_path,
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat(),
                "attachments": {},
                "linked_transactions": {},
                "row_notes": {}
            }
            self._save_metadata()
            return True

        except Exception as e:
            print(f"프로젝트 생성 오류: {e}")
            return False

    def load_project(self, project_dir: str) -> bool:
        """기존 프로젝트 로드"""
        self.project_dir = project_dir
        self.attachments_dir = os.path.join(project_dir, "attachments")
        metadata_path = os.path.join(project_dir, "project.json")

        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)

                # 이전 버전 호환성: linked_transactions 필드가 없으면 추가
                if "linked_transactions" not in self.metadata:
                    self.metadata["linked_transactions"] = {}

                self.source_file_path = self.metadata.get("source_file_path", "")
                return True
            except Exception as e:
                print(f"프로젝트 로드 오류: {e}")
        return False

    def find_existing_project(self, source_file_path: str) -> Optional[str]:
        """동일한 원본 파일에 대한 기존 프로젝트 찾기"""
        if not os.path.exists(self.PROJECTS_DIR):
            return None

        for project_name in os.listdir(self.PROJECTS_DIR):
            project_dir = os.path.join(self.PROJECTS_DIR, project_name)
            metadata_path = os.path.join(project_dir, "project.json")

            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    if meta.get("source_file_path") == source_file_path:
                        return project_dir
                except:
                    continue
        return None

    # ==========================================
    # 첨부파일 관리
    # ==========================================

    def add_attachment(self, row_idx: int, file_path: str, sheet_name: str = "Sheet1") -> Optional[str]:
        """
        행에 첨부파일 추가

        Args:
            row_idx: 행 인덱스
            file_path: 첨부할 파일 경로
            sheet_name: 시트명

        Returns:
            저장된 파일 경로 (실패 시 None)
        """
        if not self.attachments_dir or not os.path.exists(self.attachments_dir):
            return None

        try:
            # 고유 키 생성 (시트_행)
            row_key = f"{sheet_name}_{row_idx}"

            # 기존 첨부파일 수 확인
            existing = self.metadata.get("attachments", {}).get(row_key, [])
            file_num = len(existing) + 1

            # 파일명 생성: row_XXX_YYY_원본파일명
            original_name = os.path.basename(file_path)
            ext = os.path.splitext(original_name)[1]
            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in os.path.splitext(original_name)[0])
            saved_name = f"row_{row_idx+1:03d}_{file_num:03d}_{safe_name}{ext}"

            dest_path = os.path.join(self.attachments_dir, saved_name)

            # 파일 복사
            shutil.copy2(file_path, dest_path)

            # 메타데이터 업데이트
            if "attachments" not in self.metadata:
                self.metadata["attachments"] = {}
            if row_key not in self.metadata["attachments"]:
                self.metadata["attachments"][row_key] = []

            self.metadata["attachments"][row_key].append({
                "original_name": original_name,
                "saved_name": saved_name,
                "saved_path": dest_path,
                "attached_at": datetime.now().isoformat(),
                "file_type": ext.lstrip('.').lower()
            })

            self.metadata["last_modified"] = datetime.now().isoformat()
            self._save_metadata()

            return dest_path

        except Exception as e:
            print(f"첨부파일 추가 오류: {e}")
            return None

    def get_attachments(self, row_idx: int, sheet_name: str = "Sheet1") -> List[Dict]:
        """행의 첨부파일 목록 가져오기"""
        row_key = f"{sheet_name}_{row_idx}"
        return self.metadata.get("attachments", {}).get(row_key, [])

    def get_all_attachments(self) -> Dict[str, List[Dict]]:
        """모든 첨부파일 목록 가져오기"""
        return self.metadata.get("attachments", {})

    def remove_attachment(self, row_idx: int, attachment_index: int, sheet_name: str = "Sheet1") -> bool:
        """첨부파일 삭제"""
        row_key = f"{sheet_name}_{row_idx}"
        attachments = self.metadata.get("attachments", {}).get(row_key, [])

        if 0 <= attachment_index < len(attachments):
            try:
                # 파일 삭제
                file_info = attachments[attachment_index]
                file_path = file_info.get("saved_path", "")
                if os.path.exists(file_path):
                    os.remove(file_path)

                # 메타데이터에서 제거
                attachments.pop(attachment_index)
                self.metadata["attachments"][row_key] = attachments
                self._save_metadata()
                return True
            except Exception as e:
                print(f"첨부파일 삭제 오류: {e}")
        return False

    # ==========================================
    # 연관 거래(Linked Transactions) 관리
    # ==========================================

    def add_linked_transactions(self, row_idx: int, linked_rows: List[int],
                                 sheet_name: str = "Sheet1") -> bool:
        """
        행에 연관 거래 연결 추가

        Args:
            row_idx: 원본 행 인덱스
            linked_rows: 연결할 행 인덱스 목록
            sheet_name: 시트명

        Returns:
            성공 여부
        """
        try:
            row_key = f"{sheet_name}_{row_idx}"

            if "linked_transactions" not in self.metadata:
                self.metadata["linked_transactions"] = {}

            # 기존 연결에 새 연결 추가 (중복 제거)
            existing = set(self.metadata["linked_transactions"].get(row_key, []))
            existing.update(linked_rows)
            # 자기 자신은 제외
            existing.discard(row_idx)

            self.metadata["linked_transactions"][row_key] = list(existing)

            # 양방향 연결 설정 (연결된 행들도 현재 행을 참조)
            for linked_idx in linked_rows:
                if linked_idx != row_idx:
                    linked_key = f"{sheet_name}_{linked_idx}"
                    if linked_key not in self.metadata["linked_transactions"]:
                        self.metadata["linked_transactions"][linked_key] = []
                    if row_idx not in self.metadata["linked_transactions"][linked_key]:
                        self.metadata["linked_transactions"][linked_key].append(row_idx)

            self.metadata["last_modified"] = datetime.now().isoformat()
            self._save_metadata()
            return True

        except Exception as e:
            print(f"연관 거래 연결 오류: {e}")
            return False

    def get_linked_transactions(self, row_idx: int, sheet_name: str = "Sheet1") -> List[int]:
        """
        행의 연관 거래 목록 가져오기

        Args:
            row_idx: 행 인덱스
            sheet_name: 시트명

        Returns:
            연결된 행 인덱스 목록
        """
        row_key = f"{sheet_name}_{row_idx}"
        return self.metadata.get("linked_transactions", {}).get(row_key, [])

    def remove_linked_transaction(self, row_idx: int, target_row: int,
                                   sheet_name: str = "Sheet1") -> bool:
        """
        특정 연관 거래 연결 해제

        Args:
            row_idx: 원본 행 인덱스
            target_row: 연결 해제할 대상 행 인덱스
            sheet_name: 시트명

        Returns:
            성공 여부
        """
        try:
            row_key = f"{sheet_name}_{row_idx}"
            target_key = f"{sheet_name}_{target_row}"

            # 원본 행에서 대상 제거
            if row_key in self.metadata.get("linked_transactions", {}):
                links = self.metadata["linked_transactions"][row_key]
                if target_row in links:
                    links.remove(target_row)
                    self.metadata["linked_transactions"][row_key] = links

            # 대상 행에서도 원본 제거 (양방향)
            if target_key in self.metadata.get("linked_transactions", {}):
                links = self.metadata["linked_transactions"][target_key]
                if row_idx in links:
                    links.remove(row_idx)
                    self.metadata["linked_transactions"][target_key] = links

            self.metadata["last_modified"] = datetime.now().isoformat()
            self._save_metadata()
            return True

        except Exception as e:
            print(f"연관 거래 연결 해제 오류: {e}")
            return False

    def clear_linked_transactions(self, row_idx: int, sheet_name: str = "Sheet1") -> bool:
        """
        행의 모든 연관 거래 연결 해제

        Args:
            row_idx: 행 인덱스
            sheet_name: 시트명

        Returns:
            성공 여부
        """
        try:
            row_key = f"{sheet_name}_{row_idx}"

            # 먼저 연결된 모든 행에서 현재 행 참조 제거
            linked = self.get_linked_transactions(row_idx, sheet_name)
            for linked_idx in linked:
                linked_key = f"{sheet_name}_{linked_idx}"
                if linked_key in self.metadata.get("linked_transactions", {}):
                    links = self.metadata["linked_transactions"][linked_key]
                    if row_idx in links:
                        links.remove(row_idx)
                        self.metadata["linked_transactions"][linked_key] = links

            # 현재 행의 연결 초기화
            if row_key in self.metadata.get("linked_transactions", {}):
                self.metadata["linked_transactions"][row_key] = []

            self.metadata["last_modified"] = datetime.now().isoformat()
            self._save_metadata()
            return True

        except Exception as e:
            print(f"연관 거래 전체 연결 해제 오류: {e}")
            return False

    # ==========================================
    # 메타데이터 및 분류 데이터
    # ==========================================

    def _save_metadata(self):
        """메타데이터 저장"""
        if self.project_dir:
            metadata_path = os.path.join(self.project_dir, "project.json")
            try:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"메타데이터 저장 오류: {e}")

    def save_classification_data(self, sheets: Dict[str, pd.DataFrame],
                                  chat_histories: Dict[str, Dict[int, List[Dict]]]) -> bool:
        """
        분류 작업 데이터 저장 (DataFrame의 분류 컬럼 + 대화 기록)

        Args:
            sheets: {sheet_name: DataFrame} - 분류 결과가 포함된 데이터프레임
            chat_histories: {sheet_name: {row_idx: [messages]}} - 대화 기록

        Returns:
            성공 여부
        """
        if not self.project_dir:
            print("프로젝트가 초기화되지 않았습니다.")
            return False

        data_path = os.path.join(self.project_dir, "classification_data.json")

        try:
            # 저장할 데이터 구조
            save_data = {
                "saved_at": datetime.now().isoformat(),
                "sheets": {},
                "chat_histories": {}
            }

            # 각 시트의 분류 관련 컬럼만 저장
            classification_columns = ["분류_상태", "최종_분류", "분류_근거", "사용자_입력", "대화_기록", "검토표시"]

            for sheet_name, df in sheets.items():
                sheet_data = {}
                for col in classification_columns:
                    if col in df.columns:
                        # NaN 값을 빈 문자열로 변환
                        col_data = df[col].fillna("").astype(str).tolist()
                        sheet_data[col] = col_data

                if sheet_data:
                    save_data["sheets"][sheet_name] = sheet_data

            # 대화 기록 저장
            for sheet_name, rows in chat_histories.items():
                save_data["chat_histories"][sheet_name] = {
                    str(row_idx): messages for row_idx, messages in rows.items()
                }

            # JSON 파일로 저장
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            # 메타데이터 수정 시간 업데이트
            self.metadata["last_modified"] = datetime.now().isoformat()
            self._save_metadata()

            print(f"분류 데이터 저장 완료: {data_path}")
            return True

        except Exception as e:
            print(f"분류 데이터 저장 오류: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_classification_data(self) -> Optional[Dict]:
        """
        저장된 분류 작업 데이터 로드

        Returns:
            {
                "sheets": {sheet_name: {col_name: [values]}},
                "chat_histories": {sheet_name: {row_idx: [messages]}}
            }
            또는 None (파일이 없거나 오류 시)
        """
        if not self.project_dir:
            return None

        data_path = os.path.join(self.project_dir, "classification_data.json")

        if not os.path.exists(data_path):
            print(f"분류 데이터 파일이 없습니다: {data_path}")
            return None

        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # chat_histories의 키를 int로 변환
            chat_histories = {}
            for sheet_name, rows in data.get("chat_histories", {}).items():
                chat_histories[sheet_name] = {
                    int(row_idx): messages for row_idx, messages in rows.items()
                }
            data["chat_histories"] = chat_histories

            print(f"분류 데이터 로드 완료: {data_path}")
            return data

        except Exception as e:
            print(f"분류 데이터 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_project_info(self) -> Dict:
        """프로젝트 정보 반환"""
        linked_count = sum(len(v) for v in self.metadata.get("linked_transactions", {}).values())
        return {
            "project_dir": self.project_dir,
            "project_name": self.metadata.get("project_name", ""),
            "source_file": self.metadata.get("source_file", ""),
            "created_at": self.metadata.get("created_at", ""),
            "attachment_count": sum(len(v) for v in self.metadata.get("attachments", {}).values()),
            "linked_transaction_count": linked_count // 2  # 양방향이므로 2로 나눔
        }

    @classmethod
    def list_projects(cls) -> List[Dict]:
        """모든 프로젝트 목록 반환"""
        projects = []
        if not os.path.exists(cls.PROJECTS_DIR):
            return projects

        for project_name in os.listdir(cls.PROJECTS_DIR):
            project_dir = os.path.join(cls.PROJECTS_DIR, project_name)
            metadata_path = os.path.join(project_dir, "project.json")

            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)

                    linked_count = sum(len(v) for v in meta.get("linked_transactions", {}).values())

                    projects.append({
                        "project_name": project_name,
                        "project_dir": project_dir,
                        "source_file": meta.get("source_file", ""),
                        "created_at": meta.get("created_at", ""),
                        "last_modified": meta.get("last_modified", ""),
                        "attachment_count": sum(len(v) for v in meta.get("attachments", {}).values()),
                        "linked_transaction_count": linked_count // 2
                    })
                except:
                    continue

        # 최근 수정순 정렬
        projects.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
        return projects
