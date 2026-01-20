"""
Master AI Engine
대화 스타일 자율 결정, 에이전트 역할 배분, 대화 흐름 관리
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import random


class ConversationMode(str, Enum):
    """대화 모드 - 마스터 AI가 자율적으로 결정"""
    CASUAL = "casual"          # 가벼운 잡담
    DISCUSSION = "discussion"  # 토론/논의
    RESEARCH = "research"      # 심층 리서치
    BRAINSTORM = "brainstorm"  # 브레인스토밍
    DEBATE = "debate"          # 찬반 토론


@dataclass
class Agent:
    """대화에 참여하는 AI 에이전트"""
    id: str
    name: str
    model: str
    provider: str
    personality: str = ""  # 마스터 AI가 부여하는 개성
    color: str = "#0066ff"  # UI 표시용 색상

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "personality": self.personality,
            "color": self.color
        }


@dataclass
class ConversationState:
    """대화 상태 관리"""
    topic: str = ""
    mode: ConversationMode = ConversationMode.CASUAL
    agents: List[Agent] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    is_running: bool = False
    current_speaker_index: int = 0
    user_intervention: Optional[str] = None  # 사용자 개입 메시지
    user_images: List[Dict[str, Any]] = field(default_factory=list)  # 사용자 첨부 이미지
    web_search_context: Optional[str] = None  # 웹 검색 결과
    enable_web_search: bool = True  # 웹 검색 활성화 여부


class MasterAI:
    """
    마스터 AI 엔진

    역할:
    - 대화 스타일 자율 결정 (잡담, 토론, 리서치 등)
    - 에이전트 역할/개성 동적 배분
    - 대화 흐름 자연스럽게 유지
    - 사용자 개입 시 맥락 통합

    원칙:
    - 구체적 지시 금지
    - AI의 자유로운 사고 보장
    """

    # 에이전트 이름 풀 (마스터 AI가 자유롭게 선택)
    AGENT_NAMES = [
        "Alpha", "Beta", "Gamma", "Delta", "Echo",
        "Nova", "Luna", "Stella", "Orion", "Phoenix",
        "Sage", "Iris", "Atlas", "Zen", "Pixel"
    ]

    # 에이전트 색상 풀
    AGENT_COLORS = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9"
    ]

    def __init__(self):
        self.state = ConversationState()

    def initialize_conversation(
        self,
        topic: str,
        agent_count: int,
        available_models: List[Dict[str, str]],
        auto_start: bool = True
    ) -> Dict[str, Any]:
        """
        새 대화 초기화

        Args:
            topic: 대화 주제
            agent_count: 참여 에이전트 수
            available_models: 사용 가능한 모델 목록
            auto_start: True면 즉시 시작, False면 스타일 제안 후 승인 대기

        Returns:
            초기화 결과 (에이전트 목록, 제안된 스타일 등)
        """
        self.state = ConversationState()
        self.state.topic = topic
        self.state.is_running = False

        # 에이전트 생성
        self._create_agents(agent_count, available_models)

        # 대화 모드는 마스터 AI가 자율적으로 결정하도록 열어둠
        # (첫 번째 응답에서 자연스럽게 톤이 정해짐)

        result = {
            "topic": topic,
            "agents": [agent.to_dict() for agent in self.state.agents],
            "ready": True,
            "auto_start": auto_start
        }

        if auto_start:
            self.state.is_running = True

        return result

    def _create_agents(
        self,
        count: int,
        available_models: List[Dict[str, str]]
    ):
        """에이전트 생성 - 이름과 모델을 다양하게 배분"""

        # 이름과 색상 셔플
        names = random.sample(self.AGENT_NAMES, min(count, len(self.AGENT_NAMES)))
        colors = random.sample(self.AGENT_COLORS, min(count, len(self.AGENT_COLORS)))

        # 모델 순환 배분 (다양한 AI가 참여하도록)
        for i in range(count):
            model_info = available_models[i % len(available_models)]

            agent = Agent(
                id=f"agent_{i}",
                name=names[i] if i < len(names) else f"Agent_{i}",
                model=model_info["id"],
                provider=model_info["provider"],
                personality="",  # AI가 자유롭게 발전시킴
                color=colors[i] if i < len(colors) else "#888888"
            )
            self.state.agents.append(agent)

    def get_next_speaker(self) -> Optional[Agent]:
        """다음 발언자 결정"""
        if not self.state.agents or not self.state.is_running:
            return None

        agent = self.state.agents[self.state.current_speaker_index]
        self.state.current_speaker_index = (
            self.state.current_speaker_index + 1
        ) % len(self.state.agents)

        return agent

    def build_prompt_for_agent(self, agent: Agent) -> str:
        """
        에이전트용 프롬프트 구성

        핵심 원칙: 최소한의 지시만, AI의 자유로운 사고 보장
        """

        # 대화 기록 요약
        recent_messages = self.state.messages[-10:]  # 최근 10개
        history = "\n".join([
            f"[{msg['sender']}]: {msg['content']}"
            for msg in recent_messages
        ])

        # 사용자 개입이 있으면 반영
        user_note = ""
        if self.state.user_intervention:
            user_note = f"\n\n[사용자 메시지]: {self.state.user_intervention}"
            self.state.user_intervention = None  # 한 번 사용 후 초기화

        # 웹 검색 결과가 있으면 포함
        search_note = ""
        if self.state.web_search_context:
            search_note = f"\n\n[참고 정보 (웹 검색 결과)]:\n{self.state.web_search_context}"
            self.state.web_search_context = None  # 한 번 사용 후 초기화

        # 최소한의 컨텍스트만 제공 (자유 보장)
        prompt = f"""주제: {self.state.topic}

