"""
K-IFRS PDF 파싱 모듈

PDF → Markdown 변환, 섹션 감지, 문단 추출을 담당한다.
"""

import re
import logging
from pathlib import Path
from enum import Enum
from typing import Optional

import pymupdf4llm

logger = logging.getLogger(__name__)


# ============================================================
# Enums & Constants
# ============================================================

class SectionType(Enum):
    MAIN = "main"           # 기준서 본문
    APP_GUIDANCE = "ag"     # 적용지침
    BASIS = "bc"            # 결론도출근거
    ILLUSTRATIVE = "ie"     # 사례


# 3개 특수 파일 매핑 (제XXXX호 패턴이 없는 파일)
SPECIAL_FILE_MAP = {
    "개념체계": {"standard_id": "KIFRS_CF", "standard_name": "재무보고를 위한 개념체계"},
    "실무서":   {"standard_id": "KIFRS_PS2", "standard_name": "중요성에 대한 판단"},
    "경영진설명서": {"standard_id": "KIFRS_MC", "standard_name": "경영진설명서 작성을 위한 개념체계"},
}


# ============================================================
# 정규식 패턴
# ============================================================

# --- 파일명 메타데이터 추출 ---
STANDARD_ID_PATTERN = re.compile(r'제(\d{4})호')
STANDARD_NAME_PATTERN = re.compile(r'제\d{4}호_(.+?)(?:\(|$)')

# --- 문단 번호 패턴 ---
# MAIN: "1", "4.1.2", "한2.1", "한40.1"
MAIN_PARA_PATTERN = re.compile(r'^((?:한)?\d+(?:\.\d+)*)\s+')

# AG: "AG72", "AG4B"
AG_PARA_PATTERN = re.compile(r'^(AG\d+(?:[A-Z])?)\s+')

# BC: "BC1", "BC45A"
BC_PARA_PATTERN = re.compile(r'^(BC\d+(?:[A-Z])?)\s+')

# IE: "IE1", "IE12"
IE_PARA_PATTERN = re.compile(r'^(IE\d+(?:[A-Z])?)\s+')

# 하위항목: (1), (2), (가), (나) → 부모 문단에 병합
SUB_ITEM_PATTERN = re.compile(r'^\([0-9가-힣]+\)\s+')

# --- 섹션 경계 감지 ---
SECTION_BOUNDARY_PATTERNS = {
    SectionType.APP_GUIDANCE: re.compile(
        r'^#+\s*(?:부록\s*[A-Z]?\s*)?적용지침|^적용지침', re.MULTILINE
    ),
    SectionType.BASIS: re.compile(
        r'^#+\s*(?:부록\s*[A-Z]?\s*)?결론도출근거|^결론도출근거', re.MULTILINE
    ),
    SectionType.ILLUSTRATIVE: re.compile(
        r'^#+\s*(?:부록\s*[A-Z]?\s*)?(?:사례|예시)', re.MULTILINE
    ),
}

# Front matter 끝 감지 (본문 시작점)
FRONT_MATTER_END_PATTERN = re.compile(
    r'^(?:#+\s*목적|^1\s+)', re.MULTILINE
)

# Trailing 비규범 섹션 감지
TRAILING_SECTION_PATTERN = re.compile(
    r'^#+\s*기타\s*참고사항', re.MULTILINE
)

# 상호참조 패턴
CROSS_REF_PATTERN = re.compile(
    r'(?:문단\s*(?:한)?[\d]+(?:\.[\d]+)*'
    r'|AG\d+[A-Z]?'
    r'|BC\d+[A-Z]?'
    r'|IE\d+[A-Z]?'
    r'|기준서\s*(?:제)?\s*\d{4}\s*호?)'
)

# 표 감지 (마크다운 테이블)
TABLE_PATTERN = re.compile(r'\|.*\|.*\|')

# 마크다운 헤딩 패턴 (h1~h6)
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


# ============================================================
# 파일명 메타데이터 추출
# ============================================================

