"""K-IFRS referenced_standards 기반 관련 기준서 확장 모듈.

검색 결과의 referenced_standards 메타데이터를 분석하여:
1. 참조된 기준서의 핵심 청크(용어정의)를 자동 fetch (순방향 확장)
2. 특정 기준서를 참조하는 청크를 Qdrant 필터로 검색 (역방향 검색)
3. 그래프 기반 multi-hop 확장

xref_resolver가 cross_refs의 '문단 수준' 정밀 참조를 해소한다면,
이 모듈은 referenced_standards의 '기준서 수준' 확장을 담당한다.
"""

import re

from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

from search.config import CHILD_COLLECTION, chunk_id_to_int
from search.standards_graph import get_graph, get_display_id, get_neighbors
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


def expand_referenced_standards(
    docs: list[Document],
    client: QdrantClient,
    max_expansion: int = 5,
    index_path: str | None = None,
) -> list[Document]:
    """검색 결과의 referenced_standards를 분석하여 관련 기준서 핵심 청크를 추가한다.

    각 검색 결과 문서의 referenced_standards에서 고유 기준서 번호를 수집하고,
    빈도순으로 해당 기준서의 용어정의 청크(terms_index)를 fetch한다.

    Args:
        docs: rerank된 검색 결과 Document 리스트.
        client: Qdrant 클라이언트.
        max_expansion: 최대 추가 문서 수.
        index_path: 용어 인덱스 JSON 경로.

    Returns:
        원본 docs + 확장된 Document 리스트.
        확장 문서에는 metadata["fetched_by_std_ref"] = True가 설정된다.
    """
    if not docs:
        return docs

    existing_ids = {doc.metadata.get("chunk_id", "") for doc in docs}
    existing_stds = set()
    for doc in docs:
        num = _extract_std_number(doc.metadata.get("standard_id", ""))
        if num:
            existing_stds.add(num)

    # referenced_standards 빈도 수집
    ref_counts: dict[str, int] = {}
    for doc in docs:
        for ref_std in doc.metadata.get("referenced_standards", []):
            if ref_std not in existing_stds:
                ref_counts[ref_std] = ref_counts.get(ref_std, 0) + 1

    # 빈도순 정렬
    sorted_refs = sorted(ref_counts.keys(), key=lambda s: -ref_counts[s])

    expanded = []
    for std_num in sorted_refs:
        if len(expanded) >= max_expansion:
            break

        defn_doc = _fetch_definition_chunk(std_num, client, index_path)
        if defn_doc and defn_doc.metadata.get("chunk_id") not in existing_ids:
            expanded.append(defn_doc)
            existing_ids.add(defn_doc.metadata["chunk_id"])

    return docs + expanded


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


def graph_expand(
    docs: list[Document],
    client: QdrantClient,
    hops: int = 1,
    max_expansion: int = 5,
    index_path: str | None = None,
) -> list[Document]:
    """그래프 기반 multi-hop 확장: 검색 결과 → 참조 그래프 탐색 → 관련 청크 fetch.

    1. 검색 결과에서 기준서 번호 추출
    2. standards_graph.get_neighbors(hops=N)로 관련 기준서 탐색
    3. 관련 기준서의 용어정의 청크 fetch

    Args:
        docs: 검색 결과 Document 리스트.
        client: Qdrant 클라이언트.
        hops: 그래프 탐색 깊이 (1=직접 참조, 2=간접 참조).
        max_expansion: 최대 추가 문서 수.
        index_path: 용어 인덱스 경로.

    Returns:
        원본 docs + 그래프 확장 Document 리스트.
        확장 문서에는 metadata["fetched_by_graph"] = True, metadata["graph_hop"]이 설정된다.
    """
    if not docs:
        return docs

    existing_ids = {doc.metadata.get("chunk_id", "") for doc in docs}

    # 검색 결과에서 기준서 번호 추출
    source_stds: set[str] = set()
    for doc in docs:
        num = _extract_std_number(doc.metadata.get("standard_id", ""))
        if num:
            source_stds.add(num)

    if not source_stds:
        return docs

    # 그래프 탐색: 모든 소스 기준서의 이웃 합산
    all_neighbors: dict[str, float] = {}
    for src in source_stds:
        neighbors = get_neighbors(src, hops=hops)
        for n, w in neighbors.items():
            if n not in source_stds:
                all_neighbors[n] = all_neighbors.get(n, 0) + w

    # 가중치 순 정렬
    sorted_neighbors = sorted(all_neighbors.keys(), key=lambda s: -all_neighbors[s])

    expanded = []
    for std_num in sorted_neighbors:
        if len(expanded) >= max_expansion:
            break

        defn_doc = _fetch_definition_chunk(std_num, client, index_path)
        if defn_doc and defn_doc.metadata.get("chunk_id") not in existing_ids:
            # fetched_by_std_ref → fetched_by_graph로 교체
            defn_doc.metadata["fetched_by_std_ref"] = False
            defn_doc.metadata["fetched_by_graph"] = True
            defn_doc.metadata["graph_hop"] = hops
            expanded.append(defn_doc)
            existing_ids.add(defn_doc.metadata["chunk_id"])

    return docs + expanded
