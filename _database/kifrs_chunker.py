"""
K-IFRS 청킹 모듈

문단 리스트를 Parent-Child 청크 구조로 구성하고,
긴 문단에 대해 kiwipiepy 문장 분리를 적용한다.
"""

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

SENTENCE_SPLIT_THRESHOLD = 500  # 문자 수
SHORT_SENTENCE_MERGE_THRESHOLD = 50  # 이 미만은 이전 문장에 병합

# Kiwi lazy 초기화
_kiwi = None


def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


# ============================================================
# 데이터 모델
# ============================================================

@dataclass
class ParentChunk:
    parent_id: str
    standard_id: str
    section_type: str
    section_heading: str
    children: list[str] = field(default_factory=list)


@dataclass
class ChildChunk:
    chunk_id: str
    parent_id: str
    content: str
    metadata: dict = field(default_factory=dict)


# ============================================================
# 유틸리티
# ============================================================

def _make_heading_slug(heading: str) -> str:
    """헤딩을 slug 형태로 변환 (예: '4.1 금융자산의 분류' → '4.1_금융자산의_분류')."""
    slug = re.sub(r'\s+', '_', heading.strip())
    return slug[:60]


def _build_child_metadata(
    para: dict,
    is_split: bool = False,
    split_index: int = 0,
    total_splits: int = 0,
) -> dict:
    """Child 청크용 메타데이터 dict를 구성한다."""
    meta = {
        "standard_id": para["standard_id"],
        "standard_name": para["standard_name"],
        "section_type": para["section_type"],
        "para_number": para["para_number"],
        "heading_context": para["heading_context"],
        "cross_refs": para["cross_refs"],
        "has_table": para["has_table"],
        "has_example": para["has_example"],
    }
    if is_split:
        meta["is_sentence_split"] = True
        meta["split_index"] = split_index
        meta["total_splits"] = total_splits
    return meta


# ============================================================
# 문장 분리
# ============================================================

def split_into_sentences(text: str) -> list[str]:
    """
    kiwipiepy로 한국어 문장 분리.
    500자 이하 텍스트는 분리하지 않고 그대로 반환.
    50자 미만 단편은 이전 문장에 병합.
    """
    if len(text) <= SENTENCE_SPLIT_THRESHOLD:
        return [text]

    kiwi = _get_kiwi()
    result = kiwi.split_into_sents(text)
    sentences = [sent.text.strip() for sent in result if sent.text.strip()]

    if len(sentences) <= 1:
        return [text]

    # 짧은 단편 병합
    merged = [sentences[0]]
    for sent in sentences[1:]:
        if len(sent) < SHORT_SENTENCE_MERGE_THRESHOLD and merged:
            merged[-1] = merged[-1] + ' ' + sent
        else:
            merged.append(sent)

    return merged


# ============================================================
# Parent-Child 청크 구성 (핵심 로직)
# ============================================================

def build_parent_child_chunks(
    paragraphs: list[dict],
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    """
    문단 리스트를 받아 Parent-Child 청크 구조를 생성한다.

    Parent 경계 판단 기준:
    - heading_context 변경 시 → 새 Parent 시작
    - section_type 변경 시 → 새 Parent 시작

    긴 Child 청크(>500자)는 kiwipiepy로 문장 분리.

    Returns:
        (parent_chunks, child_chunks) 튜플
    """
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []

    current_parent: Optional[ParentChunk] = None
    prev_heading: Optional[str] = None
    prev_section: Optional[str] = None
    existing_parent_ids: set[str] = set()

    for para in paragraphs:
        heading = para["heading_context"]
        section = para["section_type"]
        standard_id = para["standard_id"]

        # Parent 경계 판단
        need_new_parent = (
            current_parent is None
            or heading != prev_heading
            or section != prev_section
        )

        if need_new_parent:
            heading_slug = _make_heading_slug(heading) if heading else "untitled"
            parent_id = f"{standard_id}_{section}_{heading_slug}"

            # 중복 parent_id 처리
            if parent_id in existing_parent_ids:
                counter = 2
                while f"{parent_id}_{counter}" in existing_parent_ids:
                    counter += 1
                parent_id = f"{parent_id}_{counter}"

            current_parent = ParentChunk(
                parent_id=parent_id,
                standard_id=standard_id,
                section_type=section,
                section_heading=heading or "(untitled)",
            )
            parents.append(current_parent)
            existing_parent_ids.add(parent_id)
            prev_heading = heading
            prev_section = section

        # Child 청크 생성
        base_chunk_id = f"{standard_id}_{section}_{para['para_number']}"
        content = para["content"]

        if len(content) > SENTENCE_SPLIT_THRESHOLD:
            sentences = split_into_sentences(content)
            if len(sentences) > 1:
                for i, sent in enumerate(sentences, 1):
                    child_id = f"{base_chunk_id}_s{i}"
                    child = ChildChunk(
                        chunk_id=child_id,
                        parent_id=current_parent.parent_id,
                        content=sent,
                        metadata=_build_child_metadata(
                            para,
                            is_split=True,
                            split_index=i,
                            total_splits=len(sentences),
                        ),
                    )
                    children.append(child)
                    current_parent.children.append(child_id)
                continue

        # 분리 불필요 또는 분리 결과 1개
        child = ChildChunk(
            chunk_id=base_chunk_id,
            parent_id=current_parent.parent_id,
            content=content,
            metadata=_build_child_metadata(para),
        )
        children.append(child)
        current_parent.children.append(base_chunk_id)

    logger.info(f"  {len(parents)}개 Parent, {len(children)}개 Child 청크 생성")
    return parents, children
