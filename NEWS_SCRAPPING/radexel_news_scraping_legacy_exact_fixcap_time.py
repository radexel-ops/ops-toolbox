
import os
import time
import datetime
import difflib

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

MAX_PER_CATEGORY = 5
STRICT_LEGACY = True   # keep original nth-child structure
# no scrolling: match original behavior

def _build_driver():
    chrome_opts = Options()
    chrome_opts.add_argument("--lang=ko-KR")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    # chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_opts)
    driver.set_page_load_timeout(60)
    return driver

def _text_or_empty(driver, sel):
    try:
        return driver.find_element(By.CSS_SELECTOR, sel).text.strip()
    except NoSuchElementException:
        return ""

def _attr_or_empty(driver, sel, attr):
    try:
        val = driver.find_element(By.CSS_SELECTOR, sel).get_attribute(attr)
        return val or ""
    except NoSuchElementException:
        return ""

def _fallback_time(driver, i):
    """Try multiple selectors for time (relative/absolute) for block i."""
    bases = [
        f"#rso > div > div > div:nth-child({i})",
    ]
    time_selectors = [
        " time",  # generic time tag
        " span.WG9SHc span",  # common news time
        " div.OSrXXb.rbYSKb.LfVVr > span",  # original
        " div.SVJrMe span",   # alt container
        " div.Qmr60b span",   # alt
        " span.f.nsa.fwzPFf", # older layout
    ]
    for b in bases:
        for tsel in time_selectors:
            txt = _text_or_empty(driver, b + tsel)
            if txt:
                return txt
    return ""

def _fallback_source(driver, i):
    """Try multiple selectors for publisher/source for block i."""
    bases = [
        f"#rso > div > div > div:nth-child({i}) > div > div > a > div > div.SoAPf",
        f"#rso > div > div > div:nth-child({i})",
    ]
    source_selectors = [
        " div.MgUUmf.NUnG9d span",
        " div.CEMjEf.NUnG9d span",
        " span.xSJvAe",
        " a+div span",
        " g-card span",  # rare
    ]
    for b in bases:
        for ssel in source_selectors:
            txt = _text_or_empty(driver, b + ssel)
            if txt:
                return txt
    return ""

def legacy_collect_items(driver, k):
    """Collect using original nth-child path, with fallbacks for time/source."""
    results = []
    q = 10 if k not in (2, 4) else 6
    for i in range(1, q):
        base = f"#rso > div > div > div:nth-child({i}) > div > div > a"
        try:
            title_sel = base + " > div > div.SoAPf > div.n0jPhd.ynAwRc.MBeuO.nDgy9d"
            title = _text_or_empty(driver, title_sel)
            if not title:
                continue

            href = _attr_or_empty(driver, base, "href")
            if not href:
                continue

            summary_sel = base + " > div > div.SoAPf > div.GI74Re.nDgy9d"
            summary = _text_or_empty(driver, summary_sel)

            company_sel = f"#rso > div > div > div:nth-child({i}) > div > div > a > div > div.SoAPf > div:nth-child(1) > div.MgUUmf.NUnG9d > span"
            company = _text_or_empty(driver, company_sel)
            if not company:
                company = _fallback_source(driver, i)

            time_sel = base + " > div > div.SoAPf > div.OSrXXb.rbYSKb.LfVVr > span"
            tval = _text_or_empty(driver, time_sel)
            if not tval:
                tval = _fallback_time(driver, i)

            results.append((title, company, tval, summary, href))
        except Exception:
            # skip silently to mimic original behavior
            continue
    return results

