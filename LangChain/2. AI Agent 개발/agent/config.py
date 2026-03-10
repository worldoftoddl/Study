"""agent/config.py -- 환경변수 기반 설정 상수 + 팩토리 함수."""

import os
import functools

from dotenv import load_dotenv

load_dotenv()

# ── LLM 모델 ──────────────────────────────────────────────
SMART_LLM_MODEL = os.getenv("SMART_LLM_MODEL", "claude-opus-4-5-20251101")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")
SMALL_LLM_MODEL = os.getenv("SMALL_LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# ── Embedding ─────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "solar-embedding-1-large")

# ── Chroma DB (Self-RAG) ──────────────────────────────────
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "chroma-tax")
DB_PERSIST_DIR = os.getenv("DB_PERSIST_DIR", "./preprocessed-upstage")

# ── Chroma DB (부동산세) ──────────────────────────────────
RE_COLLECTION_NAME = os.getenv("RE_COLLECTION_NAME", "real_estate_tax")
RE_DB_PERSIST_DIR = os.getenv("RE_DB_PERSIST_DIR", "./real_estate_tax_collection")

# ── Retriever ─────────────────────────────────────────────
RETRIEVER_SEARCH_TYPE = os.getenv("RETRIEVER_SEARCH_TYPE", "mmr")
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "10"))
RETRIEVER_FETCH_K = int(os.getenv("RETRIEVER_FETCH_K", "50"))
RETRIEVER_LAMBDA_MULT = float(os.getenv("RETRIEVER_LAMBDA_MULT", "0.6"))


# ── 팩토리 함수 ──────────────────────────────────────────

_LLM_TIERS = {
    "smart": SMART_LLM_MODEL,
    "default": LLM_MODEL,
    "small": SMALL_LLM_MODEL,
}


def get_embedding():
    """Upstage Embedding 인스턴스를 반환한다."""
    from langchain_upstage import UpstageEmbeddings

    return UpstageEmbeddings(model=EMBEDDING_MODEL)


def get_llm(tier: str = "default", **kwargs):
    """ChatAnthropic 인스턴스를 반환한다.

    Args:
        tier: "smart" | "default" | "small"
        **kwargs: ChatAnthropic 추가 인자 (temperature 등)
    """
    from langchain_anthropic import ChatAnthropic

    model = _LLM_TIERS.get(tier, LLM_MODEL)
    temperature = kwargs.pop("temperature", LLM_TEMPERATURE)
    return ChatAnthropic(model=model, temperature=temperature, **kwargs)


def get_retriever(
    collection_name: str | None = None,
    persist_directory: str | None = None,
    search_type: str | None = None,
    k: int | None = None,
    fetch_k: int | None = None,
    lambda_mult: float | None = None,
):
    """Chroma retriever 인스턴스를 반환한다."""
    from langchain_chroma import Chroma

    db = Chroma(
        collection_name=collection_name or COLLECTION_NAME,
        persist_directory=persist_directory or DB_PERSIST_DIR,
        embedding_function=get_embedding(),
    )
    return db.as_retriever(
        search_type=search_type or RETRIEVER_SEARCH_TYPE,
        search_kwargs={
            "k": k or RETRIEVER_K,
            "fetch_k": fetch_k or RETRIEVER_FETCH_K,
            "lambda_mult": lambda_mult or RETRIEVER_LAMBDA_MULT,
        },
    )


@functools.cache
def get_langsmith_client():
    """LangSmith Client 싱글턴을 반환한다."""
    from langsmith import Client

    return Client()
