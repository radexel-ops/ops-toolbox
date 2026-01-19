# -*- coding: utf-8 -*-
"""
[라덱셀 QMS R&R AI 자동 배정 시스템 - Strategic Director Mode]
작성일: 2026.01.13
수정일: 2026.01.15 (전략 기획 이사 모드 + Row-by-Row 분석)
버전: 7.0 (RA/QA 팀장 불안감 해소 전략 + 구어체 비고)

[핵심 로직]
1. 기존 결과 파일(QMS_RnR_최종결과_v5.xlsx)을 입력으로 사용
2. AI(경영기획 이사 정수현)가 각 행을 개별적으로 Row-by-Row 분석
3. RA/QA 팀장(이선희)의 불안감(책임, 인력부족, 감사지적)을 해소하는 관점으로 검토
4. 5개 컬럼 수정: 비고, 현재 담당팀, 현재 담당자, 미래 담당팀, 미래 담당자
5. 비고에는 회의용 구어체 질문/제안 작성 (예: "팀장님, 이건 경영팀이 1차로 거를까요?")
6. 상세 로그 출력: [Old Value] → [New Value] 형식으로 변경사항 시각화
7. 반복 실행 최적화: 여러 번 돌릴수록 내용이 다듬어짐

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
        # 기존 비고(질문) 가져오기
        note = str(row.get('비고', '')).strip()
        if note == 'nan':
            note = ''

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
        if note:
            lines.append(f"    기존 비고: {note}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# [Section 3] AI 처리 로직 (Strategic Director Mode) - Ver 7.0
# ============================================================================

def _create_strategic_prompt(row: pd.Series, context: dict) -> str:
    """
    RA/QA 팀장의 심리(불안, 책임 회피, 완벽주의)를 고려하여
    실무적인 R&R을 제안하고, 회의용 질문(비고)을 생성하는 프롬프트
    """
    # 데이터 전처리 (NaN 처리)
    job_name = str(row.get('QMS 직무', '')).strip()
    task_desc = str(row.get('설명', '')).strip()
    curr_team = str(row.get('현재 담당팀', '')).strip()
    curr_user = str(row.get('현재 담당자', '')).strip()
    fut_team = str(row.get('미래 담당팀', '')).strip()
    fut_user = str(row.get('미래 담당자/직책', '')).strip()
    curr_note = str(row.get('비고', '')).strip()

    # NaN 문자열 처리
    if task_desc == 'nan': task_desc = ""
    if curr_team == 'nan': curr_team = ""
    if curr_user == 'nan': curr_user = ""
    if fut_team == 'nan': fut_team = ""
    if fut_user == 'nan': fut_user = ""
    if curr_note == 'nan': curr_note = ""

    prompt = f"""당신은 의료기기 스타트업 '라덱셀'의 **경영기획 이사 정수현**입니다.
상대방은 신중하고 걱정이 많으며 의사결정이 조금 느린 **RA/QA 팀장 이선희**입니다.

당신의 목표:
이 엑셀 파일을 통해 업무 분장을 명확히 하되, 팀장님이 가질 수 있는 '막연한 불안감(책임, 인력 부족, 감사 지적)'을 선제적으로 해소해주며 리드해야 합니다.

# ========== 참고자료 (회사 컨텍스트) ==========

{context.get('roles', '(인력 풀 정보 없음)')}

{context.get('jd', '(JD 정보 없음)')[:3000]}

# ========== 현재 검토 중인 행(Row) 정보 ==========

- **QMS 직무명**: {job_name}
- **업무 설명**: {task_desc if task_desc else "(설명 없음)"}
- **현재 설정**: 팀[{curr_team if curr_team else "미정"}] / 담당[{curr_user if curr_user else "미정"}]
- **미래 설정**: 팀[{fut_team if fut_team else "미정"}] / 담당[{fut_user if fut_user else "미정"}]
- **기존 비고**: {curr_note if curr_note else "(없음)"}

# ========== 작성 지침 ==========

