# -*- coding: utf-8 -*-
"""
QMS R&R AI 자동 분류 스크립트
의료로봇 스타트업의 QMS 담당자 지정을 AI가 판단하여 자동 분류합니다.

사용 모델:
- gemini-3-flash-preview (1차/3차 개별 행 분석용)
- gemini-3-pro-preview (2차 일관성 검토 및 가이드라인 생성용)

실행 전 필요사항:
1. pip install pandas openpyxl google-generativeai python-dotenv pypdf
2. .env 파일에 GEMINI_API_KEY=your_api_key 설정
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# ============================================================================
# 설정 영역
# ============================================================================

# 작업 디렉토리 설정 (스크립트와 같은 위치)
SCRIPT_DIR = Path(__file__).parent.resolve()

# 모델 설정 (사용자 지정 2026년 모델명)
MODEL_FAST = "gemini-2.0-flash"  # 빠른 분석용 (개별 행 처리)
MODEL_SMART = "gemini-2.0-flash"  # 고급 분석용 (일관성 검토)

# 파일 설정
INPUT_EXCEL = "사내 QMS R&R List_251229.xlsx"
COMPANY_INFO_TXT = "라덱셀 정보.txt"  # 회사 정보 요약 파일
IR_PDF = "RADEXEL_IR_251222_1 (1).pdf"  # IR 자료 PDF
TEAM_ROLES_CSV = "각 구성원별 기존 역할.csv"  # 팀 구성원 역할 CSV
OUTPUT_DRAFT = "QMS_RnR_1차분석_결과.xlsx"  # 1차 분석 결과
OUTPUT_FINAL = "QMS_RnR_최종결과.xlsx"  # 최종 결과

# API 호출 간 대기 시간 (Rate limit 방지)
API_DELAY = 0.5  # 초

# 최대 재시도 횟수
MAX_RETRIES = 5

# ============================================================================
# 회사 기본 정보 (컨텍스트)
# ============================================================================

COMPANY_OVERVIEW = """
## 회사 개요
- 회사명: 라덱셀 (Radexel)
- 사업: 의료로봇(방사선 치료 로봇) 개발 스타트업
- 현재 스타트업 단계로 인력이 제한적
- 장기적으로 100명 규모의 의료기기 회사로 성장 예정
"""

# ============================================================================
# API 실패 시 최소한의 폴백 (AI 판단 불가 시에만 사용)
# ============================================================================

# 폴백은 최소화하고 AI 판단을 우선함

# ============================================================================
# 유틸리티 함수
# ============================================================================

def load_txt_context(txt_path: Path) -> str:
    """TXT 파일에서 회사 정보를 로드"""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()
        print(f"[INFO] 회사 정보 파일 로드 완료: {txt_path.name} ({len(text):,}자)")
        return text
    except Exception as e:
        print(f"[WARNING] TXT 파일 읽기 실패: {e}")
        return ""


def load_pdf_context(pdf_path: Path) -> str:
    """PDF 파일에서 텍스트를 추출하여 컨텍스트로 사용"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        print(f"[INFO] PDF 로드 완료: {pdf_path.name} ({len(text):,}자)")
        return text[:8000] if len(text) > 8000 else text
    except ImportError:
        print("[WARNING] pypdf 미설치. PDF 컨텍스트 없이 진행합니다.")
        return ""
    except Exception as e:
        print(f"[WARNING] PDF 읽기 실패: {e}")
        return ""


def load_team_roles_csv(csv_path: Path) -> str:
    """팀 구성원 역할 CSV 파일을 로드하여 텍스트로 변환"""
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')

        # CSV 데이터를 읽기 쉬운 형식으로 변환
        lines = ["## 현재 팀 구성 및 구성원 역할"]

        # 팀별로 그룹화
        current_team = None
        for _, row in df.iterrows():
            team = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            member = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            role = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""

            if team and team != current_team:
                lines.append(f"\n### {team}")
                current_team = team

            if member and role:
                lines.append(f"- {member}: {role}")

        result = "\n".join(lines)
        print(f"[INFO] 팀 역할 CSV 로드 완료: {csv_path.name} ({len(df)}명)")
        return result
    except Exception as e:
        print(f"[WARNING] CSV 읽기 실패: {e}")
        return ""


