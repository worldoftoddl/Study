"""agent/state.py -- LangGraph State 정의."""

from typing_extensions import List, TypedDict
from langchain_core.documents import Document


class SelfRagState(TypedDict):
    """Self-RAG 파이프라인 상태."""

    query: str
    context: List[Document]
    answer: str


class RealEstateTaxState(TypedDict):
    """종합부동산세 계산 파이프라인 상태."""

    query: str
    answer: str
    tax_base_equation: str
    tax_deduction: str
    market_ratio: str
    tax_base: str
