"""
새 도구 템플릿.

이 파일을 복사해서 새 도구를 만드세요.

사용법:
    1. 이 파일을 tools/ 폴더에 복사 (예: tools/my_retriever.py)
    2. 함수명, docstring, 로직 수정
    3. tags를 적절히 설정
    4. tools/__init__.py에 import 추가

그러면 ToolRegistry에 자동 등록되고,
agent_factory에서 tool_registry.get_all() 또는
tool_registry.get_by_tag("my_tag")로 가져올 수 있습니다.
"""
from __future__ import annotations

from .base import register_tool


@register_tool(tags=["example"])
def example_tool(query: str) -> str:
    """
    예시 도구 — 이 docstring이 LLM에게 보이는 도구 설명이 됩니다.

    Args:
        query: 입력 쿼리

    Returns:
        처리 결과 문자열
    """
    # TODO: 실제 로직 구현
    return f"example_tool이 '{query}'를 처리했습니다."
