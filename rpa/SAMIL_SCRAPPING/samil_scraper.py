import os
import time
from datetime import datetime
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ======================================================
# [설정] 파일명
# ======================================================
DB_FILE = "samil_db.html"

# ======================================================
# [HTML 템플릿] - 심플 & 모던 UI (세계적 디자이너 스타일)
# ======================================================
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Samil Accounting DB</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #2563EB;       /* 세련된 블루 */
            --primary-light: #EFF6FF;       /* 아주 연한 블루 (배경용) */
            --bg-color: #F8FAFC;            /* 전체 배경색 (쿨 그레이) */
            --sidebar-width: 360px;
            --text-main: #1E293B;           /* 진한 텍스트 */
            --text-sub: #64748B;            /* 연한 텍스트 */
            --border-color: #E2E8F0;
            --card-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, "Helvetica Neue", sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* --- 사이드바 (Left Sidebar) --- */
        #sidebar {
            width: var(--sidebar-width);
            background: #FFFFFF;
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            height: 100%;
            flex-shrink: 0;
            z-index: 50;
            box-shadow: 4px 0 24px rgba(0,0,0,0.02);
        }

        .sidebar-header {
            padding: 28px 24px;
            border-bottom: 1px solid var(--border-color);
            background: #FFFFFF;
        }

        .sidebar-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 12px;
            letter-spacing: -0.02em;
        }

        .sidebar-title i { color: var(--primary-color); }

        #toc-list {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            list-style: none;
            margin: 0;
        }

        /* 목차 아이템 스타일 */
        .toc-item {
            display: block;
            padding: 16px;
            margin-bottom: 8px;
            border-radius: 12px;
            text-decoration: none;
            color: var(--text-main);
            background: #FFFFFF;
            border: 1px solid transparent;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }

        .toc-item:hover {
            background-color: var(--bg-color);
            transform: translateY(-1px);
        }

        .toc-item.active {
            background-color: var(--primary-light);
            border-color: rgba(37, 99, 235, 0.2);
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.08);
        }

        .toc-item.active::before {
            content: '';
            position: absolute;
            left: 0;
            top: 12px;
            bottom: 12px;
            width: 4px;
            background-color: var(--primary-color);
            border-radius: 0 4px 4px 0;
        }

        .toc-title {
            display: block;
            font-size: 0.95rem;
            font-weight: 600;
            line-height: 1.5;
            margin-bottom: 8px;
            word-break: keep-all;
        }

        .toc-meta {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-sub);
        }

        .badge {
            background: var(--bg-color);
            color: var(--text-sub);
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.7rem;
            border: 1px solid var(--border-color);
        }

        .toc-item.active .badge {
            background: #FFFFFF;
            color: var(--primary-color);
            border-color: rgba(37, 99, 235, 0.2);
        }

        /* --- 메인 컨텐츠 (Main Content) --- */
        #main-content {
            flex: 1;
            overflow-y: auto;
            padding: 40px 60px;
            scroll-behavior: smooth;
        }

        .container {
            max-width: 960px;
            margin: 0 auto;
            padding-bottom: 120px;
        }

        /* 카드 스타일 */
        .doc-card {
            background: white;
            border-radius: 24px;
            box-shadow: var(--card-shadow);
            margin-bottom: 60px;
            overflow: hidden;
            border: 1px solid var(--border-color);
            transition: opacity 0.3s ease;
        }

        .doc-header {
            padding: 40px;
            background: linear-gradient(to bottom, #FFFFFF, #FAFAFA);
            border-bottom: 1px solid var(--border-color);
        }

        .doc-category-tag {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 9999px;
            background-color: var(--primary-light);
            color: var(--primary-color);
            font-size: 0.85rem;
            font-weight: 700;
            margin-bottom: 20px;
            letter-spacing: 0.01em;
        }

        .doc-title-text {
            margin: 0;
            font-size: 1.8rem;
            font-weight: 800;
            line-height: 1.4;
            color: #0F172A;
            letter-spacing: -0.02em;
            word-break: keep-all;
        }

        .doc-info {
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px dashed var(--border-color);
            display: flex;
            gap: 24px;
            font-size: 0.9rem;
            color: var(--text-sub);
        }

        .info-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .info-item a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 600;
            transition: opacity 0.2s;
        }

        .info-item a:hover { opacity: 0.8; }

        .doc-body {
            padding: 50px;
            font-size: 1.05rem;
            line-height: 1.8;
            color: #334155;
            white-space: pre-wrap;
            font-family: 'Pretendard', sans-serif;
        }

        /* 스크롤바 커스텀 */
        ::-webkit-scrollbar { width: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 5px; border: 3px solid var(--bg-color); background-clip: content-box; }
        ::-webkit-scrollbar-thumb:hover { background-color: #94A3B8; }

    </style>
</head>
<body>
    <aside id="sidebar">
        <div class="sidebar-header">
            <div class="sidebar-title">
                <i class="fas fa-layer-group"></i> Samil Archives
            </div>
        </div>
        <nav id="toc-list">
            </nav>
    </aside>

    <main id="main-content">
        <div class="container" id="content-area">
            </div>
    </main>

    <script>
        // 스크롤 스파이 (Scroll Spy) & 부드러운 이동
        const mainContent = document.getElementById('main-content');

        mainContent.addEventListener('scroll', () => {
            const cards = document.querySelectorAll('.doc-card');
            const tocItems = document.querySelectorAll('.toc-item');

            let current = '';

            cards.forEach(card => {
                const cardTop = card.offsetTop - mainContent.offsetTop;
                if (mainContent.scrollTop >= cardTop - 150) { // 감지 오프셋 조정
                    current = card.getAttribute('id');
                }
            });

            tocItems.forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('href') === '#' + current) {
                    item.classList.add('active');
                    // 목차 자동 스크롤 (화면 밖으로 나가지 않게)
                    item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        });
    </script>
</body>
</html>
"""


def init_driver():
    """브라우저 실행 및 설정"""
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    options.add_argument("--log-level=3")

    # 드라이버 설치 및 실행
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver


def load_html_db():
    """HTML 파일을 읽어 BeautifulSoup 객체로 반환"""
    if not os.path.exists(DB_FILE):
        return BeautifulSoup(HTML_TEMPLATE, "html.parser")

    with open(DB_FILE, "r", encoding="utf-8") as f:
        return BeautifulSoup(f, "html.parser")


def save_html_db(soup):
    """수정된 HTML을 파일로 저장"""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(str(soup))


def check_duplicate(current_url, soup):
    """
    [중복 방지 로직]
    URL을 디코딩(unquote)하여 HTML 내의 링크들과 비교
    """
    # 1. 현재 URL 정규화 (특수문자 변환 등 제거)
    current_clean = unquote(current_url).strip()

    # 2. 기존 DB 내 링크 검사
    existing_links = soup.select(".info-item a")

    for link in existing_links:
        href = link.get('href')
        if href:
            existing_clean = unquote(href).strip()
            # 정확히 일치하는 링크가 있는지 확인
            if current_clean == existing_clean:
                return True
    return False


def extract_category_from_tab_title(driver):
    """
    [핵심 기능: 브라우저 탭 제목 기반 카테고리 추출]
    예: '삼일 : 금융감독원 : 일반기업회계 질의 회신' -> '금융감독원 > 일반기업회계 질의 회신'
    """
    raw_title = driver.title.strip()

    # 1. 콜론(:) 기준으로 분리
    if ":" in raw_title:
        parts = raw_title.split(":")
        clean_parts = []

        for part in parts:
            p = part.strip()
            # '삼일', 'Samil' 등 불필요한 접두사 제거
            if p and "삼일" not in p and "samil" not in p.lower():
                clean_parts.append(p)

        if clean_parts:
            return " > ".join(clean_parts)

    # 2. 탭 제목 형식이 다를 경우 HTML 태그에서 시도 (Fallback)
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, ".location, .loc_wrap")
        if elements:
            return elements[0].text.strip().replace("\n", " > ")
    except:
        pass

    return "기타 자료"


def update_db(doc_header, real_subject, category, scrape_time, url, content_text):
    """HTML 구조에 새로운 데이터(카드 및 목차)를 추가"""

    soup = load_html_db()

    # 고유 ID 생성 (타임스탬프)
    doc_id = f"doc-{int(time.time())}"

    # 전체 제목 구성: [문서번호] 제목
    full_title = f"[{doc_header}] {real_subject}"

    # ---------------------------------------------------------
    # 1. 목차(TOC) 아이템 추가
    # ---------------------------------------------------------
    toc_list = soup.find(id="toc-list")
    if toc_list:
        new_toc_item = soup.new_tag("a", href=f"#{doc_id}", **{"class": "toc-item"})

        # 제목 div
        title_div = soup.new_tag("span", **{"class": "toc-title"})
        title_div.string = full_title

        # 메타 정보 div (카테고리 + 날짜)
        meta_div = soup.new_tag("div", **{"class": "toc-meta"})

        badge = soup.new_tag("span", **{"class": "badge"})
        badge.string = category  # 여기서 자동 추출된 카테고리가 들어감

        date_span = soup.new_tag("span")
        date_span.string = scrape_time.split(" ")[0]  # 날짜만 표시

        meta_div.append(badge)
        meta_div.append(date_span)

        new_toc_item.append(title_div)
        new_toc_item.append(meta_div)
        toc_list.append(new_toc_item)

    # ---------------------------------------------------------
    # 2. 본문 카드(Card) 추가
    # ---------------------------------------------------------
    content_area = soup.find(id="content-area")
    if content_area:
        # 카드 컨테이너
        card_article = soup.new_tag("article", id=doc_id, **{"class": "doc-card"})

        # (A) 헤더 영역
        header_div = soup.new_tag("div", **{"class": "doc-header"})

        # 카테고리 태그
        cat_tag = soup.new_tag("div", **{"class": "doc-category-tag"})
        cat_tag.append(soup.new_tag("i", **{"class": "fas fa-folder-open", "style": "margin-right:8px;"}))
        cat_tag.append(category)

        # 제목 H1
        h1_title = soup.new_tag("h1", **{"class": "doc-title-text"})
        h1_title.string = full_title

        # 메타 정보 (수집일, 원본링크)
        info_div = soup.new_tag("div", **{"class": "doc-info"})

        # 수집일
        item_date = soup.new_tag("div", **{"class": "info-item"})
        item_date.append(soup.new_tag("i", **{"class": "far fa-calendar-check"}))
        item_date.append(f" 수집일: {scrape_time}")

        # 원본 링크
        item_link = soup.new_tag("div", **{"class": "info-item"})
        item_link.append(soup.new_tag("i", **{"class": "fas fa-external-link-alt"}))
        link_tag = soup.new_tag("a", href=url, target="_blank")
        link_tag.string = " 원본 문서 보기"
        item_link.append(link_tag)

        info_div.append(item_date)
        info_div.append(item_link)

        header_div.append(cat_tag)
        header_div.append(h1_title)
        header_div.append(info_div)

        # (B) 본문 영역
        body_div = soup.new_tag("div", **{"class": "doc-body"})
        body_div.string = content_text

        # 합치기
        card_article.append(header_div)
        card_article.append(body_div)
        content_area.append(card_article)

    # 3. 파일 저장
    save_html_db(soup)
    return full_title


def scrape_page(driver):
    """현재 페이지 스크래핑 및 저장 로직"""
    current_url = driver.current_url
    soup = load_html_db()

    # [중복 방지 실행]
    if check_duplicate(current_url, soup):
        print(f"⚠️ [중복] 이미 저장된 페이지입니다. (저장 건너뜀)")
        return

    try:
        # [1] 문서 번호/헤더 추출 (#objPrintTitle)
        # 예: 금감원사례-029...
        try:
            doc_header = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, "objPrintTitle"))
            ).text.strip()
        except:
            doc_header = "문서번호 미상"

        # [2] 진짜 제목 추출 (table.info 내부)
        real_subject = ""
        try:
            # '제목' 텍스트를 포함하는 th를 찾고 그 옆의 td를 가져옴
            table_title_xpath = "//table[contains(@class, 'info')]//th[contains(text(), '제목')]/following-sibling::td"
            real_subject = driver.find_element(By.XPATH, table_title_xpath).text.strip()
        except:
            # 실패 시 .view_tit 클래스 시도
            try:
                real_subject = driver.find_element(By.CSS_SELECTOR, ".view_tit").text.strip()
            except:
                real_subject = ""  # 제목이 없으면 공란

        # [3] ★ 카테고리 추출 (브라우저 탭 제목 사용) ★
        category_text = extract_category_from_tab_title(driver)

        # [4] 본문 추출 (#content_body)
        try:
            content_text = driver.find_element(By.ID, "content_body").text
        except:
            print("❌ 본문(content_body)을 찾을 수 없습니다.")
            return

        # [5] DB 업데이트 실행
        scrape_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = update_db(doc_header, real_subject, category_text, scrape_time, current_url, content_text)

        print(f"✅ [저장 완료]\n   분류: {category_text}\n   제목: {title}")

    except Exception as e:
        print(f"❌ [에러] {e}")


def main():
    # 라이브러리 체크
    try:
        import bs4
    except ImportError:
        print("⚠️ 'beautifulsoup4' 설치가 필요합니다.\n   > pip install beautifulsoup4")
        return

    print(">>> 브라우저를 시작합니다...")
    driver = init_driver()
    driver.get("https://www.samili.com")

    print("\n" + "=" * 60)
    print("📢 [Samil Scraper Final V2]")
    print("1. 브라우저에서 로그인 & 자료 찾기")
    print("2. 저장하고 싶을 때 'Enter' 키 누르기")
    print("   (브라우저 탭 제목으로 분류를 자동 생성합니다)")
    print("3. 종료하려면 'q' 입력 후 Enter")
    print(f"📂 저장 파일: {os.path.abspath(DB_FILE)}")
    print("=" * 60 + "\n")

    while True:
        user_input = input("👉 명령 입력 (Enter: 저장 / q: 종료): ").strip().lower()

        if user_input == 'q':
            print("프로그램을 종료합니다.")
            driver.quit()
            break
        else:
            try:
                # 브라우저 살아있는지 체크
                _ = driver.window_handles
                print("데이터 확인 중...", end="\r")
                scrape_page(driver)
            except:
                print("❌ 브라우저가 닫혔습니다.")
                break


if __name__ == "__main__":
    main()