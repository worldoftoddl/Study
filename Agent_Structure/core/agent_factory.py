"""
에이전트 팩토리 — 모든 구성요소를 조립하는 핵심 모듈.

역할:
    1. ModelProvider로부터 LLM 인스턴스 획득
    2. ToolRegistry에서 도구 수집
    3. SubagentRegistry에서 서브에이전트 설정 수집
    4. create_deep_agent()로 최종 에이전트 조립

이 모듈이 유일한 "조립 지점"이므로,
tools/, subagents/, skills/ 폴더에서는 각자 독립적으로 개발하고
여기서 합칩니다.
"""
from __future__ import annotations

from typing import Any, Sequence

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

from ..config import settings
from .model_provider import ModelProvider, get_provider
from ..tools import tool_registry
from ..subagents import subagent_registry


def build_agent(
    *,
    # 모델 설정
    provider: ModelProvider | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,

    # 도구 설정
    tools: list | None = None,
    tool_tags: list[str] | None = None,
    exclude_tools: list[str] | None = None,

    # 서브에이전트 설정
    subagent_names: list[str] | None = None,
    include_all_subagents: bool = False,

    # 프롬프트
    system_prompt: str | None = None,

    # DeepAgents 옵션
    enable_memory: bool = True,
    memory_files: list[str] | None = None,
    skills_dirs: list[str] | None = None,
    backend: Any = None,
    checkpointer: Any = None,
    interrupt_on: dict | None = None,

    # 기타
    **deep_agent_kwargs: Any,
) -> Any:
    """
    DeepAgent를 조립하여 반환합니다.

    이 함수가 프로젝트의 "조립 라인"입니다.
    각 구성요소는 독립적으로 개발하고, 여기서 합칩니다.

    Args:
        provider: ModelProvider 인스턴스 (직접 주입)
        provider_name: 프로바이더 문자열 키 ("anthropic", "openai" 등)
        model_name: 모델명. None이면 settings 기본값 사용.

        tools: 추가 도구 리스트 (레지스트리 외에 직접 전달)
        tool_tags: 레지스트리에서 특정 태그의 도구만 가져오기
        exclude_tools: 레지스트리에서 제외할 도구 이름

        subagent_names: 사용할 서브에이전트 이름 목록
        include_all_subagents: True면 등록된 모든 서브에이전트 포함

        system_prompt: 에이전트 시스템 프롬프트
        enable_memory: 메모리 활성화 여부
        memory_files: AGENTS.md 등 메모리 파일 경로
        skills_dirs: 스킬 디렉토리 경로
        backend: 파일시스템 백엔드
        checkpointer: LangGraph 체크포인터 (HITL에 필수)
        interrupt_on: Human-in-the-loop 설정
        **deep_agent_kwargs: create_deep_agent에 전달할 추가 인자

    Returns:
        CompiledStateGraph (DeepAgent 인스턴스)

    사용 예시:
        # 기본 사용
        agent = build_agent()

        # Anthropic + 검색 도구만 + 리서치 서브에이전트
        agent = build_agent(
            provider_name="anthropic",
            tool_tags=["search"],
            subagent_names=["research-agent"],
            system_prompt="당신은 세법 전문 AI입니다."
        )

        # 외부 retriever를 도구로 직접 추가
        agent = build_agent(
            tools=[my_qdrant_retriever_tool],
            tool_tags=["search"],
        )
    """
    # ── 1. 모델 준비 ──
    if provider is None:
        prov_name = provider_name or settings.default_provider
        m_name = model_name or settings.default_model
        provider = get_provider(prov_name, model_name=m_name)

    llm = provider.get_llm()

    # ── 2. 도구 수집 ──
    collected_tools: list = []
    exclude_set = set(exclude_tools or [])

    if tool_tags:
        # 특정 태그의 도구만
        for tag in tool_tags:
            collected_tools.extend(tool_registry.get_by_tag(tag))
    else:
        # 전체 도구 (_template 제외)
        collected_tools = [
            t for t in tool_registry.get_all()
            if getattr(t, "__name__", "") != "example_tool"
        ]

    # 이름으로 필터링
    collected_tools = [
        t for t in collected_tools
        if getattr(t, "__name__", getattr(t, "name", "")) not in exclude_set
    ]

    # 직접 전달된 도구 추가
    if tools:
        collected_tools.extend(tools)

    # ── 3. 서브에이전트 수집 ──
    subagents = []
    if include_all_subagents:
        subagents = subagent_registry.get_all()
    elif subagent_names:
        subagents = subagent_registry.get_by_names(subagent_names)

    # ── 4. 체크포인터 (HITL / 메모리에 필요) ──
    if checkpointer is None and (interrupt_on or enable_memory):
        checkpointer = MemorySaver()

    # ── 5. 조립 ──
    agent_kwargs: dict[str, Any] = {
        "model": llm,
        "tools": collected_tools,
        **deep_agent_kwargs,
    }

    if system_prompt:
        agent_kwargs["system_prompt"] = system_prompt
    if subagents:
        agent_kwargs["subagents"] = subagents
    if backend:
        agent_kwargs["backend"] = backend
    if checkpointer:
        agent_kwargs["checkpointer"] = checkpointer
    if interrupt_on:
        agent_kwargs["interrupt_on"] = interrupt_on
    if skills_dirs:
        agent_kwargs["skills"] = skills_dirs
    if enable_memory and memory_files:
        agent_kwargs["memory"] = memory_files

    agent = create_deep_agent(**agent_kwargs)

    return agent
