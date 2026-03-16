"""PgVectorRetriever, load_child_documents, kiwi_tokenize.

Hybrid 검색 파이프라인에서 공유하는 retriever/loader/tokenizer 모듈.
"""

import json
import glob
import os
import re

import numpy as np
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever
from langchain_upstage import UpstageEmbeddings

from search.config import CHILDREN_TABLE, PARENTS_TABLE
from search.db import get_connection, build_where_clause

# ── 권위수준 필터 프리셋 ─────────────────────────────
AUTHORITY_FILTERS = {
    "normative": {"section_type__in": ["main", "ag"]},
    "bc_only": {"section_type": "bc"},
    "ie_only": {"section_type": "ie"},
}


def get_authority_filter(mode: str) -> dict | None:
    """권위수준 필터 모드에 따라 필터 dict를 반환한다.

    Args:
        mode: "normative" | "full" | "bc_only" | "ie_only"
    Returns:
        dict 또는 None ("full"인 경우).
    """
    if mode == "full":
        return None
    return AUTHORITY_FILTERS.get(mode)

# ── kiwipiepy 토크나이저 (lazy singleton) ──────────────
_kiwi = None
ALLOWED_TAGS = {"NNG", "NNP", "VV", "VA", "SN"}


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def kiwi_tokenize(text: str) -> list[str]:
    """kiwipiepy로 형태소 분석 후 NNG, NNP, VV, VA, SN 태그만 추출."""
    tokens = _get_kiwi().tokenize(text)
    return [t.form for t in tokens if t.tag in ALLOWED_TAGS]


def _row_to_doc(row: tuple, columns: list[str]) -> Document:
    """DB 행을 LangChain Document로 변환한다."""
    r = dict(zip(columns, row))
    return Document(
        page_content=r.get("content", ""),
        metadata={
            "chunk_id": r.get("chunk_id", ""),
            "parent_id": r.get("parent_id", ""),
            "standard_id": r.get("standard_id", ""),
            "section_type": r.get("section_type", ""),
            "para_number": r.get("para_number"),
            "cross_refs": r.get("cross_refs", []),
            "referenced_standards": r.get("referenced_standards", []),
            "has_table": r.get("has_table", False),
            "has_example": r.get("has_example", False),
        },
    )


_CHILD_COLUMNS = [
    "chunk_id", "parent_id", "content", "standard_id", "section_type",
    "para_number", "cross_refs", "referenced_standards", "has_table", "has_example",
]
_CHILD_SELECT = ", ".join(_CHILD_COLUMNS)


# ── PgVectorRetriever ──────────────────────────────
class PgVectorRetriever(BaseRetriever):
    """PostgreSQL + pgvector 기반 dense retriever.

    query_filter를 설정하면 벡터 검색 시 WHERE 필터가 적용된다.
    get_authority_filter()와 함께 사용하여 권위수준 기반 필터링이 가능하다.
    """

    embeddings: UpstageEmbeddings
    k: int = 5
    query_filter: dict | None = None

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        q_vec = np.array(self.embeddings.embed_query(query), dtype=np.float32)
        where_clause, params = build_where_clause(self.query_filter)

        sql = f"""
            SELECT {_CHILD_SELECT}
            FROM {CHILDREN_TABLE}
            WHERE embedding IS NOT NULL {where_clause}
            ORDER BY embedding <=> %(query_vec)s
            LIMIT %(limit)s
        """
        params["query_vec"] = q_vec
        params["limit"] = self.k

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [_row_to_doc(row, _CHILD_COLUMNS) for row in rows]


# ── Document 로더 ─────────────────────────────────────
def load_child_documents(chunks_dir: str) -> list[Document]:
    """output/chunks/*.json에서 child 청크를 LangChain Document로 변환."""
    docs = []
    for fpath in sorted(glob.glob(os.path.join(chunks_dir, "*.json"))):
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
                    "referenced_standards": meta.get("referenced_standards", []),
                    "has_table": meta.get("has_table", False),
                    "has_example": meta.get("has_example", False),
                },
            ))
    return docs


# ── 자연 정렬 키 ─────────────────────────────────────
def _natsort_key(s: str | None) -> list:
    """'BC16A' → ['', 16, 'A'] 형태로 분리하여 자연 정렬."""
    if not s:
        return []
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]


# ── Parent-Child 통합 검색 ────────────────────────────
def fetch_siblings(parent_id: str) -> list[dict]:
    """parent_id로 같은 Parent 아래 모든 Child를 조회 (para_number 순 정렬)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT chunk_id, para_number, content FROM {CHILDREN_TABLE} WHERE parent_id = %s LIMIT 50",
                (parent_id,),
            )
            rows = cur.fetchall()

    siblings = [
        {"chunk_id": r[0], "para_number": r[1], "content": r[2]}
        for r in rows
    ]
    siblings.sort(key=lambda x: _natsort_key(x["para_number"] or ""))
    return siblings


def _fetch_parent_heading(parent_id: str) -> str:
    """parent_id로 Parent 테이블에서 heading_text 조회."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT heading_text FROM {PARENTS_TABLE} WHERE chunk_id = %s",
                    (parent_id,),
                )
                row = cur.fetchone()
                if row:
                    return row[0] or "(없음)"
    except Exception:
        pass
    return "(조회 실패)"