def get_default_assignment(job_name: str) -> dict:
    """API 완전 실패 시에만 사용하는 최소한의 폴백"""
    # AI 판단 실패 시 빈 값 대신 반환할 기본값
    # 실제로는 AI가 판단하므로 거의 사용되지 않음
    return {
        "now_team": "미지정",
        "now_person": "미지정",
        "now_reason": "AI 판단 필요",
        "future_team": "미지정",
        "future_person": "미지정",
        "future_reason": "AI 판단 필요"
    }


def extract_json_from_text(text: str) -> dict | None:
    """텍스트에서 JSON을 추출하는 다양한 방법 시도"""

    if not text or not isinstance(text, str):
        return None

    # 방법 1: 직접 JSON 파싱 시도
    try:
        return json.loads(text.strip())
    except:
        pass

    # 방법 2: 코드블록 제거 후 파싱
    cleaned = text
    cleaned = re.sub(r'```json\s*', '', cleaned)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except:
        pass

    # 방법 3: JSON 객체 패턴 찾기 (가장 바깥쪽 중괄호)
    json_patterns = [
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # 중첩된 중괄호 허용
        r'\{[\s\S]*?\}(?=\s*$)',  # 마지막 중괄호까지
        r'\{.*\}',  # 가장 단순한 패턴
    ]

    for pattern in json_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                result = json.loads(match)
                if isinstance(result, dict) and 'now_team' in result:
                    return result
            except:
                continue

    # 방법 4: 줄바꿈을 공백으로 치환 후 재시도
    single_line = re.sub(r'\s+', ' ', text)
    try:
        match = re.search(r'\{[^}]+\}', single_line)
        if match:
            return json.loads(match.group())
    except:
        pass

    return None


def extract_fields_manually(text: str) -> dict | None:
    """정규식으로 개별 필드를 직접 추출"""

    if not text or not isinstance(text, str):
        return None

    result = {}

    # 각 필드에 대한 패턴
    field_patterns = {
        'now_team': [
            r'"now_team"\s*:\s*"([^"]+)"',
            r"'now_team'\s*:\s*'([^']+)'",
            r'now_team[:\s]+([^\n,}]+)',
            r'현재\s*담당팀[:\s]+([^\n,]+)',
        ],
        'now_person': [
            r'"now_person"\s*:\s*"([^"]+)"',
            r"'now_person'\s*:\s*'([^']+)'",
            r'now_person[:\s]+([^\n,}]+)',
            r'현재\s*담당자[:\s]+([^\n,]+)',
        ],
        'now_reason': [
            r'"now_reason"\s*:\s*"([^"]+)"',
            r"'now_reason'\s*:\s*'([^']+)'",
            r'now_reason[:\s]+([^\n,}]+)',
        ],
        'future_team': [
            r'"future_team"\s*:\s*"([^"]+)"',
            r"'future_team'\s*:\s*'([^']+)'",
            r'future_team[:\s]+([^\n,}]+)',
            r'미래\s*담당팀[:\s]+([^\n,]+)',
        ],
        'future_person': [
            r'"future_person"\s*:\s*"([^"]+)"',
            r"'future_person'\s*:\s*'([^']+)'",
            r'future_person[:\s]+([^\n,}]+)',
            r'미래\s*담당자[:\s]+([^\n,]+)',
        ],
        'future_reason': [
            r'"future_reason"\s*:\s*"([^"]+)"',
            r"'future_reason'\s*:\s*'([^']+)'",
            r'future_reason[:\s]+([^\n,}]+)',
        ],
    }

    for field, patterns in field_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # 불필요한 문자 제거
                value = re.sub(r'[,}\]]+$', '', value).strip()
                if value and value not in ['', '""', "''", 'null', 'None']:
                    result[field] = value
                    break

    # 최소 2개 이상의 필드가 추출되었으면 성공으로 간주
    if len(result) >= 2:
        return result

    return None


