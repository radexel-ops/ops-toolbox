"""Web Search Service - AI를 위한 웹 검색 기능"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# DuckDuckGo 검색 (무료, API 키 불필요)
try:
    from duckduckgo_search import DDGS
    DDGS_SUPPORT = True
except ImportError:
    DDGS_SUPPORT = False
    logger.warning("[WebSearch] duckduckgo-search not installed")


@dataclass
class SearchResult:
    """검색 결과"""
    title: str
    snippet: str
    url: str
    position: int


class WebSearchService:
    """웹 검색 서비스 - 여러 검색 제공자 지원"""

    def __init__(self, settings):
        self.settings = settings
        self.serper_api_key = getattr(settings, 'serper_api_key', None)
        self.google_api_key = getattr(settings, 'google_api_key', None)
        self.google_cse_id = getattr(settings, 'google_cse_id', None)

    async def search(
        self,
        query: str,
        num_results: int = 5,
        lang: str = "ko"
    ) -> List[SearchResult]:
        """웹 검색 실행 - 실패 시 자동으로 다음 제공자로 폴백"""

        # Serper API 우선 사용 (더 저렴하고 빠름)
        if self.serper_api_key:
            results = await self._search_serper(query, num_results, lang)
            if results:
                return results
            logger.info("[WebSearch] Serper failed, trying fallback...")

        # Google Custom Search API 대체
        if self.google_api_key and self.google_cse_id:
            results = await self._search_google_cse(query, num_results, lang)
            if results:
                return results
            logger.info("[WebSearch] Google CSE failed, trying fallback...")

        # DuckDuckGo 무료 검색 (API 키 불필요)
        if DDGS_SUPPORT:
            results = await self._search_duckduckgo(query, num_results, lang)
            if results:
                return results

        logger.warning("[WebSearch] All search providers failed or not configured")
        return []

    async def _search_duckduckgo(
        self,
        query: str,
        num_results: int,
        lang: str
    ) -> List[SearchResult]:
        """DuckDuckGo 검색 (무료, API 키 불필요)"""

        try:
            # 동기 API를 사용하므로 run_in_executor로 비동기 처리
            import asyncio

            def sync_search():
                with DDGS() as ddgs:
                    results = list(ddgs.text(
                        query,
                        region='kr-kr' if lang == 'ko' else 'us-en',
                        max_results=num_results
                    ))
                return results

            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(None, sync_search)

            results = []
            for i, item in enumerate(raw_results[:num_results]):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("body", ""),
                    url=item.get("href", ""),
                    position=i + 1
                ))

            logger.info(f"[DuckDuckGo] Found {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"[DuckDuckGo] Search error: {e}")
            return []

    async def _search_serper(
        self,
        query: str,
        num_results: int,
        lang: str
    ) -> List[SearchResult]:
        """Serper API로 검색 (Google Search Results)"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self.serper_api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "q": query,
                        "num": num_results,
                        "gl": "kr" if lang == "ko" else "us",
                        "hl": lang
                    },
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"[Serper] Error {response.status_code}: {response.text}")
                    return []

                data = response.json()
                results = []

                # Organic results
                for i, item in enumerate(data.get("organic", [])[:num_results]):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        url=item.get("link", ""),
                        position=i + 1
                    ))

                logger.info(f"[Serper] Found {len(results)} results for: {query}")
                return results

        except Exception as e:
            logger.error(f"[Serper] Search error: {e}")
            return []

    async def _search_google_cse(
        self,
        query: str,
        num_results: int,
        lang: str
    ) -> List[SearchResult]:
        """Google Custom Search Engine API로 검색"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": self.google_api_key,
                        "cx": self.google_cse_id,
                        "q": query,
                        "num": min(num_results, 10),  # CSE 최대 10개
                        "lr": f"lang_{lang}"
                    },
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"[Google CSE] Error {response.status_code}: {response.text}")
                    return []

                data = response.json()
                results = []

                for i, item in enumerate(data.get("items", [])[:num_results]):
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        url=item.get("link", ""),
                        position=i + 1
                    ))

                logger.info(f"[Google CSE] Found {len(results)} results for: {query}")
                return results

        except Exception as e:
            logger.error(f"[Google CSE] Search error: {e}")
            return []

    def format_results_for_context(
        self,
        results: List[SearchResult],
        query: str
    ) -> str:
        """검색 결과를 AI 컨텍스트 문자열로 포맷"""

        if not results:
            return f"[웹 검색 '{query}': 결과 없음]"

        formatted = [f"[웹 검색 결과: '{query}']"]

        for result in results:
            formatted.append(f"""
{result.position}. {result.title}
   {result.snippet}
   출처: {result.url}
""".strip())

        return "\n".join(formatted)

    def is_available(self) -> bool:
        """검색 서비스 사용 가능 여부"""
        return bool(self.serper_api_key or (self.google_api_key and self.google_cse_id) or DDGS_SUPPORT)


def detect_search_intent(message: str) -> Optional[str]:
    """메시지에서 검색 의도 감지 및 검색어 추출

    반환: 검색어 (검색 의도가 있는 경우) 또는 None
    """

    # 명시적 검색 요청 패턴
    search_patterns = [
        "검색해줘", "검색해 줘", "검색해봐", "찾아봐", "찾아줘",
        "알아봐", "알아봐 줘", "조사해", "조사해봐",
        "search for", "search about", "look up", "find out"
    ]

    message_lower = message.lower()

    for pattern in search_patterns:
        if pattern in message_lower:
            # 검색어 추출 시도 (패턴 앞부분이 검색어일 가능성 높음)
            idx = message_lower.find(pattern)
            search_query = message[:idx].strip()
            if search_query:
                # 불필요한 문자 제거
                search_query = search_query.replace('"', '').replace("'", '').strip()
                return search_query

            # 패턴 뒤에 검색어가 있는 경우
            after = message[idx + len(pattern):].strip()
            if after:
                # "에 대해", "을/를" 등 제거
                for suffix in ["에 대해", "에 대해서", "을", "를", "이", "가"]:
                    after = after.replace(suffix, "").strip()
                if after:
                    return after

    # 최신 정보가 필요한 질문 패턴
    current_info_patterns = [
        "요즘", "최근", "현재", "오늘", "지금",
        "최신", "new", "latest", "recent", "current"
    ]

    question_patterns = [
        "뭐야", "뭐지", "어때", "어떻게",
        "what is", "how is", "what's happening"
    ]

    has_current = any(p in message_lower for p in current_info_patterns)
    has_question = any(p in message_lower for p in question_patterns)

    if has_current and has_question:
        # 핵심 키워드 추출 (간단한 방법)
        # TODO: 더 정교한 키워드 추출
        return message[:100]  # 전체 메시지를 검색어로 사용

    return None
