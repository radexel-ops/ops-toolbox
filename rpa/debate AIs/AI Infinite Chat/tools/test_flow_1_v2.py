"""
테스트 플로우 1 (v2): 기본 대화 + 네비게이션 - 버그 재현
목적: 대화 중 화면 이동 시 상태 보존 검증

핵심 버그: 대화 진행 중 과거 대화 목록 이동 후 복귀 시 대화 기록 손실
"""
import asyncio
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5178"
OUTPUT_DIR = "./test_results/flow_1_v2"

async def run_test():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")

    def ss(name):
        path = f"{OUTPUT_DIR}/{timestamp}_{name}.png"
        print(f"  📸 {name}")
        return path

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        print("=" * 70)
        print("테스트 플로우 1 (v2): 대화 중 네비게이션 상태 보존 검증")
        print("=" * 70)

        # ===== Step 1: 페이지 로드 =====
        print("\n[1/10] 페이지 로드...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=ss("01_loaded"))

        # ===== Step 2: 새 대화 시작 =====
        print("\n[2/10] 새 대화 시작...")

        # 주제 입력
        topic_input = page.locator('textarea').first
        if await topic_input.count() > 0:
            await topic_input.fill("AI와 인류의 미래")
            await page.screenshot(path=ss("02a_topic"))

            # 시작 버튼
            start_btn = page.locator('button[type="submit"]').first
            if await start_btn.count() > 0 and not await start_btn.is_disabled():
                await start_btn.click()
                print("  ✓ 대화 시작됨")
            else:
                # 다른 시작 버튼 찾기
                alt_btn = page.locator('.send-btn, button:has(svg)').first
                if await alt_btn.count() > 0:
                    await alt_btn.click()
                    print("  ✓ 대화 시작됨 (대체 버튼)")
        else:
            print("  ✗ 입력 필드 없음 - API 키 설정 필요")
            await page.screenshot(path=ss("02_error_no_input"))
            await browser.close()
            return

        await page.wait_for_timeout(3000)
        await page.screenshot(path=ss("02b_started"))

        # ===== Step 3: 대화 진행 대기 (최소 2턴) =====
        print("\n[3/10] 대화 진행 대기...")

        def count_messages():
            return page.locator('.message-bubble, .agent-message, [class*="message-content"]')

        initial_count = 0
        for i in range(25):  # 최대 25초
            await page.wait_for_timeout(1000)
            current = await count_messages().count()
            if current > initial_count:
                initial_count = current
                print(f"  [{i+1}s] 메시지: {current}개")

            if current >= 2:  # 최소 2개 메시지
                break

        await page.screenshot(path=ss("03_messages"))
        msg_before_nav = await count_messages().count()
        print(f"  ✓ 현재 메시지 수: {msg_before_nav}")

        # ===== Step 4: 일시정지 =====
        print("\n[4/10] 일시정지...")

        # 올바른 셀렉터: .btn-control.playing 또는 title 속성 사용
        pause_btn = page.locator('.btn-control.playing, button[title="일시정지"]').first

        if await pause_btn.count() > 0:
            await pause_btn.click()
            await page.wait_for_timeout(1000)
            print("  ✓ 일시정지 클릭")
        else:
            print("  ⚠ 일시정지 버튼 찾기 실패, 계속 진행...")

        await page.screenshot(path=ss("04_paused"))

        # ===== Step 5: 현재 대화 ID 및 상태 기록 =====
        print("\n[5/10] 현재 상태 기록...")

        # 사이드바에서 현재 대화 찾기
        current_conv = page.locator('.sidebar .conversation-item, .conversation-list > div').first
        conv_title = ""
        if await current_conv.count() > 0:
            conv_title = await current_conv.inner_text()
            print(f"  현재 대화: {conv_title[:30]}...")

        # 대화 내용 일부 기록
        first_msg = page.locator('.message-bubble, .agent-message').first
        msg_preview = ""
        if await first_msg.count() > 0:
            msg_preview = await first_msg.inner_text()
            print(f"  첫 메시지 미리보기: {msg_preview[:50]}...")

        # ===== Step 6: 새 대화 버튼 클릭 (다른 화면으로 이동) =====
        print("\n[6/10] 새 대화 버튼 클릭 (화면 전환)...")

        new_chat_btn = page.locator('button:has-text("+"), .new-chat-btn, button[title*="새"]').first
        # 또는 사이드바 상단의 + 버튼
        plus_btn = page.locator('.sidebar button:has(svg), .sidebar-header button').first

        if await new_chat_btn.count() > 0:
            await new_chat_btn.click()
            print("  ✓ 새 대화 버튼 클릭")
        elif await plus_btn.count() > 0:
            await plus_btn.click()
            print("  ✓ + 버튼 클릭")
        else:
            print("  ⚠ 새 대화 버튼 찾기 실패")

        await page.wait_for_timeout(2000)
        await page.screenshot(path=ss("06_new_chat_screen"))

        # ===== Step 7: 원래 대화로 복귀 =====
        print("\n[7/10] 원래 대화로 복귀...")

        # 사이드바에서 이전 대화 클릭
        prev_conv = page.locator('.sidebar .conversation-item, .conversation-list > div').first

        if await prev_conv.count() > 0:
            await prev_conv.click()
            print("  ✓ 이전 대화 클릭")
        else:
            print("  ✗ 이전 대화를 찾을 수 없음")

        await page.wait_for_timeout(2000)
        await page.screenshot(path=ss("07_returned"))

        # ===== Step 8: ★ 핵심 검증: 대화 기록 유지 확인 ★ =====
        print("\n[8/10] ★★★ 핵심 검증: 대화 기록 유지 확인 ★★★")

        msg_after_nav = await count_messages().count()

        print(f"\n  ┌────────────────────────────────────┐")
        print(f"  │ 네비게이션 전 메시지: {msg_before_nav:3}개          │")
        print(f"  │ 네비게이션 후 메시지: {msg_after_nav:3}개          │")
        print(f"  └────────────────────────────────────┘")

        if msg_after_nav >= msg_before_nav:
            print("\n  ✅ PASS: 대화 기록 유지됨!")
        else:
            print("\n  ❌ FAIL: 대화 기록 손실!")
            print(f"     손실된 메시지: {msg_before_nav - msg_after_nav}개")
            await page.screenshot(path=ss("08_BUG_DATA_LOSS"))

        # 메시지 내용도 확인
        first_msg_after = page.locator('.message-bubble, .agent-message').first
        if await first_msg_after.count() > 0:
            msg_after_text = await first_msg_after.inner_text()
            if msg_preview and msg_preview[:30] in msg_after_text:
                print("  ✅ 메시지 내용 일치 확인")
            else:
                print("  ⚠ 메시지 내용 불일치 또는 확인 불가")

        await page.screenshot(path=ss("08_verification"))

        # ===== Step 9: 재개 시도 =====
        print("\n[9/10] 재개 시도...")

        resume_btn = page.locator('.btn-control.paused, button[title="재개"]').first

        if await resume_btn.count() > 0:
            await resume_btn.click()
            await page.wait_for_timeout(3000)
            print("  ✓ 재개 클릭")

            # 새 메시지 추가되는지 확인
            msg_after_resume = await count_messages().count()
            if msg_after_resume > msg_after_nav:
                print(f"  ✅ 대화 정상 진행 (메시지: {msg_after_resume})")
            else:
                print(f"  ⚠ 대화 진행 안됨 (메시지: {msg_after_resume})")
        else:
            # 이미 진행 중일 수 있음
            print("  ⚠ 재개 버튼 없음 (이미 진행 중?)")

        await page.screenshot(path=ss("09_resumed"))

        # ===== Step 10: 최종 상태 =====
        print("\n[10/10] 최종 상태 확인...")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=ss("10_final"))

        # 에러 요약
        if errors:
            print(f"\n⚠ 콘솔 에러 {len(errors)}개:")
            for e in errors[:3]:
                print(f"  - {e[:80]}")

        print("\n" + "=" * 70)
        print("테스트 완료")
        print(f"스크린샷: {OUTPUT_DIR}")
        print("=" * 70)

        # 결과 요약
        print("\n📊 결과 요약:")
        if msg_after_nav >= msg_before_nav:
            print("  [PASS] 네비게이션 후 데이터 보존 확인")
        else:
            print("  [FAIL] 네비게이션 후 데이터 손실 발생!")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
