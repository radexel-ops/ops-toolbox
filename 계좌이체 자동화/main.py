# -*- coding: utf-8 -*-
"""
계좌이체 자동화 - 메인 진입점
Wehago 문서 수집 + AP List 업데이트 + 세금계산서 매칭

실행 방법:
    python main.py              # 메인 애플리케이션
    python main.py --tax        # 세금계산서 매칭 UI만 실행
"""

import sys

from ui.main_window import WehagoScraperWindow
from ui.tax_match_ui import TaxMatchApp


def main():
    """메인 함수"""
    if "--tax" in sys.argv:
        # 세금계산서 매칭 UI만 실행
        app = TaxMatchApp()
    else:
        # 메인 애플리케이션 실행
        app = WehagoScraperWindow()

    app.mainloop()


if __name__ == "__main__":
    main()
