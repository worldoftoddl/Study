"""
Qdrant 적재 후 검색 테스트
- Child 검색 → Parent 조회 → 형제 Child 묶기 검증
"""

import os

from dotenv import load_dotenv
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient

from search.config import QDRANT_PATH, CHILD_COLLECTION, PARENT_COLLECTION, MODEL_NAME
from search.retriever import search_with_parent

load_dotenv()

TOP_K = 5

QUERIES = [
    "유형자산 감가상각 방법",
    "원가모형과 재평가모형의 차이",
    "유형자산 제거 시 손익 처리",
]


def main():
    print(f"[Model] Upstage {MODEL_NAME} 초기화 중...")
    embeddings = UpstageEmbeddings(
        model=MODEL_NAME,
        upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
    )
    client = QdrantClient(path=QDRANT_PATH)

    child_count = client.count(CHILD_COLLECTION).count
    parent_count = client.count(PARENT_COLLECTION).count
    print(f"[DB] Child: {child_count}, Parent: {parent_count}\n")

    for q in QUERIES:
        print(f"{'='*60}")
        print(f"쿼리: {q}")
        print(f"{'='*60}")

        groups = search_with_parent(client, embeddings, q, top_k=TOP_K)

        for g in groups:
            for mc in g["matched_children"]:
                content_preview = mc["content"][:150].replace("\n", " ")
                print(f"\n  Child Hit: 문단 {mc['para_number']} (score: {mc['score']:.4f})")
                print(f"  Parent: {g['heading']}")
                print(f"  Content: {content_preview}")

            siblings = g["siblings"]
            matched_ids = {mc["chunk_id"] for mc in g["matched_children"]}
            other_siblings = [s for s in siblings if s["chunk_id"] not in matched_ids]

            if other_siblings:
                print(f"  --- Siblings ({len(other_siblings)}건) ---")
                for s in other_siblings:
                    preview = s["content"][:80].replace("\n", " ")
                    print(f"    문단 {s['para_number']}: {preview}")
            else:
                print(f"  --- Siblings: 형제 없음 (단독 문단) ---")

            print(f"  ---")

        print()

    client.close()


if __name__ == "__main__":
    main()