def call_gemini_api_json(model_name: str, prompt: str, job_name: str = "") -> dict:
    """
    Gemini API 호출 - JSON 응답을 강제하고 파싱 실패 시 폴백 처리
    절대 파싱 오류를 반환하지 않음
    """
    model = genai.GenerativeModel(model_name)

    for attempt in range(MAX_RETRIES):
        try:
            # JSON 출력 강제 설정
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,  # 낮은 temperature로 일관성 향상
                    max_output_tokens=1024,
                    response_mime_type="application/json",  # JSON 출력 강제
                )
            )

            time.sleep(API_DELAY)

            if not response or not response.text:
                print(f"    [재시도 {attempt + 1}/{MAX_RETRIES}] 빈 응답")
                continue

            response_text = response.text

            # 파싱 시도 1: JSON 직접 추출
            result = extract_json_from_text(response_text)
            if result and validate_result(result):
                return result

            # 파싱 시도 2: 수동 필드 추출
            result = extract_fields_manually(response_text)
            if result and validate_result(result):
                return result

            print(f"    [재시도 {attempt + 1}/{MAX_RETRIES}] 파싱 실패, 재요청 중...")

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                wait_time = (attempt + 1) * 10
                print(f"    [Rate Limit] {wait_time}초 대기 중...")
                time.sleep(wait_time)
            else:
                print(f"    [에러] {error_msg[:50]}...")
                time.sleep(2)

    # 모든 시도 실패 시: 폴백 값 사용
    print(f"    [폴백] 기본 담당자 배정 사용")
    return get_default_assignment(job_name)


def validate_result(result: dict) -> bool:
    """결과 딕셔너리가 유효한지 검증"""
    if not isinstance(result, dict):
        return False

    required_fields = ['now_team', 'now_person']
    for field in required_fields:
        if field not in result:
            return False
        value = result.get(field, '')
        if not value or value in ['', 'null', 'None', '파싱 오류']:
            return False

    return True


def ensure_complete_result(result: dict, job_name: str = "") -> dict:
    """결과에 누락된 필드가 있으면 채워서 완전한 결과 반환"""
    default = get_default_assignment(job_name)

    complete = {
        'now_team': result.get('now_team') or default['now_team'],
        'now_person': result.get('now_person') or default['now_person'],
        'now_reason': result.get('now_reason') or default['now_reason'],
        'future_team': result.get('future_team') or default['future_team'],
        'future_person': result.get('future_person') or default['future_person'],
        'future_reason': result.get('future_reason') or default['future_reason'],
    }

    return complete


def load_excel_data(file_path: Path) -> pd.DataFrame:
    """엑셀 파일 로드 및 전처리"""
    df = pd.read_excel(file_path, engine='openpyxl')

    # Unnamed 컬럼 제거
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    # 마지막 행이 비고(설명)인 경우 제거
    if pd.notna(df.iloc[-1]['QMS 직무']) and '비고' in str(df.iloc[-1]['QMS 직무']):
        df = df.iloc[:-1]

    # NaN을 빈 문자열로 대체
    df = df.fillna('')

    return df


# ============================================================================
# 1단계: 개별 행 분석 (Row-by-Row Analysis)
# ============================================================================

def analyze_single_row(row_data: dict, row_index: int, context: str) -> dict:
    """단일 행에 대해 AI 분석 수행 - 절대 실패하지 않음"""

    job_name = row_data.get('QMS 직무', '')

    # 행 데이터를 텍스트로 변환
    row_text = "\n".join([f"- {k}: {v}" for k, v in row_data.items() if v])

    prompt = f"""당신은 의료기기 QMS(품질경영시스템) 및 조직관리 전문가입니다.

## 회사 정보 및 팀 구성
{context}

## 분석 대상 직무
{row_text}

## 요청사항
위 직무를 수행하기에 가장 적합한 담당자를 배정해주세요.

1. **현재 기준 (스타트업)**: 현재 팀 구성원 중에서 해당 직무의 본질과 가장 부합하는 전문성을 가진 사람. 구체적인 이름(닉네임) 포함.
2. **미래 기준 (100명 규모)**: 이상적인 조직 구조 기준 전문 부서/직책

## 판단 원칙
- 직무의 본질적인 내용을 분석하여 해당 분야 전문가에게 배정
- 팀 구성원의 역할 설명을 참고하여 가장 적합한 담당자 선택
- 배정 이유는 "왜 이 담당자가 적합한지"를 직무 내용 기반으로 설명

반드시 아래 JSON만 출력:
{{"now_team": "담당팀명", "now_person": "담당자명 (닉네임)", "now_reason": "직무 내용 기반 배정 이유", "future_team": "미래부서명", "future_person": "미래직책", "future_reason": "미래 조직 기준 배정 이유"}}"""

    result = call_gemini_api_json(MODEL_FAST, prompt, job_name)
    return ensure_complete_result(result, job_name)


