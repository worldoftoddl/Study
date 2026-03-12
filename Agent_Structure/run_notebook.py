"""
노트북용 진입점.

ipynb에서 간단하게 에이전트를 만들고 실행할 수 있는 헬퍼 함수들.

사용 예시 (노트북 셀):
    from agent_skeleton.run_notebook import create_agent, run, arun

    # 기본 에이전트
    agent = create_agent()
    result = run(agent, "K-IFRS 제1115호에 대해 조사해줘")
    print(result)

    # 모델 교체
    agent = create_agent(provider_name="openai", model_name="gpt-4o")

    # 커스텀 도구 추가
    from langchain_core.tools import tool

    @tool
    def my_retriever(query: str) -> str:
        '''내 커스텀 retriever'''
        return "검색 결과..."

    agent = create_agent(tools=[my_retriever])
"""
from __future__ import annotations

from typing import Any

from .core.agent_factory import build_agent


def create_agent(**kwargs: Any) -> Any:
    """
    에이전트를 생성합니다. build_agent의 편의 래퍼.

    자주 쓰는 패턴:
        create_agent()                                    # 기본
        create_agent(provider_name="openai")              # 모델 교체
        create_agent(tool_tags=["search"])                # 검색 도구만
        create_agent(subagent_names=["research-agent"])   # 서브에이전트 포함
        create_agent(tools=[my_custom_tool])              # 외부 도구 추가
    """
    return build_agent(**kwargs)


def run(
    agent: Any,
    message: str,
    *,
    thread_id: str = "notebook-default",
) -> str:
    """
    에이전트를 동기 실행하고 마지막 응답 텍스트를 반환합니다.

    Args:
        agent: build_agent()로 만든 에이전트
        message: 사용자 메시지
        thread_id: 대화 스레드 ID (메모리/체크포인터 사용 시 필요)

    Returns:
        에이전트의 마지막 응답 텍스트
    """
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    # 마지막 메시지에서 텍스트 추출
    last_msg = result["messages"][-1]
    if hasattr(last_msg, "content"):
        return last_msg.content
    return str(last_msg)


async def arun(
    agent: Any,
    message: str,
    *,
    thread_id: str = "notebook-default",
) -> str:
    """
    에이전트를 비동기 실행합니다. (FastAPI 연동 시 유용)

    사용법 (노트북):
        import asyncio
        result = asyncio.run(arun(agent, "질문"))

        # 또는 노트북에서 직접
        result = await arun(agent, "질문")
    """
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    last_msg = result["messages"][-1]
    if hasattr(last_msg, "content"):
        return last_msg.content
    return str(last_msg)


def stream(
    agent: Any,
    message: str,
    *,
    thread_id: str = "notebook-default",
):
    """
    에이전트 응답을 스트리밍합니다.

    사용법:
        for chunk in stream(agent, "질문"):
            print(chunk, end="", flush=True)
    """
    for event in agent.stream(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="messages",
    ):
        # event는 (message, metadata) 튜플
        msg, meta = event if isinstance(event, tuple) else (event, {})
        if hasattr(msg, "content") and msg.content:
            yield msg.content