def extract_metadata_from_filename(pdf_path: Path) -> dict:
    """
    PDF 파일명에서 standard_id와 standard_name을 추출한다.

    Returns:
        {
            "standard_id": "KIFRS1002",
            "standard_name": "재고자산",
            "source_file": "시행중_K-IFRS_제1002호_..."
        }
    """
    filename = pdf_path.stem

    # 다운로드 중복 접미사 제거: 파일명(1).pdf → 파일명
    filename_clean = re.sub(r'\(\d+\)$', '', filename).strip()

    # 표준 파일 패턴 매치
    id_match = STANDARD_ID_PATTERN.search(filename_clean)
    if id_match:
        standard_id = f"KIFRS{id_match.group(1)}"
        name_match = STANDARD_NAME_PATTERN.search(filename_clean)
        if name_match:
            standard_name = name_match.group(1).replace('_', ' ').strip()
        else:
            standard_name = standard_id
            logger.warning(f"기준서명 추출 실패: {filename}")

        return {
            "standard_id": standard_id,
            "standard_name": standard_name,
            "source_file": pdf_path.name,
        }

    # 특수 파일 매핑
    for key, mapping in SPECIAL_FILE_MAP.items():
        if key in filename_clean:
            return {
                "standard_id": mapping["standard_id"],
                "standard_name": mapping["standard_name"],
                "source_file": pdf_path.name,
            }

    # 매칭 실패 → 파일명 자체를 ID로 사용
    logger.warning(f"메타데이터 추출 실패, 파일명 사용: {filename}")
    return {
        "standard_id": filename_clean[:30],
        "standard_name": filename_clean[:30],
        "source_file": pdf_path.name,
    }


# ============================================================
# PDF → Markdown 변환
# ============================================================

def pdf_to_markdown(pdf_path: str) -> str:
    """
    PDF 파일을 Markdown 텍스트로 변환한다.

    Returns:
        str: 마크다운 형식의 전체 텍스트
    """
    result = pymupdf4llm.to_markdown(
        doc=pdf_path,
        page_chunks=False,
        show_progress=False,
    )

    # pymupdf4llm 버그 대응: list 반환 시 join
    if isinstance(result, list):
        return "\n".join(
            chunk["text"] if isinstance(chunk, dict) else str(chunk)
            for chunk in result
        )

    return result


# ============================================================
# Front Matter / Trailing 섹션 처리
# ============================================================

def skip_front_matter(md_text: str) -> str:
    """
    제목·저작권·목차 등 front matter를 건너뛰고 본문 시작점부터 반환한다.
    """
    match = FRONT_MATTER_END_PATTERN.search(md_text)
    if match:
        return md_text[match.start():]

    logger.warning("Front matter 끝을 감지하지 못함 → 전체 텍스트 반환")
    return md_text


def trim_trailing_sections(md_text: str) -> str:
    """
    '기타 참고사항' 등 비규범 trailing 섹션을 제거한다.
    """
    match = TRAILING_SECTION_PATTERN.search(md_text)
    if match:
        return md_text[:match.start()]
    return md_text


# ============================================================
# 섹션 경계 감지
# ============================================================

def detect_section_boundaries(md_text: str) -> list[tuple[int, SectionType]]:
    """
    마크다운 텍스트에서 섹션 타입 변경 지점(문자 오프셋)을 탐지한다.

    Returns:
        정렬된 (char_offset, SectionType) 튜플 리스트.
        첫 번째 경계 이전은 항상 MAIN.
    """
    boundaries: list[tuple[int, SectionType]] = [(0, SectionType.MAIN)]

    # 1. 헤딩 키워드 기반 탐지
    for section_type, pattern in SECTION_BOUNDARY_PATTERNS.items():
        match = pattern.search(md_text)
        if match:
            boundaries.append((match.start(), section_type))

    # 2. 문단 번호 접두사 기반 fallback (AG1, BC1, IE1)
    for prefix, section_type in [
        ('AG', SectionType.APP_GUIDANCE),
        ('BC', SectionType.BASIS),
        ('IE', SectionType.ILLUSTRATIVE),
    ]:
        # 이미 헤딩으로 발견됐으면 skip
        if any(st == section_type for _, st in boundaries):
            continue

        pattern = re.compile(rf'^{prefix}1\s+', re.MULTILINE)
        match = pattern.search(md_text)
        if match:
            boundaries.append((match.start(), section_type))

    boundaries.sort(key=lambda x: x[0])
    return boundaries


def _get_section_at_offset(
    boundaries: list[tuple[int, SectionType]], offset: int
) -> SectionType:
    """주어진 문자 오프셋에서 활성화된 섹션 타입을 반환한다."""
    current = SectionType.MAIN
    for boundary_offset, section_type in boundaries:
        if boundary_offset <= offset:
            current = section_type
        else:
            break
    return current


