# -*- coding: utf-8 -*-
"""
ai_enrich.py (v2)
- 전면 재설계: 필드별 신뢰도 기반 패치, 카테고리 후보 강제 선택, 날짜/금액 정규화.
- 기존 app_main.App._ai_enrich_selected_worker 와의 인터페이스 호환 유지(enrich_selected_item).
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import os, re, json, math
import httpx
from openai import OpenAI

DEFAULT_MODEL = "gpt-5-mini"
FIELD_CONF_FALLBACK = 0.80   # 필드별 confidence 누락 시 기본값
OVERALL_CONF_FALLBACK = 0.90 # overall 누락 시 기본값
PROTECTED_KEYS: Tuple[str, ...] = ("문서번호", "증빙번호", "세금계산서 번호", "전표번호", "청구번호")

# ────────────────────────── 값 정규화 ──────────────────────────
def _is_money_field(field_name: str) -> bool:
    return ("가격" in field_name) or ("금액" in field_name)

def _is_date_field(field_name: str) -> bool:
    # '일'이 들어가는 한글 필드(구매일/지급일/렌탈 시작일/종료일 등)를 날짜로 간주
    return "일" in field_name

def _norm_money(x: Any) -> Any:
    if x in (None, "", " "): return x
    s = re.sub(r"[^\d\-]", "", str(x))
    try: return str(int(s))
    except Exception: return s

def _norm_date(s: Any) -> Any:
    if s in (None, "", " "): return s
    t = str(s).strip().replace(".", "-").replace("/", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
    if m:
        y, mo, d = m.groups()
        try: return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except Exception: return t
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", t)
    if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return t

def _sanitize_values(values: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in (values or {}).items():
        if _is_date_field(k): v = _norm_date(v)
        if _is_money_field(k): v = _norm_money(v)
        out[k] = v
    return out

def _norm_text(s: Any) -> str:
    if s is None: return ""
    t = str(s)
    t = t.replace("–", "-").replace("—", "-")
    t = t.replace("\u00A0", " ").replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def _alias_header(h: str) -> str:
    aliases = {"카테고리": "카테고리 (필수)", "모델": "모델 (필수)"}
    return aliases.get(h, h)

# ────────────────────────── 프롬프트 구성 ──────────────────────────
SYSTEM_RULES = (
    "You are a precise data enricher for a Korean asset register.\n"
    "- Output ONLY JSON (no code fences, no prose).\n"
    "- Contract:\n"
    "  {\n"
    "    \"values\": {<header>: <value>},\n"
    "    \"confidences\": {<header>: <0..1>},\n"
    "    \"confidence\": <0..1>,\n"
    "    \"reasons\": {<header>: <why>}\n"
    "  }\n"
    "- Only use headers from the provided allowed_headers.\n"
    "- Category MUST be chosen from category_candidates EXACTLY; if unsure, return empty and lower confidence.\n"
    "- Do not fabricate dates or prices; prefer existing context.\n"
    "- Keep Korean concise.\n"
)

def _prepare_prompt(
    allowed_headers: List[str],
    required_headers: List[str],
    current_values: Dict[str, Any],
    ap_aggregate: Dict[str, Any],
    assets_context: Dict[str, Any],
    category_candidates: List[str],
) -> str:
    payload = {
        "allowed_headers": list(allowed_headers or []),
        "required_headers": list(required_headers or []),
        "category_candidates": list(category_candidates or []),
        "inputs": {
            "current_values": current_values or {},
            "ap": ap_aggregate or {},
            "context": {
                "top_values": (assets_context or {}).get("top_values", {}),
                "examples": (assets_context or {}).get("examples", []),
            },
        },
        "filling_guidance": [
            "카테고리 (필수): category_candidates 중에서만 선택",
            "모델 (필수): AP 품목/비고에서 실체 모델/제품명 추출(일반명사/문서명 제외)",
            "세부제품명: 모델 보조 설명(있으면)",
            "브랜드, 구매처, 결재수단, 위치, 자산상태 (필수), 소유 유형: context.top_values와 AP 정보를 참고",
            "구매일/지급일: AP 날짜 사용, YYYY-MM-DD",
            "금액/가격 필드: 숫자만",
        ]
    }
    return json.dumps(payload, ensure_ascii=False)

# ────────────────────────── OpenAI 호출 ──────────────────────────
def _chat_call(client: OpenAI, model: str, messages: list[dict], max_completion_tokens: int):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        max_completion_tokens=max_completion_tokens,
    )

def _safe_json_loads(s: str) -> Dict[str, Any]:
    try: return json.loads(s or "{}")
    except Exception: return {}

# ────────────────────────── 패치 로직 ──────────────────────────
def _match_category(suggested: str, candidates: List[str]) -> Tuple[bool, str, str]:
    sug = _norm_text(suggested)
    table = {_norm_text(c): c for c in (candidates or [])}
    return (sug in table), sug, table.get(sug, "")

def _apply_patch(
    base_values: Dict[str, Any],
    ai_values: Dict[str, Any],
    field_conf: Dict[str, float],
    threshold: float,
    allow_overwrite: bool,
    category_candidates: List[str],
    required_headers: List[str],
) -> Dict[str, Any]:
    out = dict(base_values or {})
    apply_log: Dict[str, Dict[str, Any]] = {}
    reasons_count = {
        "APPLIED": 0, "FILL": 0, "OVERWRITE": 0,
        "SKIP_BELOW_THRESHOLD": 0, "SKIP_PROTECTED": 0, "SKIP_EMPTY": 0,
        "SKIP_NOT_IN_CANDIDATES": 0, "SKIP_NO_OVERWRITE": 0
    }

    # 카테고리 후보 강제 일치
    cat_suggested = ai_values.get("카테고리 (필수)", "")
    cat_ok, cat_norm, cat_match_val = _match_category(cat_suggested, category_candidates)
    if cat_ok:
        ai_values["카테고리 (필수)"] = cat_match_val

    for k, v in _sanitize_values({_alias_header(k): v for k, v in ai_values.items()}).items():
        if k in PROTECTED_KEYS:
            apply_log[k] = {"action": "SKIP", "reason": "SKIP_PROTECTED", "suggested": v}
            reasons_count["SKIP_PROTECTED"] += 1
            continue

        if k == "카테고리 (필수)" and not cat_ok:
            apply_log[k] = {"action": "SKIP", "reason": "SKIP_NOT_IN_CANDIDATES", "suggested": v}
            reasons_count["SKIP_NOT_IN_CANDIDATES"] += 1
            continue

        if v in (None, "", " "):
            apply_log[k] = {"action": "SKIP", "reason": "SKIP_EMPTY", "suggested": v}
            reasons_count["SKIP_EMPTY"] += 1
            continue

        conf = float(field_conf.get(k, FIELD_CONF_FALLBACK))
        if conf < float(threshold):
            apply_log[k] = {"action": "SKIP", "reason": "SKIP_BELOW_THRESHOLD", "conf": conf, "suggested": v}
            reasons_count["SKIP_BELOW_THRESHOLD"] += 1
            continue

        cur = out.get(k)
        if (cur in (None, "", " ")) or allow_overwrite:
            out[k] = v
            mode = "FILL" if (cur in (None, "", " ")) else "OVERWRITE"
            apply_log[k] = {"action": "APPLIED", "mode": mode, "conf": conf, "value": v}
            reasons_count["APPLIED"] += 1; reasons_count[mode] += 1
        else:
            apply_log[k] = {"action": "SKIP", "reason": "SKIP_NO_OVERWRITE", "conf": conf, "suggested": v}
            reasons_count["SKIP_NO_OVERWRITE"] += 1

    # 필수 헤더 트림
    for h in (required_headers or []):
        out[h] = str(out.get(h, "") or "").strip()

    return {
        "merged": out,
        "apply_log": apply_log,
        "reasons_count": reasons_count,
        "category_diag": {
            "suggested": cat_suggested,
            "normalized": cat_norm,
            "matched": cat_ok,
            "matched_value": cat_match_val
        }
    }

# ────────────────────────── 퍼블릭 API ──────────────────────────
def enrich_selected_item(
    *,
    api_key: Optional[str],
    model: str,
    current_values: Dict[str, Any],
    ap_aggregate: Dict[str, Any],
    assets_context: Dict[str, Any],
    category_candidates: List[str],
    required_headers: List[str],
    threshold: float,
    allow_overwrite: bool,
    timeout_s: float = 30.0,
    log_prompt: bool = False
) -> Dict[str, Any]:

    allowed_headers = list(current_values.keys())  # 화면에 표시/업로드 대상 컬럼 집합

    prompt = _prepare_prompt(
        allowed_headers=allowed_headers,
        required_headers=required_headers,
        current_values=current_values,
        ap_aggregate=ap_aggregate,
        assets_context=assets_context,
        category_candidates=category_candidates,
    )

    client = OpenAI(api_key=(api_key or os.getenv("OPENAI_API_KEY", "")), timeout=httpx.Timeout(timeout_s))
    messages = [
        {"role": "system", "content": SYSTEM_RULES},
        {"role": "user", "content": "다음 입력을 바탕으로 자산행을 보강하세요. 반드시 JSON만 출력합니다.\n" + prompt},
    ]

    used_model = model or DEFAULT_MODEL
    try:
        rsp = _chat_call(client, used_model, messages, max_completion_tokens=900)
    except Exception as e:
        # 단순 재시도(1회) — 동일 모델
        rsp = _chat_call(client, used_model, messages, max_completion_tokens=900)

    raw_text = (rsp.choices[0].message.content or "").strip()
    parsed = _safe_json_loads(raw_text)

    ai_values_raw = parsed.get("values", {}) if isinstance(parsed.get("values"), dict) else {}
    field_conf = parsed.get("confidences", {}) if isinstance(parsed.get("confidences"), dict) else {}
    overall_conf = parsed.get("confidence")
    try:
        overall_conf = float(overall_conf) if overall_conf is not None else None
    except Exception:
        overall_conf = None
    if overall_conf is None:
        # 필드별 평균으로 산출, 없으면 상수
        vals = [float(v) for v in field_conf.values() if isinstance(v, (int, float))]
        overall_conf = (sum(vals)/len(vals)) if vals else OVERALL_CONF_FALLBACK

    patch = _apply_patch(
        base_values=current_values,
        ai_values=ai_values_raw,
        field_conf=field_conf,
        threshold=threshold,
        allow_overwrite=allow_overwrite,
        category_candidates=category_candidates,
        required_headers=required_headers,
    )

    missing_required = [h for h in required_headers if not str(patch["merged"].get(h, "")).strip()]

    return {
        "values": patch["merged"],
        "confidence": overall_conf,
        "missing_required": missing_required,
        "_trace_id": getattr(rsp, "id", "-"),
        "_used_model": used_model,
        "diag": {
            "apply_log": patch["apply_log"],
            "reasons_count": patch["reasons_count"],
            "category": patch["category_diag"],
            "ai_values_raw": ai_values_raw,
            "raw_output_len": len(raw_text),
        },
    }
