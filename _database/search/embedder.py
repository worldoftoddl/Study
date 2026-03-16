"""
K-IFRS 청크 임베딩 + PostgreSQL(pgvector) 적재 스크립트
- 모델: Upstage Solar Embedding (solar-embedding-1-large, 4096차원)
- 벡터 DB: PostgreSQL + pgvector
"""

import json
import glob
import os
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from langchain_upstage import UpstageEmbeddings
from tqdm import tqdm

from search.config import (
    CHUNKS_DIR, CHILDREN_TABLE, PARENTS_TABLE,
    MODEL_NAME, VECTOR_SIZE,
)
from search.db import get_connection

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


def init_db(conn):
    """테이블 생성 (이미 있으면 삭제 후 재생성)"""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

        cur.execute(f"DROP TABLE IF EXISTS {CHILDREN_TABLE} CASCADE")
        cur.execute(f"DROP TABLE IF EXISTS {PARENTS_TABLE} CASCADE")

        cur.execute(f"""
            CREATE TABLE {PARENTS_TABLE} (
                chunk_id        TEXT PRIMARY KEY,
                heading_text    TEXT NOT NULL DEFAULT '',
                section_type    TEXT NOT NULL DEFAULT '',
                standard_id     TEXT NOT NULL DEFAULT ''
            )
        """)

        cur.execute(f"""
            CREATE TABLE {CHILDREN_TABLE} (
                chunk_id                TEXT PRIMARY KEY,
                parent_id               TEXT NOT NULL DEFAULT '',
                content                 TEXT NOT NULL DEFAULT '',
                standard_id             TEXT NOT NULL DEFAULT '',
                section_type            TEXT NOT NULL DEFAULT '',
                para_number             TEXT,
                cross_refs              TEXT[] NOT NULL DEFAULT '{{}}'::text[],
                referenced_standards    TEXT[] NOT NULL DEFAULT '{{}}'::text[],
                has_table               BOOLEAN NOT NULL DEFAULT FALSE,
                has_example             BOOLEAN NOT NULL DEFAULT FALSE,
                embedding               vector({VECTOR_SIZE})
            )
        """)

        # btree 인덱스
        cur.execute(f"CREATE INDEX idx_children_parent_id ON {CHILDREN_TABLE} (parent_id)")
        cur.execute(f"CREATE INDEX idx_children_standard_id ON {CHILDREN_TABLE} (standard_id)")
        cur.execute(f"CREATE INDEX idx_children_section_type ON {CHILDREN_TABLE} (section_type)")
        cur.execute(f"CREATE INDEX idx_parents_standard_id ON {PARENTS_TABLE} (standard_id)")

        # GIN 인덱스 (배열 검색)
        cur.execute(f"CREATE INDEX idx_children_referenced_standards ON {CHILDREN_TABLE} USING GIN (referenced_standards)")
        cur.execute(f"CREATE INDEX idx_children_cross_refs ON {CHILDREN_TABLE} USING GIN (cross_refs)")

    conn.commit()
    print("[DB] 테이블 생성 완료")


def create_vector_index(conn):
    """HNSW 벡터 인덱스 생성 (데이터 적재 후 호출)"""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE INDEX idx_children_embedding_hnsw ON {CHILDREN_TABLE}
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 128)
        """)
    conn.commit()
    print("[DB] HNSW 벡터 인덱스 생성 완료")


def insert_parents(conn, parents: list):
    """Parent를 PostgreSQL에 저장"""
    with conn.cursor() as cur:
        for p in parents:
            cur.execute(
                f"""INSERT INTO {PARENTS_TABLE} (chunk_id, heading_text, section_type, standard_id)
                    VALUES (%(chunk_id)s, %(heading_text)s, %(section_type)s, %(standard_id)s)
                    ON CONFLICT (chunk_id) DO NOTHING""",
                {
                    "chunk_id": p["chunk_id"],
                    "heading_text": p.get("heading_text", ""),
                    "section_type": p.get("section_type", ""),
                    "standard_id": p.get("_standard_id", p.get("metadata", {}).get("standard_id", "")),
                },
            )
    conn.commit()
    print(f"[Parents] {len(parents)}개 적재 완료")


def embed_and_insert_children(conn, embeddings: UpstageEmbeddings, children: list):
    """Child 청크를 임베딩하고 PostgreSQL에 적재"""
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

    # PostgreSQL INSERT
    print(f"[DB] {len(children)}개 child 청크 적재 중...")
    with conn.cursor() as cur:
        for idx, c in enumerate(tqdm(children, desc="Inserting")):
            meta = c.get("metadata", {})
            vec = np.array(all_vectors[idx], dtype=np.float32)
            cur.execute(
                f"""INSERT INTO {CHILDREN_TABLE}
                    (chunk_id, parent_id, content, standard_id, section_type,
                     para_number, cross_refs, referenced_standards,
                     has_table, has_example, embedding)
                    VALUES (%(chunk_id)s, %(parent_id)s, %(content)s, %(standard_id)s,
                            %(section_type)s, %(para_number)s, %(cross_refs)s,
                            %(referenced_standards)s, %(has_table)s, %(has_example)s,
                            %(embedding)s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding""",
                {
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
                    "embedding": vec,
                },
            )
    conn.commit()
    print(f"[Children] {len(children)}개 적재 완료")


def update_payloads():
    """벡터 변경 없이 cross_refs, referenced_standards payload만 갱신."""
    _, children = load_json_files(CHUNKS_DIR)
    print(f"[JSON] child 청크 {len(children)}개 로드")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {CHILDREN_TABLE}")
            count = cur.fetchone()[0]
            print(f"[DB] 기존 child 행: {count}개")

            updated = 0
            for c in tqdm(children, desc="Payload 갱신"):
                meta = c.get("metadata", {})
                cur.execute(
                    f"""UPDATE {CHILDREN_TABLE}
                        SET cross_refs = %(cross_refs)s,
                            referenced_standards = %(referenced_standards)s
                        WHERE chunk_id = %(chunk_id)s""",
                    {
                        "chunk_id": c["chunk_id"],
                        "cross_refs": meta.get("cross_refs", []),
                        "referenced_standards": meta.get("referenced_standards", []),
                    },
                )
                updated += 1

        conn.commit()
        print(f"\n[완료] {updated}개 행 payload 갱신")

        # 검증: 샘플 확인
        with conn.cursor() as cur:
            cur.execute(f"SELECT chunk_id, cross_refs, referenced_standards FROM {CHILDREN_TABLE} LIMIT 2")
            for row in cur.fetchall():
                print(f"  - {row[0]}: cross_refs={row[1]}, referenced_standards={row[2]}")


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

    # 3. DB 초기화
    with get_connection() as conn:
        init_db(conn)

        # 4. Parent 적재
        insert_parents(conn, parents)

        # 5. Child 임베딩 + 적재
        embed_and_insert_children(conn, embeddings, children)

        # 6. HNSW 벡터 인덱스 생성 (데이터 적재 후)
        create_vector_index(conn)

        # 7. 결과 확인
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {CHILDREN_TABLE}")
            child_count = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {PARENTS_TABLE}")
            parent_count = cur.fetchone()[0]

        print(f"\n=== 적재 완료 ===")
        print(f"  Child 행: {child_count}")
        print(f"  Parent 행: {parent_count}")


if __name__ == "__main__":
    import sys
    if "--update-payload" in sys.argv:
        update_payloads()
    else:
        main()
