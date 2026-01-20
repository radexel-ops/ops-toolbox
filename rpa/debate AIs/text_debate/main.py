#!/usr/bin/env python3
"""
AI Debate System
Gemini와 GPT가 사용자의 질문에 대해 토론하여 합의를 도출하는 시스템

사용법:
    python main.py
"""

import os
import sys
import time
import glob
import re
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from functools import wraps

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.table import Table

from utils import FileProcessor, HtmlLogger

# 콘솔 초기화 (Windows 호환성)
console = Console(force_terminal=True, legacy_windows=False)

# 환경변수 로드
load_dotenv()


def get_current_date_str() -> str:
    """현재 날짜를 문자열로 반환"""
    return datetime.now().strftime('%Y년 %m월 %d일')


def inject_date_into_prompt(prompt: str, date_str: str) -> str:
    """프롬프트에 현재 날짜를 주입"""
    return prompt.replace('{CURRENT_DATE}', date_str)


def select_files_dialog() -> List[str]:
    """파일 탐색기를 열어 파일 선택"""
    root = tk.Tk()
    root.withdraw()  # 메인 윈도우 숨김
    root.attributes('-topmost', True)  # 다이얼로그를 최상위로

    file_paths = filedialog.askopenfilenames(
        title="첨부할 파일을 선택하세요 (여러 개 선택 가능)",
        filetypes=[
            ("모든 파일", "*.*"),
            ("이미지 파일", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("문서 파일", "*.pdf *.docx *.xlsx *.txt *.md"),
            ("코드 파일", "*.py *.js *.html *.css *.json *.yaml *.yml"),
        ]
    )

    root.destroy()
    return list(file_paths)


def load_config() -> dict:
    """설정 파일 로드"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

    if not os.path.exists(config_path):
        console.print("[red]config.yaml 파일을 찾을 수 없습니다.[/red]")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """지수 백오프를 사용한 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 초기 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # 재시도하지 않아야 할 오류들
                    non_retryable = ['invalid', 'not found', 'unauthorized', 'forbidden', 'api_key']
                    if any(err in error_msg for err in non_retryable):
                        raise e

                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        console.print(f"[yellow]API 오류 발생, {delay:.1f}초 후 재시도 ({attempt + 1}/{max_retries})...[/yellow]")
                        time.sleep(delay)

            raise last_exception
        return wrapper
    return decorator


def truncate_context(context: str, max_chars: int = 50000) -> str:
    """컨텍스트 크기를 제한하여 토큰 비용 절감 및 속도 향상

    최근 대화를 우선 유지하고, 오래된 대화는 요약 형태로 축소

    Args:
        context: 전체 컨텍스트 문자열
        max_chars: 최대 문자 수 (기본 50,000자 ≈ 약 12,500 토큰)

    Returns:
        축소된 컨텍스트
    """
    if len(context) <= max_chars:
        return context

    # 최근 컨텍스트 유지 비율 (70%)
    recent_size = int(max_chars * 0.7)
    summary_size = max_chars - recent_size

    # 컨텍스트를 라운드 단위로 분리
    rounds = context.split("\n---\n")

    if len(rounds) <= 1:
        # 라운드 구분이 없으면 단순 truncate
        return f"[...이전 대화 생략...]\n\n{context[-max_chars:]}"

    # 최근 라운드들 유지
    recent_rounds = []
    recent_chars = 0

    for round_text in reversed(rounds):
        if recent_chars + len(round_text) <= recent_size:
            recent_rounds.insert(0, round_text)
            recent_chars += len(round_text) + 5  # "\n---\n" 길이
        else:
            break

    # 오래된 라운드 요약
    old_rounds = rounds[:len(rounds) - len(recent_rounds)]
    if old_rounds:
        summary = f"[이전 {len(old_rounds)}개 라운드 요약: 토론 진행됨]"
    else:
        summary = ""

    result = summary + ("\n---\n" if summary else "") + "\n---\n".join(recent_rounds)
    return result


def cleanup_temp_files(directory: str, pattern: str = "tmpclaude-*"):
    """임시 파일 정리

    Args:
        directory: 정리할 디렉토리
        pattern: 삭제할 파일 패턴
    """
    try:
        temp_files = glob.glob(os.path.join(directory, pattern))
        deleted_count = 0
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
                deleted_count += 1
            except (OSError, PermissionError):
                pass  # 사용 중인 파일은 무시

        if deleted_count > 0:
            console.print(f"[dim]임시 파일 {deleted_count}개 정리됨[/dim]")
    except (OSError, PermissionError):
        pass  # 디렉토리 접근 오류 무시


def initialize_clients(config: dict) -> Tuple[Any, Any]:
    """API 클라이언트 초기화"""
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not google_key or google_key == "your_google_api_key_here":
        console.print("[red]GOOGLE_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.[/red]")
        sys.exit(1)

    if not openai_key or openai_key == "your_openai_api_key_here":
        console.print("[red]OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.[/red]")
        sys.exit(1)

    # Gemini 초기화
    try:
        import google.generativeai as genai
        genai.configure(api_key=google_key)
    except ImportError:
        console.print("[red]google-generativeai 라이브러리를 설치하세요: pip install google-generativeai[/red]")
        sys.exit(1)

    # OpenAI 초기화
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=openai_key)
    except ImportError:
        console.print("[red]openai 라이브러리를 설치하세요: pip install openai[/red]")
        sys.exit(1)

    return genai, openai_client


