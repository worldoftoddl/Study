"""K-IFRS 검색 도구 패키지 — Agent_Structure 에이전트에 tool로 연결 가능.

사용법 1: build_agent()에 직접 전달
    from _database.tools_for_agent import ALL_TOOLS
    agent = build_agent(tools=ALL_TOOLS)

사용법 2: Agent_Structure tool_registry에 등록
    from _database.tools_for_agent import register_all
    from Agent_Structure.tools.base import tool_registry
    register_all(tool_registry)

사용법 3: 사전 초기화 (선택 — 첫 tool 호출 지연 방지)
    from _database.tools_for_agent import initialize
    initialize()
"""

from .tools import (
    kifrs_search,
    kifrs_fetch_paragraph,
    kifrs_find_referencing,
    kifrs_explore_related,
    kifrs_term_definitions,
)
from ._resources import get_resources as initialize

ALL_TOOLS = [
    kifrs_search,
    kifrs_fetch_paragraph,
    kifrs_find_referencing,
    kifrs_explore_related,
    kifrs_term_definitions,
]

__all__ = [
    "ALL_TOOLS",
    "kifrs_search",
    "kifrs_fetch_paragraph",
    "kifrs_find_referencing",
    "kifrs_explore_related",
    "kifrs_term_definitions",
    "register_all",
    "initialize",
]


def register_all(tool_registry, *, tags: list[str] | None = None) -> None:
    """Agent_Structure의 tool_registry에 K-IFRS 도구를 일괄 등록합니다.

    Args:
        tool_registry: Agent_Structure.tools.base.tool_registry 인스턴스
        tags: 등록 시 사용할 태그 (기본: ["rag", "kifrs"])
    """
    _tags = tags or ["rag", "kifrs"]
    for t in ALL_TOOLS:
        tool_registry.register(
            t, name=t.name, tags=_tags, description=t.description,
        )
