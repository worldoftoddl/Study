"""K-IFRS 검색 도구 5종 — Agent_Structure 에이전트에 tool로 연결 가능.

도구 목록:
    1. kifrs_search: 하이브리드 검색(BM25 + Dense) + Reranker
    2. kifrs_fetch_paragraph: 특정 문단 직접 조회 (교차참조 해소)
    3. kifrs_find_referencing: 역방향 참조 검색
    4. kifrs_explore_related: 기준서 참조 그래프 탐색
    5. kifrs_term_definitions: 용어정의(Appendix A) 조회
"""

from __future__ import annotations

from langchain_core.tools import tool

from ._resources import get_resources

_SECTION_LABELS = {
    "main": "본문",
    "ag": "적용지침",
    "bc": "결론도출근거",
    "ie": "사례",
}


def _format_docs(docs: list) -> str:
    """Document 리스트를 LLM 친화적 텍스트로 포맷팅."""
    if not docs:
        return "검색 결과가 없습니다."

    parts = []
    for i, doc in enumerate(docs, 1):
        m = doc.metadata
        std_id = m.get("standard_id", "?")
        section = _SECTION_LABELS.get(
            m.get("section_type", ""), m.get("section_type", "?"),
        )
        para = m.get("para_number", "?")
        score = m.get("rerank_score")

        header = f"[{i}] {std_id} | {section} | 문단 {para}"
        if score is not None:
            header += f" | relevance={score:.4f}"
        parts.append(f"{header}\n{doc.page_content}")

    return "\n\n---\n\n".join(parts)


# ── Tool 1: 하이브리드 검색 ─────────────────────────────


@tool
def kifrs_search(query: str, top_k: int = 5) -> str:
    """K-IFRS(한국채택국제회계기준) 기준서에서 관련 내용을 검색합니다.
    BM25와 Dense Vector 하이브리드 검색 후 Reranker로 최종 정렬합니다.

    Args:
        query: 검색 쿼리 (예: "수익인식의 5단계", "금융자산 기대신용손실 측정")
        top_k: 반환할 상위 문서 수 (기본 5)
    """
    res = get_resources()
    results = res.hybrid_retriever.invoke(query)
    retrieved = [d for d in results if d.page_content.strip()][:30]
    if not retrieved:
        return "검색 결과가 없습니다."
    reranked = res.reranker.rerank(query, retrieved, top_n=top_k)
    return _format_docs(reranked)


# ── Tool 2: 특정 문단 조회 ──────────────────────────────


@tool
def kifrs_fetch_paragraph(
    standard_id: str,
    para_number: str,
    section_type: str = "main",
) -> str:
    """K-IFRS 기준서의 특정 문단 내용을 직접 조회합니다.
    교차참조('문단 XX 참조' 등)가 있을 때 해당 문단의 원문을 가져옵니다.

    Args:
        standard_id: 기준서 ID (예: 'K-IFRS 1116', 'K-IFRS 1109')
        para_number: 문단 번호 (예: '26', 'AG12', 'BC3')
        section_type: 본문=main, 적용지침=ag, 결론근거=bc, 사례=ie (기본 main)
    """
    from search.tools import execute_fetch_paragraphs

    args = {
        "references": [{
            "standard_id": standard_id,
            "para_number": para_number,
            "section_type": section_type,
        }]
    }
    new_docs, result_text = execute_fetch_paragraphs(args, set())
    if new_docs:
        return _format_docs(new_docs)
    return result_text


# ── Tool 3: 역방향 참조 검색 ─────────────────────────────


@tool
def kifrs_find_referencing(
    standard_numbers: list[str],
    max_results: int = 5,
) -> str:
    """특정 기준서를 참조하는 다른 기준서의 문단을 역방향 검색합니다.
    예: '제1109호를 다른 기준서가 어떻게 참조하는가'를 파악할 때 사용합니다.

    Args:
        standard_numbers: 기준서 번호 리스트 (예: ['1109', '1115']). 'K-IFRS' 접두사 없이 숫자만.
        max_results: 최대 반환 문서 수 (기본 5)
    """
    from search.tools import execute_find_referencing_chunks

    args = {"standard_numbers": standard_numbers, "max_results": max_results}
    new_docs, result_text = execute_find_referencing_chunks(args, set())
    if new_docs:
        return f"{result_text}\n\n{_format_docs(new_docs)}"
    return result_text


# ── Tool 4: 기준서 참조 그래프 탐색 ──────────────────────


@tool
def kifrs_explore_related(
    standard_number: str,
    hops: int = 1,
    max_results: int = 3,
) -> str:
    """기준서 참조 그래프를 탐색하여 관련 기준서를 발견합니다.
    특정 기준서와 직접·간접적으로 연결된 기준서와 그 용어정의를 반환합니다.

    Args:
        standard_number: 기준서 번호 (예: '1115'). 'K-IFRS' 접두사 없이 숫자만.
        hops: 탐색 깊이 — 1=직접 참조, 2=간접 참조까지 (기본 1)
        max_results: 최대 반환 기준서 수 (기본 3)
    """
    from search.tools import execute_explore_related_standards

    args = {
        "standard_number": standard_number,
        "hops": hops,
        "max_results": max_results,
    }
    new_docs, result_text = execute_explore_related_standards(args, set())
    if new_docs:
        return f"{result_text}\n\n{_format_docs(new_docs)}"
    return result_text


# ── Tool 5: 용어정의 조회 ───────────────────────────────


@tool
def kifrs_term_definitions(
    standard_numbers: list[str],
    max_definitions: int = 3,
) -> str:
    """K-IFRS 기준서의 용어정의(Appendix A)를 조회합니다.
    '금융자산', '리스', '수행의무' 등 회계 용어의 정확한 정의를 확인합니다.

    Args:
        standard_numbers: 기준서 번호 리스트 (예: ['1109', '1115']). 'K-IFRS' 접두사 없이 숫자만.
        max_definitions: 최대 반환할 용어정의 수 (기본 3)
    """
    from search.tools import execute_fetch_term_definitions

    args = {
        "standard_numbers": standard_numbers,
        "max_definitions": max_definitions,
    }
    new_docs, result_text = execute_fetch_term_definitions(args, set())
    if new_docs:
        return f"{result_text}\n\n{_format_docs(new_docs)}"
    return result_text
