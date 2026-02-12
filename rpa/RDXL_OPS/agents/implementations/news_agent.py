"""
News Agent

Handles news scraping and distribution tasks.
"""

from datetime import datetime
from typing import List, Optional
import asyncio

from ..base.agent_base import AgentBase
from ..registry import register_agent


@register_agent(name="news_agent")
class NewsAgent(AgentBase):
    """
    News Scraping and Distribution Agent.

    Capabilities:
    - News source monitoring
    - Keyword-based filtering
    - Summary generation
    - Slack/Kakao distribution
    """

    def __init__(self, name: str = "news_agent", config: dict = None):
        super().__init__(name, config)
        self.description = "뉴스 수집 및 배포 에이전트"
        self.keywords = config.get("keywords", ["AI", "자동화", "RPA"]) if config else ["AI", "자동화", "RPA"]
        self.sources = config.get("sources", ["naver", "google"]) if config else ["naver", "google"]
        self.capabilities = [
            "news_monitoring",
            "keyword_filtering",
            "summary_generation",
            "multi_channel_distribution"
        ]

    async def execute(self, command: str = None) -> dict:
        """
        Execute news-related tasks.

        Supported commands:
        - fetch: Fetch latest news
        - summary: Get news summary
        - keywords: List active keywords
        - distribute: Send news to channels
        """
        if not command:
            return {
                "message": "News Agent ready. Available commands: fetch, summary, keywords, distribute",
                "capabilities": self.capabilities,
                "active_keywords": self.keywords
            }

        command_lower = command.lower().strip()

        if command_lower == "fetch":
            return await self._fetch_news()
        elif command_lower == "summary":
            return await self._generate_summary()
        elif command_lower == "keywords":
            return await self._list_keywords()
        elif command_lower.startswith("distribute"):
            return await self._distribute_news()
        elif command_lower.startswith("add keyword"):
            keyword = command[12:].strip()
            return await self._add_keyword(keyword)
        else:
            return await self._search_news(command)

    async def _fetch_news(self) -> dict:
        """Fetch latest news from configured sources."""
        # In production, this would actually scrape news
        return {
            "fetched_at": datetime.now().isoformat(),
            "sources": self.sources,
            "articles": [
                {
                    "title": "AI 기술 동향: 2026년 주요 변화",
                    "source": "tech_news",
                    "published": "2026-02-10T09:00:00",
                    "summary": "올해 AI 기술의 주요 발전 방향과 기업 적용 사례",
                    "keywords_matched": ["AI"]
                },
                {
                    "title": "RPA 도입 성공 사례 분석",
                    "source": "business_daily",
                    "published": "2026-02-10T08:30:00",
                    "summary": "국내 기업의 RPA 도입 효과와 ROI 분석",
                    "keywords_matched": ["RPA", "자동화"]
                }
            ],
            "total_articles": 2
        }

    async def _generate_summary(self) -> dict:
        """Generate news summary."""
        return {
            "summary_date": datetime.now().strftime("%Y-%m-%d"),
            "total_articles": 15,
            "by_keyword": {
                "AI": 8,
                "자동화": 5,
                "RPA": 2
            },
            "top_topics": [
                "AI 기술 발전",
                "업무 자동화 트렌드",
                "디지털 전환"
            ],
            "sentiment": {
                "positive": 60,
                "neutral": 35,
                "negative": 5
            }
        }

    async def _list_keywords(self) -> dict:
        """List active monitoring keywords."""
        return {
            "keywords": self.keywords,
            "count": len(self.keywords),
            "last_updated": datetime.now().isoformat()
        }

    async def _add_keyword(self, keyword: str) -> dict:
        """Add a new monitoring keyword."""
        if keyword and keyword not in self.keywords:
            self.keywords.append(keyword)
            return {
                "success": True,
                "message": f"키워드 '{keyword}' 추가됨",
                "keywords": self.keywords
            }
        return {
            "success": False,
            "message": "키워드가 이미 존재하거나 비어있습니다"
        }

    async def _distribute_news(self) -> dict:
        """Distribute news to configured channels."""
        return {
            "distributed": True,
            "channels": ["slack", "kakao"],
            "articles_sent": 5,
            "timestamp": datetime.now().isoformat()
        }

    async def _search_news(self, query: str) -> dict:
        """Search news by query."""
        return {
            "query": query,
            "results": [
                {
                    "title": f"'{query}' 관련 뉴스 1",
                    "source": "example_source",
                    "relevance_score": 0.95
                }
            ],
            "total_results": 1
        }

    async def health_check(self) -> bool:
        """Check agent health."""
        return self.status in ["initialized", "running"]

    def get_status(self) -> dict:
        """Get extended status."""
        base_status = super().get_status()
        base_status.update({
            "description": self.description,
            "keywords": self.keywords,
            "sources": self.sources,
            "capabilities": self.capabilities
        })
        return base_status
