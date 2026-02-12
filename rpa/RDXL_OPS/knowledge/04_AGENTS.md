# 04. Agents - VibeOps

> **문서 목적**: 자동화 에이전트의 구조와 개발 가이드를 정의합니다.

---

## 1. 에이전트 개요

### 1.1 에이전트란?

에이전트는 특정 업무를 자동으로 수행하는 독립적인 프로그램 단위입니다. 각 에이전트는 Tmux의 개별 윈도우에서 실행되며, PM 에이전트의 지시를 받거나 스케줄에 따라 자동 실행됩니다.

### 1.2 에이전트 유형

| 유형 | 역할 | 예시 |
|------|------|------|
| **PM Agent** | 작업 관리자, 명령 분배 | 사용자 명령 해석 및 분배 |
| **Task Agent** | 특정 업무 수행 | 더존, 뉴스 클리핑 |
| **Utility Agent** | 보조 기능 | 로깅, 모니터링 |

---

## 2. 에이전트 아키텍처

### 2.1 기본 구조

```
agents/
├── __init__.py
├── base/
│   ├── __init__.py
│   └── agent_base.py       # 에이전트 베이스 클래스
├── pm/
│   ├── __init__.py
│   └── pm_agent.py         # PM 에이전트
├── douzone/
│   ├── __init__.py
│   ├── douzone_agent.py    # 더존 에이전트
│   └── selectors.py        # 더존 웹 요소 셀렉터
├── news/
│   ├── __init__.py
│   ├── news_agent.py       # 뉴스 에이전트
│   └── sources.py          # 뉴스 소스 설정
└── templates/
    └── new_agent_template.py  # 새 에이전트 템플릿
```

### 2.2 베이스 클래스

```python
# agents/base/agent_base.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any
import logging

class AgentBase(ABC):
    """모든 에이전트의 베이스 클래스"""

    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}
        self.status = "initialized"
        self.last_run = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """에이전트 전용 로거 설정"""
        logger = logging.getLogger(f"agent.{self.name}")
        logger.setLevel(logging.INFO)
        return logger

    @abstractmethod
    async def execute(self, command: str = None) -> dict:
        """
        에이전트 주요 작업 실행

        Args:
            command: 선택적 명령어

        Returns:
            실행 결과 딕셔너리
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """에이전트 상태 확인"""
        pass

    async def start(self):
        """에이전트 시작"""
        self.status = "running"
        self.logger.info(f"Agent {self.name} started")

    async def stop(self):
        """에이전트 중지"""
        self.status = "stopped"
        self.logger.info(f"Agent {self.name} stopped")

    async def run(self, command: str = None) -> dict:
        """실행 래퍼 (로깅, 에러 처리 포함)"""
        start_time = datetime.now()
        self.logger.info(f"Executing: {command or 'default task'}")

        try:
            result = await self.execute(command)
            self.last_run = datetime.now()
            self.logger.info(f"Completed in {datetime.now() - start_time}")
            return {
                "status": "success",
                "result": result,
                "duration": str(datetime.now() - start_time)
            }
        except Exception as e:
            self.logger.error(f"Error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "duration": str(datetime.now() - start_time)
            }
```

---

## 3. 기본 에이전트

### 3.1 PM Agent (작업 관리자)

```python
# agents/pm/pm_agent.py

from ..base.agent_base import AgentBase
from typing import Dict, Any

class PMAgent(AgentBase):
    """
    PM Agent - 작업 관리자

    역할:
    - 사용자 명령 해석
    - 적절한 에이전트에게 작업 분배
    - 결과 취합 및 보고
    """

    def __init__(self):
        super().__init__("pm")
        self.agents: Dict[str, AgentBase] = {}

    def register_agent(self, agent: AgentBase):
        """하위 에이전트 등록"""
        self.agents[agent.name] = agent
        self.logger.info(f"Registered agent: {agent.name}")

    async def execute(self, command: str = None) -> dict:
        """명령 처리"""
        if not command:
            return {"message": "No command provided"}

        # 명령 분석 및 라우팅
        target_agent = self._analyze_command(command)

        if target_agent and target_agent in self.agents:
            return await self.agents[target_agent].run(command)
        else:
            # 직접 처리 또는 Claude Code에 위임
            return {"message": f"Processing: {command}"}

    def _analyze_command(self, command: str) -> str:
        """명령어 분석하여 대상 에이전트 결정"""
        keywords = {
            "douzone": ["더존", "휴가", "근태", "출퇴근"],
            "news": ["뉴스", "기사", "클리핑"]
        }

        command_lower = command.lower()
        for agent, kws in keywords.items():
            if any(kw in command_lower for kw in kws):
                return agent

        return None

    async def health_check(self) -> bool:
        """모든 에이전트 상태 확인"""
        all_healthy = True
        for name, agent in self.agents.items():
            healthy = await agent.health_check()
            if not healthy:
                self.logger.warning(f"Agent {name} is unhealthy")
                all_healthy = False
        return all_healthy
```

### 3.2 Douzone Agent (더존 연동)

