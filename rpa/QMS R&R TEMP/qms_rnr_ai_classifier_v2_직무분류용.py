# -*- coding: utf-8 -*-
"""
[라덱셀 QMS R&R AI 자동 배정 시스템 - Iterative Refinement Edition]
작성일: 2026.01.13
버전: 6.0 (반복 개선 방식)

[핵심 로직]
1. 기존 결과 파일(QMS_RnR_최종결과_v5.xlsx)을 입력으로 사용
2. AI가 현재 배정 결과를 검토하고 문제점 분석
3. 수정이 필요한 항목만 업데이트
4. 수정된 항목 수 출력
5. 수정이 0건이 될 때까지 수동으로 반복 실행

[실행 전 필요사항]
1. pip install pandas openpyxl google-genai openai python-dotenv pypdf
2. .env 파일에 API 키 설정:
   - Gemini 사용시: GEMINI_API_KEY
   - GPT-5 사용시: OPENAI_API_KEY
"""

import os
import json
import re
from pathlib import Path

import pandas as pd
from google import genai
from openai import OpenAI
from dotenv import load_dotenv

# ============================================================================
# [Section 1] 설정 및 상수
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()

# 사용 가능한 모델 설정
AVAILABLE_MODELS = {
    "1": {
        "name": "gemini-3-pro-preview",
        "provider": "gemini",
        "display": "Gemini 3 Pro Preview"
    },
    "2": {
        "name": "gemini-3-flash-preview",
        "provider": "gemini",
        "display": "Gemini 3 Flash Preview"
    },
    "3": {
        "name": "gpt-5.2",
        "provider": "openai",
        "display": "GPT-5.2"
    },
    "4": {
        "name": "gpt-5-mini",
        "provider": "openai",
        "display": "GPT-5-mini"
    }
}
DEFAULT_MODEL = "2"  # 기본값: Gemini

FILE_CONFIG = {
    "TARGET_FILE": "QMS_RnR_최종결과_v5.xlsx",  # 입력 겸 출력 파일
    "INPUT_JD": "전사 JD 종합.xlsx",
    "INPUT_ROLES": "각 구성원별 기존 역할.csv",
    "INPUT_COMPANY": "라덱셀 정보.txt",
    "INPUT_IR": "RADEXEL_IR_251222_1 (1).pdf",
}


# ============================================================================
# [Section 2] 데이터 로더
# ============================================================================

def load_jd_dictionary(jd_path: Path) -> str:
    """JD 엑셀을 읽어 직무 분류 체계를 텍스트로 변환"""
    print(f"[Loader] JD 직무 사전 로드 중: {jd_path.name}")

    try:
        df = pd.read_excel(jd_path, sheet_name='전체 직무기술서 종합', engine='openpyxl')
        df = df.fillna('')

        job_dict = {}
        for _, row in df.iterrows():
            category_main = str(row.get('대분류', '')).strip()
            category_sub = str(row.get('중분류', '')).strip()
            task_name = str(row.get('능력단위명칭', '')).strip()
            task_detail = str(row.get('능력단위요소', '')).strip()

            if not category_main or category_main == 'nan':
                continue

            key = f"{category_main} > {category_sub}"
            if key not in job_dict:
                job_dict[key] = []

            task_desc = f"{task_name}"
            if task_detail:
                task_desc += f"({task_detail})"

            if task_desc not in job_dict[key]:
                job_dict[key].append(task_desc)

        lines = ["## [직무 사전] 업무 분류 체계", ""]
        for category, tasks in job_dict.items():
            task_list_str = ", ".join(tasks[:10])
            if len(tasks) > 10:
                task_list_str += " 등..."
            lines.append(f"### {category}")
            lines.append(f"- 포함 업무: {task_list_str}")
            lines.append("")

        print(f"[Loader] JD 사전: {len(job_dict)}개 카테고리 로드 완료")
        return "\n".join(lines)

    except Exception as e:
        print(f"[Warning] JD 파일 로드 실패: {e}")
        return ""


def load_team_roles(csv_path: Path) -> str:
    """팀원 역할 정보 로드"""
    print(f"[Loader] 팀원 역할 로드 중: {csv_path.name}")
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        lines = ["## [인력 풀] 팀원 및 담당 역할", ""]

        for _, row in df.iterrows():
            team = row.iloc[0]
            person = row.iloc[1]
            role_desc = row.iloc[2]
            lines.append(f"- **{person}** ({team}): {role_desc}")

        print(f"[Loader] 팀원 역할: {len(df)}명 로드 완료")
        return "\n".join(lines)
    except Exception as e:
        print(f"[Warning] 팀 역할 파일 로드 실패: {e}")
        return ""