def search_with_parent(
    embeddings: UpstageEmbeddings,
    query: str,
    top_k: int = 5,
    query_filter: dict | None = None,
) -> list[dict]:
    """Child 검색 → Parent heading 조회 → 형제 Child 묶기.

    Args:
        query_filter: 선택적 필터 dict (get_authority_filter()로 생성).

    Returns:
        list of {
            "parent_id", "heading",
            "matched_children": [ { chunk_id, para_number, content, score } ],
            "siblings": [ { chunk_id, para_number, content }, ... ]
        }
    """
    q_vec = np.array(embeddings.embed_query(query), dtype=np.float32)
    where_clause, params = build_where_clause(query_filter)

    sql = f"""
        SELECT {_CHILD_SELECT}, embedding <=> %(query_vec)s AS distance
        FROM {CHILDREN_TABLE}
        WHERE embedding IS NOT NULL {where_clause}
        ORDER BY embedding <=> %(query_vec)s
        LIMIT %(limit)s
    """
    params["query_vec"] = q_vec
    params["limit"] = top_k

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            results = cur.fetchall()

    seen_parents: dict[str, dict] = {}
    output = []

    for row in results:
        r = dict(zip(_CHILD_COLUMNS + ["distance"], row))
        parent_id = r.get("parent_id", "")
        score = 1.0 - r.get("distance", 1.0)  # cosine distance → similarity
        matched = {
            "chunk_id": r.get("chunk_id", ""),
            "para_number": r.get("para_number"),
            "content": r.get("content", ""),
            "score": score,
        }

        if parent_id in seen_parents:
            seen_parents[parent_id]["matched_children"].append(matched)
            continue

        heading = _fetch_parent_heading(parent_id)
        siblings = fetch_siblings(parent_id)

        entry = {
            "parent_id": parent_id,
            "heading": heading,
            "matched_children": [matched],
            "siblings": siblings,
        }
        seen_parents[parent_id] = entry
        output.append(entry)

    return output


# ── Parent 그룹핑 + Sibling 확장 ─────────────────────
def expand_to_parents(
    reranked_docs: list[Document],
    max_context_chars: int = 12000,
    max_parents: int = 7,
) -> list[dict]:
    """Reranked children을 parent 단위로 묶고 siblings를 확장한다.

    Args:
        reranked_docs: rerank 완료된 Document 리스트 (metadata에 rerank_score 포함).
        max_context_chars: 컨텍스트 총 문자 수 예산.
        max_parents: 최대 parent 그룹 수.

    Returns:
        list of {
            "parent_id", "heading", "standard_id", "section_type",
            "best_score", "children": [
                {"chunk_id", "para_number", "content", "is_matched"}
            ]
        }
    """
    # 1) parent_id별 그룹핑 + best_score 계산
    parent_map: dict[str, dict] = {}
    for doc in reranked_docs:
        m = doc.metadata
        pid = m.get("parent_id", "")
        score = m.get("rerank_score", 0.0)
        cid = m.get("chunk_id", "")

        if pid not in parent_map:
            parent_map[pid] = {
                "parent_id": pid,
                "standard_id": m.get("standard_id", ""),
                "section_type": m.get("section_type", ""),
                "best_score": score,
                "matched_ids": {cid},
            }
        else:
            parent_map[pid]["best_score"] = max(parent_map[pid]["best_score"], score)
            parent_map[pid]["matched_ids"].add(cid)

    # 2) best_score 내림차순 정렬
    sorted_parents = sorted(parent_map.values(), key=lambda p: -p["best_score"])

    # 3) 상위 parent부터 siblings 확장, 예산 내에서
    result = []
    total_chars = 0

    for pinfo in sorted_parents:
        if len(result) >= max_parents:
            break

        pid = pinfo["parent_id"]
        heading = _fetch_parent_heading(pid)
        siblings = fetch_siblings(pid)

        # parent 전체 길이 계산
        parent_len = sum(len(s["content"]) for s in siblings)
        if total_chars + parent_len > max_context_chars and result:
            break  # 첫 parent는 항상 포함

        matched_ids = pinfo["matched_ids"]
        children = [
            {
                "chunk_id": s["chunk_id"],
                "para_number": s["para_number"],
                "content": s["content"],
                "is_matched": s["chunk_id"] in matched_ids,
            }
            for s in siblings
        ]

        result.append({
            "parent_id": pid,
            "heading": heading,
            "standard_id": pinfo["standard_id"],
            "section_type": pinfo["section_type"],
            "best_score": pinfo["best_score"],
            "children": children,
        })
        total_chars += parent_len

    return result


def format_parent_context(parent_groups: list[dict]) -> str:
    """Parent-grouped 검색 결과를 LLM 컨텍스트 문자열로 포맷한다."""
    section_labels = {
        "main": "본문", "ag": "적용지침",
        "bc": "결론도출근거", "ie": "사례",
    }
    parts = []
    for i, pg in enumerate(parent_groups, 1):
        section = section_labels.get(pg["section_type"], pg["section_type"])
        header = f"[{i}] {pg['standard_id']} | {section} | {pg['heading']} (relevance={pg['best_score']:.4f})"

        child_lines = []
        for c in pg["children"]:
            para = c["para_number"] or "?"
            marker = "  ★ " if c["is_matched"] else "  "
            child_lines.append(f"{marker}문단 {para}: {c['content']}")

        parts.append(header + "\n" + "\n".join(child_lines))

    return "\n\n---\n\n".join(parts)