def select_model(options: dict, prompt_text: str) -> Tuple[str, str]:
    """모델 선택 UI"""
    console.print(f"\n[bold cyan]{prompt_text}[/bold cyan]")

    choices = list(options.keys())
    for idx, name in enumerate(choices, 1):
        console.print(f"  {idx}. {name}")

    while True:
        try:
            selection = Prompt.ask(
                "번호를 선택하세요",
                default="1"
            )
            idx = int(selection) - 1
            if 0 <= idx < len(choices):
                display_name = choices[idx]
                model_id = options[display_name]
                return display_name, model_id
        except (ValueError, IndexError):
            pass

        console.print(f"[yellow]1-{len(choices)} 사이의 번호를 입력하세요.[/yellow]")


def select_preset_question(config: dict) -> Optional[str]:
    """사전 정의된 질문 선택 UI"""
    preset_questions = config.get('preset_questions', {})

    if not preset_questions:
        return None

    # 모든 질문을 번호와 함께 표시
    console.print("\n[bold cyan]사전 정의된 질문 목록:[/bold cyan]")

    all_questions = []
    question_idx = 1

    for category, questions in preset_questions.items():
        console.print(f"\n  [bold yellow]【{category}】[/bold yellow]")
        for question in questions:
            # 질문이 너무 길면 줄여서 표시
            display_q = question if len(question) <= 60 else question[:57] + "..."
            console.print(f"    {question_idx}. {display_q}")
            all_questions.append(question)
            question_idx += 1

    console.print(f"\n  [dim]0. 직접 입력하기[/dim]")

    while True:
        try:
            selection = Prompt.ask(
                "\n질문 번호를 선택하세요 (0: 직접 입력)",
                default="0"
            )
            idx = int(selection)

            if idx == 0:
                return None  # 직접 입력 모드

            if 1 <= idx <= len(all_questions):
                selected = all_questions[idx - 1]
                console.print(f"\n[green]선택된 질문:[/green] {selected}")
                return selected

        except ValueError:
            pass

        console.print(f"[yellow]0-{len(all_questions)} 사이의 번호를 입력하세요.[/yellow]")


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def _call_gemini_api(genai_module, model_id: str, parts: List[Any]) -> str:
    """Gemini API 실제 호출 (재시도 로직 적용)"""
    model = genai_module.GenerativeModel(model_id)
    response = model.generate_content(parts)
    return response.text


