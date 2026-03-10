"""agent/nodes.py -- Self-RAG 노드 함수."""

from langchain_core.output_parsers import StrOutputParser

from agent.config import get_llm, get_retriever
from agent.prompts import REWRITE_PROMPT, get_generate_prompt
from agent.state import SelfRagState


def retrieve(state: SelfRagState):
    """쿼리로 관련 문서를 검색한다."""
    query = state["query"]
    retriever = get_retriever()
    docs = retriever.invoke(query)
    return {"context": docs}


def rewrite(state: SelfRagState):
    """일상 용어를 법률 용어로 변환하여 쿼리를 최적화한다."""
    query = state["query"]
    chain = REWRITE_PROMPT | get_llm("small") | StrOutputParser()
    response = chain.invoke({"query": query})
    return {"query": response}


def generate(state: SelfRagState):
    """검색된 문서를 기반으로 답변을 생성한다."""
    context = state["context"]
    query = state["query"]
    chain = get_generate_prompt() | get_llm()
    response = chain.invoke({"context": context, "question": query})
    return {"answer": response.content}


def helpfulness_node(state: SelfRagState):
    """유용성 평가를 위한 pass-through 노드."""
    return state
