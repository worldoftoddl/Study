"""QdrantDenseRetriever, load_child_documents, kiwi_tokenize.

Hybrid 검색 파이프라인에서 공유하는 retriever/loader/tokenizer 모듈.
"""

import json
import glob
import os
import re

from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from search.config import CHILD_COLLECTION, PARENT_COLLECTION, chunk_id_to_int

# ── 권위수준 필터 프리셋 ─────────────────────────────
AUTHORITY_FILTERS = {
    "normative": Filter(must=[
        FieldCondition(
            key="section_type",
            match=MatchAny(any=["main", "ag"]),
        )
    ]),
    "bc_only": Filter(must=[
        FieldCondition(key="section_type", match=MatchValue(value="bc"))
    ]),
    "ie_only": Filter(must=[
        FieldCondition(key="section_type", match=MatchValue(value="ie"))
    ]),
}


def get_authority_filter(mode: str) -> Filter | None:
    """권위수준 필터 모드에 따라 Qdrant Filter를 반환한다.

    Args:
        mode: "normative" | "full" | "bc_only" | "ie_only"
    Returns:
        Filter 또는 None ("full"인 경우).
    """
    if mode == "full":
        return None
    return AUTHORITY_FILTERS.get(mode)

# ── kiwipiepy 토크나이저 (lazy singleton) ──────────────
_kiwi = None
ALLOWED_TAGS = {"NNG", "NNP", "VV", "VA", "SN"}


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def kiwi_tokenize(text: str) -> list[str]:
    """kiwipiepy로 형태소 분석 후 NNG, NNP, VV, VA, SN 태그만 추출."""
    tokens = _get_kiwi().tokenize(text)
    return [t.form for t in tokens if t.tag in ALLOWED_TAGS]


# ── QdrantDenseRetriever ──────────────────────────────
class QdrantDenseRetriever(BaseRetriever):
    """Qdrant payload의 flat 구조를 Document metadata로 직접 매핑하는 retriever.

    query_filter를 설정하면 벡터 검색 시 Qdrant 필터가 적용된다.
    get_authority_filter()와 함께 사용하여 권위수준 기반 필터링이 가능하다.
    """

    client: QdrantClient
    embeddings: UpstageEmbeddings
    collection_name: str = CHILD_COLLECTION
    k: int = 5
    query_filter: Filter | None = None

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        q_vec = self.embeddings.embed_query(query)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=q_vec,
            query_filter=self.query_filter,
            limit=self.k,
            with_payload=True,
        ).points

        docs = []
        for hit in results:
            p = hit.payload
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
                },
            ))
        return docs


# ── Document 로더 ─────────────────────────────────────
def load_child_documents(chunks_dir: str) -> list[Document]:
    """output/chunks/*.json에서 child 청크를 LangChain Document로 변환."""
    docs = []
    for fpath in sorted(glob.glob(os.path.join(chunks_dir, "*.json"))):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        standard_id = data.get("standard_id", "")
        for c in data.get("children", []):
            meta = c.get("metadata", {})
            docs.append(Document(
                page_content=c["content"],
                metadata={
                    "chunk_id": c["chunk_id"],
                    "parent_id": c.get("parent_id", ""),
                    "standard_id": meta.get("standard_id", standard_id),
                    "section_type": meta.get("section_type", ""),
                    "para_number": meta.get("para_number"),
                    "cross_refs": meta.get("cross_refs", []),
                    "referenced_standards": meta.get("referenced_standards", []),
                    "has_table": meta.get("has_table", False),
                    "has_example": meta.get("has_example", False),
                },
            ))
    return docs


# ── 자연 정렬 키 ─────────────────────────────────────
def _natsort_key(s: str | None) -> list:
    """'BC16A' → ['', 16, 'A'] 형태로 분리하여 자연 정렬."""
    if not s:
        return []
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]


# ── Parent-Child 통합 검색 ────────────────────────────
def fetch_siblings(client: QdrantClient, parent_id: str) -> list[dict]:
    """parent_id로 같은 Parent 아래 모든 Child를 조회 (para_number 순 정렬)."""
    points, _ = client.scroll(
        collection_name=CHILD_COLLECTION,
        scroll_filter=Filter(must=[
            FieldCondition(key="parent_id", match=MatchValue(value=parent_id))
        ]),
        limit=50,
        with_payload=True,
    )
    siblings = [
        {
            "chunk_id": p.payload.get("chunk_id", ""),
            "para_number": p.payload.get("para_number"),
            "content": p.payload.get("content", ""),
        }
        for p in points
    ]
    siblings.sort(key=lambda x: _natsort_key(x["para_number"] or ""))
    return siblings


def _fetch_parent_heading(client: QdrantClient, parent_id: str) -> str:
    """parent_id로 Parent 컬렉션에서 heading_text 조회."""
    pid = chunk_id_to_int(parent_id)
    try:
        points = client.retrieve(
            collection_name=PARENT_COLLECTION,
            ids=[pid],
            with_payload=True,
        )
        if points:
            return points[0].payload.get("heading_text", "(없음)")
    except Exception:
        pass
    return "(조회 실패)"


def search_with_parent(
    client: QdrantClient,
    embeddings: UpstageEmbeddings,
    query: str,
    top_k: int = 5,
    query_filter: Filter | None = None,
) -> list[dict]:
    """Child 검색 → Parent heading 조회 → 형제 Child 묶기.

    Args:
        query_filter: 선택적 Qdrant 필터 (get_authority_filter()로 생성).

    Returns:
        list of {
            "parent_id", "heading",
            "matched_children": [ { chunk_id, para_number, content, score } ],
            "siblings": [ { chunk_id, para_number, content }, ... ]
        }
    """
    q_vec = embeddings.embed_query(query)
    results = client.query_points(
        collection_name=CHILD_COLLECTION,
        query=q_vec,
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    ).points

    seen_parents: dict[str, dict] = {}
    output = []

    for hit in results:
        p = hit.payload
        parent_id = p.get("parent_id", "")
        matched = {
            "chunk_id": p.get("chunk_id", ""),
            "para_number": p.get("para_number"),
            "content": p.get("content", ""),
            "score": hit.score,
        }

        if parent_id in seen_parents:
            seen_parents[parent_id]["matched_children"].append(matched)
            continue

        heading = _fetch_parent_heading(client, parent_id)
        siblings = fetch_siblings(client, parent_id)

        entry = {
            "parent_id": parent_id,
            "heading": heading,
            "matched_children": [matched],
            "siblings": siblings,
        }
        seen_parents[parent_id] = entry
        output.append(entry)

    return output
