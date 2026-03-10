"""K-IFRS 쿼리 라우터 — 질의 유형 분류 및 검색 전략 결정.

쿼리를 5가지 유형으로 분류하고, 각 유형에 맞는 검색 전략(필터, top_k 등)을 반환한다.
- normative: 규범적 요건 질의 → main+ag 필터
- interpretive: 해석/근거 질의 → bc 포함 full 검색
- example: 사례 질의 → ie 우선
- citation: 특정 문단 인용 → chunk_id 직접 조회
- comparative: 비교 질의 → broad 검색
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny


class QueryType(str, Enum):
    NORMATIVE = "normative"
    INTERPRETIVE = "interpretive"
    EXAMPLE = "example"
    CITATION = "citation"
    COMPARATIVE = "comparative"


@dataclass
class QueryPlan:
    """쿼리 분류 결과 및 검색 전략."""

    query_type: QueryType
    query_filter: Filter | None = None
    retrieval_k: int = 30
    rerank_n: int = 10
    direct_lookup_ids: list[str] = field(default_factory=list)
    authority_boost: bool = True

    @property
    def skip_vector_search(self) -> bool:
        return self.query_type == QueryType.CITATION and len(self.direct_lookup_ids) > 0


# ── 인용 패턴 정규식 ─────────────────────────────────
_CITATION_PATTERNS = [
    # "제1115호 문단 35" / "제1016호 문단 4.1.2"
    re.compile(r"제(\d{4})호.*?문단\s*([\d.]+(?:[A-Z])?)", re.IGNORECASE),
    # "K-IFRS 1016 문단 62" / "KIFRS1109 문단 4.1.2"
    re.compile(r"K?-?IFRS\s*(\d{4}).*?문단\s*([\d.]+(?:[A-Z])?)", re.IGNORECASE),
    # "IFRS 15 paragraph B22"
    re.compile(r"IFRS\s*(\d+).*?(?:paragraph|para|문단)\s*([A-Z]*[\d.]+[A-Z]?)", re.IGNORECASE),
]

# ── 유형별 키워드 패턴 ───────────────────────────────
_INTERPRETIVE_KEYWORDS = re.compile(
    r"왜|이유|근거|배경|논거|결론도출|BC|basis for conclusions|rationale|why",
    re.IGNORECASE,
)
_EXAMPLE_KEYWORDS = re.compile(
    r"사례|예시|예제|example|illustrat|IE|적용 사례|실무 예",
    re.IGNORECASE,
)
_COMPARATIVE_KEYWORDS = re.compile(
    r"차이|비교|구분|versus|vs\.?|다른\s*점|구별|변경.*전후",
    re.IGNORECASE,
)


def _parse_citations(query: str) -> list[str]:
    """쿼리에서 특정 기준서 문단 인용을 추출하여 chunk_id 목록을 반환한다."""
    chunk_ids = []
    for pattern in _CITATION_PATTERNS:
        for m in pattern.finditer(query):
            std_num = m.group(1).zfill(4)
            para = m.group(2)

            # section_type 추론: B/AG 접두사 → ag, BC → bc, IE → ie
            para_upper = para.upper()
            if para_upper.startswith("B") and not para_upper.startswith("BC"):
                section = "ag"
            elif para_upper.startswith("AG"):
                section = "ag"
            elif para_upper.startswith("BC"):
                section = "bc"
            elif para_upper.startswith("IE"):
                section = "ie"
            else:
                section = "main"

            # IFRS 번호가 3자리면 1000번대로 매핑 (IFRS 15 → 1115)
            if len(m.group(1)) <= 2:
                std_num = str(1100 + int(m.group(1))).zfill(4)
            elif len(m.group(1)) == 3:
                std_num = str(1000 + int(m.group(1))).zfill(4)

            chunk_id = f"KIFRS{std_num}_{section}_{para}"
            chunk_ids.append(chunk_id)
    return chunk_ids


def _build_normative_filter() -> Filter:
    return Filter(must=[
        FieldCondition(key="section_type", match=MatchAny(any=["main", "ag"]))
    ])


def _build_ie_priority_filter() -> Filter:
    return Filter(must=[
        FieldCondition(key="section_type", match=MatchValue(value="ie"))
    ])


def classify_query(query: str) -> QueryPlan:
    """쿼리를 분류하고 검색 전략을 결정한다.

    규칙 기반 분류기. LLM 호출 없이 패턴 매칭으로 빠르게 분류한다.
    모호한 경우 normative(가장 일반적)로 기본 분류한다.
    """
    # 1. Citation 체크 (가장 우선)
    direct_ids = _parse_citations(query)
    if direct_ids:
        return QueryPlan(
            query_type=QueryType.CITATION,
            direct_lookup_ids=direct_ids,
            retrieval_k=5,
            rerank_n=5,
            authority_boost=False,
        )

    # 2. Example 체크
    if _EXAMPLE_KEYWORDS.search(query):
        return QueryPlan(
            query_type=QueryType.EXAMPLE,
            query_filter=_build_ie_priority_filter(),
            retrieval_k=20,
            rerank_n=10,
            authority_boost=False,
        )

    # 3. Interpretive 체크
    if _INTERPRETIVE_KEYWORDS.search(query):
        return QueryPlan(
            query_type=QueryType.INTERPRETIVE,
            query_filter=None,  # full search
            retrieval_k=30,
            rerank_n=10,
            authority_boost=False,
        )

    # 4. Comparative 체크
    if _COMPARATIVE_KEYWORDS.search(query):
        return QueryPlan(
            query_type=QueryType.COMPARATIVE,
            query_filter=None,
            retrieval_k=40,
            rerank_n=15,
            authority_boost=True,
        )

    # 5. 기본값: Normative
    return QueryPlan(
        query_type=QueryType.NORMATIVE,
        query_filter=_build_normative_filter(),
        retrieval_k=30,
        rerank_n=10,
        authority_boost=True,
    )


def apply_authority_boost(
    documents: list, boost_factor: float = 0.85
) -> list:
    """Rerank 후 비규범적 문서(bc/ie)의 점수를 낮춘다.

    Args:
        documents: rerank_score가 metadata에 있는 Document 리스트.
        boost_factor: bc/ie 문서에 곱할 계수 (0~1). 기본 0.85.

    Returns:
        authority boost 적용 후 재정렬된 Document 리스트.
    """
    from langchain_core.documents import Document

    boosted = []
    for doc in documents:
        score = doc.metadata.get("rerank_score", 0.0)
        section = doc.metadata.get("section_type", "")
        if section in ("bc", "ie"):
            score *= boost_factor
        new_doc = Document(
            page_content=doc.page_content,
            metadata={**doc.metadata, "rerank_score": round(score, 6)},
        )
        boosted.append(new_doc)

    boosted.sort(key=lambda d: d.metadata["rerank_score"], reverse=True)
    return boosted
