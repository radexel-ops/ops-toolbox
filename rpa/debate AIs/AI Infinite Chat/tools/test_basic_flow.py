"""단순 대화 흐름 테스트 - 네비게이션 없이 대화만 테스트"""
import asyncio
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5178"
OUTPUT_DIR = "./test_results/basic_flow"

async def run_test():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})

        all_logs = []
        page.on("console", lambda msg: all_logs.append(f"[{msg.type}] {msg.text}"))

        print("=" * 60)
        print("단순 대화 흐름 테스트")
        print("=" * 60)

        # 1. 페이지 로드
        print("\n[1] 페이지 로드...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_01_loaded.png")

        # 2. 주제 입력
        print("\n[2] 주제 입력...")
        textarea = page.locator('textarea').first
        await textarea.fill("인공지능의 미래")
        await page.wait_for_timeout(500)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_02_topic.png")

        # 3. 시작 버튼 클릭
        print("\n[3] 시작 버튼 클릭...")
        send_btn = page.locator('.send-btn').first
        if await send_btn.count() > 0:
            # 버튼이 활성화될 때까지 대기
            await page.wait_for_timeout(500)
            await send_btn.click()
            print("  ✓ 클릭됨")
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_03_clicked.png")

        # 4. 대화 시작 대기 (60초 동안 관찰)
        print("\n[4] 대화 진행 관찰 (60초)...")

        for i in range(60):
            await page.wait_for_timeout(1000)

            # 메시지 버블 확인 (여러 셀렉터 시도)
            msg_bubbles = page.locator('.message-bubble, .message-content')
            bubble_count = await msg_bubbles.count()

            # 에이전트 칩 상태
            speaking = page.locator('.agent-chip.speaking, [class*="agent-chip"]')
            speaking_count = await speaking.count()

            # 입력 중 상태
            typing = page.locator('[class*="typing"], .typing-indicator')
            typing_count = await typing.count()

            # 실제 텍스트 내용 확인
            all_text = ""
            if bubble_count > 0:
                try:
                    all_text = await msg_bubbles.first.inner_text()
                    all_text = all_text[:50] + "..." if len(all_text) > 50 else all_text
                except:
                    pass

            print(f"  [{i+1:2}초] 메시지: {bubble_count}, 에이전트: {speaking_count}, 타이핑: {typing_count} | {all_text}")

            # 5초, 15초, 30초, 60초에 스크린샷
            if i+1 in [5, 15, 30, 45, 60]:
                await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_04_{i+1}s.png")
                print(f"        📸 스크린샷 저장")

            # 메시지가 2개 이상이면 성공으로 간주
            if bubble_count >= 2:
                print(f"\n  ✅ 대화 정상 진행 확인! ({bubble_count}개 메시지)")
                break

        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_05_final.png")

        # 5. 콘솔 로그 분석
        print("\n[5] 콘솔 로그 분석...")
        errors = [l for l in all_logs if 'error' in l.lower()]
        ws_logs = [l for l in all_logs if 'ws' in l.lower()]

        print(f"  전체 로그: {len(all_logs)}개")
        print(f"  에러: {len(errors)}개")
        print(f"  WebSocket 관련: {len(ws_logs)}개")

        if errors:
            print("\n  에러 로그:")
            for e in errors[:10]:
                print(f"    - {e[:100]}")

        if ws_logs:
            print("\n  WebSocket 로그:")
            for w in ws_logs[-10:]:
                print(f"    - {w[:100]}")

        print("\n" + "=" * 60)
        print(f"스크린샷: {OUTPUT_DIR}")
        print("=" * 60)

        # 브라우저 잠시 유지
        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