다음 5개 항목을 검토하여 JSON으로 수정안을 제시하십시오.
**수정할 필요가 없으면 해당 필드를 null로 두세요.**

1. **비고 (Core - 가장 중요!)**:
   - 회의 때 내가 팀장님 눈을 보고 바로 읽을 수 있는 **'간결한 구어체 한 줄 질문/제안'**이어야 함.
   - 팀장님의 '아픈 포인트(Pain Point)'를 건드려야 함:
     예시:
     - "팀장님, 이건 단순 행정이니 저희가 기록만 챙기고, 팀장님은 최종 도장만 찍어서 책임 부담 덜으시죠?"
     - "이걸 지금 다 검토하시려면 업무 마비되실 텐데, 1차 필터링은 경영팀에 맡기시죠?"
     - "규정상 QA가 꼭 해야 하는 거면, 다른 잡무를 줄여드릴 테니 이것만 확실히 가져가시죠."
     - "팀장님, 혹시 이 업무가 SW검증인가요, HW검증인가요? 담당자 정하려면 범위를 알아야 해서요."
   - **업무가 명확하면 비워두어도 됨(null)**. 모든 행에 질문 달지 마세요.

2. **현재 담당팀 / 현재 담당자**:
   - 'RA/QA' 처럼 모호하게 적힌 경우, 업무 성격을 봐서 'RA(인허가)'인지 'QA(품질관리)'인지 구체적으로 제안.
   - 담당자가 비어있다면, '이선희(검토)', '경영지원(실무)' 등으로 구체적 역할 명시.

3. **미래 담당팀 / 미래 담당자**:
   - 100명 규모 조직을 가정하여 이상적인 부서/직책 제안 (예: 품질본부장, QA Manager, 인재개발팀 등).

# ========== 출력 형식 (JSON Only) ==========

반드시 아래 형식의 JSON 객체 하나만 출력하세요. 마크다운 없이 순수 JSON만.
수정이 필요 없는 필드는 null로 두세요.

