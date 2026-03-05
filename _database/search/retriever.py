"""QdrantDenseRetriever, load_child_documents, kiwi_tokenize.

Hybrid 검색 파이프라인에서 공유하는 retriever/loader/tokenizer 모듈.
"""

import json
import glob
import os

from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient

from search.config import CHILD_COLLECTION

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
    """Qdrant payload의 flat 구조를 Document metadata로 직접 매핑하는 retriever."""

    client: QdrantClient
    embeddings: UpstageEmbeddings
    collection_name: str = CHILD_COLLECTION
    k: int = 5

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        q_vec = self.embeddings.embed_query(query)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=q_vec,
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
                    "has_table": meta.get("has_table", False),
                    "has_example": meta.get("has_example", False),
                },
            ))
    return docs
