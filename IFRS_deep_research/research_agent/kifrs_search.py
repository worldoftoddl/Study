"""K-IFRS RAG 검색 도구.

K-IFRS(한국채택국제회계기준) Qdrant 벡터DB를 검색하고 리랭킹하여
에이전트에게 기준서 본문을 반환하는 LangChain tool.
"""

import re
import sys
import threading
from pathlib import Path

from langchain_core.tools import tool

# ── 경로 해소 ──────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATABASE_DIR = _PROJECT_ROOT / "_database"
_QDRANT_PATH = str(_DATABASE_DIR / "qdrant_storage")
_CHUNKS_DIR = str(_DATABASE_DIR / "output" / "chunks")

# _database/를 sys.path에 추가하여 "import search" 가능하게 함
_db_path = str(_DATABASE_DIR)
if _db_path not in sys.path:
    sys.path.insert(0, _db_path)

# ── 섹션 타입 한국어 레이블 ────────────────────────────
_SECTION_LABELS = {
    "main": "본문",
    "ag": "적용지침(AG)",
    "bc": "결론도출근거(BC)",
    "ie": "사례(IE)",
}


class _KIFRSPipeline:
    """K-IFRS 검색 파이프라인 lazy singleton.

    QdrantClient, UpstageEmbeddings, Reranker 등 heavy 객체를
    첫 호출 시에만 초기화한다.
    """

    _instance: "_KIFRSPipeline | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # config 모듈의 상대 경로를 절대 경로로 패치
        import search.config as _cfg

        _cfg.QDRANT_PATH = _QDRANT_PATH
        _cfg.CHUNKS_DIR = _CHUNKS_DIR

        # 그래프 싱글턴을 올바른 경로로 초기화
        # (standards_graph.py는 module-level import로 CHUNKS_DIR 값을 복사하므로
        #  config 패치만으로는 불충분 — 명시적으로 chunks_dir 전달)
        from search.standards_graph import get_graph

        get_graph(chunks_dir=_CHUNKS_DIR)

        from langchain_upstage import UpstageEmbeddings
        from qdrant_client import QdrantClient

        from search import CHILD_COLLECTION, get_reranker

        self.client = QdrantClient(path=_QDRANT_PATH)
        self.embeddings = UpstageEmbeddings(model="solar-embedding-1-large")
        self.reranker = get_reranker()
        self.collection_name = CHILD_COLLECTION

    @classmethod
    def get(cls) -> "_KIFRSPipeline":
        """싱글턴 인스턴스를 반환한다. 최초 호출 시 초기화 (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def run(self, query: str) -> tuple:
        """7단계 파이프라인을 실행하고 (docs, plan)을 반환한다."""
        from langchain_core.documents import Document

        from search import (
            QdrantDenseRetriever,
            apply_authority_boost,
            classify_query,
            expand_referenced_standards,
            graph_expand,
            inject_term_definitions,
            resolve_cross_refs,
        )
        from search.config import CHILD_COLLECTION, chunk_id_to_int
        from search.standards_expander import reverse_lookup_chunks

        # 1. 쿼리 분류
        plan = classify_query(query)

        # 2. 검색
        if plan.skip_vector_search:
            # Citation 타입: 직접 point fetch
            docs = []
            for cid in plan.direct_lookup_ids:
                pid = chunk_id_to_int(cid)
                try:
                    points = self.client.retrieve(
                        collection_name=CHILD_COLLECTION,
                        ids=[pid],
                        with_payload=True,
                    )
                    if points:
                        p = points[0].payload
                        docs.append(
                            Document(
                                page_content=p.get("content", ""),
                                metadata={
                                    "chunk_id": p.get("chunk_id", cid),
                                    "parent_id": p.get("parent_id", ""),
                                    "standard_id": p.get("standard_id", ""),
                                    "section_type": p.get("section_type", ""),
                                    "para_number": p.get("para_number"),
                                    "cross_refs": p.get("cross_refs", []),
                                    "referenced_standards": p.get(
                                        "referenced_standards", []
                                    ),
                                },
                            )
                        )
                except Exception:
                    continue
        else:
            retriever = QdrantDenseRetriever(
                client=self.client,
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                k=plan.retrieval_k,
                query_filter=plan.query_filter,
            )
            docs = retriever.invoke(query)

        if not docs:
            return docs, plan

        # 3. 리랭킹
        docs = self.reranker.rerank(query, docs, top_n=plan.rerank_n)

        # 4. 권위수준 부스트
        if plan.authority_boost:
            docs = apply_authority_boost(docs)

        # 5. 교차참조 확장
        docs = resolve_cross_refs(docs, self.client, max_expansion=10)

        # 6. 용어정의 주입
        docs = inject_term_definitions(docs, self.client, max_definitions=3)

        # 7. 기준서 확장 검색
        if plan.expand_standards:
            docs = expand_referenced_standards(docs, self.client, max_expansion=5)

            std_nums = []
            for s in plan.detected_standards:
                m = re.search(r"(\d{3,4})", s)
                if m:
                    std_nums.append(m.group(1))
            if std_nums:
                q_vec = self.embeddings.embed_query(query)
                rev_docs = reverse_lookup_chunks(
                    std_nums, self.client, query_vector=q_vec, max_results=5
                )
                existing = {d.metadata.get("chunk_id") for d in docs}
                docs += [
                    d
                    for d in rev_docs
                    if d.metadata.get("chunk_id") not in existing
                ]

            docs = graph_expand(docs, self.client, hops=1, max_expansion=3)

        return docs, plan


def _format_results(query: str, docs: list, plan) -> str:
    """검색 결과를 LLM이 소비할 수 있는 마크다운 문자열로 포맷한다."""
    if not docs:
        return f"K-IFRS 검색 결과 없음: '{query}'"

    parts = [
        f"## K-IFRS 검색 결과 ({len(docs)}건)",
        f"**쿼리**: {query}",
        f"**분류**: {plan.query_type.value}",
        "",
    ]

    for i, doc in enumerate(docs, 1):
        m = doc.metadata
        section_label = _SECTION_LABELS.get(
            m.get("section_type", ""), m.get("section_type", "")
        )
        score = m.get("rerank_score")

        # 태그
        tags = []
        if m.get("is_glossary"):
            tags.append("[용어정의]")
        if m.get("fetched_by_xref"):
            tags.append(f"[교차참조: {m.get('xref_source', '')}]")
        if m.get("fetched_by_std_ref"):
            tags.append("[참조기준서]")
        if m.get("fetched_by_graph"):
            tags.append(f"[그래프확장 hop={m.get('graph_hop', 1)}]")
        if m.get("fetched_by_reverse_lookup"):
            tags.append("[역방향참조]")

        tag_str = " ".join(tags)
        score_str = f" (관련도: {score:.3f})" if score is not None else ""

        parts.append(
            f"### [{i}] {m.get('standard_id', '?')} — "
            f"{section_label} 문단 {m.get('para_number', '?')}{score_str}"
        )
        if tag_str:
            parts.append(f"*{tag_str}*")
        parts.append("")
        parts.append(doc.page_content)
        parts.append("")
        parts.append("---")
        parts.append("")

    return "\n".join(parts)


# ── Tool 정의 ──────────────────────────────────────────
@tool(parse_docstring=True)
def kifrs_search(query: str) -> str:
    """Search the K-IFRS (Korean International Financial Reporting Standards) vector database.

    Use this tool to find specific accounting standards, regulations, definitions,
    examples, and interpretive guidance from K-IFRS. The tool automatically classifies
    the query type, retrieves relevant paragraphs, reranks by relevance, and expands
    cross-references and term definitions.

    Best for queries about:
    - Specific accounting treatment requirements (e.g., "유형자산 감가상각 방법")
    - Standard definitions and scope (e.g., "리스의 정의")
    - Comparisons between standards (e.g., "충당부채와 우발부채의 차이")
    - Specific paragraph lookups (e.g., "제1016호 문단 62")
    - Interpretive guidance and basis for conclusions

    Args:
        query: Search query in Korean or English about K-IFRS standards

    Returns:
        Formatted search results with standard paragraphs, metadata, and relevance scores
    """
    try:
        pipeline = _KIFRSPipeline.get()
        docs, plan = pipeline.run(query)
        return _format_results(query, docs, plan)
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        return f"K-IFRS 검색 오류: {e}\n\nTraceback:\n{tb}"
