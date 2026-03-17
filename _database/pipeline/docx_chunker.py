"""
K-IFRS IR -> Parent-Child JSON 청커

IR 요소 리스트를 직접 소비하여 구조 인식 청킹을 수행한다.
기존 kifrs_chunker.py의 유틸리티 함수를 재사용한다.

Usage:
    from pipeline.docx_chunker import chunk_elements
    output = chunk_elements(elements, meta)
"""

import re
from datetime import datetime, timezone
from typing import Optional

from pipeline.docx_parser import (
    IRElement, MetaInfo, SectionHeader, NumberedParagraph,
    ContinuationText, ContentTable,
)
from pipeline.kifrs_chunker import (
    extract_cross_refs,
    extract_referenced_standards,
    split_large_content,
    slugify,
    detect_has_table,
    detect_has_example,
)

# ---------------------------------------------------------------------------
# 상수 (KURE-v1 역산 기반)
# ---------------------------------------------------------------------------

TARGET_MAX_CHARS = 5000     # 분할 임계값
MERGE_CEILING = 1500        # 작은 청크 병합 상한
MIN_CHUNK_CHARS = 100       # 이 미만은 인접 병합

# ---------------------------------------------------------------------------
# BC 제외 규칙
# ---------------------------------------------------------------------------

_BC_META_DISCLAIMER = [
    "이 결론도출근거는",
    "일부를 구성하는 것은 아니다",
]

_BC_ADMIN_INTRO = "한국회계기준원은 한국채택국제회계기준 제정시"

_BC_EXCLUDE_SLUGS = [
    "제_개정_경과", "제개정_경과", "제개정",
    "소수의견",
    "국제회계기준과의_관계",
]


def _is_bc_excluded_by_content(content: str) -> bool:
    """BC 보일러플레이트 내용 기반 제외."""
    if all(phrase in content for phrase in _BC_META_DISCLAIMER):
        return True
    if _BC_ADMIN_INTRO in content:
        return True
    return False


def _is_bc_excluded_by_slug(slug: str) -> bool:
    """BC 보일러플레이트 parent slug 기반 제외."""
    slug_lower = slug.lower()
    return any(pattern in slug_lower for pattern in _BC_EXCLUDE_SLUGS)


# ---------------------------------------------------------------------------
# 대형 표 분할
# ---------------------------------------------------------------------------


def _split_table_heavy(content: str, max_chars: int) -> list[str]:
    """표 행 기반 분할. 표가 포함된 대형 청크를 행 단위로 나눈다."""
    lines = content.split('\n')
    groups: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current:
            groups.append('\n'.join(current))
            # 표 구분선(|---|) 유지를 위해 새 그룹 시작 시 추가
            if line.startswith('|') and current and current[0].startswith('|'):
                header = current[0]
                sep_line = '| ' + ' | '.join(
                    ['---'] * header.count('|')) + ' |'
                current = [header, sep_line]
                current_len = len(header) + len(sep_line) + 2
            else:
                current = []
                current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        groups.append('\n'.join(current))

    return groups if groups else [content]


# ---------------------------------------------------------------------------
# 청크 텍스트 렌더링
# ---------------------------------------------------------------------------


def _render_numbered_para(np: NumberedParagraph) -> str:
    """NumberedParagraph를 청크 텍스트로 렌더링.

    호/목 마커를 줄 시작에 배치하여 split_large_content의
    SEMANTIC_BREAK_RE와 호환되도록 한다.
    """
    lines = [f"{np.para_number}\t{np.content}"]
    for si in np.sub_items:
        lines.append(f"{si.marker}\t{si.content}")
        for ssi in si.sub_sub_items:
            lines.append(f"  {ssi.marker}\t{ssi.content}")
    return "\n".join(lines)


def _render_table(tbl: ContentTable) -> str:
    """ContentTable을 Markdown 표로 렌더링."""
    if not tbl.headers:
        return ""
    n = len(tbl.headers)
    lines = [
        "| " + " | ".join(tbl.headers) + " |",
        "| " + " | ".join(["---"] * n) + " |",
    ]
    for row in tbl.rows:
        padded = (row + [""] * n)[:n]
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 병합 유틸리티
# ---------------------------------------------------------------------------