# ============================================================
# 문단 추출 (핵심 로직)
# ============================================================

def _try_paragraph_match(line: str, section: SectionType) -> Optional[re.Match]:
    """라인 시작의 문단 번호 매치를 시도한다."""
    if section == SectionType.MAIN:
        m = MAIN_PARA_PATTERN.match(line)
        if m:
            # 4자리 이상 정수는 기준서 번호 줄바꿈 잔해 (예: "1109 호를 적용할 때")
            para_num = m.group(1)
            if para_num.isdigit() and int(para_num) >= 1000:
                return None
        return m
    elif section == SectionType.APP_GUIDANCE:
        return AG_PARA_PATTERN.match(line)
    elif section == SectionType.BASIS:
        return BC_PARA_PATTERN.match(line)
    elif section == SectionType.ILLUSTRATIVE:
        return IE_PARA_PATTERN.match(line)
    return None


def _finalize_para(para_acc: dict, metadata: dict) -> dict:
    """축적된 문단 라인을 최종 문단 dict로 변환한다."""
    content = '\n'.join(para_acc["content_lines"]).strip()
    cross_refs = CROSS_REF_PATTERN.findall(content)
    has_table = bool(TABLE_PATTERN.search(content))

    return {
        "para_number": para_acc["para_number"],
        "section_type": para_acc["section_type"],
        "content": content,
        "heading_context": para_acc["heading_context"],
        "cross_refs": list(set(cross_refs)),
        "has_table": has_table,
        "has_example": "예를 들" in content or "【사례" in content,
        "standard_id": metadata["standard_id"],
        "standard_name": metadata["standard_name"],
    }


def extract_paragraphs(md_text: str, metadata: dict) -> list[dict]:
    """
    마크다운 텍스트를 개별 문단으로 분리하고 메타데이터를 추출한다.

    Args:
        md_text: 원본 마크다운 텍스트 (front matter 포함)
        metadata: extract_metadata_from_filename()의 반환값

    Returns:
        문단 dict 리스트. 각 dict는 para_number, section_type, content,
        heading_context, cross_refs, has_table, has_example, standard_id,
        standard_name 필드를 포함한다.
    """
    # Front matter 제거 + trailing 섹션 제거
    body = skip_front_matter(md_text)
    body = trim_trailing_sections(body)

    # 섹션 경계 감지
    boundaries = detect_section_boundaries(body)

    # 라인 단위 순회
    lines = body.split('\n')
    paragraphs: list[dict] = []
    current_heading = ""
    current_para: Optional[dict] = None
    char_offset = 0

    for line in lines:
        line_start_offset = char_offset
        char_offset += len(line) + 1  # +1 for \n

        current_section = _get_section_at_offset(boundaries, line_start_offset)
        stripped = line.strip()

        if not stripped:
            continue

        # 마크다운 헤딩 체크
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            # 현재 문단 flush
            if current_para:
                paragraphs.append(_finalize_para(current_para, metadata))
                current_para = None
            current_heading = heading_match.group(2).strip()
            continue

        # 문단 번호 매치 시도
        para_match = _try_paragraph_match(stripped, current_section)

        if para_match:
            # 새 문단 시작 → 이전 문단 flush
            if current_para:
                paragraphs.append(_finalize_para(current_para, metadata))

            current_para = {
                "para_number": para_match.group(1),
                "section_type": current_section.value,
                "content_lines": [stripped[para_match.end():]],
                "heading_context": current_heading,
            }
        elif SUB_ITEM_PATTERN.match(stripped):
            # 하위항목 (1), (2) → 현재 문단에 병합
            if current_para:
                current_para["content_lines"].append(stripped)
            else:
                logger.debug(f"고아 하위항목: {stripped[:50]}")
        else:
            # 이어지는 라인 → 현재 문단에 추가
            if current_para:
                current_para["content_lines"].append(stripped)

    # 마지막 문단 flush
    if current_para:
        paragraphs.append(_finalize_para(current_para, metadata))

    logger.info(
        f"  [{metadata['standard_id']}] {len(paragraphs)}개 문단 추출 완료 "
        f"(섹션: {', '.join(sorted(set(p['section_type'] for p in paragraphs)))})"
    )
    return paragraphs