def load_txt_context(path: Path) -> str:
    """텍스트 파일 로드"""
    print(f"[Loader] 텍스트 파일 로드 중: {path.name}")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"[Loader] 텍스트 파일 로드 완료: {len(content)}자")
        return content
    except Exception as e:
        print(f"[Warning] 텍스트 파일 로드 실패: {e}")
        return ""


def load_pdf_text(path: Path) -> str:
    """PDF 파일에서 텍스트 추출"""
    print(f"[Loader] PDF 파일 로드 중: {path.name}")
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        text = "\n".join([p.extract_text() or "" for p in reader.pages])[:15000]
        print(f"[Loader] PDF 로드 완료: {len(text)}자")
        return text
    except Exception as e:
        print(f"[Warning] PDF 로드 실패: {e}")
        return ""


def load_result_excel(path: Path) -> pd.DataFrame:
    """결과 엑셀 파일 로드"""
    print(f"[Loader] 결과 엑셀 로드 중: {path.name}")
    df = pd.read_excel(path, engine='openpyxl')
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df = df.fillna('')
    print(f"[Loader] 결과 엑셀 로드 완료: {len(df)}행")
    return df


def current_result_to_text(df: pd.DataFrame) -> str:
    """현재 결과를 AI가 검토할 수 있는 텍스트로 변환"""
    lines = ["## [현재 배정 결과] 검토 대상", ""]

    for idx, row in df.iterrows():
        job_name = str(row.get('QMS 직무', '')).strip()
        desc = str(row.get('설명', '')).strip()
        now_team = str(row.get('현재 담당팀', '')).strip()
        now_person = str(row.get('현재 담당자', '')).strip()
        now_reason = str(row.get('현재 배정 이유', '')).strip()
        future_team = str(row.get('미래 담당팀', '')).strip()
        future_person = str(row.get('미래 담당자/직책', '')).strip()
        future_reason = str(row.get('미래 배정 이유', '')).strip()

        # 빈 값 표시 (AI가 인지하도록)
        if not future_team:
            future_team = "(비어있음)"
        if not future_person:
            future_person = "(비어있음)"
        if not future_reason:
            future_reason = "(비어있음)"

        lines.append(f"[{idx}] 직무: {job_name}")
        if desc:
            lines.append(f"    설명: {desc}")
        lines.append(f"    현재 배정: {now_team} / {now_person}")
        lines.append(f"    현재 이유: {now_reason}")
        lines.append(f"    미래 배정: {future_team} / {future_person}")
        lines.append(f"    미래 이유: {future_reason}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# [Section 3] AI 검토 및 수정
# ============================================================================

def call_gemini_review(client, model_name: str, prompt: str) -> list:
    """Gemini API 호출하여 검토 결과를 받음"""
    print(f"\n[AI] Gemini API 호출 중... (모델: {model_name})")

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={
                "temperature": 0.1,
                "max_output_tokens": 30000,
                "response_mime_type": "application/json",
                "safety_settings": [
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}
                ]
            }
        )

        text = response.text
        if text is None:
            print("[AI] 응답이 비어있습니다. (안전 필터 또는 API 오류)")
            # 차단 사유 확인
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                print(f"[AI] 차단 사유: {response.prompt_feedback}")
            return []

        print(f"[AI] 응답 수신 완료: {len(text)}자")

        # JSON 배열 추출
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            print(f"[AI] JSON 파싱 완료: {len(result)}건 수정 제안")
            return result
        else:
            print("[AI] JSON 배열을 찾을 수 없음 (수정 없음으로 처리)")
            return []

    except Exception as e:
        print(f"[AI Error] {e}")
        return []


