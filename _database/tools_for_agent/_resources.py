"""K-IFRS 검색 도구용 공유 리소스 관리.

import 시 부작용:
    1. _database/ 디렉토리를 sys.path에 추가
    2. search.config의 상대경로를 절대경로로 패치
    3. Study/.env 로드

리소스(Qdrant, 임베딩, BM25, 하이브리드 리트리버, 리랭커)는
get_resources() 첫 호출 시 lazy 초기화됩니다.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path

# ── 경로 설정 (모듈 로드 시 즉시 실행) ──────────────────

DATABASE_DIR = Path(__file__).resolve().parent.parent

if str(DATABASE_DIR) not in sys.path:
    sys.path.insert(0, str(DATABASE_DIR))

# search.config 상대경로 → 절대경로 패치 (다른 search 모듈 import 전에)
import search.config as _cfg  # noqa: E402

_cfg.QDRANT_PATH = str(DATABASE_DIR / "qdrant_storage")
_cfg.CHUNKS_DIR = str(DATABASE_DIR / "output" / "chunks")

# .env 로드 (Study/.env)
try:
    from dotenv import load_dotenv

    load_dotenv(DATABASE_DIR.parent / ".env")
except ImportError:
    pass


# ── 리소스 컨테이너 ─────────────────────────────────────


@dataclass
class KifrsResources:
    """초기화된 K-IFRS 검색 리소스."""

    client: object  # QdrantClient
    embeddings: object  # UpstageEmbeddings
    hybrid_retriever: object  # EnsembleRetriever
    reranker: object  # BaseReranker


_resources: KifrsResources | None = None
_RETRIEVAL_K = 30


def _docs_fingerprint(docs: list) -> str:
    """BM25 캐시 유효성 검증용 fingerprint."""
    h = hashlib.md5()
    h.update(str(len(docs)).encode())
    if docs:
        h.update(docs[0].page_content.encode())
        h.update(docs[-1].page_content.encode())
    return h.hexdigest()


def get_resources() -> KifrsResources:
    """공유 리소스를 반환합니다. 첫 호출 시 lazy 초기화.

    초기화 항목:
        - UpstageEmbeddings (solar-embedding-1-large)
        - QdrantClient (qdrant_storage/)
        - BM25Retriever (캐시 사용)
        - EnsembleRetriever (BM25 0.4 + Dense 0.6)
        - Reranker (RERANKER_TYPE 환경변수 참조)
    """
    global _resources
    if _resources is not None:
        return _resources

    from langchain_upstage import UpstageEmbeddings
    from qdrant_client import QdrantClient
    from langchain_community.retrievers import BM25Retriever
    from langchain_classic.retrievers import EnsembleRetriever

    from search.config import QDRANT_PATH, CHUNKS_DIR, MODEL_NAME, CHILD_COLLECTION
    from search.retriever import (
        QdrantDenseRetriever,
        load_child_documents,
        kiwi_tokenize,
    )
    from search.reranker import get_reranker

    # 1. 임베딩
    embeddings = UpstageEmbeddings(
        model=MODEL_NAME,
        upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
    )

    # 2. Qdrant
    client = QdrantClient(path=QDRANT_PATH)

    # 3. BM25 (캐시 활용)
    docs = load_child_documents(CHUNKS_DIR)
    bm25_cache = DATABASE_DIR / "bm25_retriever.pkl"
    bm25_meta = DATABASE_DIR / "bm25_cache_meta.json"
    fingerprint = _docs_fingerprint(docs)

    cache_hit = False
    if bm25_cache.exists() and bm25_meta.exists():
        meta = json.loads(bm25_meta.read_text(encoding="utf-8"))
        if meta.get("fingerprint") == fingerprint:
            with open(bm25_cache, "rb") as f:
                bm25_retriever = pickle.load(f)
            bm25_retriever.k = _RETRIEVAL_K
            cache_hit = True

    if not cache_hit:
        bm25_retriever = BM25Retriever.from_documents(
            docs, preprocess_func=kiwi_tokenize, k=_RETRIEVAL_K,
        )
        with open(bm25_cache, "wb") as f:
            pickle.dump(bm25_retriever, f)
        bm25_meta.write_text(
            json.dumps(
                {"fingerprint": fingerprint, "doc_count": len(docs)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    # 4. Hybrid retriever (BM25 0.4 + Dense 0.6)
    dense_retriever = QdrantDenseRetriever(
        client=client,
        embeddings=embeddings,
        collection_name=CHILD_COLLECTION,
        k=_RETRIEVAL_K,
    )
    hybrid_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, dense_retriever],
        weights=[0.4, 0.6],
    )

    # 5. Reranker
    reranker = get_reranker()

    _resources = KifrsResources(
        client=client,
        embeddings=embeddings,
        hybrid_retriever=hybrid_retriever,
        reranker=reranker,
    )
    return _resources
