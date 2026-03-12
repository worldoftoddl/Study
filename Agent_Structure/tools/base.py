"""
도구(Tool) 레지스트리.

도구를 등록하고, 이름으로 조회하고, 한꺼번에 꺼내서
create_deep_agent(tools=...)에 넘길 수 있습니다.

설계 의도:
    - 다른 폴더(예: Study/_database/)에서 만든 retriever 함수를
      여기에 등록하면 에이전트가 바로 사용 가능
    - @register_tool 데코레이터로 함수 정의와 동시에 등록 가능
    - 태그 기반 필터링으로 용도별 도구 세트 구성 가능

사용 예시:
    # 방법 1: 데코레이터
    @register_tool(tags=["search"])
    def web_search(query: str) -> str:
        ...

    # 방법 2: 수동 등록
    tool_registry.register(my_retriever_func, tags=["rag"])

    # 도구 꺼내기
    all_tools = tool_registry.get_all()
    search_tools = tool_registry.get_by_tag("search")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolEntry:
    """레지스트리에 저장되는 도구 메타데이터."""
    func: Callable
    name: str
    tags: list[str] = field(default_factory=list)
    description: str = ""


class ToolRegistry:
    """도구 저장소. 싱글턴으로 사용."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        func: Callable,
        *,
        name: str | None = None,
        tags: list[str] | None = None,
        description: str = "",
    ) -> Callable:
        """
        도구를 레지스트리에 등록합니다.

        Args:
            func: @tool 데코레이터가 붙은 함수 또는 일반 함수
            name: 등록 이름 (기본: 함수 이름)
            tags: 분류 태그 (예: ["search"], ["rag", "tax"])
            description: 설명 (기본: docstring)

        Returns:
            원래 함수 (데코레이터 체이닝 가능)
        """
        tool_name = name or getattr(func, "name", func.__name__)
        desc = description or (func.__doc__ or "").strip()
        entry = ToolEntry(func=func, name=tool_name, tags=tags or [], description=desc)
        self._tools[tool_name] = entry
        return func

    def get(self, name: str) -> Callable:
        """이름으로 도구를 가져옵니다."""
        entry = self._tools.get(name)
        if entry is None:
            available = ", ".join(self._tools.keys())
            raise KeyError(f"도구 '{name}'을 찾을 수 없습니다. 등록된 도구: {available}")
        return entry.func

    def get_all(self) -> list[Callable]:
        """등록된 모든 도구를 리스트로 반환합니다."""
        return [e.func for e in self._tools.values()]

    def get_by_tag(self, tag: str) -> list[Callable]:
        """특정 태그가 달린 도구만 반환합니다."""
        return [e.func for e in self._tools.values() if tag in e.tags]

    def list_names(self) -> list[str]:
        """등록된 도구 이름 목록."""
        return list(self._tools.keys())

    def summary(self) -> str:
        """등록된 도구 요약 (디버깅용)."""
        lines = [f"=== ToolRegistry ({len(self._tools)} tools) ==="]
        for name, entry in self._tools.items():
            tags_str = ", ".join(entry.tags) if entry.tags else "-"
            lines.append(f"  [{tags_str}] {name}: {entry.description[:60]}")
        return "\n".join(lines)

    def clear(self) -> None:
        """모든 도구 제거 (테스트용)."""
        self._tools.clear()


# 글로벌 싱글턴
tool_registry = ToolRegistry()


def register_tool(
    func: Callable | None = None,
    *,
    tags: list[str] | None = None,
    name: str | None = None,
    description: str = "",
) -> Any:
    """
    데코레이터로 도구를 등록합니다.

    사용법:
        @register_tool(tags=["search"])
        def web_search(query: str) -> str:
            '''웹 검색'''
            ...

        # 또는 인자 없이
        @register_tool
        def simple_tool(x: str) -> str:
            ...
    """
    def decorator(f: Callable) -> Callable:
        tool_registry.register(f, name=name, tags=tags, description=description)
        return f

    # @register_tool (괄호 없이) 호출된 경우
    if func is not None:
        return decorator(func)

    # @register_tool(tags=["search"]) 형태
    return decorator
