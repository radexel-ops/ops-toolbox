"""대화 시작 디버깅 - 왜 대화가 시작되지 않는지 확인"""
import asyncio
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5178"
OUTPUT_DIR = "./test_results/debug_start"

async def run_debug():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})

        # 모든 콘솔 로그 캡처
        all_logs = []
        page.on("console", lambda msg: all_logs.append(f"[{msg.type}] {msg.text}"))

        print("=" * 60)
        print("대화 시작 디버깅")
        print("=" * 60)

        # 1. 페이지 로드
        print("\n[1] 페이지 로드...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # 2. 페이지 분석
        print("\n[2] 페이지 요소 분석...")

        # 모든 버튼 찾기
        buttons = await page.locator('button').all()
        print(f"\n  버튼 목록 ({len(buttons)}개):")
        for i, btn in enumerate(buttons[:15]):
            text = await btn.inner_text()
            classes = await btn.get_attribute('class') or ''
            disabled = await btn.is_disabled()
            print(f"    [{i}] text='{text[:20]}' class='{classes[:30]}' disabled={disabled}")

        # 모든 input/textarea 찾기
        inputs = await page.locator('input, textarea').all()
        print(f"\n  입력 필드 ({len(inputs)}개):")
        for i, inp in enumerate(inputs[:10]):
            tag = await inp.evaluate('el => el.tagName')
            placeholder = await inp.get_attribute('placeholder') or ''
            disabled = await inp.is_disabled()
            print(f"    [{i}] {tag} placeholder='{placeholder[:30]}' disabled={disabled}")

        # 3. 주제 입력
        print("\n[3] 주제 입력 시도...")
        textarea = page.locator('textarea').first
        if await textarea.count() > 0:
            is_disabled = await textarea.is_disabled()
            print(f"  textarea 발견, disabled={is_disabled}")

            if not is_disabled:
                await textarea.click()
                await textarea.fill("테스트 주제입니다")
                current_value = await textarea.input_value()
                print(f"  입력된 값: '{current_value}'")
            else:
                print("  ⚠ textarea가 비활성화됨!")
        else:
            print("  ✗ textarea 없음")

        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_after_input.png")

        # 4. 시작 버튼 찾기 및 클릭
        print("\n[4] 시작 버튼 찾기...")

        # 다양한 셀렉터 시도
        selectors = [
            ('button[type="submit"]', 'submit 타입'),
            ('.send-btn', 'send-btn 클래스'),
            ('button:has(svg)', 'SVG 포함 버튼'),
            ('button.btn-primary', 'primary 버튼'),
            ('.input-area button', 'input-area 내 버튼'),
            ('.setup-form button', 'setup-form 내 버튼'),
        ]

        clicked = False
        for selector, desc in selectors:
            btn = page.locator(selector).first
            if await btn.count() > 0:
                disabled = await btn.is_disabled()
                visible = await btn.is_visible()
                print(f"  [{desc}] found, disabled={disabled}, visible={visible}")

                if not disabled and visible and not clicked:
                    print(f"  → 클릭 시도: {selector}")
                    await btn.click()
                    clicked = True
                    await page.wait_for_timeout(2000)
                    break

        if not clicked:
            print("  ✗ 클릭 가능한 시작 버튼 없음!")

        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_after_click.png")

        # 5. 결과 확인
        print("\n[5] 결과 확인...")
        await page.wait_for_timeout(3000)

        # URL 확인
        current_url = page.url
        print(f"  현재 URL: {current_url}")

        # 대화 화면인지 확인
        conv_area = page.locator('.conversation-area, .chat-area, .message-area')
        if await conv_area.count() > 0:
            print("  ✓ 대화 영역 발견!")
        else:
            print("  ✗ 대화 영역 없음 - 아직 설정 화면")

        # 에이전트 칩 확인
        agent_chips = page.locator('.agent-chip')
        if await agent_chips.count() > 0:
            print(f"  ✓ 에이전트 칩 {await agent_chips.count()}개 발견")
        else:
            print("  ✗ 에이전트 칩 없음")

        # 에러 메시지 확인
        errors = page.locator('.error, [class*="error"], .alert-error')
        if await errors.count() > 0:
            error_text = await errors.first.inner_text()
            print(f"  ⚠ 에러 발견: {error_text[:100]}")

        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_final.png")

        # 6. 콘솔 로그 분석
        print("\n[6] 콘솔 로그 분석...")
        errors = [l for l in all_logs if '[error]' in l.lower() or 'error' in l.lower()]
        ws_logs = [l for l in all_logs if 'ws' in l.lower()]

        if errors:
            print(f"  에러 로그 ({len(errors)}개):")
            for e in errors[:5]:
                print(f"    - {e[:80]}")

        if ws_logs:
            print(f"  WebSocket 로그 ({len(ws_logs)}개):")
            for w in ws_logs[:5]:
                print(f"    - {w[:80]}")

        # 7. 수동 대기 (화면 확인용)
        print("\n[7] 5초 대기 (화면 확인)...")
        await page.wait_for_timeout(5000)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_wait_final.png")

        print("\n" + "=" * 60)
        print(f"스크린샷 저장: {OUTPUT_DIR}")
        print("=" * 60)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_debug())
