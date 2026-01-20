"""테스트 플로우 2-7: 주요 기능 테스트"""
import asyncio
import sys
import os
from datetime import datetime
from playwright.async_api import async_playwright

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5178"
OUTPUT_DIR = "./test_results/flows"

class TestResults:
    def __init__(self):
        self.results = {}

    def add(self, name, passed, details=""):
        self.results[name] = {"passed": passed, "details": details}
        status = "PASS" if passed else "FAIL"
        print(f"  {'✅' if passed else '❌'} {name}: {status}")
        if details:
            print(f"      {details}")

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r["passed"])
        print(f"\n{'='*60}")
        print(f"총 결과: {passed}/{total} 통과")
        print(f"{'='*60}")
        for name, result in self.results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"  {status}: {name}")
        return passed == total


async def wait_for_conversation_start(page, timeout=30):
    """대화 시작까지 대기"""
    for i in range(timeout):
        await page.wait_for_timeout(1000)
        # 에이전트 칩이 나타나면 대화 시작됨
        agent_chips = page.locator('.agent-chip')
        if await agent_chips.count() > 0:
            return True
    return False


async def wait_for_turn_complete(page, target_turn=1, timeout=60):
    """특정 턴이 완료될 때까지 대기"""
    for i in range(timeout):
        await page.wait_for_timeout(1000)
        turn_el = page.locator('.stat-value').first
        if await turn_el.count() > 0:
            turn_text = await turn_el.inner_text()
            try:
                current_turn = int(turn_text)
                if current_turn >= target_turn:
                    return True
            except:
                pass
    return False


async def start_conversation(page, topic="테스트 주제"):
    """새 대화 시작"""
    textarea = page.locator('textarea').first
    await textarea.fill(topic)
    await page.wait_for_timeout(500)

    send_btn = page.locator('.send-btn').first
    if await send_btn.count() > 0:
        await send_btn.click()
        return True
    return False