def _merge_small_chunks(chunks: list[dict], min_chars: int,
                        ceiling: int) -> list[dict]:
    """parent 그룹 단위로 작은 청크를 인접 청크에 병합.

    1차: backward merge (이전 청크에 병합)
    2차: forward merge (다음 청크에 병합, 그룹 첫 항목용)
    """
    if not chunks:
        return chunks

    # parent_id별 그룹화 (순서 유지)
    groups: list[list[dict]] = []
    current_group: list[dict] = [chunks[0]]
    for c in chunks[1:]:
        if c["parent_id"] == current_group[0]["parent_id"]:
            current_group.append(c)
        else:
            groups.append(current_group)
            current_group = [c]
    groups.append(current_group)

    result: list[dict] = []
    for group in groups:
        # Backward merge
        merged_group: list[dict] = []
        for chunk in group:
            content_len = len(chunk["content"])
            if (content_len < min_chars
                    and merged_group
                    and len(merged_group[-1]["content"]) + content_len + 2
                    <= ceiling):
                merged_group[-1]["content"] += "\n\n" + chunk["content"]
                if chunk["has_table"]:
                    merged_group[-1]["has_table"] = True
            else:
                merged_group.append(chunk)

        # Forward merge: 첫 항목이 작으면 다음에 병합
        if (len(merged_group) > 1
                and len(merged_group[0]["content"]) < min_chars
                and len(merged_group[0]["content"])
                + len(merged_group[1]["content"]) + 2 <= ceiling):
            merged_group[1]["content"] = (
                merged_group[0]["content"] + "\n\n"
                + merged_group[1]["content"])
            if merged_group[0]["has_table"]:
                merged_group[1]["has_table"] = True
            merged_group.pop(0)

        result.extend(merged_group)

    return result


# ---------------------------------------------------------------------------
# 핵심 알고리즘
# ---------------------------------------------------------------------------