def get_gemini_response(
    genai_module,
    model_id: str,
    system_prompt: str,
    history_context: str,
    current_prompt: str,
    files: List[Any]
) -> str:
    """Gemini API 호출 (컨텍스트 제한 및 재시도 로직 적용)"""
    try:
        # 프롬프트 구성
        parts = [system_prompt]

        # 히스토리 (있는 경우) - 컨텍스트 크기 제한 적용
        if history_context:
            truncated_history = truncate_context(history_context)
            parts.append(f"\n--- 이전 토론 기록 ---\n{truncated_history}\n--- 기록 끝 ---\n")

        # 현재 요청
        parts.append(f"\n{current_prompt}")

        # 파일 추가 (문자열 또는 File 객체)
        for f in files:
            parts.append(f)

        return _call_gemini_api(genai_module, model_id, parts)

    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
            return f"[Gemini 오류] 모델 '{model_id}'을(를) 사용할 수 없습니다. config.yaml에서 다른 모델을 선택하세요.\n상세: {error_msg}"
        return f"[Gemini 오류] {error_msg}"


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def _call_gpt_api(openai_client, create_params: dict) -> str:
    """GPT API 실제 호출 (재시도 로직 적용)"""
    response = openai_client.chat.completions.create(**create_params)
    return response.choices[0].message.content


def get_gpt_response(
    openai_client,
    model_id: str,
    system_prompt: str,
    history_context: str,
    current_prompt: str,
    file_contents: List[Dict[str, Any]]
) -> str:
    """GPT API 호출 (컨텍스트 제한 및 재시도 로직 적용)"""
    try:
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # 히스토리 (있는 경우) - 컨텍스트 크기 제한 적용
        if history_context:
            truncated_history = truncate_context(history_context)
            messages.append({
                "role": "user",
                "content": f"[이전 토론 기록]\n{truncated_history}\n[기록 끝]"
            })

        # 현재 요청 + 파일
        user_content = [{"type": "text", "text": current_prompt}]
        user_content.extend(file_contents)

        messages.append({
            "role": "user",
            "content": user_content
        })

        # GPT-5 계열은 max_tokens 대신 max_completion_tokens 사용
        create_params = {
            "model": model_id,
            "messages": messages,
        }

        # 모델에 따라 토큰 제한 파라미터 선택
        # GPT-5 계열은 reasoning tokens를 많이 사용하므로 충분히 높게 설정
        if "gpt-5" in model_id.lower():
            create_params["max_completion_tokens"] = 32000
        else:
            create_params["max_tokens"] = 16384

        return _call_gpt_api(openai_client, create_params)

    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
            return f"[GPT 오류] 모델 '{model_id}'을(를) 사용할 수 없습니다. config.yaml에서 다른 모델을 선택하세요.\n상세: {error_msg}"
        return f"[GPT 오류] {error_msg}"


def check_consensus(response: str, token: str) -> bool:
    """응답에 합의 토큰이 있는지 확인"""
    return token in response


def extract_final_conclusion(response: str, token: str) -> Optional[str]:
    """합의된 응답에서 최종 결론 추출"""
    # [AGREED] 토큰 이후의 내용을 추출
    if token in response:
        parts = response.split(token)
        if len(parts) > 1:
            conclusion = parts[1].strip()
            # "최종 결론:", "최종 합의:", "결론:" 등의 레이블 제거
            for label in ["최종 결론:", "최종 합의 내용 요약:", "최종 합의:", "결론:"]:
                if conclusion.startswith(label):
                    conclusion = conclusion[len(label):].strip()
            return conclusion if conclusion else None
    return None