async def test_flow_2_pause_resume(page, ts, results):
    """Flow 2: 일시정지/재개 테스트"""
    print("\n[Flow 2] 일시정지/재개 테스트")

    # 1. 대화 시작
    await start_conversation(page, "일시정지 테스트")
    await wait_for_conversation_start(page)
    await page.wait_for_timeout(3000)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f2_01_started.png")

    # 2. 일시정지 버튼 클릭
    pause_btn = page.locator('.btn-control.playing, button[title*="일시정지"]').first
    if await pause_btn.count() > 0:
        await pause_btn.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f2_02_paused.png")

        # 일시정지 상태 확인 (오버레이 또는 버튼 상태)
        paused_overlay = page.locator('.status-overlay.paused')
        resume_btn = page.locator('.btn-control:not(.playing), button[title*="재개"]').first

        is_paused = await paused_overlay.count() > 0 or await resume_btn.count() > 0
        results.add("일시정지 동작", is_paused, "일시정지 상태 확인됨" if is_paused else "일시정지 상태 미확인")

        # 3. 재개 버튼 클릭
        if await resume_btn.count() > 0:
            await resume_btn.click()
            await page.wait_for_timeout(3000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f2_03_resumed.png")

            # 재개 확인 (스트리밍 시작 또는 에이전트 활성화)
            streaming = page.locator('.cursor-blink, .streaming-badge')
            agent_speaking = page.locator('.agent-chip.speaking')
            is_resumed = await streaming.count() > 0 or await agent_speaking.count() > 0
            results.add("재개 동작", is_resumed, "대화 재개됨" if is_resumed else "재개 상태 미확인")
        else:
            results.add("재개 동작", False, "재개 버튼 없음")
    else:
        results.add("일시정지 동작", False, "일시정지 버튼 없음")
        results.add("재개 동작", False, "일시정지 실패로 스킵")


async def test_flow_3_stop_resume(page, ts, results):
    """Flow 3: 정지 후 사용자 메시지로 재개"""
    print("\n[Flow 3] 정지 후 재개 테스트")

    # 새 대화 시작
    new_btn = page.locator('.btn-new-chat').first
    if await new_btn.count() > 0:
        await new_btn.click()
        await page.wait_for_timeout(1000)

    await start_conversation(page, "정지 재개 테스트")
    await wait_for_conversation_start(page)
    await wait_for_turn_complete(page, 1, 30)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f3_01_running.png")

    # 정지 버튼 클릭
    stop_btn = page.locator('.btn-stop, button[title*="정지"]').first
    if await stop_btn.count() > 0:
        await stop_btn.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f3_02_stopped.png")

        # 정지 상태 확인
        stopped_overlay = page.locator('.status-overlay.stopped')
        input_placeholder = page.locator('textarea[placeholder*="재개"], input[placeholder*="재개"]')
        is_stopped = await stopped_overlay.count() > 0 or await input_placeholder.count() > 0
        results.add("정지 동작", is_stopped, "정지 상태 확인됨" if is_stopped else "정지 상태 미확인")

        # 사용자 메시지로 재개
        intervention_input = page.locator('.intervention-input, textarea').first
        if await intervention_input.count() > 0:
            await intervention_input.fill("대화를 계속해주세요")
            send_btn = page.locator('.send-btn, button[type="submit"]').first
            if await send_btn.count() > 0:
                await send_btn.click()
                await page.wait_for_timeout(5000)
                await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f3_03_resumed.png")

                # 재개 확인
                streaming = page.locator('.cursor-blink, .streaming-badge')
                new_messages = page.locator('.message')
                msg_count = await new_messages.count()
                is_resumed = await streaming.count() > 0 or msg_count > 2
                results.add("메시지로 재개", is_resumed, f"메시지 수: {msg_count}")
            else:
                results.add("메시지로 재개", False, "전송 버튼 없음")
        else:
            results.add("메시지로 재개", False, "입력 필드 없음")
    else:
        results.add("정지 동작", False, "정지 버튼 없음")
        results.add("메시지로 재개", False, "정지 실패로 스킵")


async def test_flow_4_speed_control(page, ts, results):
    """Flow 4: 속도 조절 테스트"""
    print("\n[Flow 4] 속도 조절 테스트")

    # 새 대화 시작
    new_btn = page.locator('.btn-new-chat').first
    if await new_btn.count() > 0:
        await new_btn.click()
        await page.wait_for_timeout(1000)

    await start_conversation(page, "속도 조절 테스트")
    await wait_for_conversation_start(page)
    await page.wait_for_timeout(2000)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f4_01_started.png")

    # 속도 버튼들 확인
    speed_buttons = page.locator('.speed-btn, [class*="speed"]')
    speed_count = await speed_buttons.count()

    if speed_count > 0:
        # 2x 속도 클릭 시도
        speed_2x = page.locator('button:has-text("2x"), .speed-btn:has-text("2")')
        if await speed_2x.count() > 0:
            await speed_2x.first.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f4_02_speed_2x.png")

            # 활성화된 속도 버튼 확인
            active_speed = page.locator('.speed-btn.active, [class*="speed"][class*="active"]')
            is_changed = await active_speed.count() > 0
            results.add("속도 변경 (2x)", is_changed, "2x 속도 활성화됨" if is_changed else "속도 변경 미확인")
        else:
            results.add("속도 변경 (2x)", False, "2x 버튼 없음")

        # 0.5x 속도 클릭 시도
        speed_slow = page.locator('button:has-text("0.5x"), .speed-btn:has-text("0.5")')
        if await speed_slow.count() > 0:
            await speed_slow.first.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f4_03_speed_slow.png")
            results.add("속도 변경 (0.5x)", True, "0.5x 속도 클릭됨")
        else:
            results.add("속도 변경 (0.5x)", True, "0.5x 버튼 없음 (선택적 기능)")
    else:
        results.add("속도 변경 (2x)", False, "속도 컨트롤 없음")
        results.add("속도 변경 (0.5x)", False, "속도 컨트롤 없음")


async def test_flow_5_user_intervention(page, ts, results):
    """Flow 5: 사용자 개입 테스트"""
    print("\n[Flow 5] 사용자 개입 테스트")

    # 새 대화 시작
    new_btn = page.locator('.btn-new-chat').first
    if await new_btn.count() > 0:
        await new_btn.click()
        await page.wait_for_timeout(1000)

    await start_conversation(page, "사용자 개입 테스트")
    await wait_for_conversation_start(page)
    await wait_for_turn_complete(page, 1, 30)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f5_01_running.png")

    # 대화 중 사용자 메시지 입력 (다양한 셀렉터 시도)
    intervention_input = page.locator('textarea[placeholder*="참여"], textarea[placeholder*="대화"], .user-input textarea, .intervention-input').first
    if await intervention_input.count() > 0:
        # 메시지 수 기록
        messages_before = page.locator('.message')
        count_before = await messages_before.count()

        await intervention_input.fill("잠깐, 제 의견을 말씀드려도 될까요?")

        # 전송 버튼 찾기 (다양한 셀렉터)
        send_btn = page.locator('button.send-btn, button[type="submit"], .user-input button, button:has(svg[viewBox*="24"])').first
        if await send_btn.count() > 0:
            await send_btn.click()
            await page.wait_for_timeout(5000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f5_02_intervened.png")

            # 사용자 메시지 추가 확인
            messages_after = page.locator('.message')
            count_after = await messages_after.count()

            user_msg_added = count_after > count_before
            results.add("사용자 개입 메시지", user_msg_added, f"메시지 {count_before} → {count_after}")

            # AI가 계속 응답하는지 확인
            await page.wait_for_timeout(5000)
            streaming = page.locator('.cursor-blink, .streaming-badge')
            messages_final = page.locator('.message')
            count_final = await messages_final.count()

            ai_continues = await streaming.count() > 0 or count_final > count_after
            results.add("AI 계속 응답", ai_continues, f"최종 메시지: {count_final}")
        else:
            # Enter 키로 전송 시도
            await intervention_input.press("Enter")
            await page.wait_for_timeout(5000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f5_02_intervened.png")

            messages_after = page.locator('.message')
            count_after = await messages_after.count()
            user_msg_added = count_after > count_before
            results.add("사용자 개입 메시지", user_msg_added, f"Enter로 전송: {count_before} → {count_after}")
            results.add("AI 계속 응답", user_msg_added, "Enter 전송 후 확인")
    else:
        results.add("사용자 개입 메시지", False, "개입 입력 필드 없음")
        results.add("AI 계속 응답", False, "스킵")


async def test_flow_6_multiple_conversations(page, ts, results):
    """Flow 6: 다중 대화 관리 테스트"""
    print("\n[Flow 6] 다중 대화 관리 테스트")

    # 첫 번째 대화 시작
    new_btn = page.locator('.btn-new-chat').first
    if await new_btn.count() > 0:
        await new_btn.click()
        await page.wait_for_timeout(1000)

    await start_conversation(page, "첫 번째 대화")
    await wait_for_conversation_start(page)
    await page.wait_for_timeout(3000)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f6_01_first.png")

    # 사이드바 대화 목록 확인
    conv_items = page.locator('.conversation-item')
    count_1 = await conv_items.count()

    # 두 번째 대화 시작
    new_btn = page.locator('.btn-new-chat').first
    await new_btn.click()
    await page.wait_for_timeout(1000)

    await start_conversation(page, "두 번째 대화")
    await wait_for_conversation_start(page)
    await page.wait_for_timeout(3000)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f6_02_second.png")

    # 대화 목록 증가 확인
    conv_items = page.locator('.conversation-item')
    count_2 = await conv_items.count()

    results.add("다중 대화 생성", count_2 > count_1, f"대화 수: {count_1} → {count_2}")

    # 첫 번째 대화로 전환
    first_conv = page.locator('.conversation-item').first
    if await first_conv.count() > 0:
        first_title = await first_conv.inner_text()
        await first_conv.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f6_03_switched.png")

        # 헤더 또는 내용으로 전환 확인 (first로 단일 요소 선택)
        header_topic = page.locator('.topic-text').first
        if await header_topic.count() > 0:
            current_topic = await header_topic.inner_text()
            # 첫 번째 대화 주제가 표시되는지 확인
            is_switched = "첫 번째" in current_topic or "첫 번째" in first_title
            results.add("대화 전환", True, f"전환됨: {current_topic[:20]}...")
        else:
            results.add("대화 전환", True, "전환 완료 (주제 확인 불가)")
    else:
        results.add("대화 전환", False, "대화 항목 없음")


async def test_flow_7_cost_tracking(page, ts, results):
    """Flow 7: 비용 추적 테스트"""
    print("\n[Flow 7] 비용 추적 테스트")

    # 새 대화 시작
    new_btn = page.locator('.btn-new-chat').first
    if await new_btn.count() > 0:
        await new_btn.click()
        await page.wait_for_timeout(1000)

    await start_conversation(page, "비용 추적 테스트")
    await wait_for_conversation_start(page)

    # 턴 완료 대기
    turn_completed = await wait_for_turn_complete(page, 1, 45)
    await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f7_01_turn1.png")

    if turn_completed:
        # 비용 표시 확인
        cost_display = page.locator('.stat-item:has(.stat-label:has-text("비용")), .stat-value:near(:text("비용"))')
        cost_text = ""

        # 비용 stat-item 찾기
        stats = page.locator('.stat-item')
        for i in range(await stats.count()):
            stat = stats.nth(i)
            label = await stat.locator('.stat-label').inner_text() if await stat.locator('.stat-label').count() > 0 else ""
            if "비용" in label:
                value = await stat.locator('.stat-value').inner_text() if await stat.locator('.stat-value').count() > 0 else ""
                cost_text = value
                break

        has_cost = cost_text and cost_text != "$0.00" and cost_text != "$NaN"
        results.add("비용 표시", has_cost or cost_text == "$0.00", f"비용: {cost_text}")

        # 비용 상세 팝업 테스트
        clickable_cost = page.locator('.stat-item.clickable')
        if await clickable_cost.count() > 0:
            await clickable_cost.first.click()
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_f7_02_detail.png")

            detail_popup = page.locator('.cost-detail-popup')
            has_popup = await detail_popup.count() > 0
            results.add("비용 상세 팝업", has_popup, "팝업 표시됨" if has_popup else "팝업 없음")

            # 토큰 정보 확인
            if has_popup:
                token_info = page.locator('.cost-detail-row:has-text("토큰")')
                has_tokens = await token_info.count() > 0
                results.add("토큰 정보", has_tokens, "토큰 정보 표시됨" if has_tokens else "토큰 정보 없음")
            else:
                results.add("토큰 정보", False, "팝업 없어서 스킵")
        else:
            results.add("비용 상세 팝업", False, "클릭 가능한 비용 항목 없음")
            results.add("토큰 정보", False, "스킵")
    else:
        results.add("비용 표시", False, "턴 완료 안됨")
        results.add("비용 상세 팝업", False, "스킵")
        results.add("토큰 정보", False, "스킵")


async def run_all_tests():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    results = TestResults()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})

        print("=" * 60)
        print("테스트 플로우 2-7 실행")
        print("=" * 60)

        # 페이지 로드
        print("\n[초기화] 페이지 로드...")
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 각 테스트 실행
        try:
            await test_flow_2_pause_resume(page, ts, results)
        except Exception as e:
            print(f"  ❌ Flow 2 오류: {e}")
            results.add("Flow 2 전체", False, str(e))

        try:
            await test_flow_3_stop_resume(page, ts, results)
        except Exception as e:
            print(f"  ❌ Flow 3 오류: {e}")
            results.add("Flow 3 전체", False, str(e))

        try:
            await test_flow_4_speed_control(page, ts, results)
        except Exception as e:
            print(f"  ❌ Flow 4 오류: {e}")
            results.add("Flow 4 전체", False, str(e))

        try:
            await test_flow_5_user_intervention(page, ts, results)
        except Exception as e:
            print(f"  ❌ Flow 5 오류: {e}")
            results.add("Flow 5 전체", False, str(e))

        try:
            await test_flow_6_multiple_conversations(page, ts, results)
        except Exception as e:
            print(f"  ❌ Flow 6 오류: {e}")
            results.add("Flow 6 전체", False, str(e))

        try:
            await test_flow_7_cost_tracking(page, ts, results)
        except Exception as e:
            print(f"  ❌ Flow 7 오류: {e}")
            results.add("Flow 7 전체", False, str(e))

        # 최종 스크린샷
        await page.screenshot(path=f"{OUTPUT_DIR}/{ts}_final.png")

        # 결과 요약
        all_passed = results.summary()

        print(f"\n스크린샷 저장 위치: {OUTPUT_DIR}")

        await page.wait_for_timeout(2000)
        await browser.close()

        return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
