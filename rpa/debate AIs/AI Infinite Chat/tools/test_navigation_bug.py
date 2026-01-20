"""네비게이션 버그 테스트 - 대화 중 다른 화면으로 이동 후 복귀"""
import asyncio
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5178"
OUTPUT_DIR = "./test_results/nav_bug"

async def run_test():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})

        print("=" * 60)
        print("네비게이션 버그 테스트")
        print("=" * 60)

        # 1. 페이지 로드
        print("\n[1] 페이지 로드...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 2. 대화 시작
        print("\n[2] 대화 시작...")
        textarea = page.locator('textarea').first
        await textarea.fill("인공지능과 인류의 미래")

        send_btn = page.locator('.send-btn').first
        await send_btn.click()
        await page.wait_for_timeout(3000)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_01_started.png")

        # 3. 대화 진행 대기 (최소 1턴 완료)
        print("\n[3] 대화 진행 대기 (30초)...")
        for i in range(30):
            await page.wait_for_timeout(1000)
            turn_el = page.locator('[class*="stat-value"], .stat-value').first
            if await turn_el.count() > 0:
                turn_text = await turn_el.inner_text()
                if turn_text and turn_text != "0":
                    print(f"  [{i+1}초] 턴 완료: {turn_text}")
                    break
            if i % 5 == 0:
                print(f"  [{i+1}초] 대기 중...")

        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_02_conversation.png")

        # 4. 현재 메시지 수 기록
        print("\n[4] 현재 상태 기록...")
        # 스트리밍 메시지 제외하고 완료된 메시지만 카운트
        # 스트리밍 메시지는 .streaming-badge 또는 cursor-blink 포함
        all_messages = page.locator('.message')
        all_msg_count = await all_messages.count()

        # 스트리밍 중인 메시지 찾기 (cursor-blink 또는 streaming-badge 포함)
        streaming_msgs = page.locator('.message:has(.cursor-blink), .message:has(.streaming-badge)')
        streaming_count = await streaming_msgs.count()

        msg_count_before = all_msg_count - streaming_count

        # 첫 번째 완료된 메시지 내용 기록
        completed_msgs = page.locator('.message:not(:has(.cursor-blink)):not(:has(.streaming-badge)) .message-content')
        first_msg_text = ""
        if await completed_msgs.count() > 0:
            first_msg_text = await completed_msgs.first.inner_text()
            first_msg_text = first_msg_text[:100]

        print(f"  전체 메시지: {all_msg_count} (스트리밍: {streaming_count})")
        print(f"  완료된 메시지: {msg_count_before}")
        print(f"  첫 메시지: {first_msg_text[:50]}...")

        # 5. 사이드바의 대화 제목 확인
        conv_item = page.locator('.conversation-item').first
        conv_title = ""
        if await conv_item.count() > 0:
            conv_title = await conv_item.inner_text()
            print(f"  대화 항목: {conv_title[:30]}...")

        # 6. ★ 새 대화 버튼 클릭 (네비게이션) ★
        print("\n[5] ★ 새 대화 버튼 클릭 (네비게이션) ★")
        new_btn = page.locator('.btn-new-chat').first
        if await new_btn.count() > 0:
            await new_btn.click()
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_03_new_chat.png")
            print("  ✓ 새 대화 화면으로 이동")
        else:
            print("  ✗ 새 대화 버튼 없음")

        # 7. ★ 이전 대화로 복귀 ★
        print("\n[6] ★ 이전 대화로 복귀 ★")
        # 사이드바에서 이전 대화 클릭
        prev_conv = page.locator('.conversation-item').first
        if await prev_conv.count() > 0:
            await prev_conv.click()
            await page.wait_for_timeout(3000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_04_returned.png")
            print("  ✓ 이전 대화 클릭")
        else:
            print("  ✗ 이전 대화 없음")

        # 8. ★★★ 핵심 검증: 데이터 유지 확인 ★★★
        print("\n[7] ★★★ 핵심 검증 ★★★")

        # 완료된 메시지만 카운트 (스트리밍 제외)
        all_messages_after = page.locator('.message')
        all_msg_count_after = await all_messages_after.count()
        streaming_msgs_after = page.locator('.message:has(.cursor-blink), .message:has(.streaming-badge)')
        streaming_count_after = await streaming_msgs_after.count()
        msg_count_after = all_msg_count_after - streaming_count_after

        print(f"\n  ┌─────────────────────────────────────────┐")
        print(f"  │ 네비게이션 전 완료된 메시지: {msg_count_before:3}        │")
        print(f"  │ 네비게이션 후 완료된 메시지: {msg_count_after:3}        │")
        print(f"  └─────────────────────────────────────────┘")

        if msg_count_after >= msg_count_before and msg_count_before > 0:
            print("\n  ✅ PASS: 데이터 유지됨!")

            # 내용도 확인
            completed_msgs_after = page.locator('.message:not(:has(.cursor-blink)):not(:has(.streaming-badge)) .message-content')
            if await completed_msgs_after.count() > 0:
                after_text = await completed_msgs_after.first.inner_text()
                if first_msg_text[:30] in after_text[:100]:
                    print("  ✅ 메시지 내용도 일치!")
                else:
                    print("  ⚠ 메시지 내용이 다름")
                    print(f"    전: {first_msg_text[:50]}")
                    print(f"    후: {after_text[:50]}")
        elif msg_count_before == 0:
            print("\n  ⚠ 테스트 불완전: 네비게이션 전에 메시지가 없었음")
        else:
            print("\n  ❌ FAIL: 데이터 손실!")
            print(f"     손실된 메시지: {msg_count_before - msg_count_after}개")
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_05_BUG.png")

        # 9. 대화 재개 가능 여부 확인
        print("\n[8] 대화 재개 가능 확인...")

        # 재개 버튼 또는 입력 필드 확인
        input_field = page.locator('.intervention-input, textarea[placeholder*="참여"]')
        if await input_field.count() > 0:
            is_disabled = await input_field.first.is_disabled()
            if not is_disabled:
                print("  ✅ 대화 재개 가능 (입력 필드 활성화)")
            else:
                print("  ⚠ 입력 필드 비활성화")
        else:
            print("  ⚠ 입력 필드 없음")

        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_06_final.png")

        print("\n" + "=" * 60)
        print(f"스크린샷: {OUTPUT_DIR}")
        print("=" * 60)

        await page.wait_for_timeout(2000)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
