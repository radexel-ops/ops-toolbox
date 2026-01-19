# -*- coding: utf-8 -*-
import sys
import pandas as pd
import re
import os

# ⛔ (삭제) Anaconda 경로 강제 주입
# pyqt5_path = r'c:\users\pop84\anaconda3\lib\site-packages'
# try:
#     sys.path.append(pyqt5_path)
# except:
#     pas
# ✅ (추가) 잘못된 Qt 플러그인 경로 환경변수 제거 + 현재 가상환경의 PyQt5 플러그인 경로 사용
for k in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
    os.environ.pop(k, None)


# try :
#     sys.path.append(pyqt5_path)
# except :
#     pass

from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, QLabel,
                             QGroupBox, QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtGui import QColor

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import warnings
warnings.simplefilter("ignore", UserWarning)
import time


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.title = '급여 자료 처리 프로그램'
        self.left = 100
        self.top = 100
        self.width = 1000
        self.height = 600
        self.initUI()

    # -------------------------- UI -------------------------- #
    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        main_layout = QVBoxLayout()

        # ① 급여 이체 절차 그룹박스
        self.payroll_procedures_group = self.createGroup("급여 이체 절차", """
        급여 이체 업무 순서

        1. 급여일 전주 준비
           ① 세무대리인에게 공유할 파일 준비 (급여일 1주 전)
               - 급여 내역 : 고려사항 - 개인법카 오용, 상여금 여부, 수당, 휴직 등 기타 정산할 사항 확인 
               - 사업소득 지급 대장
               - 기타소득 지급 대장
               - 사이닝 보너스 내역 (참고: 사이닝 보너스는 상여금으로 분류. 근로소득으로 과세됨)
           ② 세무대리인이 급여자료 입력 완료 시, 입력된 내용 재확인.

        2. 급여일 실무 순서
            <급여일 최소 1일 전>
           ① 직원 정보 파일 업데이트
           ② 급여 내역 다운로드 <'https://smarta.wehago.com/#/smarta/humanresource/SWSA0101?sao&cno=2956135&cd_com=biz202312040013897&gisu=8&yminsa=2025&searchData=2025010120251231&color=#F09A1E&companyName=%EC%A3%BC%EC%8B%9D%ED%9A%8C%EC%82%AC%20%EB%9D%BC%EB%8D%B1%EC%85%80&companyID=pop84268'>
               - 위하고 티엣지 > 급여 입력 > 귀속연월 설정 > 급여와 상여 설정 > 직원 전체 선택 > 우측 상단 - 엑셀 파일 다운로드 
               > '위하고 급여자료 다운로드'로 파일명 설정
           ③ 사업소득 다운로드 <'https://smarta.wehago.com/#/smarta/humanresource/SWBU0103?sao&cno=2956135&cd_com=biz202312040013897&gisu=7&yminsa=2025&searchData=2025010120241231&color=#1C90FB&companyName=%EC%A3%BC%EC%8B%9D%ED%9A%8C%EC%82%AC%20%EB%9D%BC%EB%8D%B1%EC%85%80&companyID=pop84268'>
               - 위하고 티엣지 > 사업소득조회 > 귀속연월 설정 > 소득자 - 전체 선택 > 명단 전체 선택 > 우측 상단 - 엑셀 내보내기
               > '사업소득조회'로 파일명 설정
           
           ④ '급여 항목 검증'버튼 클릭. 예상 실수령과 차인지급액 차이가 큰 항목 재검토
           ⑤ '급여이체용 양식 만들기.xlsx 만들기' 버튼 클릭
           ⑥ '파일 확인' 버튼 클릭 후 입력정보 최종 확인
           ⑦ 우리은행 홈페이지 > 이체 > 급여이체 > 파일등록 > '급여이체용_양식'파일 업로드 후 급여 일괄 이체예약 (급여일 오전 9시).
               - 참고) 이름과 계좌번호가 매칭되지 않는 건은 자동으로 이체 취소됨

           <급여일 예약 이체 이 후>
           ① 급여명세서 발송 (나하고/이메일)
               - 위하고 티엣지 > 급여 입력 > 귀속연월 설정 > 급여와 상여 설정 > 직원 전체 선택 > 우측 하단 - 급여명세서 보내기 
               > 우측 상단 - 설정 > 발급 방법 : 나하고, E-Mail 모두 체크, 급여명세서 보안 확인방법 : 사용안함, 회신받을 이메일 : hr@radexel.com > 보내기  
           ② 기타소득 이체
           ③ 기타소득에 대한 원천징수 영수증 발송 (사업소득은 원천징수 발급x, 요청 시 발급)


        3. 급여일 후 처리
           ① 원천세 및 지방세 관련 처리 (급여일 1주 후)
               - 세무대리인에 의한 원천세, 지방세 신고 및 납부 안내
               - 우리은행을 통한 납부 진행 (국세/관세, 지방세 납부 절차 진행)
               - 홈택스를 통한 납부완료 여부 확인 가능
        """)
        main_layout.addWidget(self.payroll_procedures_group)

        # 사용 메뉴얼 그룹박스
        # 사용 메뉴얼 그룹박스
        self.usage_manual_group = self.createGroup("급여 자료 처리 프로그램 사용 매뉴얼", """
        사용 목적 : 
        1) 반복 업무 효율화 
        2) 휴먼 에러 최소화

        1. 준비 단계 : 필요한 파일 준비하기
           - '위하고 급여자료 다운로드.xlsx'와 '직원정보.xlsx' 파일을 준비하세요. 
           - 이 파일들은 파이썬 스크립트와 같은 폴더에 있어야 정상적으로 작동합니다.

        2. 실행 단계 : 스크립트 실행
           - 파이썬 스크립트를 실행하여, '위하고 급여자료 다운로드.xlsx' 파일에서 급여 정보를 추출하고 '직원정보.xlsx' 파일에서 각 직원의 은행 계좌 정보를 매칭합니다.
           - 스크립트는 각 직원의 은행, 계좌번호, 지급될 금액, 이름 등 필요한 정보를 자동으로 양식에 맞춰 정리합니다.

        3. 급여 항목 검증 : 예상 실수령액 비교
           - '급여 항목 검증' 버튼을 클릭하여 예상 실수령액과 차인지급액을 비교합니다.
           - 예상 실수령액과 차인지급액의 차이가 5% 이상인 항목은 테이블에서 빨간색으로 표시되며, 이를 통해 문제 항목을 쉽게 확인할 수 있습니다.

        4. 결과 저장 : 급여 이체용 파일 생성
           - '급여이체용_양식.xlsx 만들기' 버튼을 클릭하여 급여 이체에 필요한 모든 정보가 포함된 엑셀 파일을 생성합니다.
           - 이 파일은 엑셀에서 직접 열어 확인할 수 있으며, 우리은행 급여 이체 시스템에 업로드할 수 있습니다.

        5. 최종 확인 : 파일 확인
           - '파일 확인' 버튼을 클릭하여 생성된 파일을 열어 최종적으로 데이터가 올바르게 입력되었는지 확인합니다.

        6. 주의사항 : 주의할 점
           - 파일명과 위치를 정확히 확인하세요. 파일이 정확한 위치에 있지 않거나 파일명이 올바르지 않으면 스크립트가 작동하지 않습니다.
           - 생성된 데이터의 정확성을 반드시 확인하세요. 잘못된 데이터 입력은 급여 이체에 오류를 일으킬 수 있으니 주의가 필요합니다.
        """)

        main_layout.addWidget(self.usage_manual_group)

        # ③ 버튼 세트
        btn_check = QPushButton('급여 항목 검증', self)
        btn_check.setToolTip('세후 금액이 적정한지 검증합니다.')
        btn_check.clicked.connect(self.check_payroll)
        main_layout.addWidget(btn_check)

        btn_process = QPushButton('급여이체용_양식.xlsx 만들기', self)
        btn_process.setToolTip('급여 자료 파일을 처리해 이체용 양식을 만듭니다.')
        btn_process.clicked.connect(self.process_files)
        main_layout.addWidget(btn_process)

        btn_open = QPushButton('파일 확인', self)
        btn_open.setToolTip('처리된 파일을 엽니다.')
        btn_open.clicked.connect(self.check_file)
        main_layout.addWidget(btn_open)

        # ④ 메시지·결과 테이블
        self.message_label = QLabel(self)
        self.message_label.setStyleSheet("QLabel { font-size: 14px; }")
        main_layout.addWidget(self.message_label)

        self.payroll_table = QTableWidget(self)
        main_layout.addWidget(self.payroll_table)

        self.setLayout(main_layout)
        self.show()

    def createGroup(self, title, content):
        group = QGroupBox(title)
        group.setCheckable(True)
        group.setChecked(False)

        layout = QVBoxLayout()
        label = QLabel(content)
        label.setWordWrap(True)
        label.setVisible(False)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)
        group.setLayout(layout)
        group.toggled.connect(lambda checked: label.setVisible(checked))
        return group


    def check_payroll(self):
        try:
            # 1) 급여 자료 로드
            df = pd.read_excel('위하고 급여자료 다운로드.xlsx', sheet_name='Sheet1', header=None)

            # 2) 헤더 보정
            for idx, col_value in enumerate(df.iloc[0]):
                if col_value in ["수당", "공제"] or pd.isna(col_value):
                    df.iloc[0, idx] = df.iloc[1, idx]
            df.columns = df.iloc[0]
            df = df.drop(0).reset_index(drop=True)
            df = df[1:-1]   # 요약행 제거

            # 3) Selenium 설정
            driver = webdriver.Chrome()
            wait = WebDriverWait(driver, 10)

            # 4) 결과 테이블 헤더
            self.payroll_table.setColumnCount(10)
            self.payroll_table.setHorizontalHeaderLabels(
                ['사원명', '식대', '연구보조비', '보육수당',
                 '지급액계', '비과세 금액', '소득월액',
                 '차인지급액', '예상실수령액', '차이'])

            # 5) 사원별 계산
            for _, row in df.iterrows():
                employee_name = row['사원명']
                meal_allowance = row.get('식대', 0)
                research_allowance = row.get('연구보조비', 0)
                childcare_allowance = row.get('보육수당', 0)         # 추가 항목
                total_payment = row.get('지급액계', 0)
                difference_payment = row.get('차인지급액', 0)

                # 비과세 합산 (각 항목당 20만 원 한도)
                non_taxable = sum(min(allow, 200000)
                                  for allow in (meal_allowance, research_allowance, childcare_allowance))

                # 소득월액
                income_monthly = total_payment - non_taxable

                # 예상 실수령액
                try:
                    driver.get("https://www.nodong.kr/AnnuaIncomeCal")
                    wait.until(EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "#wage_radio > label:nth-child(2)"))).click()

                    wage_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#wage")))
                    wage_input.clear()
                    wage_input.send_keys(str(total_payment))

                    exemption_input = driver.find_element(By.CSS_SELECTOR, "#exemption")
                    exemption_input.clear()
                    exemption_input.send_keys(str(non_taxable))

                    driver.find_element(By.CSS_SELECTOR, "#button_calculate").click()
                    receipt_text = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#receipt")))
                    expected_take_home = int(re.sub(r'[^0-9]', '', receipt_text.text) or 0)
                except Exception:
                    expected_take_home = 0

                # 결과 테이블
                r = self.payroll_table.rowCount()
                self.payroll_table.insertRow(r)
                for c, v in enumerate([
                        employee_name, meal_allowance, research_allowance, childcare_allowance,
                        total_payment, non_taxable, income_monthly,
                        difference_payment, expected_take_home]):
                    self.payroll_table.setItem(r, c, QTableWidgetItem(str(v)))

                diff_pct = (abs(expected_take_home - difference_payment) / difference_payment
                            if difference_payment else 0)
                self.payroll_table.setItem(r, 9, QTableWidgetItem(f"{diff_pct:.2%}"))

                if expected_take_home and diff_pct > 0.05:
                    for col in (7, 8):  # 차인지급액, 예상실수령액
                        self.payroll_table.item(r, col).setBackground(QColor(255, 0, 0))

            driver.quit()

        except Exception as e:
            self.show_error_message(f"파일 처리 중 오류: {str(e)}")

    # This function will check the header condition and update only those that meet the criteria.

    # This function now handles the condition where headers that exactly match "수당", "공제" or contain "Unnamed" are adjusted using the second row.

    # This function handles the condition where headers in certain columns are adjusted using the second row if they contain "수당", "공제", or "Unnamed".

    def process_files(self):
        try:
            self.show_info_message("파일 처리를 시작합니다...")

            df_A  = pd.read_excel('위하고 급여자료 다운로드.xlsx', skiprows=[1], skipfooter=1)
            df_A2 = pd.read_excel('사업소득조회.xlsx',          skipfooter=3)
            df_emp = pd.read_excel('직원정보.xlsx')

            df_B = pd.DataFrame(columns=[
                '은행', '계좌번호', '차인지급액', '이름',
                '생년월일/사업자번호', '집금(CMS)코드', '급여지급여부', '급여명세'])

            rows = []

            # 근로소득
            for _, row in df_A.iterrows():
                name  = row['사원명']
                pay   = row.get('차인지급액', "수기 입력필요")
                code  = str(row.get('사원코드', ''))
                is_sal= bool(re.search(r'\d', code))

                info = df_emp[df_emp['이름'] == name]
                rows.append({
                    '은행': info.iloc[0]['은행'] if not info.empty else "정보 없음",
                    '계좌번호': str(int(info.iloc[0]['계좌번호'])) if not info.empty else "정보 없음",
                    '차인지급액': pay,
                    '이름': name,
                    '생년월일/사업자번호': '',
                    '집금(CMS)코드': '',
                    '급여지급여부': "급여_(주)라덱셀" if is_sal else "(주)라덱셀",
                    '급여명세': f"{name}_{'급여' if is_sal else '사업소득'}"
                })

            # 사업소득
            for _, row in df_A2.iterrows():
                name = row['소득자명']
                pay  = row.get('차인지급액', "수기 입력필요")

                info = df_emp[df_emp['이름'] == name]
                rows.append({
                    '은행': info.iloc[0]['은행'] if not info.empty else "정보 없음",
                    '계좌번호': str(int(info.iloc[0]['계좌번호'])) if not info.empty else "정보 없음",
                    '차인지급액': pay,
                    '이름': name,
                    '생년월일/사업자번호': '',
                    '집금(CMS)코드': '',
                    '급여지급여부': "(주)라덱셀",
                    '급여명세': f"{name}_사업소득"
                })

            df_B = pd.concat([df_B, pd.DataFrame(rows)], ignore_index=True)
            df_B.to_excel('급여이체용_양식.xlsx', index=False, header=False)

            self.show_info_message("완료되었습니다. '파일 확인'으로 결과를 확인하세요.")
        except Exception as e:
            self.show_error_message(f"예상치 못한 오류: {str(e)}")

    def process_files2(self):
        try:
            self.show_info_message("파일 처리를 시작합니다...")

            df_A  = pd.read_excel('위하고 급여자료 다운로드.xlsx', skiprows=[1], skipfooter=1)
            df_emp= pd.read_excel('직원정보.xlsx')

            df_B = pd.DataFrame(columns=[
                '은행', '계좌번호', '차인지급액', '이름',
                '생년월일/사업자번호', '집금(CMS)코드', '급여지급여부', '급여명세'])

            rows = []
            for _, row in df_A.iterrows():
                name = row['사원명']
                pay  = row.get('차인지급액', "수기 입력필요")
                code = str(row.get('사원코드', ''))
                is_sal = bool(re.search(r'\d', code))

                info = df_emp[df_emp['이름'] == name]
                rows.append({
                    '은행': info.iloc[0]['은행'] if not info.empty else "정보 없음",
                    '계좌번호': str(int(info.iloc[0]['계좌번호'])) if not info.empty else "정보 없음",
                    '차인지급액': pay,
                    '이름': name,
                    '생년월일/사업자번호': '',
                    '집금(CMS)코드': '',
                    '급여지급여부': "급여_(주)라덱셀" if is_sal else "(주)라덱셀",
                    '급여명세': f"{name}_{'급여' if is_sal else '사업소득'}"
                })

            df_B = pd.concat([df_B, pd.DataFrame(rows)], ignore_index=True)
            df_B.to_excel('급여이체용_양식.xlsx', index=False, header=False)

            self.show_info_message("완료되었습니다. '파일 확인'으로 결과를 확인하세요.")
        except Exception as e:
            self.show_error_message(f"예상치 못한 오류: {str(e)}")
    def show_error_message(self, message):
        err = QLabel(message, self)
        err.setStyleSheet("QLabel { color: red; font-size: 14px; }")
        self.layout().addWidget(err)

    def show_info_message(self, message):
        info = QLabel(message, self)
        info.setStyleSheet("QLabel { color: green; font-size: 14px; }")
        self.layout().addWidget(info)

    def check_file(self):
        os.startfile('급여이체용_양식.xlsx')

    def close_application(self):
        QCoreApplication.instance().quit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())