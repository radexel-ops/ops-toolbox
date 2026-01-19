"""
회계처리 실무지침 관리자
========================
실무지침 파일의 로드, 저장, 학습 케이스 관리를 담당합니다.

회계담당자 안내:
- accounting_guidelines.yaml 파일을 직접 편집하여 실무지침 수정 가능
- YAML 형식은 JSON보다 읽기/쓰기가 쉬움
- 앱 내 '지침 편집기' 기능으로도 수정 가능

버전 관리:
- 변경 시 자동 백업
- guidelines_versions/ 폴더에 버전 히스토리 저장
- 언제든 이전 버전으로 복원 가능
"""

import json
import os
import datetime
import hashlib
import shutil
import glob
from typing import Dict, List, Optional, Tuple

# YAML 지원 (설치되어 있으면 사용)
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("참고: PyYAML이 설치되지 않아 YAML 형식을 사용할 수 없습니다.")
    print("YAML 사용하려면: pip install pyyaml")

from config import (
    GUIDELINES_JSON_PATH,
    GUIDELINES_YAML_PATH,
    GUIDELINES_VERSIONS_DIR,
    GUIDELINES_STATE_FILE,
    MAX_VERSIONS_TO_KEEP,
    MAX_LEARNED_CASES_FOR_AI
)


# ==========================================
# 버전 관리 및 변경 감지
# ==========================================

def _ensure_versions_dir():
    """버전 폴더 생성"""
    if not os.path.exists(GUIDELINES_VERSIONS_DIR):
        os.makedirs(GUIDELINES_VERSIONS_DIR)


