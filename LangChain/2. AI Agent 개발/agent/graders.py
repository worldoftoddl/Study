"""agent/graders.py -- Self-RAG 조건부 엣지 함수 (라우팅 로직)."""

from typing import Literal, TypedDict

from agent.config import get_llm
from agent.prompts import (
    HALLUCINATION_CHECK_PROMPT,
    get_relevance_check_prompt,
    get_helpfulness_prompt,
)
from agent.state import SelfRagState


class HallucinationGrade(TypedDict):
    Score: int
    Explanation: str


def doc_relevance_check_grader(state: SelfRagState) -> Literal["relevant", "irrelevant"]:
    """검색된 문서의 관련성을 평가한다."""
    context = state["context"]
    query = state["query"]

    chain = get_relevance_check_prompt() | get_llm("small")
    response = chain.invoke({"documents": context, "question": query})

    if response["Score"] == 1:
        return "relevant"
    return "irrelevant"


def hallucination_check(state: SelfRagState) -> Literal["hallucinated", "not hallucinated"]:
    """생성된 답변의 환각 여부를 평가한다."""
    answer = state["answer"]
    context = [doc.page_content for doc in state["context"]]

    llm = get_llm("small", temperature=0)
    chain = HALLUCINATION_CHECK_PROMPT | llm.with_structured_output(HallucinationGrade)
    response = chain.invoke({"answer": answer, "context": context})

    if response["Score"] == 1:
        return "not hallucinated"
    return "hallucinated"


def check_helpfulness_grader(state: SelfRagState) -> Literal["helpful", "not helpful"]:
    """답변의 유용성을 평가한다."""
    query = state["query"]
    answer = state["answer"]

    chain = get_helpfulness_prompt() | get_llm("small")
    response = chain.invoke({"question": query, "student_answer": answer})

    if response["Score"] == 1:
        return "helpful"
    return "not helpful"
