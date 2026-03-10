"""K-IFRS 용어 정의 자동 주입 모듈.

검색 결과에서 관련 기준서를 식별하고, 해당 기준서의 용어정의 청크를
컨텍스트에 자동으로 추가한다.

용어정의 청크는 기준서의 Appendix A에 해당하며, 규범적(authoritative)
구성요소로서 본문과 동일한 권위를 갖는다.
"""

import json
import os

from langchain_core.documents import Document
from qdrant_client import QdrantClient

from search.config import CHILD_COLLECTION, chunk_id_to_int

# 용어 인덱스 캐시
_terms_index: dict | None = None
_INDEX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "output", "terms_index.json"
)


def _load_terms_index(index_path: str | None = None) -> dict:
    """용어 인덱스를 로드하고 캐시한다."""
    global _terms_index
    if _terms_index is not None:
        return _terms_index

    path = index_path or _INDEX_PATH
    if not os.path.exists(path):
        _terms_index = {"standard_to_chunk": {}, "chunk_id_list": []}
        return _terms_index

    with open(path, "r", encoding="utf-8") as f:
        _terms_index = json.load(f)
    return _terms_index


def inject_term_definitions(
    docs: list[Document],
    client: QdrantClient,
    max_definitions: int = 3,
    index_path: str | None = None,
) -> list[Document]:
    """검색 결과의 기준서에 대한 용어정의 청크를 컨텍스트에 주입한다.

    Args:
        docs: 검색 결과 Document 리스트.
        client: Qdrant 클라이언트.
        max_definitions: 최대 주입할 용어정의 청크 수.
        index_path: 용어 인덱스 JSON 경로 (기본값: output/terms_index.json).

    Returns:
        용어정의 Document가 선두에 추가된 리스트.
        추가된 문서에는 metadata["is_glossary"] = True가 설정된다.
    """
    if not docs:
        return docs

    index = _load_terms_index(index_path)
    std_to_chunk = index.get("standard_to_chunk", {})

    # 검색 결과에서 등장하는 기준서 목록 (순서 유지, 빈도순)
    std_counts: dict[str, int] = {}
    existing_chunk_ids = set()
    for doc in docs:
        std_id = doc.metadata.get("standard_id", "")
        if std_id:
            std_counts[std_id] = std_counts.get(std_id, 0) + 1
        existing_chunk_ids.add(doc.metadata.get("chunk_id", ""))

    # 빈도 높은 기준서 순으로 정렬
    sorted_stds = sorted(std_counts.keys(), key=lambda s: -std_counts[s])

    glossary_docs = []
    for std_id in sorted_stds:
        if len(glossary_docs) >= max_definitions:
            break

        if std_id not in std_to_chunk:
            continue

        chunk_info = std_to_chunk[std_id]
        chunk_id = chunk_info["chunk_id"]

        # 이미 검색 결과에 포함되어 있으면 skip
        if chunk_id in existing_chunk_ids:
            continue

        # Qdrant에서 용어정의 청크 fetch
        point_id = chunk_id_to_int(chunk_id)
        try:
            points = client.retrieve(
                collection_name=CHILD_COLLECTION,
                ids=[point_id],
                with_payload=True,
            )
        except Exception:
            continue

        if not points:
            continue

        p = points[0].payload
        glossary_docs.append(Document(
            page_content=p.get("content", ""),
            metadata={
                "chunk_id": chunk_id,
                "parent_id": p.get("parent_id", ""),
                "standard_id": p.get("standard_id", std_id),
                "section_type": "main",
                "para_number": p.get("para_number"),
                "cross_refs": p.get("cross_refs", []),
                "has_table": False,
                "has_example": False,
                "is_glossary": True,
            },
        ))
        existing_chunk_ids.add(chunk_id)

    # 용어정의를 컨텍스트 선두에 배치
    return glossary_docs + docs