def _get_file_hash(file_path: str) -> str:
    """파일의 MD5 해시 계산"""
    if not os.path.exists(file_path):
        return ""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def _load_state() -> Dict:
    """저장된 상태 로드 (마지막으로 확인한 파일 해시 등)"""
    if os.path.exists(GUIDELINES_STATE_FILE):
        try:
            with open(GUIDELINES_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def _save_state(state: Dict):
    """상태 저장"""
    with open(GUIDELINES_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def check_yaml_changes() -> Dict:
    """
    YAML 파일 변경 감지

    Returns:
        Dict:
            - changed: bool - 변경되었는지 여부
            - last_modified: str - 마지막 수정 시간
            - message: str - 사용자에게 보여줄 메시지
    """
    if not os.path.exists(GUIDELINES_YAML_PATH):
        return {"changed": False, "message": "YAML 파일이 없습니다."}

    current_hash = _get_file_hash(GUIDELINES_YAML_PATH)
    current_mtime = os.path.getmtime(GUIDELINES_YAML_PATH)
    current_mtime_str = datetime.datetime.fromtimestamp(current_mtime).strftime("%Y-%m-%d %H:%M:%S")

    state = _load_state()
    last_hash = state.get("yaml_hash", "")

    if not last_hash:
        # 처음 실행 - 현재 상태 저장
        state["yaml_hash"] = current_hash
        state["yaml_acknowledged"] = current_mtime_str
        _save_state(state)
        return {"changed": False, "message": "초기 상태 저장됨"}

    if current_hash != last_hash:
        return {
            "changed": True,
            "last_modified": current_mtime_str,
            "last_acknowledged": state.get("yaml_acknowledged", "알 수 없음"),
            "message": f"실무지침(YAML)이 수정되었습니다.\n수정 시간: {current_mtime_str}"
        }

    return {"changed": False, "message": "변경 없음"}


def acknowledge_yaml_changes():
    """YAML 변경사항 확인함으로 표시 (사용자가 '적용' 선택 시)"""
    if not os.path.exists(GUIDELINES_YAML_PATH):
        return

    current_hash = _get_file_hash(GUIDELINES_YAML_PATH)
    current_mtime = os.path.getmtime(GUIDELINES_YAML_PATH)
    current_mtime_str = datetime.datetime.fromtimestamp(current_mtime).strftime("%Y-%m-%d %H:%M:%S")

    state = _load_state()
    state["yaml_hash"] = current_hash
    state["yaml_acknowledged"] = current_mtime_str
    _save_state(state)


def create_backup(reason: str = "manual") -> Optional[str]:
    """
    현재 실무지침 백업 생성

    Args:
        reason: 백업 사유 (manual, before_restore, auto, yaml_change 등)

    Returns:
        str: 백업 파일 경로 (실패 시 None)
    """
    _ensure_versions_dir()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"guidelines_{timestamp}_{reason}"

    try:
        # 현재 상태를 하나의 JSON으로 병합 저장
        current_data = load_guidelines()
        if not current_data:
            return None

        # 백업 메타데이터 추가
        current_data["_backup_info"] = {
            "created": datetime.datetime.now().isoformat(),
            "reason": reason,
            "yaml_existed": os.path.exists(GUIDELINES_YAML_PATH),
            "json_existed": os.path.exists(GUIDELINES_JSON_PATH)
        }

        backup_path = os.path.join(GUIDELINES_VERSIONS_DIR, f"{backup_name}.json")
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

        # 오래된 백업 정리
        _cleanup_old_backups()

        return backup_path

    except Exception as e:
        print(f"백업 생성 오류: {e}")
        return None


def _cleanup_old_backups():
    """오래된 백업 파일 정리 (MAX_VERSIONS_TO_KEEP 초과 시)"""
    backup_files = glob.glob(os.path.join(GUIDELINES_VERSIONS_DIR, "guidelines_*.json"))
    backup_files.sort(key=os.path.getmtime, reverse=True)

    # 최신 N개만 유지
    for old_file in backup_files[MAX_VERSIONS_TO_KEEP:]:
        try:
            os.remove(old_file)
        except:
            pass


def get_version_list() -> List[Dict]:
    """
    저장된 버전 목록 반환

    Returns:
        List[Dict]: 버전 정보 목록 (최신순)
            - filename: 파일명
            - path: 전체 경로
            - created: 생성 시간
            - reason: 백업 사유
            - size: 파일 크기
    """
    _ensure_versions_dir()

    versions = []
    backup_files = glob.glob(os.path.join(GUIDELINES_VERSIONS_DIR, "guidelines_*.json"))

    for filepath in backup_files:
        try:
            stat = os.stat(filepath)
            filename = os.path.basename(filepath)

            # 백업 정보 읽기
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                backup_info = data.get("_backup_info", {})

            versions.append({
                "filename": filename,
                "path": filepath,
                "created": backup_info.get("created", datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()),
                "reason": backup_info.get("reason", "unknown"),
                "size": stat.st_size,
                "display_name": _format_version_name(filename, backup_info)
            })
        except Exception as e:
            print(f"버전 정보 읽기 오류 ({filepath}): {e}")

    # 최신순 정렬
    versions.sort(key=lambda x: x["created"], reverse=True)
    return versions


def _format_version_name(filename: str, backup_info: Dict) -> str:
    """버전 표시 이름 생성"""
    reason_names = {
        "manual": "수동 백업",
        "before_restore": "복원 전 백업",
        "auto": "자동 백업",
        "yaml_change": "YAML 변경 적용",
        "learned_case": "학습 케이스 추가",
        "conflict": "충돌 기록"
    }

    created = backup_info.get("created", "")
    if created:
        try:
            dt = datetime.datetime.fromisoformat(created)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = created[:16]
    else:
        # 파일명에서 추출
        parts = filename.replace("guidelines_", "").replace(".json", "").split("_")
        if len(parts) >= 2:
            date_str = f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]} {parts[1][:2]}:{parts[1][2:4]}"
        else:
            date_str = "알 수 없음"

    reason = backup_info.get("reason", "unknown")
    reason_display = reason_names.get(reason, reason)

    return f"{date_str} ({reason_display})"


