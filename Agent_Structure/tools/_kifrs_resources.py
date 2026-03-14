"""K-IFRS 검색 도구용 공유 리소스 관리.

리소스(Qdrant, 임베딩, BM25, 하이브리드 리트리버, 리랭커)와
경로 설정(sys.path, search.config 패치)은 모두
get_resources() 첫 호출 시 lazy 초기화됩니다.

DATABASE_DIR 환경변수가 _database 디렉토리 경로를 가리켜야 합니다.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class KifrsResources:
    """초기화된 K-IFRS 검색 리소스."""

    client: object  # QdrantClient
    embeddings: object  # UpstageEmbeddings
    hybrid_retriever: object  # EnsembleRetriever
    reranker: object  # BaseReranker


_resources: KifrsResources | None = None
_path_configured = False
_RETRIEVAL_K = 30


def _docs_fingerprint(docs: list) -> str:
    """BM25 캐시 유효성 검증용 fingerprint."""
    h = hashlib.md5()
    h.update(str(len(docs)).encode())
    if docs:
        h.update(docs[0].page_content.encode())
        h.update(docs[-1].page_content.encode())
    return h.hexdigest()


def _ensure_path_configured() -> Path:
    """DATABASE_DIR 경로 설정 및 search.config 패치. 최초 1회만 실행."""
    global _path_configured

    from ..config import settings

    if not settings.database_dir:
        raise EnvironmentError(
            "DATABASE_DIR 환경변수가 설정되지 않았습니다. "
            ".env 파일에 DATABASE_DIR=/path/to/_database 를 추가하세요."
        )

    database_dir = Path(settings.database_dir)

    if not _path_configured:
        if str(database_dir) not in sys.path:
            sys.path.insert(0, str(database_dir))

        # search/__init__.py의 전체 import를 피하기 위해 config.py만 직접 로드
        import importlib.util
        config_path = database_dir / "search" / "config.py"
        spec = importlib.util.spec_from_file_location("search.config", config_path)
        _cfg = importlib.util.module_from_spec(spec)
        sys.modules["search.config"] = _cfg
        spec.loader.exec_module(_cfg)

        _cfg.QDRANT_PATH = str(database_dir / "qdrant_storage")
        _cfg.CHUNKS_DIR = str(database_dir / "output" / "chunks")
        _path_configured = True

    return database_dir


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

    database_dir = _ensure_path_configured()

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
    bm25_cache = database_dir / "bm25_retriever.pkl"
    bm25_meta = database_dir / "bm25_cache_meta.json"
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
