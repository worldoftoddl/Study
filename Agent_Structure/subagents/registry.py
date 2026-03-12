"""
서브에이전트 레지스트리.

DeepAgents의 subagent는 dict 형태로 정의됩니다:
    {
        "name": "research-agent",
        "description": "...",
        "system_prompt": "...",
        "tools": [...],
        "model": "..."  # Optional, 메인 에이전트 모델 상속
    }

이 모듈에서 서브에이전트 정의를 관리하고,
필요한 것만 골라서 메인 에이전트에 조립합니다.
"""
from __future__ import annotations

from typing import Any, Callable


class SubagentRegistry:
    """서브에이전트 정의 저장소."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}

    def register(self, config: dict[str, Any]) -> None:
        """
        서브에이전트 설정을 등록합니다.

        Args:
            config: DeepAgents subagent 설정 dict.
                    최소 "name"과 "description" 필수.
        """
        name = config.get("name")
        if not name:
            raise ValueError("서브에이전트 config에 'name' 키가 필요합니다.")
        self._agents[name] = config

    def get(self, name: str) -> dict[str, Any]:
        """이름으로 서브에이전트 설정을 가져옵니다."""
        if name not in self._agents:
            available = ", ".join(self._agents.keys())
            raise KeyError(f"서브에이전트 '{name}'을 찾을 수 없습니다. 등록됨: {available}")
        return self._agents[name]

    def get_all(self) -> list[dict[str, Any]]:
        """등록된 모든 서브에이전트 설정을 반환합니다."""
        return list(self._agents.values())

    def get_by_names(self, names: list[str]) -> list[dict[str, Any]]:
        """이름 목록으로 서브에이전트들을 선택적으로 가져옵니다."""
        return [self.get(n) for n in names]

    def list_names(self) -> list[str]:
        return list(self._agents.keys())


# 글로벌 싱글턴
subagent_registry = SubagentRegistry()
