"""agent/graph.py -- Self-RAG 그래프 조립."""

from langgraph.graph import StateGraph, START, END

from agent.state import SelfRagState
from agent.nodes import retrieve, generate, rewrite, helpfulness_node
from agent.graders import (
    doc_relevance_check_grader,
    hallucination_check,
    check_helpfulness_grader,
)


def build_self_rag_graph():
    """Self-RAG 그래프를 빌드하고 컴파일하여 반환한다.

    그래프 흐름:
        START → retrieve → (관련성 평가)
            → relevant  : generate → (환각 검증)
                → not hallucinated : check_helpfulness → (유용성 평가)
                    → helpful     : END
                    → not helpful : rewrite → retrieve (루프)
                → hallucinated     : generate (재생성)
            → irrelevant : END
    """
    graph = StateGraph(SelfRagState)

    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("rewrite", rewrite)
    graph.add_node("check_helpfulness", helpfulness_node)

    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        doc_relevance_check_grader,
        {"relevant": "generate", "irrelevant": END},
    )
    graph.add_conditional_edges(
        "generate",
        hallucination_check,
        {"not hallucinated": "check_helpfulness", "hallucinated": "generate"},
    )
    graph.add_conditional_edges(
        "check_helpfulness",
        check_helpfulness_grader,
        {"helpful": END, "not helpful": "rewrite"},
    )
    graph.add_edge("rewrite", "retrieve")

    return graph.compile()


self_rag_graph = build_self_rag_graph()
