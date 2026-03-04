"""
Qdrant 적재 후 검색 테스트
- Child 검색 → Parent 조회 흐름 검증
"""

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

QDRANT_PATH = "./qdrant_storage"
CHILD_COLLECTION = "kifrs_chunks"
PARENT_COLLECTION = "kifrs_parents"
MODEL_NAME = "nlpai-lab/KURE-v1"
TOP_K = 5

QUERIES = [
    "유형자산 감가상각 방법",
    "원가모형과 재평가모형의 차이",
    "유형자산 제거 시 손익 처리",
]


def chunk_id_to_int(chunk_id: str) -> int:
    import hashlib
    h = hashlib.md5(chunk_id.encode("utf-8")).hexdigest()
    return int(h[:15], 16)


def get_parent_heading(client: QdrantClient, parent_id: str) -> str:
    """parent_id로 Parent 컬렉션에서 heading_text 조회"""
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


def main():
    print(f"[Model] {MODEL_NAME} 로딩 중...")
    model = SentenceTransformer(MODEL_NAME)
    client = QdrantClient(path=QDRANT_PATH)

    child_count = client.count(CHILD_COLLECTION).count
    parent_count = client.count(PARENT_COLLECTION).count
    print(f"[DB] Child: {child_count}, Parent: {parent_count}\n")

    for q in QUERIES:
        print(f"{'='*60}")
        print(f"쿼리: {q}")
        print(f"{'='*60}")

        q_vec = model.encode(q, normalize_embeddings=True).tolist()
        results = client.query_points(
            collection_name=CHILD_COLLECTION,
            query=q_vec,
            limit=TOP_K,
            with_payload=True,
        ).points

        for i, hit in enumerate(results, 1):
            p = hit.payload
            parent_heading = get_parent_heading(client, p.get("parent_id", ""))
            content_preview = p.get("content", "")[:100].replace("\n", " ")

            print(f"\n  [{i}] score={hit.score:.4f}")
            print(f"      chunk_id: {p.get('chunk_id')}")
            print(f"      para_number: {p.get('para_number')}")
            print(f"      section_type: {p.get('section_type')}")
            print(f"      parent heading: {parent_heading}")
            print(f"      content: {content_preview}...")

        print()

    client.close()


if __name__ == "__main__":
    main()
