# -*- coding: utf-8 -*-
"""
[R&R Cross-Validation Auto Runner]
작성자: 정수현 이사
기능: Gemini와 GPT를 교차 실행하며 R&R 문서를 극한으로 정제함.
"""

import os
import time
import shutil
import qms_rnr_ai_classifier_v2_tier as worker  # 기존 스크립트를 모듈로 불러옴

# ============================================================================
# [설정] 최신 모델명 지정 (API 지원 여부 확인 필요)
# ============================================================================
GEMINI_MODEL = "gemini-3-pro-preview"  # 예: 최신 프리뷰 모델명 (없으면 gemini-2.0-flash-exp 사용)
GPT_MODEL = "gpt-5.2"  # 예: gpt-5.2 (아직 미출시라면 gpt-4o 또는 o1-preview 사용)

# 타겟 파일 설정
ORIGINAL_FILE = "QMS_RnR_Optimization_Live.xlsx"
WORKING_FILE = "QMS_RnR_Optimization_Live_tier.xlsx"  # 작업용 파일 (계속 덮어씌워짐)


# ============================================================================
# [실행 로직]
# ============================================================================
def main():
    print("=" * 60)
    print("🚀 [R&R Cross-Refinement] 자동화 프로세스 시작")
    print(f"👉 전략: {GEMINI_MODEL} <-> {GPT_MODEL} 핑퐁 실행 (5 Sets)")
    print("=" * 60)

    # 1. 원본 보존을 위해 작업용 파일 복사 생성
    if not os.path.exists(ORIGINAL_FILE):
        print(f"❌ 오류: 원본 파일({ORIGINAL_FILE})이 없습니다.")
        return

    shutil.copy(ORIGINAL_FILE, WORKING_FILE)
    print(f"✅ 초기화: {ORIGINAL_FILE} -> {WORKING_FILE} 복사 완료\n")

    # 2. 루프 실행 (5 세트)
    for set_num in range(1, 6):  # 1부터 5까지
        print(f"\n🔥🔥 [SET {set_num} / 5] 시작 🔥🔥")

        # --- [Phase A] Gemini Turn ---
        print(f"\n[Set {set_num}-A] Google Gemini ({GEMINI_MODEL}) 투입...")
        try:
            worker.process_rnr_file(
                file_path=WORKING_FILE,
                model_type="gemini",
                model_name=GEMINI_MODEL
            )
            # 중간 백업 (혹시 모를 사태 대비)
            shutil.copy(WORKING_FILE, f"backup_set{set_num}_A_gemini.xlsx")
            print(f"   └─ 백업 완료: backup_set{set_num}_A_gemini.xlsx")

        except Exception as e:
            print(f"❌ Gemini 실행 중 오류 발생: {e}")

        time.sleep(2)  # API 과부하 방지 쿨타임

        # --- [Phase B] GPT Turn ---
        print(f"\n[Set {set_num}-B] OpenAI GPT ({GPT_MODEL}) 투입...")
        try:
            worker.process_rnr_file(
                file_path=WORKING_FILE,
                model_type="openai",
                model_name=GPT_MODEL
            )
            # 중간 백업
            shutil.copy(WORKING_FILE, f"backup_set{set_num}_B_gpt.xlsx")
            print(f"   └─ 백업 완료: backup_set{set_num}_B_gpt.xlsx")

        except Exception as e:
            print(f"❌ GPT 실행 중 오류 발생: {e}")

        time.sleep(2)

    print("\n" + "=" * 60)
    print("🎉 모든 세트(5 Sets) 완료! 최적화된 파일이 준비되었습니다.")
    print(f"📂 최종 파일: {WORKING_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()