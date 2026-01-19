# -*- coding: utf-8 -*-
"""
WehagoScraper + AP-List 업데이트 (하위 호환용 래퍼)

이 파일은 기존 호환성을 위해 유지됩니다.
새로운 진입점: main.py

실행 방법:
    python main.py              # 권장
    python APLIST_AUTOMATION.py # 기존 방식 (호환성 유지)
"""

from ui.main_window import WehagoScraperWindow

# 기존 클래스명 호환
WehagoScraper = WehagoScraperWindow

if __name__ == "__main__":
    WehagoScraper().mainloop()