def chunk_elements(elements: list[IRElement], meta: MetaInfo) -> dict:
    """IR 요소 리스트를 Parent-Child JSON 구조로 변환.

    4단계 알고리즘:
      Phase 1: 부모 그룹화 (SectionHeader별)
      Phase 2: 원시 청크 생성 + BC 제외
      Phase 3: 병합/분할
      Phase 4: ID 생성 + 메타데이터
    """
    normalized_id = meta.normalized_id
    display_id = meta.display_id
    standard_num = meta.standard_number

    # ---------------------------------------------------------------
    # Phase 1: 부모 그룹화
    # ---------------------------------------------------------------
    groups: list[tuple[Optional[SectionHeader], list[IRElement]]] = []
    current_header: Optional[SectionHeader] = None
    current_elements: list[IRElement] = []

    for el in elements:
        if isinstance(el, MetaInfo):
            continue
        if isinstance(el, SectionHeader):
            if current_elements or current_header is not None:
                groups.append((current_header, current_elements))
                current_elements = []
            current_header = el
        else:
            current_elements.append(el)

    if current_elements or current_header is not None:
        groups.append((current_header, current_elements))

    # ---------------------------------------------------------------
    # Phase 2: 원시 청크 생성
    # ---------------------------------------------------------------
    parents: list[dict] = []
    raw_chunks: list[dict] = []
    slug_counts: dict = {}

    for header, elems in groups:
        # Parent 생성
        if header is None:
            section_type = "main"
            parent_id = f"{normalized_id}_main_h_root"
            heading_text = "root"
        else:
            section_type = header.section_type
            slug = slugify(header.text)
            count = slug_counts.get(slug, 0)
            slug_counts[slug] = count + 1
            if count == 0:
                parent_id = f"{normalized_id}_{section_type}_h_{slug}"
            else:
                parent_id = f"{normalized_id}_{section_type}_h_{slug}_{count + 1}"
            heading_text = header.text

        parents.append({
            "chunk_id": parent_id,
            "heading_text": heading_text,
            "section_type": section_type,
            "metadata": {"standard_id": display_id, "section_type": section_type},
        })

        # BC 그룹 레벨 제외 (parent slug 기반)
        parent_slug = slug_counts and slugify(heading_text) or "root"
        if section_type == "bc" and _is_bc_excluded_by_slug(parent_slug):
            continue

        # 요소 -> 원시 청크
        for el in elems:
            if isinstance(el, NumberedParagraph):
                text = _render_numbered_para(el)
                raw_chunks.append({
                    "content": text,
                    "para_number": el.para_number,
                    "parent_id": parent_id,
                    "section_type": section_type,
                    "has_table": False,
                })

            elif isinstance(el, ContinuationText):
                if raw_chunks and raw_chunks[-1]["parent_id"] == parent_id:
                    raw_chunks[-1]["content"] += "\n\n" + el.content
                else:
                    raw_chunks.append({
                        "content": el.content,
                        "para_number": None,
                        "parent_id": parent_id,
                        "section_type": section_type,
                        "has_table": False,
                    })

            elif isinstance(el, ContentTable):
                table_text = _render_table(el)
                if not table_text:
                    continue
                if raw_chunks and raw_chunks[-1]["parent_id"] == parent_id:
                    raw_chunks[-1]["content"] += "\n\n" + table_text
                    raw_chunks[-1]["has_table"] = True
                else:
                    raw_chunks.append({
                        "content": table_text,
                        "para_number": None,
                        "parent_id": parent_id,
                        "section_type": section_type,
                        "has_table": True,
                    })

    # BC 내용 기반 제외
    raw_chunks = [
        c for c in raw_chunks
        if not (c["section_type"] == "bc"
                and _is_bc_excluded_by_content(c["content"]))
    ]

    # ---------------------------------------------------------------
    # Phase 3: 병합/분할
    # ---------------------------------------------------------------

    # 3a: 작은 청크 병합 (parent 그룹 단위, backward + forward)
    merged = _merge_small_chunks(raw_chunks, MIN_CHUNK_CHARS, MERGE_CEILING)

    # 3b: 큰 청크 분할 (> TARGET_MAX_CHARS)
    final_chunks: list[dict] = []
    for chunk in merged:
        if len(chunk["content"]) <= TARGET_MAX_CHARS:
            final_chunks.append(chunk)
        else:
            # 표 비중이 높으면 행 기반 분할 우선
            if chunk.get("has_table") and detect_has_table(chunk["content"]):
                parts = _split_table_heavy(chunk["content"], TARGET_MAX_CHARS)
            else:
                parts = split_large_content(chunk["content"],
                                            max_chars=TARGET_MAX_CHARS)
            # 2차 분할: 여전히 큰 파트는 split_large_content로 재분할
            final_parts: list[str] = []
            for part in parts:
                if len(part) > TARGET_MAX_CHARS:
                    final_parts.extend(
                        split_large_content(part, max_chars=TARGET_MAX_CHARS))
                else:
                    final_parts.append(part)

            for i, part in enumerate(final_parts):
                final_chunks.append({
                    **chunk,
                    "content": part,
                    "_split_idx": i + 1 if len(final_parts) > 1 else 0,
                })

    # ---------------------------------------------------------------
    # Phase 4: ID 생성 + 메타데이터
    # ---------------------------------------------------------------
    children: list[dict] = []
    unk_counter = 0

    for chunk in final_chunks:
        content = chunk["content"].strip()
        if not content or len(content) < 10:
            continue

        para_num = chunk.get("para_number")
        section_type = chunk["section_type"]
        split_idx = chunk.get("_split_idx", 0)

        # chunk_id 생성
        if para_num:
            base_id = f"{normalized_id}_{section_type}_{para_num}"
        else:
            unk_counter += 1
            base_id = f"{normalized_id}_{section_type}_unk_{unk_counter}"

        chunk_id = base_id + (f"_s{split_idx}" if split_idx else "")

        # 메타데이터
        cross_refs = extract_cross_refs(content, own_standard_num=standard_num)
        ref_stds = extract_referenced_standards(content,
                                                own_standard_num=standard_num)

        if para_num and para_num in cross_refs:
            cross_refs = [r for r in cross_refs if r != para_num]

        child_meta = {
            "standard_id": display_id,
            "section_type": section_type,
            "para_number": para_num,
            "cross_refs": cross_refs,
            "referenced_standards": ref_stds,
            "has_table": chunk.get("has_table", False) or detect_has_table(content),
            "has_example": detect_has_example(content),
        }

        children.append({
            "chunk_id": chunk_id,
            "parent_id": chunk["parent_id"],
            "content": content,
            "metadata": child_meta,
        })

    # 고아 parent 정리
    active_parent_ids = {c["parent_id"] for c in children}
    kept_parents = [
        p for p in parents
        if p["chunk_id"] in active_parent_ids
        or p["chunk_id"].endswith("_h_root")
    ]

    return {
        "standard_id": display_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "source": "docx",
        "parents": kept_parents,
        "children": children,
    }