def check_substantial_disagreement(response: str) -> bool:
    """응답에 실질적인 반론이 있는지 확인"""
    # 합의/동의를 나타내는 표현들
    agreement_phrases = [
        "전적으로 합의", "전적으로 동의", "완벽히 합의", "완벽히 동의",
        "완전히 동의", "완전히 합의", "이에 합의", "이에 동의",
        "합의에 도달", "합의합니다", "동의합니다", "타당합니다",
        "문제없음", "검증 결과 문제없음", "정확합니다", "올바릅니다"
    ]

    # 반론/지속 토론을 나타내는 표현들
    disagreement_phrases = [
        "계속 토론", "추가 논의", "반박", "오류가 있", "틀렸", "잘못",
        "수정이 필요", "보완이 필요", "동의하지 않", "동의할 수 없"
    ]

    response_lower = response.lower()

    # 명시적인 반론 표현이 있는지 확인
    has_disagreement = any(phrase in response for phrase in disagreement_phrases)

    # 합의 표현이 더 많은지 확인
    agreement_count = sum(1 for phrase in agreement_phrases if phrase in response)

    # "(계속 토론)" 이 있어도, 전체적으로 합의하는 내용이면 실질적 반론 없음으로 판단
    if has_disagreement and agreement_count >= 3:
        return False  # 합의 표현이 많으면 실질적 반론 없음

    return has_disagreement


def display_response(role: str, model_name: str, content: str, turn: int, config: dict):
    """응답 표시"""
    if config['system'].get('output_mode', 'verbose') == 'minimal':
        return

    if role == "gemini":
        color = "orange1"
        icon = "G"
    else:
        color = "green"
        icon = "O"

    title = f"[bold {color}]{icon} {role.upper()} ({model_name}) - Turn {turn}[/bold {color}]"

    # 마크다운 렌더링
    try:
        md = Markdown(content)
        console.print(Panel(md, title=title, border_style=color))
    except Exception:
        console.print(Panel(content, title=title, border_style=color))


def build_debate_prompt(
    current_date: str,
    user_query: str,
    opponent_name: str,
    opponent_model: str,
    last_response: str,
    consensus_token: str,
    is_first_turn: bool
) -> str:
    """토론 프롬프트 구성"""

    if is_first_turn:
        return f"""
[기준 날짜: {current_date}]

[사용자 질문]
{user_query}

[지시사항]
당신이 첫 번째 발언자입니다.
사용자의 질문에 대해 {current_date} 기준의 정확한 정보를 바탕으로 답변하세요.
첨부된 파일이 있다면 참고자료로 활용하세요.
"""
    else:
        return f"""
[기준 날짜: {current_date}]

[사용자 질문]
{user_query}

[상대방({opponent_name}, {opponent_model})의 발언]
{last_response}

[지시사항]
상대방 AI({opponent_name})의 위 발언을 검토하세요.

**핵심 확인 사항:**
1. 상대방의 정보가 {current_date} 기준으로 유효한가?
2. 논리적 오류나 사실 오류가 있는가?
3. 추가하거나 수정해야 할 중요한 내용이 있는가?

**결정:**
- 실질적인 문제가 있다면: 토론 모드로 상세히 검증하고 의견을 제시하세요.
- 상대방 의견이 충분히 좋고 핵심적인 이견이 없다면: "{consensus_token}"와 함께 최종 결론만 간결하게 출력하세요.

⚠️ 사소한 표현 차이로 토론을 길게 끌지 마세요. 핵심이 맞으면 빠르게 합의하세요.
"""


