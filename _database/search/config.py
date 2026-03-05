"""K-IFRS 검색 파이프라인 공유 설정."""

import hashlib

# ── 경로 ──
QDRANT_PATH = "./qdrant_storage"
CHUNKS_DIR = "./output/chunks"

# ── Qdrant 컬렉션명 ──
CHILD_COLLECTION = "kifrs_chunks"
PARENT_COLLECTION = "kifrs_parents"

# ── 임베딩 모델 ──
MODEL_NAME = "solar-embedding-1-large"
VECTOR_SIZE = 4096


def chunk_id_to_int(chunk_id: str) -> int:
    """chunk_id 문자열을 안정적인 양의 정수 ID로 변환 (60-bit via MD5)."""
    h = hashlib.md5(chunk_id.encode("utf-8")).hexdigest()
    return int(h[:15], 16)
