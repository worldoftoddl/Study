from langgraph.graph import StateGraph, START, END
from state import AgentState
from nodes import (
    retrieve, generate, rewrite, helpfulness_node,
    doc_relevance_check_grader, hallucination_check, check_helpfulness_grader
)

graph_builder = StateGraph(AgentState)
graph_builder.add_node('retrieve', retrieve)
# ... edge 연결 ...
self_rag_graph = graph_builder.compile()