def run_debate_session(
    config: dict,
    genai_module,
    openai_client,
    gemini_model: Tuple[str, str],
    gpt_model: Tuple[str, str],
    file_processor: FileProcessor,
    html_logger: HtmlLogger,
    accumulated_context: str
):
    """토론 세션 실행"""

    consensus_token = config['system']['consensus_token']
    max_turns = config['system']['max_turns']
    delay = config['system'].get('delay_between_turns', 1)

    # 현재 날짜 가져오기
    current_date = get_current_date_str()

    # 시스템 프롬프트 구성 (날짜 주입)
    base_prompt = inject_date_into_prompt(
        config['prompts']['system_instruction'],
        current_date
    )
    gemini_additional = inject_date_into_prompt(
        config['prompts'].get('gemini_additional', ''),
        current_date
    )
    gpt_additional = inject_date_into_prompt(
        config['prompts'].get('gpt_additional', ''),
        current_date
    )

    gemini_system_prompt = base_prompt + "\n" + gemini_additional
    gpt_system_prompt = base_prompt + "\n" + gpt_additional

    while True:  # 추가 질문 루프
        console.rule("[bold blue]새 질문 입력[/bold blue]")
        console.print(f"[dim]현재 날짜: {current_date}[/dim]")

        # 1. 먼저 첨부파일 선택 (탐색기)
        if Confirm.ask("\n첨부파일을 추가하시겠습니까?", default=False):
            console.print("[cyan]파일 탐색기에서 파일을 선택하세요...[/cyan]")
            file_paths = select_files_dialog()
            if file_paths:
                console.print(f"[green]선택된 파일 {len(file_paths)}개:[/green]")
                for fp in file_paths:
                    console.print(f"  • {os.path.basename(fp)}")
            else:
                console.print("[dim]선택된 파일 없음[/dim]")
        else:
            file_paths = []

        # 파일 존재 확인
        valid_files = []
        for fp in file_paths:
            if os.path.exists(fp):
                valid_files.append(fp)
            else:
                console.print(f"[yellow]파일을 찾을 수 없음: {fp}[/yellow]")

        # 2. 질문 입력 (사전 정의 질문 선택 또는 직접 입력)
        preset_questions = config.get('preset_questions', {})

        if preset_questions:
            # 사전 정의 질문이 있으면 선택 옵션 제공
            if Confirm.ask("\n사전 정의된 질문에서 선택하시겠습니까?", default=True):
                user_query = select_preset_question(config)
                if user_query is None:
                    # 직접 입력 선택
                    user_query = Prompt.ask(
                        "\n질문을 입력하세요 (종료: 'exit' 또는 'quit')"
                    )
            else:
                user_query = Prompt.ask(
                    "\n질문을 입력하세요 (종료: 'exit' 또는 'quit')"
                )
        else:
            # 사전 정의 질문이 없으면 직접 입력
            user_query = Prompt.ask(
                "\n질문을 입력하세요 (종료: 'exit' 또는 'quit')"
            )

        if user_query.lower() in ('exit', 'quit', 'q'):
            console.print("[yellow]세션을 종료합니다.[/yellow]")
            break

        # HTML 로거에 세션 정보 설정
        html_logger.set_session_info(
            gemini_model[0],
            gpt_model[0],
            valid_files
        )

        # 사용자 질문 로깅 (날짜 포함)
        user_query_with_date = f"[{current_date}] {user_query}"
        html_logger.add_entry("User", "Human", user_query_with_date, valid_files)

        # 파일 전처리 (통합 처리로 I/O 최적화)
        console.print("\n[cyan]파일 처리 중...[/cyan]")
        processed_files = file_processor.process_files_unified(valid_files)
        gemini_files = processed_files['gemini']
        gpt_files = processed_files['gpt']

        # 토론 시작
        console.rule("[bold magenta]토론 시작[/bold magenta]")

        turn = 0
        gemini_agreed = False
        gpt_agreed = False
        first_agreement_by = None  # 먼저 합의한 AI 추적
        final_conclusion = None  # 최종 결론 저장

        # 현재 라운드 대화 기록
        round_context = f"[기준 날짜]: {current_date}\n[사용자 질문]: {user_query}\n[첨부파일]: {', '.join(valid_files) if valid_files else '없음'}\n"

        # 전체 컨텍스트 (이전 세션 포함)
        full_context = accumulated_context

        last_response = ""
        current_speaker = "gemini"  # Gemini 먼저 시작
        last_agreed_response = ""  # 합의한 AI의 마지막 응답 저장

        with console.status("[bold green]AI들이 토론 중...[/bold green]", spinner="dots"):
            while turn < max_turns or max_turns == 0:
                turn += 1

                # Rate limit 방지
                if turn > 1:
                    time.sleep(delay)

                if current_speaker == "gemini":
                    # Gemini의 프롬프트 구성
                    prompt = build_debate_prompt(
                        current_date=current_date,
                        user_query=user_query,
                        opponent_name="GPT",
                        opponent_model=gpt_model[0],
                        last_response=last_response,
                        consensus_token=consensus_token,
                        is_first_turn=(turn == 1)
                    )

                    response = get_gemini_response(
                        genai_module,
                        gemini_model[1],
                        gemini_system_prompt,
                        full_context + round_context,
                        prompt,
                        gemini_files
                    )

                    # 화면 출력
                    console.print()  # 줄바꿈
                    display_response("gemini", gemini_model[0], response, turn, config)

                    # 로깅
                    is_consensus = check_consensus(response, consensus_token)
                    html_logger.add_entry("Gemini", gemini_model[0], response, is_consensus=is_consensus)
                    round_context += f"\n[Gemini ({gemini_model[0]})]: {response}\n"

                    if is_consensus:
                        gemini_agreed = True
                        last_agreed_response = response
                        if not first_agreement_by:
                            first_agreement_by = "Gemini"
                        console.print("[bold orange1]Gemini가 합의를 표명했습니다.[/bold orange1]")
                        # 최종 결론 추출 시도
                        extracted = extract_final_conclusion(response, consensus_token)
                        if extracted:
                            final_conclusion = extracted

                    last_response = response
                    current_speaker = "gpt"

                else:  # GPT 차례
                    # GPT의 프롬프트 구성
                    prompt = build_debate_prompt(
                        current_date=current_date,
                        user_query=user_query,
                        opponent_name="Gemini",
                        opponent_model=gemini_model[0],
                        last_response=last_response,
                        consensus_token=consensus_token,
                        is_first_turn=False  # GPT는 항상 두 번째
                    )

                    response = get_gpt_response(
                        openai_client,
                        gpt_model[1],
                        gpt_system_prompt,
                        full_context + round_context,
                        prompt,
                        gpt_files
                    )

                    # 화면 출력
                    console.print()
                    display_response("gpt", gpt_model[0], response, turn, config)

                    # 로깅
                    is_consensus = check_consensus(response, consensus_token)
                    html_logger.add_entry("GPT", gpt_model[0], response, is_consensus=is_consensus)
                    round_context += f"\n[GPT ({gpt_model[0]})]: {response}\n"

                    if is_consensus:
                        gpt_agreed = True
                        last_agreed_response = response
                        if not first_agreement_by:
                            first_agreement_by = "GPT"
                        console.print("[bold green]GPT가 합의를 표명했습니다.[/bold green]")
                        # 최종 결론 추출 시도
                        extracted = extract_final_conclusion(response, consensus_token)
                        if extracted:
                            final_conclusion = extracted

                    last_response = response
                    current_speaker = "gemini"

                # 합의 확인 로직 개선
                # 1. 양쪽 모두 AGREED 출력
                if gemini_agreed and gpt_agreed:
                    console.print()
                    console.rule("[bold red]상호 합의 도출 완료![/bold red]")

                    # 최종 결론이 없으면 마지막 합의 응답에서 추출 시도
                    if not final_conclusion and last_agreed_response:
                        final_conclusion = extract_final_conclusion(last_agreed_response, consensus_token)

                    html_logger.add_entry(
                        "System",
                        "",
                        f"양측 AI가 합의에 도달했습니다. (총 {turn} 턴, 기준 날짜: {current_date})",
                        is_consensus=True
                    )
                    break

                # 2. 한쪽이 합의했는데 다른 쪽이 실질적 반론 없이 대화를 이어가는 경우 강제 종료
                if (gemini_agreed or gpt_agreed) and turn >= 4:
                    # 마지막 응답에 실질적인 반론이 없으면 암묵적 합의로 간주
                    if not check_substantial_disagreement(response):
                        console.print()
                        console.rule("[bold yellow]암묵적 합의 도출 (실질적 이견 없음)[/bold yellow]")

                        # 최종 결론 추출
                        if not final_conclusion:
                            final_conclusion = extract_final_conclusion(last_agreed_response, consensus_token)

                        html_logger.add_entry(
                            "System",
                            "",
                            f"한쪽 AI가 합의를 표명하고 상대방이 실질적 반론 없이 동의하여 토론을 종료합니다. (총 {turn} 턴, 기준 날짜: {current_date})",
                            is_consensus=True
                        )
                        gemini_agreed = True
                        gpt_agreed = True
                        break

        # 토론 종료
        if not (gemini_agreed and gpt_agreed):
            if max_turns > 0:
                console.print(f"\n[yellow]최대 턴 수({max_turns})에 도달하여 토론을 종료합니다.[/yellow]")
                html_logger.add_entry(
                    "System",
                    "",
                    f"최대 턴 수({max_turns})에 도달하여 토론이 종료되었습니다. (기준 날짜: {current_date})"
                )
                # 최대 턴 도달 시에도 마지막 응답에서 결론 추출 시도
                if not final_conclusion:
                    final_conclusion = last_response  # 마지막 응답 전체를 결론으로 사용

        # 최종 결론 표시
        if final_conclusion:
            console.print()
            console.rule("[bold magenta]최종 합의된 결론[/bold magenta]")
            try:
                md = Markdown(final_conclusion)
                console.print(Panel(md, title="[bold]Final Conclusion[/bold]", border_style="magenta"))
            except Exception:
                console.print(Panel(final_conclusion, title="[bold]Final Conclusion[/bold]", border_style="magenta"))

            # HTML에 최종 결론 추가
            html_logger.add_final_conclusion(final_conclusion, user_query, current_date)

        # HTML 파일 저장 (토론 종료 시 한 번만 저장 - 성능 최적화)
        html_logger.save()

        # 결과 저장 안내
        console.print(f"\n[dim]토론 기록 저장됨: {html_logger.filename}[/dim]")

        # 컨텍스트 누적 (추가 질문용)
        accumulated_context += round_context + "\n---\n"

        # 추가 질문 여부
        console.print()
        if not Confirm.ask("이 결과를 바탕으로 추가 질문을 하시겠습니까?"):
            break

    return accumulated_context