def run_first_pass(df: pd.DataFrame, context: str) -> pd.DataFrame:
    """1차 분석: 모든 행에 대해 개별 분석 수행"""
    print("\n" + "=" * 60)
    print("Phase 1: 1차 분석 시작 (개별 행 분석)")
    print("=" * 60)

    results = []
    total_rows = len(df)

    for idx, row in df.iterrows():
        row_data = row.to_dict()
        job_name = str(row_data.get('QMS 직무', 'N/A'))[:30]
        print(f"\n[{idx + 1}/{total_rows}] 분석 중: {job_name}...")

        result = analyze_single_row(row_data, int(idx), context)
        results.append(result)

        print(f"  → 현재: {result.get('now_team', '')} / {result.get('now_person', '')}")
        print(f"  → 미래: {result.get('future_team', '')} / {result.get('future_person', '')}")

    # 결과를 DataFrame에 추가
    df['현재 담당팀'] = [r.get('now_team', '') for r in results]
    df['현재 담당자'] = [r.get('now_person', '') for r in results]
    df['현재 분류 이유'] = [r.get('now_reason', '') for r in results]
    df['미래 담당팀'] = [r.get('future_team', '') for r in results]
    df['미래 담당자/직책'] = [r.get('future_person', '') for r in results]
    df['미래 분류 이유'] = [r.get('future_reason', '') for r in results]

    return df


# ============================================================================
# 2단계: 일관성 검토 및 가이드라인 생성
# ============================================================================

def generate_consistency_guidelines(df: pd.DataFrame, context: str) -> str:
    """1차 분석 결과를 검토하고 일관성 가이드라인 생성"""
    print("\n" + "=" * 60)
    print("Phase 2: 일관성 검토 및 가이드라인 생성")
    print("=" * 60)

    # 1차 분석 결과 요약
    summary_data = df[['QMS 직무', '현재 담당팀', '현재 담당자', '미래 담당팀', '미래 담당자/직책']].to_string()

    prompt = f"""당신은 의료기기 회사의 COO(최고운영책임자)입니다.
AI가 1차 작성한 QMS 업무 분장표를 검토하고, 일관성 있는 가이드라인을 수립해주세요.

## 회사 팀 구조
{context}

## 1차 분석 결과
{summary_data}

## 검토 요청사항
1. 일관성 문제 파악: 유사한 직무인데 다른 팀/담당자가 배정된 경우
2. 업무 과중 검토: 특정 인원에게 업무가 과도하게 집중된 경우
3. 역할 적합성: 해당 팀/담당자의 전문성과 맞지 않는 배정
4. 누락 검토: 지정되지 않은 항목 확인

아래 형식으로 재분류 가이드라인 5-7개를 작성해주세요:

### 재분류 가이드라인
1. [가이드라인 1]: 구체적인 지침 내용
2. [가이드라인 2]: 구체적인 지침 내용
..."""

    print("[INFO] 가이드라인 생성 중...")

    model = genai.GenerativeModel(MODEL_SMART)

    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=2048,
                )
            )
            time.sleep(API_DELAY)

            if response and response.text:
                guidelines = response.text
                print("\n[생성된 가이드라인]")
                print("-" * 40)
                print(guidelines[:2000] if len(guidelines) > 2000 else guidelines)
                print("-" * 40)
                return guidelines

        except Exception as e:
            print(f"[재시도 {attempt + 1}/{MAX_RETRIES}] 가이드라인 생성 오류: {str(e)[:50]}")
            time.sleep(5)

    # 실패 시 중립적 가이드라인 반환 (AI 자유 판단 유도)
    return """### 재분류 가이드라인
1. 각 직무의 본질적인 내용을 분석하여 가장 적합한 전문성을 가진 담당자에게 배정한다.
2. 특정 팀이나 개인에게 업무가 과도하게 집중되지 않도록 균형 있게 분배한다.
3. 담당자의 현재 역할과 직무 내용의 연관성을 고려하여 배정한다.
4. 직무 수행에 필요한 전문 지식과 담당자의 경험을 종합적으로 판단한다."""


# ============================================================================
# 3단계: 최종 분석 (가이드라인 적용)
# ============================================================================

