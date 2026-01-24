"""
Debug Logger for AI Infinite Chat Backend

디버깅용 상세 로그 유틸리티
서비스 안정화 후 삭제 예정
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps
import traceback

# 디버그 로거 설정
debug_logger = logging.getLogger("debug")
debug_logger.setLevel(logging.DEBUG)

# 콘솔 핸들러 (색상 지원)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# 포맷터
formatter = logging.Formatter(
    '\033[36m[%(asctime)s.%(msecs)03d]\033[0m '
    '\033[1m[%(levelname)s]\033[0m '
    '\033[33m[%(category)s]\033[0m '
    '%(message)s',
    datefmt='%H:%M:%S'
)
console_handler.setFormatter(formatter)
debug_logger.addHandler(console_handler)

# 로그 히스토리 (최근 N개 유지)
log_history = []
MAX_LOG_HISTORY = 1000


def _safe_serialize(obj: Any) -> Any:
    """객체를 안전하게 직렬화"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj[:10]]  # 최대 10개
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in list(obj.items())[:20]}  # 최대 20개 키
    return str(obj)[:200]  # 문자열로 변환, 최대 200자


def _add_to_history(entry: Dict):
    """로그 히스토리에 추가"""
    log_history.append(entry)
    if len(log_history) > MAX_LOG_HISTORY:
        log_history.pop(0)


def log_action(session_id: str, action: str, details: Dict = None):
    """
    사용자/시스템 액션 로그

    Args:
        session_id: 세션 ID
        action: 액션 이름
        details: 상세 정보
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "ACTION",
        "session_id": session_id[:8] if session_id else "N/A",
        "action": action,
        "details": _safe_serialize(details)
    }
    _add_to_history(entry)

    details_str = json.dumps(entry["details"], ensure_ascii=False) if details else ""
    debug_logger.info(
        f"{action} | session={entry['session_id']} | {details_str}",
        extra={"category": "ACTION"}
    )


def log_ws_recv(session_id: str, message_type: str, payload: Dict = None):
    """
    WebSocket 수신 로그

    Args:
        session_id: 세션 ID
        message_type: 메시지 타입
        payload: 수신 데이터
    """
    # 민감한 정보 필터링
    filtered_payload = None
    if payload:
        filtered_payload = {k: v for k, v in payload.items() if k not in ['existing_messages', 'file_ids']}
        if 'existing_messages' in payload:
            filtered_payload['existing_messages_count'] = len(payload.get('existing_messages', []))
        if 'existing_agents' in payload:
            filtered_payload['existing_agents'] = [
                {"name": a.get("name"), "model": a.get("model")}
                for a in payload.get('existing_agents', [])
            ]

    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "WS_RECV",
        "session_id": session_id[:8] if session_id else "N/A",
        "message_type": message_type,
        "payload": _safe_serialize(filtered_payload)
    }
    _add_to_history(entry)

    payload_str = json.dumps(entry["payload"], ensure_ascii=False) if filtered_payload else ""
    debug_logger.info(
        f"RECV {message_type} | session={entry['session_id']} | {payload_str}",
        extra={"category": "WS_RECV"}
    )


def log_ws_send(session_id: str, message_type: str, payload: Dict = None):
    """
    WebSocket 전송 로그

    Args:
        session_id: 세션 ID
        message_type: 메시지 타입
        payload: 전송 데이터
    """
    # 긴 내용 축약
    filtered_payload = None
    if payload:
        filtered_payload = {}
        for k, v in payload.items():
            if k == 'content' and isinstance(v, str) and len(v) > 100:
                filtered_payload[k] = v[:100] + f"... ({len(v)} chars)"
            elif k == 'data' and isinstance(v, dict):
                filtered_payload[k] = {sk: sv for sk, sv in list(v.items())[:5]}
            else:
                filtered_payload[k] = v

    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "WS_SEND",
        "session_id": session_id[:8] if session_id else "N/A",
        "message_type": message_type,
        "payload": _safe_serialize(filtered_payload)
    }
    _add_to_history(entry)

    # token 메시지는 너무 많으므로 DEBUG 레벨
    if message_type == 'token':
        debug_logger.debug(
            f"SEND {message_type} | session={entry['session_id']}",
            extra={"category": "WS_SEND"}
        )
    else:
        payload_str = json.dumps(entry["payload"], ensure_ascii=False) if filtered_payload else ""
        debug_logger.info(
            f"SEND {message_type} | session={entry['session_id']} | {payload_str}",
            extra={"category": "WS_SEND"}
        )


def log_state_change(session_id: str, state_name: str, old_value: Any, new_value: Any, reason: str = ""):
    """
    상태 변화 로그

    Args:
        session_id: 세션 ID
        state_name: 상태 이름
        old_value: 이전 값
        new_value: 새 값
        reason: 변경 이유
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "STATE",
        "session_id": session_id[:8] if session_id else "N/A",
        "state_name": state_name,
        "old_value": _safe_serialize(old_value),
        "new_value": _safe_serialize(new_value),
        "reason": reason
    }
    _add_to_history(entry)

    reason_str = f" ({reason})" if reason else ""
    debug_logger.info(
        f"{state_name}: {old_value} -> {new_value}{reason_str} | session={entry['session_id']}",
        extra={"category": "STATE"}
    )