def call_openai_review(client, model_name: str, prompt: str) -> list:
    """OpenAI API 호출하여 검토 결과를 받음"""
    print(f"\n[AI] OpenAI API 호출 중... (모델: {model_name})")

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 조직관리 전문가입니다. 요청에 따라 JSON 형식으로 응답하세요."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=30000,
            response_format={"type": "json_object"}
        )

        # [DEBUG] 전체 응답 객체 정보
        print(f"[DEBUG] response.choices 개수: {len(response.choices)}")
        print(f"[DEBUG] finish_reason: {response.choices[0].finish_reason}")

        text = response.choices[0].message.content

        # [DEBUG] 응답 텍스트 확인
        if text is None:
            print("[DEBUG] text가 None입니다!")
            return []

        print(f"[AI] 응답 수신 완료: {len(text)}자")
        print(f"[DEBUG] 응답 원본 (처음 500자):\n{text[:500]}")
        if len(text) > 500:
            print(f"[DEBUG] 응답 원본 (마지막 200자):\n...{text[-200:]}")

        # JSON 파싱 시도
        try:
            parsed = json.loads(text)
            print(f"[DEBUG] JSON 파싱 성공, 타입: {type(parsed).__name__}")

            # 응답이 바로 배열인 경우
            if isinstance(parsed, list):
                print(f"[AI] JSON 파싱 완료: {len(parsed)}건 수정 제안")
                return parsed

            # 응답이 객체인 경우 - 배열 필드 찾기
            if isinstance(parsed, dict):
                print(f"[DEBUG] 객체 키 목록: {list(parsed.keys())}")

                # 일반적인 키 이름들 확인
                for key in ['corrections', 'fixes', 'results', 'data', 'items']:
                    if key in parsed and isinstance(parsed[key], list):
                        result = parsed[key]
                        print(f"[AI] JSON 파싱 완료: {len(result)}건 수정 제안 (키: {key})")
                        if len(result) > 0:
                            print(f"[DEBUG] 첫 번째 항목: {result[0]}")
                        return result

                # 첫 번째로 발견되는 배열 반환
                for key, value in parsed.items():
                    if isinstance(value, list):
                        print(f"[AI] JSON 파싱 완료: {len(value)}건 수정 제안 (키: {key})")
                        if len(value) > 0:
                            print(f"[DEBUG] 첫 번째 항목: {value[0]}")
                        return value

                # 객체가 직접 수정 항목인 경우 (idx 키가 있으면 단일 수정 항목으로 간주)
                if 'idx' in parsed:
                    print(f"[AI] 단일 수정 항목 감지, 배열로 변환")
                    return [parsed]

                # 배열이 없는 경우 전체 객체 출력
                print(f"[DEBUG] 배열 필드 없음. 전체 객체:\n{json.dumps(parsed, ensure_ascii=False, indent=2)[:1000]}")

            print("[AI] JSON에서 배열을 찾을 수 없음 (수정 없음으로 처리)")
            return []

        except json.JSONDecodeError as e:
            print(f"[AI] JSON 파싱 오류: {e}")
            print(f"[DEBUG] 파싱 실패한 텍스트:\n{text[:1000]}")
            return []

    except Exception as e:
        print(f"[AI Error] {e}")
        import traceback
        print(f"[DEBUG] 상세 오류:\n{traceback.format_exc()}")
        return []


def call_ai_review(client, model_config: dict, prompt: str) -> list:
    """모델 설정에 따라 적절한 AI API 호출"""
    provider = model_config["provider"]
    model_name = model_config["name"]

    if provider == "gemini":
        return call_gemini_review(client, model_name, prompt)
    elif provider == "openai":
        return call_openai_review(client, model_name, prompt)
    else:
        print(f"[Error] 지원하지 않는 provider: {provider}")
        return []