이전 대화:
{history if history else "(대화 시작)"}
{user_note}{search_note}

당신은 '{agent.name}'입니다. 위 대화를 이어가세요.
자유롭게 생각하고, 자연스럽게 대화하세요."""

        return prompt

    def set_web_search_context(self, context: str):
        """웹 검색 결과 설정"""
        self.state.web_search_context = context

    def set_enable_web_search(self, enabled: bool):
        """웹 검색 활성화/비활성화"""
        self.state.enable_web_search = enabled

    def is_web_search_enabled(self) -> bool:
        """웹 검색 활성화 여부"""
        return self.state.enable_web_search

    def add_message(
        self,
        sender: str,
        content: str,
        agent_id: Optional[str] = None,
        model: Optional[str] = None
    ):
        """대화에 메시지 추가"""
        self.state.messages.append({
            "sender": sender,
            "content": content,
            "agent_id": agent_id,
            "model": model,
            "turn": self.state.turn_count
        })
        self.state.turn_count += 1

    def user_intervene(self, message: str, images: List[Dict[str, Any]] = None):
        """사용자가 대화에 개입"""
        self.state.user_intervention = message
        self.state.user_images = images or []
        self.add_message(
            sender="User",
            content=message,
            agent_id="user",
            model=None
        )

    def get_pending_images(self) -> List[Dict[str, Any]]:
        """대기 중인 이미지 반환 및 초기화"""
        images = self.state.user_images
        self.state.user_images = []
        return images

    def pause(self):
        """대화 일시정지"""
        self.state.is_running = False

    def resume(self):
        """대화 재개"""
        self.state.is_running = True

    def stop(self):
        """대화 완전 종료"""
        self.state.is_running = False
        self.state.current_speaker_index = 0

    def get_state(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        return {
            "topic": self.state.topic,
            "mode": self.state.mode.value,
            "agents": [a.to_dict() for a in self.state.agents],
            "turn_count": self.state.turn_count,
            "is_running": self.state.is_running,
            "message_count": len(self.state.messages)
        }
