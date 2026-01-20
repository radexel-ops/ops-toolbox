"""
테스트 플로우 1: 기본 대화 + 네비게이션
목적: 대화 중 화면 이동 시 상태 보존 검증

시작 → API 키 설정 확인 → 새 대화 시작 → 3턴 진행
    → [일시정지] → 과거 대화 목록 이동 → 다시 현재 대화로 복귀
    → 대화 기록 유지 확인 → [재개] → 정상 진행 확인
"""
import asyncio
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5178"
OUTPUT_DIR = "./test_results/flow_1"

async def run_test():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")

    def screenshot(name):
        return f"{OUTPUT_DIR}/{timestamp}_{name}.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=300)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        # 콘솔 로그 캡처
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        print("=" * 60)
        print("테스트 플로우 1: 기본 대화 + 네비게이션")
        print("=" * 60)

        # Step 1: 페이지 로드
        print("\n[Step 1] 페이지 로드...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=screenshot("01_initial"))
        print(f"  ✓ 스크린샷: {screenshot('01_initial')}")

        # Step 2: API 키 설정 상태 확인
        print("\n[Step 2] API 키 설정 상태 확인...")
        # 입력 필드가 활성화되어 있는지 확인
        topic_input = page.locator('textarea').first
        is_disabled = await topic_input.is_disabled() if await topic_input.count() > 0 else True

        if is_disabled:
            print("  ⚠ 입력 필드 비활성화 - API 키 설정 필요")
            # 설정 버튼 찾기
            settings_btn = page.locator('button:has-text("설정"), .settings-btn, [class*="setting"]').first
            if await settings_btn.count() > 0:
                await settings_btn.click()
                await page.wait_for_timeout(1000)
                await page.screenshot(path=screenshot("02_settings_panel"))
                print(f"  ✓ 설정 패널 열림")
            else:
                print("  ✗ 설정 버튼을 찾을 수 없음")
        else:
            print("  ✓ 입력 필드 활성화됨 - API 키 설정됨")

        await page.screenshot(path=screenshot("02_api_status"))

        # Step 3: 새 대화 시작
        print("\n[Step 3] 새 대화 시작...")
        topic_input = page.locator('textarea').first

        if await topic_input.count() > 0 and not await topic_input.is_disabled():
            await topic_input.fill("인공지능의 미래에 대해 토론해주세요")
            await page.screenshot(path=screenshot("03_topic_entered"))
            print("  ✓ 주제 입력 완료")

            # 시작 버튼 클릭
            start_btn = page.locator('button[type="submit"], .send-btn, button:has-text("시작")').first
            if await start_btn.count() > 0:
                await start_btn.click()
                print("  ✓ 시작 버튼 클릭")
                await page.wait_for_timeout(2000)
                await page.screenshot(path=screenshot("03_conversation_started"))
            else:
                print("  ✗ 시작 버튼을 찾을 수 없음")
        else:
            print("  ✗ 주제 입력 불가 - API 키 설정 필요")
            await page.screenshot(path=screenshot("03_cannot_start"))
            await browser.close()
            return

        # Step 4: 3턴 진행 대기
        print("\n[Step 4] 대화 진행 대기 (약 30초)...")
        message_count_prev = 0
        turn_count = 0

        for i in range(30):  # 최대 30초 대기
            await page.wait_for_timeout(1000)

            # 메시지 수 확인
            messages = page.locator('.message-content, .agent-message, [class*="message-bubble"]')
            current_count = await messages.count()

            if current_count > message_count_prev:
                turn_count += 1
                message_count_prev = current_count
                print(f"  [{i+1}초] 메시지 {current_count}개 (턴 {turn_count})")

                if turn_count >= 3:
                    print("  ✓ 3턴 완료!")
                    break

            # 에러 확인
            error_el = page.locator('.error, [class*="error"]')
            if await error_el.count() > 0:
                error_text = await error_el.first.inner_text()
                print(f"  ✗ 에러 발생: {error_text[:100]}")
                await page.screenshot(path=screenshot("04_error"))
                break

        await page.screenshot(path=screenshot("04_after_3_turns"))
        print(f"  현재 메시지 수: {message_count_prev}")

        # Step 5: 일시정지
        print("\n[Step 5] 일시정지...")
        pause_btn = page.locator('button:has-text("일시정지"), button:has-text("Pause"), .pause-btn, [class*="pause"]').first

        if await pause_btn.count() > 0:
            await pause_btn.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=screenshot("05_paused"))
            print("  ✓ 일시정지 완료")
        else:
            print("  ✗ 일시정지 버튼을 찾을 수 없음")
            # 버튼 목록 출력
            buttons = page.locator('button')
            btn_count = await buttons.count()
            print(f"  현재 버튼 수: {btn_count}")
            for j in range(min(btn_count, 10)):
                btn_text = await buttons.nth(j).inner_text()
                print(f"    - {btn_text[:30]}")

        # Step 6: 과거 대화 목록으로 이동
        print("\n[Step 6] 과거 대화 목록으로 이동...")
        # 사이드바 또는 메뉴에서 과거 대화 찾기
        past_btn = page.locator('button:has-text("과거"), button:has-text("기록"), button:has-text("히스토리"), .history-btn, [class*="history"], [class*="past"]').first
        sidebar_item = page.locator('.sidebar-item, .conversation-item, [class*="conversation-list"] > *').first

        if await past_btn.count() > 0:
            await past_btn.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=screenshot("06_past_conversations"))
            print("  ✓ 과거 대화 목록으로 이동")
        elif await sidebar_item.count() > 0:
            await sidebar_item.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=screenshot("06_sidebar_clicked"))
            print("  ✓ 사이드바 항목 클릭")
        else:
            print("  ⚠ 과거 대화 버튼/목록을 찾을 수 없음")
            await page.screenshot(path=screenshot("06_no_past_btn"))

        # Step 7: 다시 현재 대화로 복귀
        print("\n[Step 7] 현재 대화로 복귀...")
        await page.wait_for_timeout(2000)

        # 새 대화 또는 돌아가기 버튼
        back_btn = page.locator('button:has-text("돌아가기"), button:has-text("현재"), button:has-text("Back"), .back-btn').first
        new_chat_btn = page.locator('button:has-text("새 대화"), button:has-text("New"), .new-chat-btn').first

        # 현재 대화 항목 클릭 시도
        current_conv = page.locator('.conversation-item.active, .conversation-item:first-child, [class*="conversation"]:first-child').first

        if await back_btn.count() > 0:
            await back_btn.click()
            print("  ✓ 돌아가기 버튼 클릭")
        elif await current_conv.count() > 0:
            await current_conv.click()
            print("  ✓ 현재 대화 항목 클릭")
        else:
            print("  ⚠ 복귀 방법을 찾을 수 없음")

        await page.wait_for_timeout(2000)
        await page.screenshot(path=screenshot("07_returned"))

        # Step 8: 대화 기록 유지 확인 (핵심 검증!)
        print("\n[Step 8] ★ 대화 기록 유지 확인 ★")
        messages_after = page.locator('.message-content, .agent-message, [class*="message-bubble"]')
        count_after = await messages_after.count()

        print(f"  복귀 전 메시지 수: {message_count_prev}")
        print(f"  복귀 후 메시지 수: {count_after}")

        if count_after >= message_count_prev:
            print("  ✓ 대화 기록 유지됨!")
        else:
            print("  ✗ ★ 버그 발견! 대화 기록 손실됨 ★")
            await page.screenshot(path=screenshot("08_BUG_data_loss"))

        await page.screenshot(path=screenshot("08_message_check"))

        # Step 9: 재개 시도
        print("\n[Step 9] 재개 시도...")
        resume_btn = page.locator('button:has-text("재개"), button:has-text("Resume"), button:has-text("계속"), .resume-btn').first

        if await resume_btn.count() > 0:
            await resume_btn.click()
            await page.wait_for_timeout(3000)
            await page.screenshot(path=screenshot("09_resumed"))
            print("  ✓ 재개 버튼 클릭")

            # 새 메시지가 추가되는지 확인
            messages_new = page.locator('.message-content, .agent-message, [class*="message-bubble"]')
            count_new = await messages_new.count()

            if count_new > count_after:
                print(f"  ✓ 대화 정상 진행 중 (메시지: {count_new})")
            else:
                print(f"  ⚠ 대화가 진행되지 않음 (메시지: {count_new})")
        else:
            print("  ✗ 재개 버튼을 찾을 수 없음")
            await page.screenshot(path=screenshot("09_no_resume_btn"))

        # 최종 상태
        print("\n[최종] 테스트 완료")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=screenshot("10_final"))

        # 콘솔 에러 확인
        if errors:
            print(f"\n⚠ 콘솔 에러 {len(errors)}개 발견:")
            for err in errors[:5]:
                print(f"  - {err[:100]}")

        print("\n" + "=" * 60)
        print(f"스크린샷 저장 위치: {OUTPUT_DIR}")
        print("=" * 60)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
