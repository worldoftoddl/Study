"""
K-IFRS 검색 테스트: Dense / BM25 / Hybrid (BM25 0.4 + Dense 0.6)
- Dense: Qdrant + Upstage solar-embedding-1-large
- BM25: kiwipiepy 형태소 분석 + LangChain BM25Retriever
- Hybrid: EnsembleRetriever
"""

import json
import glob
import os
import time

from dotenv import load_dotenv
from kiwipiepy import Kiwi
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient

load_dotenv()

# ── 설정 ──────────────────────────────────────────────
QDRANT_PATH = "./qdrant_storage"
CHUNKS_DIR = "./output/chunks"
CHILD_COLLECTION = "kifrs_chunks"
MODEL_NAME = "solar-embedding-1-large"
TOP_K = 5

QUERIES = [
    "유형자산 감가상각 방법",
    "금융자산의 기대신용손실 측정",
    "수행의무 식별과 거래가격 배분",
    "사용권자산과 리스부채의 최초 측정",
    "연결재무제표 작성 시 지배력 판단 기준",
]

# ── kiwipiepy 토크나이저 ──────────────────────────────
kiwi = Kiwi()
ALLOWED_TAGS = {"NNG", "NNP", "VV", "VA", "SN"}


def kiwi_tokenize(text: str) -> list[str]:
    """kiwipiepy로 형태소 분석 후 NNG, NNP, VV, VA, SN 태그만 추출"""
    tokens = kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in ALLOWED_TAGS]


# ── Qdrant Dense Retriever (payload → metadata 직접 매핑) ─
class QdrantDenseRetriever(BaseRetriever):
    """QdrantVectorStore의 metadata 누락 문제를 우회하는 커스텀 retriever.
    payload의 flat 구조를 그대로 Document metadata로 매핑한다."""

    client: QdrantClient
    embeddings: UpstageEmbeddings
    collection_name: str = CHILD_COLLECTION
    k: int = TOP_K

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


# ── JSON → LangChain Document 변환 ───────────────────
def load_child_documents(chunks_dir: str) -> list[Document]:
    """output/chunks/*.json에서 child 청크를 LangChain Document로 변환"""
    docs = []
    files = sorted(glob.glob(os.path.join(chunks_dir, "*.json")))
    for fpath in files:
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


def print_result(rank: int, score, doc_or_payload, is_document=False):
    """검색 결과 한 건 출력"""
    if is_document:
        meta = doc_or_payload.metadata
        content = doc_or_payload.page_content
        score_str = "    -" if score is None else f"{score:.4f}"
    else:
        meta = doc_or_payload
        content = meta.get("content", "")
        score_str = f"{score:.4f}"

    para = meta.get("para_number", "-")
    stype = meta.get("section_type", "-")
    std_id = meta.get("standard_id", "-")
    preview = content[:80].replace("\n", " ")

    print(f"  [{rank}] score={score_str}  |  {std_id} 문단 {para} ({stype})")
    print(f"      {preview}")


# ── 1. Dense 검색 ─────────────────────────────────────
def test_dense(client: QdrantClient, embeddings: UpstageEmbeddings):
    print("\n" + "=" * 70)
    print("  1. Dense 검색 (Qdrant + Upstage solar-embedding-1-large)")
    print("=" * 70)

    dense_results = {}  # 쿼리별 para_number 리스트 저장 (Hybrid 비교용)

    for q in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"  쿼리: {q}")
        print(f"{'─' * 60}")

        q_vec = embeddings.embed_query(q)
        results = client.query_points(
            collection_name=CHILD_COLLECTION,
            query=q_vec,
            limit=TOP_K,
            with_payload=True,
        ).points

        para_list = []
        for i, hit in enumerate(results, 1):
            print_result(i, hit.score, hit.payload)
            para_list.append(hit.payload.get("para_number", "-"))

        dense_results[q] = para_list

    return dense_results


# ── 2. BM25 검색 ─────────────────────────────────────
def test_bm25(bm25_retriever: BM25Retriever):
    print("\n" + "=" * 70)
    print("  2. BM25 검색 (kiwipiepy 토크나이저)")
    print("=" * 70)

    for q in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"  쿼리: {q}")
        print(f"{'─' * 60}")

        results = bm25_retriever.invoke(q)
        for i, doc in enumerate(results, 1):
            print_result(i, None, doc, is_document=True)


# ── 3. Hybrid 검색 ────────────────────────────────────
def test_hybrid(ensemble_retriever: EnsembleRetriever, dense_results: dict):
    print("\n" + "=" * 70)
    print("  3. Hybrid 검색 (BM25 0.4 + Dense 0.6)")
    print("=" * 70)

    hybrid_results = {}

    for q in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"  쿼리: {q}")
        print(f"{'─' * 60}")

        raw_results = ensemble_retriever.invoke(q)
        # 빈 문서 필터링
        results = [d for d in raw_results if d.page_content.strip()][:TOP_K]
        para_list = []
        for i, doc in enumerate(results, 1):
            print_result(i, None, doc, is_document=True)
            para_list.append(doc.metadata.get("para_number", "-"))

        hybrid_results[q] = para_list

    # Dense vs Hybrid 비교
    print("\n" + "=" * 70)
    print("  Dense vs Hybrid 결과 비교")
    print("=" * 70)

    for q in QUERIES:
        d_paras = dense_results.get(q, [])
        h_paras = hybrid_results.get(q, [])
        d_set = set(str(p) for p in d_paras)
        h_set = set(str(p) for p in h_paras)
        only_dense = d_set - h_set
        only_hybrid = h_set - d_set
        common = d_set & h_set

        print(f"\n  쿼리: {q}")
        print(f"    Dense  문단: {d_paras}")
        print(f"    Hybrid 문단: {h_paras}")
        print(f"    공통: {common if common else '없음'}")
        print(f"    Dense에만: {only_dense if only_dense else '없음'}")
        print(f"    Hybrid에만: {only_hybrid if only_hybrid else '없음'}")


# ── main ──────────────────────────────────────────────
def main():
    print("[1/4] 임베딩 모델 초기화 중...")
    embeddings = UpstageEmbeddings(
        model=MODEL_NAME,
        upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
    )

    print("[2/4] Qdrant 연결 중...")
    client = QdrantClient(path=QDRANT_PATH)
    child_count = client.count(CHILD_COLLECTION).count
    print(f"  → Child 포인트: {child_count}개")

    print("[3/4] JSON에서 child 청크 로딩 중...")
    docs = load_child_documents(CHUNKS_DIR)
    print(f"  → LangChain Document: {len(docs)}개")

    print("[4/4] BM25 인덱스 구축 중 (kiwipiepy 토크나이저)...")
    t0 = time.time()
    bm25_retriever = BM25Retriever.from_documents(
        docs, preprocess_func=kiwi_tokenize, k=TOP_K
    )
    print(f"  → BM25 인덱스 완료 ({time.time() - t0:.1f}초)")

    # Dense retriever (커스텀 — payload를 metadata로 직접 매핑)
    dense_retriever = QdrantDenseRetriever(
        client=client, embeddings=embeddings,
        collection_name=CHILD_COLLECTION, k=TOP_K,
    )

    # Ensemble retriever
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, dense_retriever],
        weights=[0.4, 0.6],
    )

    # ── 테스트 실행 ──
    dense_results = test_dense(client, embeddings)
    test_bm25(bm25_retriever)
    test_hybrid(ensemble_retriever, dense_results)

    client.close()
    print("\n[완료] 모든 검색 테스트가 끝났습니다.")


if __name__ == "__main__":
    main()
