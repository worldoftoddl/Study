"""[DEPRECATED] K-IFRS 교차참조 자동 확장 모듈.

이 모듈은 더 이상 파이프라인에서 사용되지 않습니다.
교차참조 해소는 LLM이 fetch_paragraphs tool을 통해 선택적으로 수행합니다.
파싱 로직은 향후 참조용으로 보존합니다.
"""

import re
from langchain_core.documents import Document

from search.config import CHILDREN_TABLE
from search.db import get_connection

# ── 교차참조 파싱 패턴 ───────────────────────────────
# 범위 구분자: ~ (U+007E), ∼ (U+223C), - (하이픈)
_RANGE_SEP = r"[~∼\-]"

# "AG12~AG15", "AG12~15" (축약형), "BC28∼BC31" → range
_RANGE_RE = re.compile(
    rf"^(AG|BC|IE)(\d+)[A-Z]?\s*{_RANGE_SEP}\s*(?:\1)?(\d+)[A-Z]?$"
)

# "제1109호" → standard number (정규화된 형태, 공백 제거 후)
_STD_REF_RE = re.compile(r"제(\d{3,4})호")

# "제1109호문단4.1.2" → standard + paragraph (정규화된 형태)
_STD_PARA_RE = re.compile(r"제(\d{3,4})호.*?문단([\d.]+[A-Z]?)")

# "문단35", "문단4.1.2" → bare paragraph ref (intra-standard)
_BARE_PARA_RE = re.compile(r"^문단([\d.]+[A-Z]?)$")

# section_type 추론: 접두사 기반
_SECTION_PREFIX_MAP = {
    "AG": "ag",
    "B": "ag",  # IFRS 9 스타일 (B4.1.7)
    "BC": "bc",
    "IE": "ie",
}


def _infer_section_type(ref: str) -> str:
    """참조 문자열에서 section_type을 추론한다."""
    ref_upper = ref.upper()
    for prefix, section in _SECTION_PREFIX_MAP.items():
        if ref_upper.startswith(prefix) and not (
            prefix == "B" and ref_upper.startswith("BC")
        ):
            return section
    return "main"


def _normalize_standard_id(standard_id: str) -> str:
    """'K-IFRS 1016' → 'KIFRS1016'."""
    return standard_id.replace("K-IFRS ", "KIFRS").replace(" ", "")


def _expand_range_ref(ref: str) -> list[str]:
    """범위 참조를 개별 참조로 확장한다. 'AG12~AG15' → ['AG12', 'AG13', 'AG14', 'AG15']."""
    m = _RANGE_RE.match(ref)
    if not m:
        return [ref]
    prefix, start, end = m.group(1), int(m.group(2)), int(m.group(3))
    return [f"{prefix}{i}" for i in range(start, end + 1)]


def _build_chunk_ids_from_refs(
    cross_refs: list[str],
    source_standard_id: str,
) -> list[tuple[str, str]]:
    """교차참조 목록에서 (chunk_id, source_info) 쌍을 생성한다.

    Returns:
        list of (chunk_id, description) tuples.
    """
    normalized_std = _normalize_standard_id(source_standard_id)
    results = []

    for ref in cross_refs:
        # "개념체계" — 특정 청크로 해소 불가, skip
        if "개념체계" in ref:
            continue

        # 범위 참조 확장
        expanded = _expand_range_ref(ref)
        for single_ref in expanded:
            # "제1109호문단4.1.2" — 기준서 간 + 문단 정밀 참조
            para_match = _STD_PARA_RE.search(single_ref)
            if para_match:
                target_std = f"KIFRS{para_match.group(1).zfill(4)}"
                para = para_match.group(2)
                section = _infer_section_type(para)
                chunk_id = f"{target_std}_{section}_{para}"
                results.append((chunk_id, f"xref:{single_ref}"))
                continue

            # "제1109호" — 기준서 간 참조 (문단 번호 없으면 skip)
            std_match = _STD_REF_RE.match(single_ref)
            if std_match:
                continue  # 문단 번호 없는 기준서 참조는 범위가 너무 넓음

            # "문단35", "문단4.1.2" — 동일 기준서 내 문단 참조
            bare_match = _BARE_PARA_RE.match(single_ref)
            if bare_match:
                para = bare_match.group(1)
                section = _infer_section_type(para)
                chunk_id = f"{normalized_std}_{section}_{para}"
                results.append((chunk_id, f"xref:{single_ref}"))
                continue

            # AG12, BC3, IE5, B4.1.7 등 — 동일 기준서 내 참조
            section = _infer_section_type(single_ref)
            chunk_id = f"{normalized_std}_{section}_{single_ref}"
            results.append((chunk_id, f"xref:{single_ref}"))

    return results


_CHILD_COLUMNS = [
    "chunk_id", "parent_id", "content", "standard_id", "section_type",
    "para_number", "cross_refs", "referenced_standards", "has_table", "has_example",
]
_CHILD_SELECT = ", ".join(_CHILD_COLUMNS)


def resolve_cross_refs(
    docs: list[Document],
    max_expansion: int = 10,
    authority_filter: list[str] | None = None,
) -> list[Document]:
    """검색 결과의 교차참조를 자동으로 해결하여 추가 문서를 반환한다.

    Args:
        docs: rerank된 검색 결과 Document 리스트.
        max_expansion: 최대 추가 문서 수.
        authority_filter: 허용할 section_type 목록 (예: ["main", "ag"]).
            None이면 모든 section_type 허용.

    Returns:
        원본 docs + 교차참조로 확장된 Document 리스트.
        확장 문서에는 metadata["fetched_by_xref"] = True가 설정된다.
    """
    if not docs:
        return docs

    # 이미 있는 chunk_id 수집 (중복 방지)
    existing_ids = {doc.metadata.get("chunk_id", "") for doc in docs}

    # 모든 문서의 cross_refs에서 chunk_id 후보 생성
    candidates: list[tuple[str, str]] = []
    for doc in docs:
        cross_refs = doc.metadata.get("cross_refs", [])
        source_std = doc.metadata.get("standard_id", "")
        if not cross_refs or not source_std:
            continue

        pairs = _build_chunk_ids_from_refs(cross_refs, source_std)
        for chunk_id, info in pairs:
            if chunk_id not in existing_ids:
                candidates.append((chunk_id, info))
                existing_ids.add(chunk_id)  # 중복 방지

    if not candidates:
        return docs

    # max_expansion으로 제한
    candidates = candidates[:max_expansion]

    # PostgreSQL에서 batch fetch
    expanded_docs = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for chunk_id, xref_info in candidates:
                try:
                    cur.execute(
                        f"SELECT {_CHILD_SELECT} FROM {CHILDREN_TABLE} WHERE chunk_id = %s",
                        (chunk_id,),
                    )
                    row = cur.fetchone()
                except Exception:
                    continue

                if not row:
                    continue

                r = dict(zip(_CHILD_COLUMNS, row))
                section_type = r.get("section_type", "")

                # authority_filter 적용
                if authority_filter and section_type not in authority_filter:
                    continue

                expanded_docs.append(Document(
                    page_content=r.get("content", ""),
                    metadata={
                        "chunk_id": r.get("chunk_id", chunk_id),
                        "parent_id": r.get("parent_id", ""),
                        "standard_id": r.get("standard_id", ""),
                        "section_type": section_type,
                        "para_number": r.get("para_number"),
                        "cross_refs": r.get("cross_refs", []),
                        "has_table": r.get("has_table", False),
                        "has_example": r.get("has_example", False),
                        "fetched_by_xref": True,
                        "xref_source": xref_info,
                    },
                ))

    return docs + expanded_docs
