"""agent/real_estate.py -- 종합부동산세 계산 파이프라인."""

from datetime import date

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_community.tools import TavilySearchResults
from langgraph.graph import StateGraph, START, END

from agent.config import get_llm, get_retriever, RE_COLLECTION_NAME, RE_DB_PERSIST_DIR
from agent.prompts import (
    TAX_BASE_EQUATION_PROMPT,
    TAX_MARKET_RATIO_PROMPT,
    TAX_BASE_CALCULATE_PROMPT,
    TAX_CALCULATE_PROMPT,
    get_generate_prompt,
)
from agent.state import RealEstateTaxState


# ── 헬퍼: 부동산세 전용 retriever ────────────────────────

def _get_re_retriever():
    return get_retriever(
        collection_name=RE_COLLECTION_NAME,
        persist_directory=RE_DB_PERSIST_DIR,
        k=4,
        fetch_k=10,
    )


# ── 노드 함수 ────────────────────────────────────────────

def get_tax_base_equation(state: RealEstateTaxState) -> dict:
    """종합부동산세 과세표준 계산 수식을 가져온다."""
    retriever = _get_re_retriever()
    small_llm = get_llm("small")

    tax_base_retrieval_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | get_generate_prompt()
        | small_llm
        | StrOutputParser()
    )
    tax_base_equation_chain = (
        {"tax_base_equation_information": RunnablePassthrough()}
        | TAX_BASE_EQUATION_PROMPT
        | small_llm
        | StrOutputParser()
    )
    tax_base_chain = {"tax_base_equation_information": tax_base_retrieval_chain} | tax_base_equation_chain

    question = "주택에 대한 종합부동산세 계산시 과세표준을 계산하는 방법을 수식으로 표현해서 알려주세요"
    tax_base_equation = tax_base_chain.invoke(question)
    return {"tax_base_equation": tax_base_equation}


def get_tax_deduction(state: RealEstateTaxState) -> dict:
    """종합부동산세 공제금액 정보를 가져온다."""
    retriever = _get_re_retriever()
    small_llm = get_llm("small")

    tax_deduction_chain = (
        {
            "context": RunnableLambda(lambda x: x["search_query"]) | retriever,
            "question": RunnableLambda(lambda x: x["full_prompt"]),
        }
        | get_generate_prompt()
        | small_llm
        | StrOutputParser()
    )

    question = {
        "search_query": "납세의무자 유형별 종합부동산세 공제금액",
        "full_prompt": "종합부동산세 공제금액을 납세의무자 유형별로 정리하세요. 반드시 다음 형식으로...",
    }
    tax_deduction = tax_deduction_chain.invoke(question)
    return {"tax_deduction": tax_deduction}


def get_market_ratio(state: RealEstateTaxState) -> dict:
    """웹 검색으로 공정시장가액비율을 가져온다."""
    small_llm = get_llm("small")

    tavily = TavilySearchResults(
        max_results=7,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=True,
        include_images=False,
    )

    query = f"오늘 날짜:({date.today()})에 해당하는 주택 공시가격 공정시장가액비율은 몇%인가요?"
    context = tavily.invoke(query)

    chain = TAX_MARKET_RATIO_PROMPT | small_llm | StrOutputParser()
    market_ratio = chain.invoke({"context": context, "query": query})
    return {"market_ratio": market_ratio}


def calculate_tax_base(state: RealEstateTaxState) -> dict:
    """과세표준을 계산한다."""
    llm = get_llm()

    chain = TAX_BASE_CALCULATE_PROMPT | llm | StrOutputParser()
    tax_base = chain.invoke({
        "tax_base_equation": state["tax_base_equation"],
        "tax_deduction": state["tax_deduction"],
        "market_ratio": state["market_ratio"],
        "query": state["query"],
    })
    return {"tax_base": tax_base}


def calculate_tax(state: RealEstateTaxState) -> dict:
    """세액을 계산한다."""
    retriever = _get_re_retriever()
    llm = get_llm()

    context = retriever.invoke("종합부동산세 제9조 주택 세율표 2주택 3주택")

    chain = TAX_CALCULATE_PROMPT | llm | StrOutputParser()
    tax = chain.invoke({
        "query": state["query"],
        "tax_base": state["tax_base"],
        "context": context,
    })
    return {"answer": tax}


# ── 그래프 조립 ───────────────────────────────────────────

def build_real_estate_graph():
    """종합부동산세 계산 그래프를 빌드하고 컴파일하여 반환한다.

    그래프 흐름:
        START ─┬→ get_tax_base_equation ─┐
               ├→ get_tax_deduction ─────┼→ calculate_tax_base → calculate_tax → END
               └→ get_market_ratio ──────┘
    """
    graph = StateGraph(RealEstateTaxState)

    graph.add_node("get_tax_base_equation", get_tax_base_equation)
    graph.add_node("get_tax_deduction", get_tax_deduction)
    graph.add_node("get_market_ratio", get_market_ratio)
    graph.add_node("calculate_tax_base", calculate_tax_base)
    graph.add_node("calculate_tax", calculate_tax)

    graph.add_edge(START, "get_tax_base_equation")
    graph.add_edge(START, "get_tax_deduction")
    graph.add_edge(START, "get_market_ratio")

    graph.add_edge("get_tax_base_equation", "calculate_tax_base")
    graph.add_edge("get_tax_deduction", "calculate_tax_base")
    graph.add_edge("get_market_ratio", "calculate_tax_base")

    graph.add_edge("calculate_tax_base", "calculate_tax")
    graph.add_edge("calculate_tax", END)

    return graph.compile()


real_estate_graph = build_real_estate_graph()
