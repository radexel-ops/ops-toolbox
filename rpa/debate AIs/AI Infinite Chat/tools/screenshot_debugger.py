"""
AI Infinite Chat - 스크린샷 디버깅 도구
=========================================
Playwright를 사용하여 웹 앱의 상태를 스크린샷으로 캡처하고
콘솔 로그, WebSocket 메시지 등을 분석하는 표준 디버깅 도구입니다.

사용법:
    python tools/screenshot_debugger.py [URL] [--headless] [--output DIR]

예시:
    python tools/screenshot_debugger.py                           # 기본 URL 사용
    python tools/screenshot_debugger.py http://localhost:5178     # 특정 URL 지정
    python tools/screenshot_debugger.py --headless                # 헤드리스 모드
    python tools/screenshot_debugger.py --output ./debug_output   # 출력 디렉토리 지정

요구사항:
    pip install playwright
    playwright install chromium
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 기본 설정
DEFAULT_URL = "http://localhost:5173"
DEFAULT_OUTPUT_DIR = "./debug_screenshots"


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description='AI Infinite Chat 스크린샷 디버깅 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'url',
        nargs='?',
        default=DEFAULT_URL,
        help=f'테스트할 URL (기본값: {DEFAULT_URL})'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='헤드리스 모드로 실행 (브라우저 창 숨김)'
    )
    parser.add_argument(
        '--output', '-o',
        default=DEFAULT_OUTPUT_DIR,
        help=f'스크린샷 저장 디렉토리 (기본값: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--wait', '-w',
        type=int,
        default=10,
        help='대화 모니터링 시간 (초, 기본값: 10)'
    )
    parser.add_argument(
        '--topic', '-t',
        default='인공지능이 인류에 미치는 영향',
        help='테스트할 대화 주제'
    )
    return parser.parse_args()


async def debug_conversation(url: str, headless: bool, output_dir: str, wait_time: int, topic: str):
    """메인 디버깅 함수"""

    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def screenshot_path(name: str) -> str:
        return os.path.join(output_dir, f"{timestamp}_{name}.png")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        console_logs = []
        ws_messages = []

        # 콘솔 로그 캡처
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"[PAGE ERROR] {err}"))

        # WebSocket 메시지 캡처
        async def handle_ws(ws):
            print(f"\n[WS] 연결됨: {ws.url}")
            ws.on("framesent", lambda payload: ws_messages.append(f"[SENT] {payload}"))
            ws.on("framereceived", lambda payload: ws_messages.append(f"[RECV] {payload}"))
            ws.on("close", lambda: print("[WS] 연결 종료"))

        page.on("websocket", handle_ws)

        print("=" * 60)
        print("AI Infinite Chat - 스크린샷 디버깅 도구")
        print("=" * 60)
        print(f"URL: {url}")
        print(f"출력 디렉토리: {output_dir}")
        print(f"헤드리스 모드: {headless}")
        print("=" * 60)

        # 1. 페이지 로드
        print("\n[1] 페이지 로드 중...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"    [ERROR] 페이지 로드 실패: {e}")
            await page.screenshot(path=screenshot_path("01_load_error"))
            await browser.close()
            return

        await page.wait_for_timeout(2000)
        await page.screenshot(path=screenshot_path("01_initial_load"))
        print(f"    스크린샷 저장: {screenshot_path('01_initial_load')}")

        # 페이지 상태 확인
        title = await page.title()
        print(f"    페이지 타이틀: {title}")

        # 2. 입력 필드 상태 확인
        print("\n[2] 입력 필드 상태 확인...")
        topic_input = page.locator('.unified-textarea').first

        if await topic_input.count() > 0:
            is_disabled = await topic_input.is_disabled()
            placeholder = await topic_input.get_attribute("placeholder") or ""
            print(f"    비활성화 상태: {is_disabled}")
            print(f"    Placeholder: {placeholder}")

            if is_disabled:
                body_text = await page.locator("body").inner_text()
                if "API 키" in body_text:
                    print("    [WARNING] API 키 설정이 필요합니다")
                await page.screenshot(path=screenshot_path("02_disabled_input"))
        else:
            print("    [WARNING] 입력 필드를 찾을 수 없음")

        # 3. 주제 입력
        print("\n[3] 주제 입력...")
        if await topic_input.count() > 0 and not await topic_input.is_disabled():
            await topic_input.fill(topic)
            print(f"    주제 입력 완료: {topic}")
            await page.screenshot(path=screenshot_path("03_topic_entered"))
        else:
            print("    [SKIP] 입력 필드가 비활성화됨")

        # 4. 시작 버튼 클릭
        print("\n[4] 시작 버튼 클릭...")
        start_btn = page.locator('.send-btn').first

        if await start_btn.count() > 0:
            is_disabled = await start_btn.is_disabled()
            print(f"    버튼 비활성화 상태: {is_disabled}")

            if not is_disabled:
                await start_btn.click()
                print("    버튼 클릭 완료")
                await page.wait_for_timeout(500)
                await page.screenshot(path=screenshot_path("04_after_click"))
            else:
                print("    [SKIP] 버튼이 비활성화됨")

        # 5. 대화 진행 모니터링
        print(f"\n[5] 대화 진행 모니터링 ({wait_time}초)...")

        for i in range(wait_time):
            await page.wait_for_timeout(1000)

            # 메시지 수 확인
            messages = page.locator('.message, .agent-message, [class*="message"]')
            msg_count = await messages.count()

            # 에이전트 상태 확인
            agent_chips = page.locator('.agent-chip')
            chip_count = await agent_chips.count()

            # 현재 말하는 에이전트 확인
            speaking = page.locator('.agent-chip.speaking, .agent-chip.active, [class*="speaking"]')
            speaking_count = await speaking.count()

            print(f"    [{i+1}초] 메시지: {msg_count}개, 에이전트: {chip_count}개, 발언중: {speaking_count}")

            # 에러 메시지 확인
            error_el = page.locator('.error, [class*="error"], .alert')
            if await error_el.count() > 0:
                error_text = await error_el.first.inner_text()
                print(f"    [ERROR] {error_text[:100]}")
                await page.screenshot(path=screenshot_path(f"05_error_at_{i+1}s"))

        # 6. 최종 상태 스크린샷
        print("\n[6] 최종 상태 저장...")
        await page.screenshot(path=screenshot_path("06_final_state"))
        print(f"    스크린샷 저장: {screenshot_path('06_final_state')}")

        # 7. 콘솔 로그 분석
        print("\n[7] 콘솔 로그 분석...")
        errors = [log for log in console_logs if 'error' in log.lower()]
        ws_logs = [log for log in console_logs if 'ws' in log.lower() or 'websocket' in log.lower()]

        if errors:
            print(f"    에러 로그 {len(errors)}개:")
            for err in errors[:5]:
                print(f"      - {err[:150]}")

        if ws_logs:
            print(f"    WebSocket 로그 {len(ws_logs)}개:")
            for ws in ws_logs[:5]:
                print(f"      - {ws[:150]}")

        # 8. WebSocket 메시지 분석
        print("\n[8] WebSocket 메시지 분석...")
        print(f"    총 {len(ws_messages)}개 메시지")

        sent = [m for m in ws_messages if m.startswith("[SENT]")]
        recv = [m for m in ws_messages if m.startswith("[RECV]")]

        print(f"    송신: {len(sent)}개")
        print(f"    수신: {len(recv)}개")

        if recv:
            print("    수신 메시지 샘플:")
            for msg in recv[:5]:
                print(f"      - {msg[:200]}")

        # 9. HTML 구조 확인
        print("\n[9] 대화 영역 HTML 구조 확인...")
        conversation_area = page.locator('.conversation-area, .chat-area, .messages-container, [class*="conversation"]')
        if await conversation_area.count() > 0:
            html = await conversation_area.first.inner_html()
            print(f"    HTML 길이: {len(html)}")
            if len(html) < 500:
                print(f"    내용: {html}")
            else:
                print(f"    내용 (앞 500자): {html[:500]}...")

        await browser.close()

        print("\n" + "=" * 60)
        print("디버깅 완료")
        print(f"스크린샷 저장 위치: {output_dir}")
        print("=" * 60)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(debug_conversation(
        url=args.url,
        headless=args.headless,
        output_dir=args.output,
        wait_time=args.wait,
        topic=args.topic
    ))