def main():
    """메인 함수"""
    console.clear()

    # 현재 날짜 표시
    current_date = get_current_date_str()

    console.print(Panel.fit(
        f"[bold magenta]AI Debate System[/bold magenta]\n"
        f"Gemini와 GPT가 1:1 토론하여 최적의 답변을 도출합니다\n"
        f"[dim]기준 날짜: {current_date}[/dim]",
        border_style="magenta"
    ))

    # 설정 로드
    config = load_config()

    # 임시 파일 정리 (프로그램 시작 시)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cleanup_temp_files(script_dir, "tmpclaude-*")

    # API 클라이언트 초기화
    console.print("\n[cyan]API 초기화 중...[/cyan]")
    genai_module, openai_client = initialize_clients(config)
    console.print("[green]API 초기화 완료[/green]")

    # 모델 선택
    gemini_display, gemini_id = select_model(
        config['models']['google'],
        "Gemini 모델을 선택하세요:"
    )

    gpt_display, gpt_id = select_model(
        config['models']['openai'],
        "GPT 모델을 선택하세요:"
    )

    # 선택 확인
    console.print()
    table = Table(title="선택된 모델")
    table.add_column("Provider", style="cyan")
    table.add_column("Display Name", style="green")
    table.add_column("Model ID", style="yellow")
    table.add_row("Google", gemini_display, gemini_id)
    table.add_row("OpenAI", gpt_display, gpt_id)
    console.print(table)

    # 유틸리티 초기화
    file_processor = FileProcessor(config)
    html_logger = HtmlLogger(config['system']['history_dir'], config)

    # 토론 세션 시작
    accumulated_context = ""
    run_debate_session(
        config=config,
        genai_module=genai_module,
        openai_client=openai_client,
        gemini_model=(gemini_display, gemini_id),
        gpt_model=(gpt_display, gpt_id),
        file_processor=file_processor,
        html_logger=html_logger,
        accumulated_context=accumulated_context
    )

    console.print("\n[bold green]프로그램을 종료합니다. 감사합니다![/bold green]")


if __name__ == "__main__":
    main()
