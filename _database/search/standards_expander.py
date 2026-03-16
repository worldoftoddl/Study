"""K-IFRS 기준서 확장 백엔드 유틸리티.

Agentic tool executor의 백엔드로 사용되는 함수들을 제공한다:
- _fetch_definition_chunk(): 용어정의 청크 조회 (fetch_term_definitions, explore_related_standards tool)
- reverse_lookup_chunks(): 역방향 검색 (find_referencing_chunks tool)
"""

import re

import numpy as np
from langchain_core.documents import Document

from search.config import CHILDREN_TABLE
from search.db import get_connection
from search.standards_graph import get_display_id
from search.terms_resolver import _load_terms_index

# standard_id에서 번호 추출
_STD_NUM_RE = re.compile(r"(\d{3,4})")

_CHILD_COLUMNS = [
    "chunk_id", "parent_id", "content", "standard_id", "section_type",
    "para_number", "cross_refs", "referenced_standards", "has_table", "has_example",
]
_CHILD_SELECT = ", ".join(_CHILD_COLUMNS)


def _extract_std_number(standard_id: str) -> str | None:
    """'K-IFRS 1016' → '1016'."""
    m = _STD_NUM_RE.search(standard_id)
    return m.group(1) if m else None


def _fetch_definition_chunk(
    std_number: str, index_path: str | None = None,
) -> Document | None:
    """terms_index에서 해당 기준서의 용어정의 청크를 fetch한다."""
    index = _load_terms_index(index_path)
    std_to_chunk = index.get("standard_to_chunk", {})

    display_id = get_display_id(std_number)
    chunk_info = std_to_chunk.get(display_id)
    if not chunk_info:
        return None

    chunk_id = chunk_info["chunk_id"]

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_CHILD_SELECT} FROM {CHILDREN_TABLE} WHERE chunk_id = %s",
                    (chunk_id,),
                )
                row = cur.fetchone()
    except Exception:
        return None

    if not row:
        return None

    r = dict(zip(_CHILD_COLUMNS, row))
    return Document(
        page_content=r.get("content", ""),
        metadata={
            "chunk_id": r.get("chunk_id", chunk_id),
            "parent_id": r.get("parent_id", ""),
            "standard_id": r.get("standard_id", display_id),
            "section_type": r.get("section_type", "main"),
            "para_number": r.get("para_number"),
            "cross_refs": r.get("cross_refs", []),
            "referenced_standards": r.get("referenced_standards", []),
            "has_table": r.get("has_table", False),
            "has_example": r.get("has_example", False),
            "fetched_by_std_ref": True,
            "source_standard": std_number,
        },
    )


def reverse_lookup_chunks(
    standard_numbers: list[str],
    query_vector: list[float] | None = None,
    max_results: int = 10,
) -> list[Document]:
    """특정 기준서를 참조하는 청크를 PostgreSQL 필터로 검색한다.

    referenced_standards && ARRAY[...] 를 사용하여
    해당 기준서들을 참조하는 모든 청크 중 상위 결과를 반환한다.

    Args:
        standard_numbers: 검색 대상 기준서 번호 리스트 (["1109", "1115"]).
        query_vector: 제공 시 벡터 유사도로 정렬. None이면 순서 없이 조회.
        max_results: 최대 반환 문서 수.

    Returns:
        관련 Document 리스트. metadata["fetched_by_reverse_lookup"] = True.
    """
    if not standard_numbers:
        return []

    if query_vector is not None:
        vec = np.array(query_vector, dtype=np.float32)
        sql = f"""
            SELECT {_CHILD_SELECT}
            FROM {CHILDREN_TABLE}
            WHERE referenced_standards && %(std_nums)s
              AND embedding IS NOT NULL
            ORDER BY embedding <=> %(query_vec)s
            LIMIT %(limit)s
        """
        params = {"std_nums": standard_numbers, "query_vec": vec, "limit": max_results}
    else:
        sql = f"""
            SELECT {_CHILD_SELECT}
            FROM {CHILDREN_TABLE}
            WHERE referenced_standards && %(std_nums)s
            LIMIT %(limit)s
        """
        params = {"std_nums": standard_numbers, "limit": max_results}

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    docs = []
    for row in rows:
        r = dict(zip(_CHILD_COLUMNS, row))
        docs.append(Document(
            page_content=r.get("content", ""),
            metadata={
                "chunk_id": r.get("chunk_id", ""),
                "parent_id": r.get("parent_id", ""),
                "standard_id": r.get("standard_id", ""),
                "section_type": r.get("section_type", ""),
                "para_number": r.get("para_number"),
                "cross_refs": r.get("cross_refs", []),
                "referenced_standards": r.get("referenced_standards", []),
                "has_table": r.get("has_table", False),
                "has_example": r.get("has_example", False),
                "fetched_by_reverse_lookup": True,
            },
        ))

    return docs