def analyze_with_guidelines(row_data: dict, row_index: int, context: str,
                            guidelines: str, previous_result: dict) -> dict:
    """가이드라인을 적용하여 최종 분석 - AI가 독립적으로 판단"""

    job_name = row_data.get('QMS 직무', '')

    row_text = "\n".join([f"- {k}: {v}" for k, v in row_data.items()
                          if v and k not in ['현재 담당팀', '현재 담당자', '현재 분류 이유',
                                             '미래 담당팀', '미래 담당자/직책', '미래 분류 이유']])

    prompt = f"""당신은 의료기기 QMS(품질경영시스템) 및 조직관리 전문가입니다.

## 회사 정보 및 팀 구성
{context}

## 분석 대상 직무
{row_text}

## 배정 가이드라인
{guidelines}

## 요청사항
위 직무를 수행하기에 가장 적합한 담당자를 배정해주세요.

1. **현재 기준**: 현재 팀 구성원 중에서 해당 직무의 본질과 가장 부합하는 전문성을 가진 사람
2. **미래 기준**: 100명 규모로 성장했을 때 이상적인 부서/직책

## 판단 원칙
- 직무의 본질적인 내용을 분석하여 해당 분야 전문가에게 배정
- 특정 팀에 업무가 과도하게 집중되지 않도록 균형 있게 배분
- 배정 이유는 "왜 이 담당자가 적합한지"를 직무 내용 기반으로 설명

반드시 아래 JSON만 출력:
{{"now_team": "담당팀명", "now_person": "담당자명 (닉네임)", "now_reason": "직무 내용 기반 배정 이유", "future_team": "미래부서명", "future_person": "미래직책", "future_reason": "미래 조직 기준 배정 이유"}}"""

    result = call_gemini_api_json(MODEL_FAST, prompt, job_name)
    return ensure_complete_result(result, job_name)


def run_final_pass(df: pd.DataFrame, context: str, guidelines: str) -> pd.DataFrame:
    """3차 분석: 가이드라인을 적용하여 최종 확정"""
    print("\n" + "=" * 60)
    print("Phase 3: 최종 분석 (가이드라인 적용)")
    print("=" * 60)

    results = []
    total_rows = len(df)

    for idx, row in df.iterrows():
        row_data = row.to_dict()
        job_name = str(row_data.get('QMS 직무', 'N/A'))[:30]
        print(f"\n[{idx + 1}/{total_rows}] 최종 검토: {job_name}...")

        # 이전 결과 추출
        prev_result = {
            '현재 담당팀': row.get('현재 담당팀', ''),
            '현재 담당자': row.get('현재 담당자', ''),
            '미래 담당팀': row.get('미래 담당팀', ''),
            '미래 담당자/직책': row.get('미래 담당자/직책', '')
        }

        result = analyze_with_guidelines(row_data, int(idx), context, guidelines, prev_result)
        results.append(result)

        # 변경 여부 확인
        changed = (result.get('now_team', '') != prev_result['현재 담당팀'] or
                   result.get('now_person', '') != prev_result['현재 담당자'])
        status = "수정됨" if changed else "유지"

        print(f"  → [{status}] 현재: {result.get('now_team', '')} / {result.get('now_person', '')}")
        print(f"  → [{status}] 미래: {result.get('future_team', '')} / {result.get('future_person', '')}")

    # 최종 결과 업데이트
    df['현재 담당팀'] = [r.get('now_team', '') for r in results]
    df['현재 담당자'] = [r.get('now_person', '') for r in results]
    df['현재 분류 이유'] = [r.get('now_reason', '') for r in results]
    df['미래 담당팀'] = [r.get('future_team', '') for r in results]
    df['미래 담당자/직책'] = [r.get('future_person', '') for r in results]
    df['미래 분류 이유'] = [r.get('future_reason', '') for r in results]

    return df


# ============================================================================
# 메인 실행
# ============================================================================

