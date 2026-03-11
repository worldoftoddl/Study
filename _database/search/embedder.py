"""
K-IFRS 청크 임베딩 + Qdrant 적재 스크립트
- 모델: Upstage Solar Embedding (solar-embedding-1-large, 4096차원)
- 벡터 DB: Qdrant 로컬 파일 모드
"""

import json
import glob
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, PayloadSchemaType
)
from tqdm import tqdm

from search.config import (
    CHUNKS_DIR, QDRANT_PATH, CHILD_COLLECTION, PARENT_COLLECTION,
    MODEL_NAME, VECTOR_SIZE, chunk_id_to_int,
)

load_dotenv()

# ── embedder 전용 설정 ────────────────────────────────
BATCH_SIZE = 8  # API rate limit 고려
MAX_CHARS = 4000  # solar-embedding-1-large 최대 4000 토큰, 한글+테이블 고려 보수적 설정


def load_json_files(chunks_dir: str):
    """output/chunks/ 내 모든 JSON 파일을 로드해서 parents, children 리스트 반환"""
    all_parents = []
    all_children = []

    files = glob.glob(os.path.join(chunks_dir, "*.json"))
    if not files:
        print(f"[WARN] {chunks_dir}에 JSON 파일이 없습니다.")
        return all_parents, all_children

    for fpath in sorted(files):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        standard_id = data.get("standard_id", Path(fpath).stem)
        for p in data.get("parents", []):
            p["_standard_id"] = standard_id
            all_parents.append(p)
        for c in data.get("children", []):
            c["_standard_id"] = standard_id
            all_children.append(c)

    return all_parents, all_children


def init_qdrant(client: QdrantClient):
    """컬렉션 생성 (이미 있으면 삭제 후 재생성)"""
    # Child 컬렉션 (벡터 있음)
    if client.collection_exists(CHILD_COLLECTION):
        client.delete_collection(CHILD_COLLECTION)
    client.create_collection(
        collection_name=CHILD_COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    # Parent 컬렉션 (벡터 없음, payload only)
    if client.collection_exists(PARENT_COLLECTION):
        client.delete_collection(PARENT_COLLECTION)
    client.create_collection(
        collection_name=PARENT_COLLECTION,
        vectors_config={},  # 벡터 없음
    )


def upsert_parents(client: QdrantClient, parents: list):
    """Parent를 Qdrant에 payload only로 저장"""
    points = []
    for p in parents:
        pid = chunk_id_to_int(p["chunk_id"])
        payload = {
            "chunk_id": p["chunk_id"],
            "heading_text": p.get("heading_text", ""),
            "section_type": p.get("section_type", ""),
            "standard_id": p.get("_standard_id", p.get("metadata", {}).get("standard_id", "")),
        }
        points.append(PointStruct(id=pid, vector={}, payload=payload))

    # 배치 upsert
    for i in range(0, len(points), 100):
        batch = points[i : i + 100]
        client.upsert(collection_name=PARENT_COLLECTION, points=batch)

    print(f"[Parents] {len(points)}개 적재 완료")


def embed_and_upsert_children(client: QdrantClient, embeddings: UpstageEmbeddings, children: list):
    """Child 청크를 임베딩하고 Qdrant에 적재"""
    contents = [c["content"][:MAX_CHARS] for c in children]
    truncated = sum(1 for c in children if len(c["content"]) > MAX_CHARS)
    if truncated:
        print(f"[WARN] {truncated}개 청크가 {MAX_CHARS}자로 잘림")

    # 배치 임베딩
    print(f"[Embedding] {len(contents)}개 child 청크 임베딩 중...")
    all_vectors = []
    for i in tqdm(range(0, len(contents), BATCH_SIZE), desc="Embedding"):
        batch_texts = contents[i : i + BATCH_SIZE]
        vecs = embeddings.embed_documents(batch_texts)
        all_vectors.extend(vecs)
        time.sleep(0.1)  # API rate limit 방지

    # Qdrant 포인트 구성
    points = []
    for idx, c in enumerate(children):
        meta = c.get("metadata", {})
        payload = {
            "chunk_id": c["chunk_id"],
            "parent_id": c.get("parent_id", ""),
            "content": c["content"],
            "standard_id": meta.get("standard_id", c.get("_standard_id", "")),
            "section_type": meta.get("section_type", ""),
            "para_number": meta.get("para_number"),
            "cross_refs": meta.get("cross_refs", []),
            "referenced_standards": meta.get("referenced_standards", []),
            "has_table": meta.get("has_table", False),
            "has_example": meta.get("has_example", False),
        }
        points.append(PointStruct(
            id=chunk_id_to_int(c["chunk_id"]),
            vector=all_vectors[idx],
            payload=payload,
        ))

    # 배치 upsert
    for i in tqdm(range(0, len(points), 100), desc="Upserting"):
        batch = points[i : i + 100]
        client.upsert(collection_name=CHILD_COLLECTION, points=batch)

    print(f"[Children] {len(points)}개 적재 완료")


def main():
    # 1. JSON 로드
    parents, children = load_json_files(CHUNKS_DIR)
    print(f"총 Parents: {len(parents)}, Children: {len(children)}")

    if not children:
        print("적재할 child 청크가 없습니다. 종료합니다.")
        return

    # 2. Upstage Embeddings 초기화
    print(f"[Model] Upstage {MODEL_NAME} 초기화 중...")
    embeddings = UpstageEmbeddings(
        model=MODEL_NAME,
        upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
    )
    print(f"[Model] 초기화 완료 (vector dim: {VECTOR_SIZE})")

    # 3. Qdrant 초기화
    client = QdrantClient(path=QDRANT_PATH)
    init_qdrant(client)

    # 4. Parent 적재
    upsert_parents(client, parents)

    # 5. Child 임베딩 + 적재
    embed_and_upsert_children(client, embeddings, children)

    # 6. 결과 확인
    child_count = client.count(CHILD_COLLECTION).count
    parent_count = client.count(PARENT_COLLECTION).count
    print(f"\n=== 적재 완료 ===")
    print(f"  Child 포인트: {child_count}")
    print(f"  Parent 포인트: {parent_count}")
    print(f"  저장 경로: {QDRANT_PATH}")

    client.close()


if __name__ == "__main__":
    main()