class go_crawling:
    def __init__(self):
        super().__init__()
        self.start_crawl()

    def start_crawl(self):
        # per-category cap
        caps = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}

        url1 = "https://www.google.com/search?q=(%EB%B0%A9%EC%82%AC%EC%84%A0+OR+%EA%B4%91%EC%9E%90%EB%B9%94+OR+(%EC%A4%91%EC%9E%85%EC%9E%90+OR+%EC%96%91%EC%84%B1%EC%9E%90+OR+(IORT+OR+%EC%82%AC%EC%9D%B4%EB%B2%84%EB%82%98%EC%9D%B4%ED%94%84)))+AND+(%EC%B9%98%EB%A3%8C+AND+(%EC%9E%A5%EB%B9%84+OR+%EA%B8%B0%EA%B8%B0+OR+%EC%B9%98%EB%A3%8C%EA%B8%B0))&tbm=nws&tbs=qdr:d&hl=ko"
        url1w = "https://www.google.com/search?q=(%EB%B0%A9%EC%82%AC%EC%84%A0+OR+%EA%B4%91%EC%9E%90%EB%B9%94+OR+(%EC%A4%91%EC%9E%85%EC%9E%90+OR+%EC%96%91%EC%84%B1%EC%9E%90+OR+(IORT+OR+%EC%82%AC%EC%9D%B4%EB%B2%84%EB%82%98%EC%9D%B4%ED%94%84)))+AND+(%EC%B9%98%EB%A3%8C+AND+(%EC%9E%A5%EB%B9%84+OR+%EA%B8%B0%EA%B8%B0+OR+%EC%B9%98%EB%A3%8C%EA%B8%B0))&tbm=nws&tbs=qdr:w&hl=ko"
        cat1 = "*<광자빔/양성자/중입자 치료기 관련 뉴스>*"

        url2 = "https://www.google.com/search?q=(radiation+OR+photon+OR+(particle+OR+proton))+AND+(device+OR+machine)+AND+(therapy+OR+oncology)+OR+(varian+OR+elekta)&tbm=nws&tbs=qdr:d&hl=en"
        url2w = "https://www.google.com/search?q=(radiation+OR+photon+OR+(particle+OR+proton))+AND+(device+OR+machine)+AND+(therapy+OR+oncology)+OR+(varian+OR+elekta)&tbm=nws&tbs=qdr:w&hl=en"
        cat2 = "*<광자빔/양성자/중입자 치료기 관련 해외뉴스>*"

        url3 = "https://www.google.com/search?q=%EB%A1%9C%EB%B4%87+AND+(%EB%B0%A9%EC%82%AC%EC%84%A0+OR+%EC%88%98%EC%88%A0+OR+%EC%9D%98%EB%A3%8C)+AND+(%EA%B0%9C%EB%B0%9C+OR+%ED%88%AC%EC%9E%90+OR+(%EC%8A%B9%EC%9D%B8+OR+%EA%B8%B0%EC%88%A0+OR+%EA%B7%9C%EC%A0%9C)))&tbm=nws&tbs=qdr:d&hl=ko"
        url3w = "https://www.google.com/search?q=%EB%A1%9C%EB%B4%87+AND+(%EB%B0%A9%EC%82%AC%EC%84%A0+OR+%EC%88%98%EC%88%A0+OR+%EC%9D%98%EB%A3%8C)+AND+(%EA%B0%9C%EB%B0%9C+OR+%ED%88%AC%EC%9E%90+OR+(%EC%8A%B9%EC%9D%B8+OR+%EA%B8%B0%EC%88%A0+OR+%EA%B7%9C%EC%A0%9C)))&tbm=nws&tbs=qdr:w&hl=ko"
        cat3 = "*<로봇수술 관련 뉴스>*"

        url4 = "https://www.google.com/search?q=robot+AND+(radiation+OR+surgery+OR+medical)+AND+(develop+OR+invest+OR+(approval+OR+technology+OR+regulation))&tbm=nws&tbs=qdr:d&hl=en"
        url4w = "https://www.google.com/search?q=robot+AND+(radiation+OR+surgery+OR+medical)+AND+(develop+OR+invest+OR+(approval+OR+technology+OR+regulation))&tbm=nws&tbs=qdr:w&hl=en"
        cat4 = "*<로봇수술 관련 해외뉴스>*"

        url5 = "https://www.google.com/search?q=(%EC%9E%A5%EB%B9%84+OR+%EC%9D%98%EB%A3%8C%EA%B8%B0%EA%B8%B0)+AND+(%ED%97%88%EA%B0%80+OR+%EC%9D%B8%ED%97%88%EA%B0%80+OR+%EC%9E%84%EC%83%81)&tbm=nws&tbs=qdr:d&hl=ko"
        url5w = "https://www.google.com/search?q=(%EC%9E%A5%EB%B9%84+OR+%EC%9D%98%EB%A3%8C%EA%B8%B0%EA%B8%B0)+AND+(%ED%97%88%EA%B0%80+OR+%EC%9D%B8%ED%97%88%EA%B0%80+OR+%EC%9E%84%EC%83%81)&tbm=nws&tbs=qdr:w&hl=ko"
        cat5 = "*<의료기기 인허가>*"

        url6 = "https://www.google.com/search?q=%EC%9D%98%EB%A3%8C+AND+(%EA%B8%B0%EA%B8%B0+OR+%EB%A1%9C%EB%B4%87)+AND+(%ED%88%AC%EC%9E%90+OR+%EC%9C%A0%EC%B9%98+OR+%ED%8E%80%EB%93%9C)&tbm=nws&tbs=qdr:d&hl=ko"
        url6w = "https://www.google.com/search?q=%EC%9D%98%EB%A3%8C+AND+(%EA%B8%B0%EA%B8%B0+OR+%EB%A1%9C%EB%B4%87)+AND+(%ED%88%AC%EC%9E%90+OR+%EC%9C%A0%EC%B9%98+OR+%ED%8E%80%EB%93%9C)&tbm=nws&tbs=qdr:w&hl=ko"
        cat6 = "*<의료로봇/기기 업계 동향>*"

        today = datetime.datetime.today()
        today_str = f"*{today.year}. {today.month}.{today.day}.*"
        is_monday = (today.weekday() == 0)

        news_text = ":large_blue_circle:" + today_str

        for k in [1, 2, 3, 4, 5, 6]:
            if k == 1:
                url = url1w if is_monday else url1
                cat = cat1
            elif k == 2:
                url = url2w if is_monday else url2
                cat = cat2
            elif k == 3:
                url = url3w if is_monday else url3
                cat = cat3
            elif k == 4:
                url = url4w if is_monday else url4
                cat = cat4
            elif k == 5:
                url = url5w if is_monday else url5
                cat = cat5
            elif k == 6:
                url = url6w if is_monday else url6
                cat = cat6
            else:
                continue

            driver = _build_driver()
            try:
                driver.get(url)

                # header for all except 2 and 4 (as original)
                if k != 2 and k != 4:
                    news_text += "\n\n" + cat

                items = legacy_collect_items(driver, k)

                # strict per-category cap
                added = 0
                blacklist = [
                    '코리아인슈', '아시아타임즈', '임순남', '미디어꿈', '엘뉴스', '한국관광협회중앙회', 'Gold Kids', 'agninews',
                    '문화일보', '파이에듀뉴스', '머니플러스', '양주·동두천신문', '이슈엠', 'issue-m', '전북더푸른뉴스', '시니어생활경제신문',
                    '뮤직룸', '香港文汇报山东网', 'Blogsasuna.com', 'Anfix.tv', 'openPR.com', 'Medgadget', 'digitalesiciliana'
                ]

                seen_titles = []
                for (title, source, tval, summary, href) in items:
                    if added >= MAX_PER_CATEGORY:
                        break
                    if not title or not href:
                        continue
                    # dedup by title with fuzzy threshold 0.4 (original logic)
                    dup = False
                    for ex_title in seen_titles:
                        if ex_title == title:
                            dup = True; break
                        try:
                            import difflib as _df
                            if _df.SequenceMatcher(None, title, ex_title).ratio() >= 0.4:
                                dup = True; break
                        except Exception:
                            pass
                    if dup:
                        continue
                    seen_titles.append(title)

                    if not any(b in (source or "") for b in blacklist):
                        news_text += f"\n🔸 *<{href}|{title}>*  @{source}  {tval}"
                        added += 1

            except Exception as e:
                print(f"카테고리 {k} 처리 중 오류: {e}")
            finally:
                try:
                    driver.quit()
                except Exception:
                    pass

        # output/save
        today_str_yyyymmdd = datetime.datetime.now().strftime("%Y%m%d")
        news_text_slack = news_text
        news_text_kakao = news_text.replace("*", "").replace(":large_blue_circle:", "★")

        print(news_text_slack)
        print(news_text_kakao)

        os.makedirs("slack", exist_ok=True)
        with open(os.path.join("slack", f"slack_{today_str_yyyymmdd}.txt"), "wt", encoding="utf-8") as f:
            f.write(news_text_slack)

        os.makedirs("kakao", exist_ok=True)
        with open(os.path.join("kakao", f"kakao_{today_str_yyyymmdd}.txt"), "wt", encoding="utf-8") as f:
            f.write(news_text_kakao)


if __name__ == "__main__":
    go_crawling()