def run_review_and_fix(client, model_config: dict, df: pd.DataFrame, context: dict) -> tuple:
    """현재 결과를 검토하고 수정"""

    current_text = current_result_to_text(df)

    prompt = f"""당신은 100명 규모로 성장을 목표로 하는 의료기기 스타트업 '라덱셀'의 QMS(품질경영시스템) 조직 설계 최고 전문가입니다.

    우리의 목표는 현재의 스타트업 단계(한정된 인원, 1인 다역)에서 출발하여, 향후 100명 규모의 전문 의료기기 회사(ISO 13485 준수, 체계적 분업)로 나아가는 로드맵을 수립하는 것입니다.

    아래 [현재 배정 결과]는 초안일 뿐이며, 논리적 허점이나 비효율적인 부분이 많을 수 있습니다.
    당신은 이 데이터를 **'첨삭'하는 수준을 넘어, '최적화(Optimization)'** 해야 합니다.

    # ========== 참고자료 ==========

    {context['jd']}

    {context['roles']}

    ## [회사 정보]
    {context['info']}

    ## [IR 자료]
    {context['ir']}

    # ========== 현재 배정 결과 (검토 대상) ==========

    {current_text}

    # ========== 작업 지시사항 (Priority High) ==========

    위 [현재 배정 결과]를 전체적으로 조망하며, 다음 기준에 따라 기존 내용을 **과감하게 수정**하거나 보완하세요.

    1. **[미래 시점] 100명 규모 조직 관점에서의 재설계**:
       - 이미 '미래 담당팀/담당자'가 채워져 있더라도, 그것이 **100명 규모의 의료기기 회사 조직도**에 비추어 부적절하다면 수정하세요.
       - 예: 미래에도 개발팀이 QA 감사를 한다고 되어 있다면 -> 독립된 '품질보증팀(QA)'으로 수정.
       - 미래의 직무는 전문화/세분화되어야 합니다.

    2. **[현재 시점] 스타트업 현실 반영 및 최적화**:
       - 현재 담당자가 지정되어 있더라도, 인력 풀(roles)의 역량과 실제 역할을 고려할 때 **더 적합한 인원**이 있다면 변경하세요.
       - 한 사람이 감당하기 어려운 논리적 모순(예: 개발자가 본인 코드를 검증하는 역할 등 이해상충)이 있다면 반드시 역할을 분리하거나 조정하세요.

    3. **[적극적 수정] 빈칸 채우기 그 이상**:
       - 빈칸은 당연히 채워야 합니다.
       - **중요:** 빈칸이 아니더라도, 당신의 전문가적 식견으로 보기에 **"더 나은 R&R 배정 논리"**가 있다면 기존 텍스트를 지우고 새로운 안을 제시하세요.
       - 설명이 부실하거나("그냥 담당임"), 논리가 빈약한 경우에도 구체적인 근거(ISO 규격, JD 기반)를 들어 수정하세요.

    # ========== 출력 형식 (JSON) ==========

    **수정이 필요한 항목(기존 내용을 더 나은 내용으로 덮어쓰는 경우 포함)**을 아래 형식의 JSON 배열로 출력하세요.
    수정할 사항이 없다면 빈 배열 `[]`을 출력하되, 정말로 개선의 여지가 없는지 치열하게 고민하십시오.

    [
      {{
        "idx": 수정할_행_인덱스(숫자),
        "problem": "수정 사유 (예: 현재 배정된 인원은 해당 업무 전문성이 부족하여 변경함, 또는 미래 조직 규모에 맞지 않는 팀 배정임)",
        "now_team": "최적화된 현재 소속팀",
        "now_person": "최적화된 현재 담당자",
        "now_reason": "수정된 현재 배정 논리",
        "future_team": "100명 규모 시점의 담당팀",
        "future_person": "100명 규모 시점의 직책/담당자",
        "future_reason": "성장 로드맵에 따른 배정 근거"
      }}
    ]

    주의: JSON 형식을 엄격히 지키세요. 마크다운 없이 JSON 데이터만 출력해도 좋습니다.
    """

    results = call_ai_review(client, model_config, prompt)

    # 수정 적용
    modified_count = 0
    modified_indices = []

    for fix in results:
        idx = fix.get('idx')
        if idx is None:
            continue

        # idx를 정수로 변환
        try:
            idx = int(idx)
        except (ValueError, TypeError):
            continue

        if idx >= len(df):
            continue

        problem = fix.get('problem', '')
        print(f"  [수정 {idx}] {problem}")

        # 값 업데이트 (값이 있을 때만)
        if fix.get('now_team'):
            df.at[idx, '현재 담당팀'] = fix['now_team']
        if fix.get('now_person'):
            df.at[idx, '현재 담당자'] = fix['now_person']
        if fix.get('now_reason'):
            df.at[idx, '현재 배정 이유'] = fix['now_reason']
        if fix.get('future_team'):
            df.at[idx, '미래 담당팀'] = fix['future_team']
        if fix.get('future_person'):
            df.at[idx, '미래 담당자/직책'] = fix['future_person']
        if fix.get('future_reason'):
            df.at[idx, '미래 배정 이유'] = fix['future_reason']

        modified_count += 1
        modified_indices.append(idx)

    return df, modified_count, modified_indices


# ============================================================================
# [Section 4] 메인 실행
# ============================================================================