```python
# agents/douzone/douzone_agent.py

from ..base.agent_base import AgentBase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os

class DouzoneAgent(AgentBase):
    """
    더존 WEHAGO 연동 에이전트

    기능:
    - 휴가/근태 데이터 자동 추출
    - 구글 캘린더 동기화
    """

    def __init__(self, config: dict = None):
        super().__init__("douzone", config)
        self.driver = None
        self.base_url = "https://wehago.com"

    async def execute(self, command: str = None) -> dict:
        """명령에 따른 작업 실행"""
        if "휴가" in command:
            return await self._get_vacation_data()
        elif "근태" in command:
            return await self._get_attendance_data()
        else:
            return {"error": "Unknown command"}

    async def _get_vacation_data(self) -> dict:
        """휴가 데이터 추출"""
        try:
            self._init_driver()
            await self._login()

            # 휴가 페이지 접근
            self.driver.get(f"{self.base_url}/vacation")

            # 데이터 추출 로직
            # ... (실제 구현)

            return {"vacations": []}

        finally:
            self._close_driver()

    async def _get_attendance_data(self) -> dict:
        """근태 데이터 추출"""
        # 구현
        pass

    async def _login(self):
        """더존 로그인"""
        username = os.getenv("DOUZONE_USERNAME")
        password = os.getenv("DOUZONE_PASSWORD")

        self.driver.get(f"{self.base_url}/login")

        # 로그인 폼 입력
        # ... (실제 구현)

    def _init_driver(self):
        """Selenium 드라이버 초기화"""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        self.driver = webdriver.Chrome(options=options)

    def _close_driver(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    async def health_check(self) -> bool:
        """더존 연결 상태 확인"""
        try:
            # 간단한 연결 테스트
            return True
        except Exception:
            return False
```

### 3.3 News Agent (뉴스 클리핑)

```python
# agents/news/news_agent.py

from ..base.agent_base import AgentBase
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict
import os

class NewsAgent(AgentBase):
    """
    뉴스 클리핑 에이전트

    기능:
    - 키워드 기반 뉴스 스크래핑
    - 요약 생성
    - 슬랙 전송
    """

    def __init__(self, config: dict = None):
        super().__init__("news", config)
        self.keywords = config.get("keywords", ["AI", "자동화", "RPA"])
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

    async def execute(self, command: str = None) -> dict:
        """뉴스 클리핑 실행"""
        articles = await self._scrape_news()
        summary = await self._summarize(articles)

        if self.slack_webhook:
            await self._send_to_slack(summary)

        return {
            "articles_count": len(articles),
            "articles": articles,
            "summary": summary
        }

    async def _scrape_news(self) -> List[Dict]:
        """뉴스 스크래핑"""
        articles = []

        async with httpx.AsyncClient() as client:
            for keyword in self.keywords:
                # 네이버 뉴스 검색 (예시)
                url = f"https://search.naver.com/search.naver?where=news&query={keyword}"

                response = await client.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # 기사 파싱
                for item in soup.select('.news_wrap'):
                    title = item.select_one('.news_tit')
                    if title:
                        articles.append({
                            "keyword": keyword,
                            "title": title.text,
                            "url": title.get('href'),
                            "source": item.select_one('.info_group').text if item.select_one('.info_group') else ""
                        })

        return articles[:10]  # 상위 10개

    async def _summarize(self, articles: List[Dict]) -> str:
        """기사 요약 (Claude API 활용 가능)"""
        summary_lines = []
        for article in articles:
            summary_lines.append(f"- [{article['keyword']}] {article['title']}")

        return "\n".join(summary_lines)

    async def _send_to_slack(self, message: str):
        """슬랙 전송"""
        if not self.slack_webhook:
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                self.slack_webhook,
                json={"text": f"📰 *오늘의 뉴스 클리핑*\n{message}"}
            )

    async def health_check(self) -> bool:
        """뉴스 소스 접근 가능 여부 확인"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("https://www.naver.com", timeout=5)
                return response.status_code == 200
        except Exception:
            return False
```

---

## 4. 새 에이전트 개발 가이드

### 4.1 템플릿

```python
# agents/templates/new_agent_template.py

"""
새 에이전트 템플릿

사용법:
1. 이 파일을 복사하여 agents/{에이전트명}/ 폴더 생성
2. 클래스명과 기능 구현
3. PM Agent에 등록
"""

from ..base.agent_base import AgentBase

class NewAgent(AgentBase):
    """
    에이전트 설명

    기능:
    - 기능 1
    - 기능 2
    """

    def __init__(self, config: dict = None):
        super().__init__("new_agent", config)
        # 추가 초기화

    async def execute(self, command: str = None) -> dict:
        """
        주요 작업 실행

        Args:
            command: 사용자 명령

        Returns:
            실행 결과
        """
        # 구현
        return {"result": "done"}

    async def health_check(self) -> bool:
        """상태 확인"""
        return True
```

### 4.2 개발 체크리스트

- [ ] `AgentBase` 상속
- [ ] `execute()` 메서드 구현
- [ ] `health_check()` 메서드 구현
- [ ] 로깅 활용
- [ ] 에러 핸들링
- [ ] 환경변수 사용 (하드코딩 금지)
- [ ] PM Agent에 등록

---

## 5. 에이전트 라이프사이클

```
┌─────────────┐
│ initialized │ ← 에이전트 생성
└──────┬──────┘
       │ start()
       ▼
┌─────────────┐
│   running   │ ← 정상 동작
└──────┬──────┘
       │ execute()
       ▼
┌─────────────┐
│  executing  │ ← 작업 수행 중
└──────┬──────┘
       │ (완료/에러)
       ▼
┌─────────────┐
│   running   │ ← 대기
└──────┬──────┘
       │ stop()
       ▼
┌─────────────┐
│   stopped   │ ← 중지됨
└─────────────┘
```

---

*Last Updated: 2026-02-10*
