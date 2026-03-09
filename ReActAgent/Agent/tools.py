import atexit
import logging
import os
import sys
from typing import Literal
from langchain_core.tools import tool
from tavily import TavilyClient

logger = logging.getLogger(__name__)


tavily_client = TavilyClient()

# _database/search 모듈 임포트를 위한 경로 추가
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_database")
sys.path.insert(0, os.path.abspath(DATABASE_DIR))


@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """인터넷에서 최신 정보를 검색합니다. 날씨, 뉴스, 실시간 정보 등을 찾을 때 사용하세요."""
    results = tavily_client.search(
        query, max_results=max_results, topic=topic
    )
    # 검색 결과를 읽기 좋게 포맷팅
    output = []
    for r in results.get("results", []):
        output.append(f"**{r['title']}**\n{r['content']}\n출처: {r['url']}\n")
    return "\n---\n".join(output) if output else "검색 결과가 없습니다."


@tool
def calculator(expression: str) -> str:
    """수학 계산을 수행합니다. 사칙연산, 거듭제곱(**), 나머지(%) 등을 지원합니다.
    예: '123 * 456 + 789', '2 ** 10', '100 / 3'"""
    # 안전한 문자만 허용
    allowed = set("0123456789+-*/.() %")
    if not all(c in allowed for c in expression.replace(" ", "")):
        return "오류: 허용되지 않는 문자가 포함되어 있습니다. 숫자와 연산자만 사용하세요."
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"계산 오류: {e}"


# ── K-IFRS Qdrant 검색 도구 ──

from qdrant_client import QdrantClient
from langchain_upstage import UpstageEmbeddings
from search.config import MODEL_NAME

_qdrant_path = os.path.join(os.path.abspath(DATABASE_DIR), "qdrant_storage")
qdrant_client_shared = QdrantClient(path=_qdrant_path)
qdrant_embeddings_shared = UpstageEmbeddings(
    model=MODEL_NAME,
    upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
)
atexit.register(lambda: qdrant_client_shared.close())

_reranker = None
_reranker_initialized = False

RERANK_THRESHOLD = float(os.getenv("RERANK_THRESHOLD", "0.3"))


def _get_reranker():
    """Reranker를 lazy 초기화합니다. 로딩 실패 시 None을 반환합니다."""
    global _reranker, _reranker_initialized
    if not _reranker_initialized:
        _reranker_initialized = True
        try:
            from search.reranker import get_reranker
            _reranker = get_reranker()
            logger.info("Reranker 로딩 완료: %s", type(_reranker).__name__)
        except Exception as e:
            logger.warning("Reranker 로딩 실패, dense 검색으로 fallback: %s", e)
            _reranker = None
    return _reranker


def _rerank_groups(query: str, groups: list[dict], top_k: int) -> list[dict]:
    """search_with_parent 결과를 reranker로 재정렬합니다."""
    from langchain_core.documents import Document

    reranker = _get_reranker()
    if reranker is None:
        return groups

    # 모든 matched_children을 flat 리스트로 추출
    all_children = []
    for g in groups:
        for mc in g["matched_children"]:
            all_children.append({
                "parent_id": g["parent_id"],
                "heading": g["heading"],
                "siblings": g["siblings"],
                **mc,
            })

    if not all_children:
        return groups

    # rerank
    docs = [Document(page_content=c["content"]) for c in all_children]
    reranked_docs = reranker.rerank(query, docs, top_n=len(docs))

    # threshold 필터링 및 parent 그룹 재구성
    reranked_groups: dict[str, dict] = {}
    for doc in reranked_docs:
        rerank_score = doc.metadata.get("rerank_score", 0)
        if rerank_score < RERANK_THRESHOLD:
            continue

        # 원본 child 찾기 (content 매칭)
        matched = None
        for c in all_children:
            if c["content"] == doc.page_content:
                matched = c
                break
        if matched is None:
            continue

        parent_id = matched["parent_id"]
        child_entry = {
            "chunk_id": matched["chunk_id"],
            "para_number": matched["para_number"],
            "content": matched["content"],
            "rerank_score": rerank_score,
        }

        if parent_id in reranked_groups:
            reranked_groups[parent_id]["matched_children"].append(child_entry)
        else:
            reranked_groups[parent_id] = {
                "parent_id": parent_id,
                "heading": matched["heading"],
                "matched_children": [child_entry],
                "siblings": matched["siblings"],
            }

    # 그룹 내 child 최고 rerank_score 기준 내림차순 정렬
    result = list(reranked_groups.values())
    result.sort(
        key=lambda g: max(c["rerank_score"] for c in g["matched_children"]),
        reverse=True,
    )
    return result[:top_k]


@tool
def kifrs_search(query: str, top_k: int = 5, standard_id: str | None = None) -> str:
    """K-IFRS(한국채택국제회계기준) 기준서를 검색합니다.
    회계 기준, 재무제표, 자산/부채/수익/비용 관련 질문에 사용하세요.
    Parent-Child 계층 검색으로 관련 문단과 형제 문단을 함께 반환합니다.
    standard_id를 지정하면 특정 기준서만 검색합니다 (예: '1115', '1037')."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from search.retriever import search_with_parent

    query_filter = None
    if standard_id:
        query_filter = Filter(must=[
            FieldCondition(key="standard_id", match=MatchValue(value=standard_id))
        ])

    # reranker에 충분한 후보를 확보하기 위해 top_k * 3으로 검색
    fetch_k = top_k * 3 if _get_reranker() is not None else top_k
    groups = search_with_parent(
        qdrant_client_shared, qdrant_embeddings_shared, query,
        top_k=fetch_k, query_filter=query_filter,
    )

    if not groups:
        return "K-IFRS 기준서에서 관련 내용을 찾지 못했습니다."

    # reranker 적용 (실패 시 dense 결과로 fallback)
    use_rerank = _get_reranker() is not None
    if use_rerank:
        try:
            groups = _rerank_groups(query, groups, top_k)
        except Exception as e:
            logger.warning("Rerank 실패, dense 결과로 fallback: %s", e)
            use_rerank = False

    output = []
    for g_idx, g in enumerate(groups, 1):
        section = f"[{g_idx}] {g['heading']}"
        output.append(section)

        # 매칭된 Child 문단
        for mc in g["matched_children"]:
            para = mc.get("para_number", "?")
            if use_rerank:
                score = mc.get("rerank_score", 0)
                output.append(f"  (문단 {para}, rerank={score:.4f})")
            else:
                score = mc.get("score", 0)
                output.append(f"  (문단 {para}, score={score:.4f})")
            output.append(f"  {mc['content']}\n")

        # 형제 문단 (매칭된 것 제외, 맥락 제공)
        matched_ids = {mc["chunk_id"] for mc in g["matched_children"]}
        siblings = [s for s in g["siblings"] if s["chunk_id"] not in matched_ids]
        if siblings:
            output.append(f"  [형제 문단 {len(siblings)}건]")
            for s in siblings[:3]:  # 최대 3개만
                preview = s["content"][:200].replace("\n", " ")
                output.append(f"  - 문단 {s.get('para_number', '?')}: {preview}...")

        output.append("---")

    return "\n".join(output)


ALL_TOOLS = [web_search, calculator, kifrs_search]