def restore_version(version_path: str) -> Tuple[bool, str]:
    """
    특정 버전으로 복원

    Args:
        version_path: 복원할 버전 파일 경로

    Returns:
        Tuple[bool, str]: (성공 여부, 메시지)
    """
    if not os.path.exists(version_path):
        return False, "버전 파일을 찾을 수 없습니다."

    try:
        # 복원 전 현재 상태 백업
        create_backup("before_restore")

        # 버전 파일 로드
        with open(version_path, 'r', encoding='utf-8') as f:
            version_data = json.load(f)

        # _backup_info 제거
        version_data.pop("_backup_info", None)

        # JSON 파일에 전체 복원
        with open(GUIDELINES_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, ensure_ascii=False, indent=2)

        # YAML 파일도 복원 (YAML 지원 시)
        if HAS_YAML:
            with open(GUIDELINES_YAML_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(version_data, f, allow_unicode=True,
                         default_flow_style=False, sort_keys=False)

        # 상태 업데이트
        acknowledge_yaml_changes()

        return True, "복원이 완료되었습니다."

    except Exception as e:
        return False, f"복원 중 오류 발생: {e}"


def get_version_diff(version_path: str) -> Dict:
    """
    현재 버전과 선택한 버전의 차이점 요약

    Args:
        version_path: 비교할 버전 파일 경로

    Returns:
        Dict: 차이점 요약
    """
    if not os.path.exists(version_path):
        return {"error": "버전 파일을 찾을 수 없습니다."}

    try:
        current = load_guidelines()

        with open(version_path, 'r', encoding='utf-8') as f:
            old_version = json.load(f)
            old_version.pop("_backup_info", None)

        diff = {
            "learned_cases": {
                "current": len(current.get("learned_cases", [])),
                "old": len(old_version.get("learned_cases", []))
            },
            "conflict_log": {
                "current": len(current.get("conflict_log", [])),
                "old": len(old_version.get("conflict_log", []))
            },
            "decision_tree_steps": {
                "current": len(current.get("master_decision_tree", {})),
                "old": len(old_version.get("master_decision_tree", {}))
            }
        }

        return diff

    except Exception as e:
        return {"error": str(e)}


def load_guidelines() -> Dict:
    """
    실무지침 파일 로드 (YAML 구조 + JSON 동적데이터 병합)

    파일 역할 분리:
    - YAML: 정적 지침 (decision tree, categories 등) - 회계담당자 수기 편집용
    - JSON: 동적 데이터 (learned_cases, conflict_log, audit_trail) - 앱 자동 관리

    Returns:
        Dict: 병합된 실무지침 데이터
    """
    result = {}

    # 1. YAML에서 정적 지침 로드 (회계담당자 편집본)
    if HAS_YAML and os.path.exists(GUIDELINES_YAML_PATH):
        try:
            with open(GUIDELINES_YAML_PATH, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f) or {}
                result.update(yaml_data)
        except Exception as e:
            print(f"YAML 로드 오류: {e}")

    # 2. JSON에서 동적 데이터 로드 (앱이 관리하는 데이터)
    if os.path.exists(GUIDELINES_JSON_PATH):
        try:
            with open(GUIDELINES_JSON_PATH, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

                # JSON에서 동적 데이터만 가져옴 (YAML이 없을 경우 전체 사용)
                if result:
                    # YAML이 있으면 동적 데이터만 병합
                    for key in ["learned_cases", "conflict_log", "audit_trail"]:
                        if key in json_data:
                            result[key] = json_data[key]
                else:
                    # YAML이 없으면 JSON 전체 사용
                    result = json_data
        except Exception as e:
            print(f"JSON 로드 오류: {e}")

    if not result:
        print(f"경고: 실무지침 파일을 찾을 수 없습니다")

    return result


def save_guidelines(guidelines: Dict, dynamic_only: bool = True) -> bool:
    """
    실무지침 저장

    기본적으로 동적 데이터(learned_cases 등)만 JSON에 저장합니다.
    YAML은 회계담당자가 수기로 관리하므로 자동 덮어쓰기하지 않습니다.

    Args:
        guidelines: 저장할 데이터
        dynamic_only: True면 동적 데이터만 JSON에 저장 (기본값)
                     False면 전체 데이터를 JSON에 저장 (YAML 백업용)

    Returns:
        bool: 성공 여부
    """
    success = True

    try:
        if dynamic_only:
            # 기존 JSON 로드 후 동적 데이터만 업데이트
            existing_json = {}
            if os.path.exists(GUIDELINES_JSON_PATH):
                with open(GUIDELINES_JSON_PATH, 'r', encoding='utf-8') as f:
                    existing_json = json.load(f)

            # 동적 데이터 업데이트
            for key in ["learned_cases", "conflict_log", "audit_trail"]:
                if key in guidelines:
                    existing_json[key] = guidelines[key]

            # 메타데이터에 동적 데이터 갱신 시간 기록
            if "_metadata" not in existing_json:
                existing_json["_metadata"] = {}
            existing_json["_metadata"]["dynamic_data_updated"] = datetime.datetime.now().isoformat()

            with open(GUIDELINES_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(existing_json, f, ensure_ascii=False, indent=2)
        else:
            # 전체 저장 (백업/내보내기 용도)
            if "_metadata" not in guidelines:
                guidelines["_metadata"] = {}
            guidelines["_metadata"]["last_updated"] = datetime.datetime.now().isoformat()

            with open(GUIDELINES_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(guidelines, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"JSON 저장 오류: {e}")
        success = False

    return success


def export_to_yaml(guidelines: Dict = None) -> bool:
    """
    실무지침을 YAML로 내보내기 (명시적 호출 시에만 실행)

    회계담당자가 직접 편집할 수 있도록 YAML 형식으로 내보냅니다.
    기존 YAML 파일이 있으면 덮어씁니다.

    Args:
        guidelines: 내보낼 데이터 (None이면 현재 로드된 데이터 사용)

    Returns:
        bool: 성공 여부
    """
    if not HAS_YAML:
        print("PyYAML이 설치되지 않아 YAML 내보내기를 할 수 없습니다.")
        return False

    if guidelines is None:
        guidelines = load_guidelines()

    try:
        with open(GUIDELINES_YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(guidelines, f, allow_unicode=True,
                     default_flow_style=False, sort_keys=False)
        print(f"YAML 내보내기 완료: {GUIDELINES_YAML_PATH}")
        return True
    except Exception as e:
        print(f"YAML 내보내기 오류: {e}")
        return False


def add_learned_case(case_data: Dict) -> bool:
    """
    신규 케이스를 learned_cases에 추가

    실무지침에 없는 새로운 분류 사례를 학습합니다.
    AI가 향후 유사한 거래에서 참고할 수 있습니다.

    Args:
        case_data: 학습할 케이스 정보
            - description: 케이스 설명
            - classification: 분류 결과
            - reasoning: 분류 근거
            - example_data: 거래 데이터 예시

    Returns:
        bool: 성공 여부
    """
    guidelines = load_guidelines()
    if not guidelines:
        return False

    # learned_cases 배열 초기화
    if "learned_cases" not in guidelines:
        guidelines["learned_cases"] = []

    # 타임스탬프 및 출처 추가
    case_data["added_date"] = datetime.datetime.now().isoformat()
    case_data["source"] = "user_classification"

    # 추가
    guidelines["learned_cases"].append(case_data)

    # 감사 추적
    _add_audit_trail(guidelines, "add_learned_case",
                     case_data.get("description", "신규 케이스"))

    return save_guidelines(guidelines)


def add_conflict_log(conflict_data: Dict) -> bool:
    """
    분류 충돌 기록

    사용자가 AI/기존 분류와 다르게 직접 입력한 경우를 기록합니다.
    반복되는 충돌은 실무지침 수정이 필요할 수 있습니다.

    Args:
        conflict_data: 충돌 정보
            - original_classification: 원래 분류
            - user_classification: 사용자가 선택한 분류
            - user_reasoning: 사용자의 분류 근거

    Returns:
        bool: 성공 여부
    """
    guidelines = load_guidelines()
    if not guidelines:
        return False

    # conflict_log 배열 초기화
    if "conflict_log" not in guidelines:
        guidelines["conflict_log"] = []

    # 타임스탬프 추가
    conflict_data["timestamp"] = datetime.datetime.now().isoformat()

    # 추가
    guidelines["conflict_log"].append(conflict_data)

    # 감사 추적
    _add_audit_trail(guidelines, "add_conflict",
                     f"{conflict_data.get('original_classification', '?')} → {conflict_data.get('user_classification', '?')}")

    return save_guidelines(guidelines)


def _add_audit_trail(guidelines: Dict, action: str, summary: str):
    """감사 추적 기록 추가 (내부 함수)"""
    if "audit_trail" not in guidelines:
        guidelines["audit_trail"] = []

    guidelines["audit_trail"].append({
        "action": action,
        "timestamp": datetime.datetime.now().isoformat(),
        "summary": summary
    })


def get_decision_tree() -> Dict:
    """의사결정 트리만 반환 (빠른 접근용)"""
    guidelines = load_guidelines()
    return guidelines.get("master_decision_tree", {})


def get_learned_cases(limit: Optional[int] = None) -> List[Dict]:
    """
    학습된 케이스 목록 반환

    Args:
        limit: 최대 개수 (None이면 전체)

    Returns:
        List[Dict]: 학습 케이스 목록
    """
    guidelines = load_guidelines()
    cases = guidelines.get("learned_cases", [])

    if limit and len(cases) > limit:
        return cases[-limit:]  # 최신 케이스 우선
    return cases


def get_conflict_log(limit: Optional[int] = None) -> List[Dict]:
    """충돌 기록 목록 반환"""
    guidelines = load_guidelines()
    conflicts = guidelines.get("conflict_log", [])

    if limit and len(conflicts) > limit:
        return conflicts[-limit:]
    return conflicts


def build_ai_prompt() -> str:
    """
    AI 시스템 프롬프트 생성

    실무지침에서 핵심 정보만 추출하여 AI에게 전달합니다.
    토큰 절약을 위해 audit_trail, conflict_log는 제외합니다.

    Returns:
        str: AI 시스템 프롬프트
    """
    guidelines = load_guidelines()

    if not guidelines:
        return _get_fallback_prompt()

    # 핵심 정보만 추출 (토큰 절약)
    essential = {
        "_metadata": guidelines.get("_metadata", {}),
        "company_profile": guidelines.get("company_profile", {}),
        "required_input_columns": guidelines.get("required_input_columns", {}),
        "classification_categories": guidelines.get("classification_categories", {}),
        "master_decision_tree": guidelines.get("master_decision_tree", {}),
        "contract_payment_check": guidelines.get("contract_payment_check", {}),
        "tax_checkpoints": guidelines.get("tax_checkpoints", {}),
        "workflow": guidelines.get("workflow", {})
    }

    # learned_cases는 최근 N개만
    learned = guidelines.get("learned_cases", [])
    if len(learned) > MAX_LEARNED_CASES_FOR_AI:
        essential["learned_cases"] = learned[-MAX_LEARNED_CASES_FOR_AI:]
        essential["_note"] = f"총 {len(learned)}개 중 최근 {MAX_LEARNED_CASES_FOR_AI}개만 표시"
    else:
        essential["learned_cases"] = learned

    prompt = f"""당신은 대한민국 회계처리 계정과목 분류 전문가 AI입니다.

아래의 '회계처리 실무지침서'를 읽고, 사용자가 제공한 거래를 분류하세요.

## 회계처리 실무지침서 (JSON)
```json
{json.dumps(essential, ensure_ascii=False, indent=2)}
```

## 분류 수행 방법
1. 'master_decision_tree'의 STEP1~STEP6을 따라가며 분류
2. 'company_profile'에서 회계 기준과 자본화 정책 확인
3. 'learned_cases'에 유사 케이스가 있으면 참고
4. 정보가 부족하면 추가 질문

## 중요 지침
- 한 번에 1-2개 질문만
- 이미 알고 있는 정보는 다시 묻지 말 것
- 분류 확정되면 즉시 최종 결과 출력

## 출력 형식 (JSON)
{{
    "status": "INCOMPLETE" | "COMPLETE",
    "message": "사용자에게 보여줄 질문 또는 설명",
    "questions": ["질문1", "질문2"],
    "final_classification": "1_유형자산(계정명)" | "2_건설중인자산" | "3_무형자산(계정명)" | "4_기타(계정명)",
    "account_code": "206",
    "reasoning": "판단 근거 (어떤 STEP을 거쳤는지)",
    "is_new_case": true | false,
    "new_case_suggestion": "실무지침에 없는 케이스면 추가할 규칙 제안"
}}
"""
    return prompt


def _get_fallback_prompt() -> str:
    """실무지침 파일이 없을 때 기본 프롬프트"""
    return """당신은 회계처리 계정과목 분류 전문가 AI입니다.
거래 내역을 분석하여 적절한 계정과목을 분류해주세요.

## 출력 형식 (JSON)
{
    "status": "INCOMPLETE" | "COMPLETE",
    "message": "질문 또는 설명",
    "questions": ["질문"],
    "final_classification": "분류결과",
    "account_code": "계정코드",
    "reasoning": "판단 근거"
}
"""


# ==========================================
# 실무지침 편집 도우미 함수들
# ==========================================

def get_guidelines_summary() -> Dict:
    """
    실무지침 요약 정보 반환 (UI 표시용)

    Returns:
        Dict: 요약 정보
    """
    guidelines = load_guidelines()

    return {
        "version": guidelines.get("_metadata", {}).get("version", "알 수 없음"),
        "last_updated": guidelines.get("_metadata", {}).get("last_updated", "알 수 없음"),
        "company": guidelines.get("company_profile", {}).get("accounting_standard", "알 수 없음"),
        "decision_tree_steps": len(guidelines.get("master_decision_tree", {})),
        "learned_cases_count": len(guidelines.get("learned_cases", [])),
        "conflict_log_count": len(guidelines.get("conflict_log", [])),
        "audit_trail_count": len(guidelines.get("audit_trail", []))
    }


def update_decision_tree_step(step_id: str, step_data: Dict) -> bool:
    """
    의사결정 트리의 특정 단계 수정

    Args:
        step_id: 단계 ID (예: "STEP1_IP체크")
        step_data: 수정할 데이터

    Returns:
        bool: 성공 여부
    """
    guidelines = load_guidelines()
    if not guidelines:
        return False

    if "master_decision_tree" not in guidelines:
        guidelines["master_decision_tree"] = {}

    guidelines["master_decision_tree"][step_id] = step_data

    _add_audit_trail(guidelines, "update_decision_tree", f"수정: {step_id}")

    return save_guidelines(guidelines)


def delete_learned_case(index: int) -> bool:
    """학습 케이스 삭제"""
    guidelines = load_guidelines()
    if not guidelines:
        return False

    cases = guidelines.get("learned_cases", [])
    if 0 <= index < len(cases):
        deleted = cases.pop(index)
        _add_audit_trail(guidelines, "delete_learned_case",
                        deleted.get("description", f"인덱스 {index}"))
        return save_guidelines(guidelines)

    return False
