"""
Tavily 웹 검색 도구.

DeepAgents 공식문서의 패턴을 따릅니다.
Tavily는 LLM 에이전트에 최적화된 검색 API로,
일반 검색 외에 뉴스/금융 토픽 필터링을 지원합니다.
"""
from __future__ import annotations

from typing import Literal

from .base import register_tool
from ..config import settings


@register_tool(tags=["search", "web"])
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> dict:
    """
    Tavily API를 사용한 웹 검색.

    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수 (기본 5)
        topic: 검색 카테고리 — "general", "news", "finance"
        include_raw_content: 원본 HTML 포함 여부

    Returns:
        Tavily 검색 결과 딕셔너리
    """
    from tavily import TavilyClient

    api_key = settings.tavily_api_key
    if not api_key:
        return {"error": "TAVILY_API_KEY가 설정되지 않았습니다."}

    client = TavilyClient(api_key=api_key)
    return client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
