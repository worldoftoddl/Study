"""K-IFRS 검색 파이프라인 공유 설정."""

import os

# ── 경로 ──
CHUNKS_DIR = "./output/chunks"

# ── PostgreSQL ──
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "kifrs_rag")
PG_USER = os.getenv("PG_USER", "shin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

CHILDREN_TABLE = "kifrs_children"
PARENTS_TABLE = "kifrs_parents"

# ── 임베딩 모델 ──
MODEL_NAME = "solar-embedding-1-large"
VECTOR_SIZE = 4096