{{
    "비고": "회의용 구어체 멘트 (필요한 경우에만, 없으면 null)",
    "현재 담당팀": "수정안 (변경 없으면 null)",
    "현재 담당자": "수정안 (변경 없으면 null)",
    "미래 담당팀": "수정안 (변경 없으면 null)",
    "미래 담당자": "수정안 (변경 없으면 null)",
    "reason": "수정/질문 이유 (로그용, 간단히)"
}}
"""
    return prompt


# [qms_rnr_ai_classifier_v2.py 파일 내부 수정]

# ============================================================================
# [Section 1] 전략적 프롬프트 생성 함수 (수정됨: context 인자 제거)
# ============================================================================
def _create_strategic_prompt(row):
    """
    RA/QA 팀장의 심리(불안, 책임 회피, 완벽주의)를 고려하여
    실무적인 R&R을 제안하고, 회의용 질문(비고)을 생성하는 프롬프트
    """
    # 데이터 전처리
    task_desc = str(row.get('설명', '')).strip()
    curr_team = str(row.get('현재 담당팀', '')).strip()
    curr_user = str(row.get('현재 담당자', '')).strip()
    fut_team = str(row.get('미래 담당팀', '')).strip()
    # 엑셀 헤더가 '미래 담당자' 또는 '미래 담당자/직책'일 수 있음
    fut_user = str(row.get('미래 담당자/직책', row.get('미래 담당자', ''))).strip()
    curr_note = str(row.get('비고', '')).strip()
    if curr_note == 'nan': curr_note = ""

    prompt = f"""
    당신은 의료기기 스타트업의 '경영기획 이사 정수현'입니다.
    상대방은 신중하고 걱정이 많으며 의사결정이 조금 느린 'RA/QA 팀장 이선희'입니다.

    [당신의 목표]
    이 엑셀 파일을 통해 업무 분장을 명확히 하되, 팀장님이 가질 수 있는 '막연한 불안감(책임, 인력 부족, 감사 지적)'을 선제적으로 해소해주며 리드해야 합니다.

    [현재 검토 중인 행(Row) 정보]
    - 업무 설명: {task_desc}
    - 현재 설정: 팀[{curr_team}] / 담당[{curr_user}]
    - 미래 설정: 팀[{fut_team}] / 담당[{fut_user}]
    - 기존 비고: {curr_note}

    [작성 지침]
    다음 항목을 검토하여 JSON으로 수정안을 제시하십시오.

    1. **비고 (Core)**: 
       - 회의 때 내가 팀장님 눈을 보고 바로 읽을 수 있는 **'간결한 구어체 한 줄 질문'**이어야 함.
       - 팀장님의 '아픈 포인트(Pain Point)'를 건드려야 함.
         (예: "팀장님, 이건 단순 행정이니 저희가 기록만 챙기고, 팀장님은 최종 도장만 찍어서 책임 부담 더시겠어요?")
         (예: "이걸 지금 다 검토하시려면 업무 마비되실 텐데, 1차 필터링은 경영팀에 맡기시죠?")
       - 이미 명확하면 비워두어도 됨(null).

    2. **현재/미래 담당팀 및 담당자**:
       - 'RA/QA' 처럼 모호하게 적힌 경우, 업무 성격을 봐서 'RA(인허가)'인지 'QA(품질관리)'인지 구체적으로 제안.
       - 담당자가 비어있다면, '이선희(검토)', '경영지원(실무)' 등으로 구체적 역할 명시.

    [Response Format (JSON Only)]
    {{
        "비고": "회의용 구어체 멘트 (없으면 null)",
        "현재 담당팀": "수정안",
        "현재 담당자": "수정안",
        "미래 담당팀": "수정안",
        "미래 담당자": "수정안",
        "reason": "수정 이유(로그용)"
    }}
    """
    return prompt


# ============================================================================
# [Section 2] AI 호출 및 업데이트 로직 (수정됨: model_name 인자 추가 및 호출부 일치화)
# ============================================================================
def analyze_and_update_row(client, model_type, model_name, row, index):
    try:
        # [수정 포인트] context 인자 없이 row만 전달
        prompt = _create_strategic_prompt(row)

        # 1. AI 호출
        response_text = ""
        if model_type == "gemini":
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            response_text = response.text
        elif model_type == "openai":
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a strategic planning director. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            response_text = response.choices[0].message.content

        # 2. 결과 파싱
        data = json.loads(response_text)

        # 3. 변경 사항 감지 및 업데이트
        columns_map = {
            '비고': '비고',
            '현재 담당팀': '현재 담당팀',
            '현재 담당자': '현재 담당자',
            '미래 담당팀': '미래 담당팀',
            '미래 담당자': '미래 담당자/직책'
        }

        changes = []
        is_modified = False

        for json_key, excel_col in columns_map.items():
            # 컬럼 존재 여부 체크 (미래 담당자/직책 vs 미래 담당자)
            target_col = excel_col
            if target_col not in row.index:
                if json_key == '미래 담당자' and '미래 담당자' in row.index:
                    target_col = '미래 담당자'
                else:
                    continue

            original_val = str(row.get(target_col, '')).strip()
            if original_val == 'nan': original_val = ""

            new_val = str(data.get(json_key, '')).strip()
            if new_val.lower() in ['none', 'null', 'nan']: new_val = ""

            if new_val and new_val != original_val:
                changes.append(f"   └ [{target_col}] : {original_val}  ->  {new_val}")
                row[target_col] = new_val
                is_modified = True

        # 4. 로그 출력
        if is_modified:
            job_name = str(row.get('QMS 직무', str(row.get('설명', ''))))[:30]
            print(f"\n[Row {index}] {job_name}...")
            print(f"   (이유: {data.get('reason', 'N/A')})")
            for change in changes:
                print(change)
            return True, row
        else:
            return False, row

    except Exception as e:
        print(f"[Error] Row {index}: {e}")
        return False, row


# ============================================================================
# [Section 3] 파일 처리 메인 함수 (수정됨: 파라미터 확장)
# ============================================================================
def process_rnr_file(file_path, model_type="gemini", model_name="gemini-2.0-flash-exp"):
    print(f"\n>>> [Processing] 파일: {file_path}")
    print(f">>> [Model] {model_type.upper()} : {model_name} 가동 중...")

    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"❌ 파일 읽기 실패: {e}")
        return

    load_dotenv()

    try:
        if model_type == "gemini":
            client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        else:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    except Exception as e:
        print(f"❌ API 클라이언트 초기화 실패: {e}")
        return

    total_updates = 0

    for index, row in df.iterrows():
        # [수정 포인트] model_name 전달 및 호출
        is_updated, new_row = analyze_and_update_row(client, model_type, model_name, row, index)
        if is_updated:
            df.loc[index] = new_row
            total_updates += 1

    try:
        df.to_excel(file_path, index=False)
        print(f">>> [완료] {total_updates}건 수정됨. (저장됨: {file_path})")
    except Exception as e:
        print(f"❌ 파일 저장 실패: {e}")
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
    print("라덱셀 QMS 자동 배정 시스템 (Ver 7.0 - 전략 기획 이사 모드)")
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
            return
        client = genai.Client(api_key=api_key)

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[ERROR] OPENAI_API_KEY가 설정되지 않았습니다.")
            return
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

    # '비고' 컬럼이 없으면 생성
    if '비고' not in df.columns:
        df['비고'] = ''

    # 7. AI Row-by-Row 분석
    print("\n[Step 3] AI Row-by-Row 정밀 분석 (전략 기획 이사 모드)")
    print("-" * 50)
    print(">>> RA/QA 팀장의 불안감을 해소하는 전략적 R&R 검토 시작...\n")

    total_rows = len(df)
    total_updates = 0
    note_updates = 0

    for index, row in df.iterrows():
        # 진행률 표시 (10개마다)
        if index % 10 == 0:
            print(f"  ... 진행 중: {index}/{total_rows}")

        is_updated, updated_row, changes, reason = analyze_and_update_row(
            client, model_config, row, index, context
        )

        if is_updated:
            df.loc[index] = updated_row
            total_updates += 1

            # 상세 로그 출력
            job_name = str(row.get('QMS 직무', ''))[:35]
            print(f"\n  [Row {index}] {job_name}")
            if reason:
                print(f"    (이유: {reason})")

            for change in changes:
                col = change['col']
                old = change['old'][:30] + "..." if len(change['old']) > 30 else change['old']
                new = change['new'][:50] + "..." if len(change['new']) > 50 else change['new']
                print(f"    └ [{col}]: {old}  →  {new}")

                if col == '비고':
                    note_updates += 1

    # 8. 결과 저장
    print("\n" + "-" * 50)
    print("[Step 4] 결과 저장")
    print("-" * 50)

    # 병합 컬럼 업데이트
    df['현재 담당팀/담당자'] = df['현재 담당팀'].astype(str) + " / " + df['현재 담당자'].astype(str)
    df['미래 담당팀/담당자'] = df['미래 담당팀'].astype(str) + " / " + df['미래 담당자/직책'].astype(str)

    # 저장
    df.to_excel(target_file, index=False)
    print(f"[저장 완료] {target_file.name}")

    # 9. 결과 요약
    print("\n" + "=" * 70)
    print(f"[결과 요약]")
    print(f"  - 전체 검토 행: {total_rows}건")
    print(f"  - 수정된 행: {total_updates}건")
    print(f"  - QA팀 질의 사항(비고): {note_updates}건")
    print("=" * 70)

    if total_updates > 0:
        print(f"\n[안내] {total_updates}건이 수정되었습니다.")
        if note_updates > 0:
            print(f"       엑셀 '비고' 컬럼에 {note_updates}건의 회의용 질문이 작성되었습니다.")
        print("       다시 실행하면 추가 개선 사항을 찾을 수 있습니다.")
    else:
        print("\n[완료] 추가적인 수정이나 질의 사항이 없습니다.")


if __name__ == "__main__":
    main()