def log_agent(session_id: str, event: str, agent_info: Dict = None):
    """
    에이전트 관련 로그

    Args:
        session_id: 세션 ID
        event: 이벤트 (START, COMPLETE, ERROR 등)
        agent_info: 에이전트 정보
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "AGENT",
        "session_id": session_id[:8] if session_id else "N/A",
        "event": event,
        "agent_info": _safe_serialize(agent_info)
    }
    _add_to_history(entry)

    agent_str = json.dumps(entry["agent_info"], ensure_ascii=False) if agent_info else ""
    debug_logger.info(
        f"{event} | session={entry['session_id']} | {agent_str}",
        extra={"category": "AGENT"}
    )


def log_error(session_id: str, error_type: str, message: str, context: Dict = None):
    """
    에러 로그

    Args:
        session_id: 세션 ID
        error_type: 에러 유형
        message: 에러 메시지
        context: 추가 컨텍스트
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "ERROR",
        "session_id": session_id[:8] if session_id else "N/A",
        "error_type": error_type,
        "message": message,
        "context": _safe_serialize(context),
        "traceback": traceback.format_exc() if context and context.get("include_traceback") else None
    }
    _add_to_history(entry)

    context_str = json.dumps(entry["context"], ensure_ascii=False) if context else ""
    debug_logger.error(
        f"{error_type}: {message} | session={entry['session_id']} | {context_str}",
        extra={"category": "ERROR"}
    )


def log_system(session_id: str, event: str, details: Dict = None):
    """
    시스템 이벤트 로그

    Args:
        session_id: 세션 ID
        event: 이벤트 이름
        details: 상세 정보
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": "SYSTEM",
        "session_id": session_id[:8] if session_id else "N/A",
        "event": event,
        "details": _safe_serialize(details)
    }
    _add_to_history(entry)

    details_str = json.dumps(entry["details"], ensure_ascii=False) if details else ""
    debug_logger.info(
        f"{event} | session={entry['session_id']} | {details_str}",
        extra={"category": "SYSTEM"}
    )


def get_log_history(session_id: Optional[str] = None, category: Optional[str] = None, limit: int = 100):
    """
    로그 히스토리 반환

    Args:
        session_id: 특정 세션만 필터 (선택)
        category: 특정 카테고리만 필터 (선택)
        limit: 최대 개수
    """
    filtered = log_history

    if session_id:
        filtered = [e for e in filtered if e.get("session_id", "").startswith(session_id[:8])]

    if category:
        filtered = [e for e in filtered if e.get("category") == category]

    return filtered[-limit:]


def export_logs_json():
    """로그를 JSON 문자열로 내보내기"""
    return json.dumps(log_history, ensure_ascii=False, indent=2)


def clear_logs():
    """로그 히스토리 초기화"""
    log_history.clear()
    debug_logger.info("Log history cleared", extra={"category": "SYSTEM"})
