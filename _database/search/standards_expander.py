"""K-IFRS 기준서 확장 백엔드 유틸리티.

Agentic tool executor의 백엔드로 사용되는 함수들을 제공한다:
- _fetch_definition_chunk(): 용어정의 청크 조회 (fetch_term_definitions, explore_related_standards tool)
- reverse_lookup_chunks(): 역방향 검색 (find_referencing_chunks tool)
"""

import re

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

from search.config import CHILD_COLLECTION, chunk_id_to_int
from search.standards_graph import get_display_id
from search.terms_resolver import _load_terms_index

# standard_id에서 번호 추출
_STD_NUM_RE = re.compile(r"(\d{3,4})")


def _extract_std_number(standard_id: str) -> str | None:
    """'K-IFRS 1016' → '1016'."""
    m = _STD_NUM_RE.search(standard_id)
    return m.group(1) if m else None


def _fetch_definition_chunk(
    std_number: str, client: QdrantClient, index_path: str | None = None,
) -> Document | None:
    """terms_index에서 해당 기준서의 용어정의 청크를 fetch한다."""
    index = _load_terms_index(index_path)
    std_to_chunk = index.get("standard_to_chunk", {})

    display_id = get_display_id(std_number)
    chunk_info = std_to_chunk.get(display_id)
    if not chunk_info:
        return None

    chunk_id = chunk_info["chunk_id"]
    point_id = chunk_id_to_int(chunk_id)

    try:
        points = client.retrieve(
            collection_name=CHILD_COLLECTION,
            ids=[point_id],
            with_payload=True,
        )
    except Exception:
        return None

    if not points:
        return None

    p = points[0].payload
    return Document(
        page_content=p.get("content", ""),
        metadata={
            "chunk_id": p.get("chunk_id", chunk_id),
            "parent_id": p.get("parent_id", ""),
            "standard_id": p.get("standard_id", display_id),
            "section_type": p.get("section_type", "main"),
            "para_number": p.get("para_number"),
            "cross_refs": p.get("cross_refs", []),
            "referenced_standards": p.get("referenced_standards", []),
            "has_table": p.get("has_table", False),
            "has_example": p.get("has_example", False),
            "fetched_by_std_ref": True,
            "source_standard": std_number,
        },
    )


def reverse_lookup_chunks(
    standard_numbers: list[str],
    client: QdrantClient,
    query_vector: list[float] | None = None,
    max_results: int = 10,
) -> list[Document]:
    """특정 기준서를 참조하는 청크를 Qdrant 필터로 검색한다.

    FieldCondition(key="referenced_standards", match=MatchAny(any=standard_numbers))
    를 사용하여 해당 기준서들을 참조하는 모든 청크 중 상위 결과를 반환한다.

    Args:
        standard_numbers: 검색 대상 기준서 번호 리스트 (["1109", "1115"]).
        client: Qdrant 클라이언트.
        query_vector: 제공 시 벡터 유사도로 정렬. None이면 scroll로 조회.
        max_results: 최대 반환 문서 수.

    Returns:
        관련 Document 리스트. metadata["fetched_by_reverse_lookup"] = True.
    """
    if not standard_numbers:
        return []

    qfilter = Filter(must=[
        FieldCondition(
            key="referenced_standards",
            match=MatchAny(any=standard_numbers),
        )
    ])

    if query_vector is not None:
        results = client.query_points(
            collection_name=CHILD_COLLECTION,
            query=query_vector,
            query_filter=qfilter,
            limit=max_results,
            with_payload=True,
        ).points
    else:
        results, _ = client.scroll(
            collection_name=CHILD_COLLECTION,
            scroll_filter=qfilter,
            limit=max_results,
            with_payload=True,
        )

    docs = []
    for pt in results:
        p = pt.payload
        docs.append(Document(
            page_content=p.get("content", ""),
            metadata={
                "chunk_id": p.get("chunk_id", ""),
                "parent_id": p.get("parent_id", ""),
                "standard_id": p.get("standard_id", ""),
                "section_type": p.get("section_type", ""),
                "para_number": p.get("para_number"),
                "cross_refs": p.get("cross_refs", []),
                "referenced_standards": p.get("referenced_standards", []),
                "has_table": p.get("has_table", False),
                "has_example": p.get("has_example", False),
                "fetched_by_reverse_lookup": True,
            },
        ))

    return docs