def select_model() -> dict:
    """사용자에게 모델 선택 메뉴 표시"""
    print("\n[모델 선택]")
    print("-" * 30)
    for key, model in AVAILABLE_MODELS.items():
        default_mark = " (기본값)" if key == DEFAULT_MODEL else ""
        print(f"  {key}. {model['display']}{default_mark}")
    print("-" * 30)

    while True:
        choice = input(f"사용할 모델 번호를 입력하세요 [{DEFAULT_MODEL}]: ").strip()
        if not choice:
            choice = DEFAULT_MODEL
        if choice in AVAILABLE_MODELS:
            selected = AVAILABLE_MODELS[choice]
            print(f"[선택됨] {selected['display']}")
            return selected
        print(f"[경고] 잘못된 선택입니다. {', '.join(AVAILABLE_MODELS.keys())} 중 선택하세요.")


def main():
    print("=" * 70)
    print("라덱셀 QMS 자동 배정 시스템 (Iterative Refinement Ver.)")
    print("=" * 70)

    # 1. 모델 선택
    model_config = select_model()
    provider = model_config["provider"]

    print(f"\n사용 모델: {model_config['display']}")

    # 2. API 키 로드
    load_dotenv(SCRIPT_DIR / '.env')

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[ERROR] GEMINI_API_KEY가 설정되지 않았습니다.")
            print("[INFO] .env 파일에 GEMINI_API_KEY를 설정하세요.")
            return
        # Gemini 클라이언트 초기화
        client = genai.Client(api_key=api_key)

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[ERROR] OPENAI_API_KEY가 설정되지 않았습니다.")
            print("[INFO] .env 파일에 OPENAI_API_KEY를 설정하세요.")
            return
        # OpenAI 클라이언트 초기화
        client = OpenAI(api_key=api_key)

    else:
        print(f"[ERROR] 지원하지 않는 provider: {provider}")
        return

    # 3. 파일 경로 설정
    files = {k: SCRIPT_DIR / v for k, v in FILE_CONFIG.items()}

    # 4. 대상 파일 확인
    target_file = files['TARGET_FILE']
    if not target_file.exists():
        print(f"[ERROR] 대상 파일이 없습니다: {target_file.name}")
        print("[INFO] 먼저 초기 분석을 실행하여 결과 파일을 생성하세요.")
        return

    # 5. 참고자료 로드
    print("\n[Step 1] 참고자료 로드")
    print("-" * 50)

    context = {
        'jd': load_jd_dictionary(files['INPUT_JD']) if files['INPUT_JD'].exists() else "",
        'roles': load_team_roles(files['INPUT_ROLES']) if files['INPUT_ROLES'].exists() else "",
        'info': load_txt_context(files['INPUT_COMPANY']) if files['INPUT_COMPANY'].exists() else "",
        'ir': load_pdf_text(files['INPUT_IR']) if files['INPUT_IR'].exists() else ""
    }

    # 6. 결과 파일 로드
    print("\n[Step 2] 현재 결과 파일 로드")
    print("-" * 50)

    df = load_result_excel(target_file)

    # 7. AI 검토 및 수정
    print("\n[Step 3] AI 검토 및 수정")
    print("-" * 50)

    df_result, modified_count, modified_indices = run_review_and_fix(client, model_config, df, context)

    # 8. 결과 저장
    print("\n[Step 4] 결과 저장")
    print("-" * 50)

    # 병합 컬럼 업데이트
    df_result['현재 담당팀/담당자'] = df_result['현재 담당팀'] + " / " + df_result['현재 담당자']
    df_result['미래 담당팀/담당자'] = df_result['미래 담당팀'] + " / " + df_result['미래 담당자/직책']

    # 저장
    df_result.to_excel(target_file, index=False)

    # 9. 결과 요약
    print("\n" + "=" * 70)
    print(f"[결과] 수정된 항목 수: {modified_count}건")
    print("=" * 70)

    if modified_count > 0:
        print("\n[수정된 항목 목록]")
        for idx in modified_indices:
            row = df_result.iloc[idx]
            print(f"  [{idx}] {row.get('QMS 직무', '')[:40]}")
            print(f"       → {row.get('현재 담당팀/담당자', '')}")
        print(f"\n[안내] 수정이 {modified_count}건 있습니다. 다시 실행하여 추가 검토하세요.")
    else:
        print("\n[완료] 수정 사항이 없습니다. 검토가 완료되었습니다.")


if __name__ == "__main__":
    main()