def main():
    """메인 실행 함수"""
    print("\n" + "=" * 60)
    print("QMS R&R AI 자동 분류 시스템")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 환경 변수 로드
    load_dotenv(SCRIPT_DIR / '.env')
    api_key = os.getenv('GEMINI_API_KEY')

    if not api_key:
        print("\n[ERROR] API 키가 설정되지 않았습니다.")
        print("1. .env 파일을 생성하세요")
        print("2. GEMINI_API_KEY=your_api_key 형식으로 입력하세요")
        sys.exit(1)

    genai.configure(api_key=api_key)
    print(f"[INFO] API 키 설정 완료")
    print(f"[INFO] 사용 모델: {MODEL_FAST} (빠른분석), {MODEL_SMART} (고급분석)")

    # 입력 파일 확인
    input_path = SCRIPT_DIR / INPUT_EXCEL
    if not input_path.exists():
        print(f"\n[ERROR] 입력 파일을 찾을 수 없습니다: {INPUT_EXCEL}")
        sys.exit(1)

    # ===== 컨텍스트 로드 (회사 정보 TXT + IR PDF + 팀 역할 CSV) =====
    print("\n[컨텍스트 파일 로드]")

    # 1. 회사 정보 TXT 파일 로드
    txt_path = SCRIPT_DIR / COMPANY_INFO_TXT
    company_info = ""
    if txt_path.exists():
        company_info = load_txt_context(txt_path)
    else:
        print(f"[INFO] 회사 정보 파일 없음: {COMPANY_INFO_TXT}")

    # 2. IR PDF 파일 로드
    pdf_path = SCRIPT_DIR / IR_PDF
    pdf_context = ""
    if pdf_path.exists():
        pdf_context = load_pdf_context(pdf_path)
    else:
        pdf_files = list(SCRIPT_DIR.glob("*.pdf"))
        if pdf_files:
            pdf_context = load_pdf_context(pdf_files[0])
        else:
            print(f"[INFO] IR PDF 파일 없음: {IR_PDF}")

    # 3. 팀 구성원 역할 CSV 파일 로드
    csv_path = SCRIPT_DIR / TEAM_ROLES_CSV
    team_roles = ""
    if csv_path.exists():
        team_roles = load_team_roles_csv(csv_path)
    else:
        print(f"[INFO] 팀 역할 CSV 파일 없음: {TEAM_ROLES_CSV}")

    # 전체 컨텍스트 구성
    full_context = COMPANY_OVERVIEW

    # 팀 구성원 역할 정보 추가 (CSV에서 로드)
    if team_roles:
        full_context += f"\n{team_roles}"

    if company_info:
        full_context += f"\n\n## 라덱셀 회사 정보 요약\n{company_info}"

    if pdf_context:
        full_context += f"\n\n## IR 자료 주요 내용\n{pdf_context}"

    print(f"[INFO] 전체 컨텍스트 크기: {len(full_context):,}자")

    # 엑셀 데이터 로드
    print(f"\n[INFO] 엑셀 파일 로드: {INPUT_EXCEL}")
    df = load_excel_data(input_path)
    print(f"[INFO] 총 {len(df)}개 직무 항목 로드 완료")

    # Phase 1: 1차 분석
    df = run_first_pass(df, full_context)

    # 1차 결과 저장
    draft_path = SCRIPT_DIR / OUTPUT_DRAFT
    df.to_excel(draft_path, index=False, engine='openpyxl')
    print(f"\n[INFO] 1차 분석 결과 저장: {OUTPUT_DRAFT}")

    # Phase 2: 가이드라인 생성
    guidelines = generate_consistency_guidelines(df, full_context)

    # Phase 3: 최종 분석
    df_final = run_final_pass(df.copy(), full_context, guidelines)

    # 최종 결과 저장
    final_path = SCRIPT_DIR / OUTPUT_FINAL

    # 컬럼명 변경
    rename_map = {
        '현재 분류 이유': '현재 분류 이유 1줄 설명',
        '미래 분류 이유': '미래 분류 이유 1줄 설명'
    }
    df_final = df_final.rename(columns=rename_map)

    # 통합 컬럼 생성
    df_final['현재 담당팀 / 담당자'] = df_final['현재 담당팀'] + ' / ' + df_final['현재 담당자']
    df_final['미래 담당팀 / 담당자'] = df_final['미래 담당팀'] + ' / ' + df_final['미래 담당자/직책']

    df_final.to_excel(final_path, index=False, engine='openpyxl')

    print("\n" + "=" * 60)
    print("작업 완료!")
    print("=" * 60)
    print(f"1차 분석 결과: {OUTPUT_DRAFT}")
    print(f"최종 결과: {OUTPUT_FINAL}")
    print(f"\n총 처리 항목: {len(df_final)}개")
    print("=" * 60)


if __name__ == "__main__":
    main()
