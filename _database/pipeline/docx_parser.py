"""
K-IFRS DOCX -> IR (Intermediate Representation) 파서

DOCX 원본을 파싱하여 타입이 지정된 IR 요소 리스트를 생성한다.
텍스트 패턴 + 1행1열 표만으로 파싱하며, 스타일 기반 분기는 사용하지 않는다.
스타일 정보는 dry-run 통계 로깅에만 기록한다.

Usage:
    from pipeline.docx_parser import parse_docx, render_markdown
    elements, stats = parse_docx("data/raw/IFRS_docx/...docx")
    md_text = render_markdown(elements)
"""

import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table as DocxTable

# ---------------------------------------------------------------------------
# IR 데이터 클래스
# ---------------------------------------------------------------------------


@dataclass
class MetaInfo:
    """기준서 메타데이터 (파일명 기반 추출)"""
    standard_number: str    # "1016" or ""
    standard_title: str     # "유형자산" or "재무보고 개념체계"
    display_id: str         # "K-IFRS 1016" or "재무보고 개념체계"
    normalized_id: str      # "KIFRS1016" or "KIFRS_CF"


@dataclass
class SectionHeader:
    """섹션 헤더 (1x1 표에서 추출)"""
    text: str
    level: int              # 2 (major section) or 3 (sub-section)
    section_type: str       # "main", "ag", "bc", "ie"


@dataclass
class SubItem:
    """호/목 (⑴⑵⑶, ㈎㈏㈐ 등)"""
    marker: str
    content: str
    sub_sub_items: list = field(default_factory=list)


@dataclass
class NumberedParagraph:
    """번호 있는 문단 (원자 단위)"""
    para_number: str        # "1", "AG5", "BC12A", "한2.1"
    section_type: str
    content: str
    sub_items: list = field(default_factory=list)


@dataclass
class ContinuationText:
    """번호 없는 이어지는 텍스트"""
    content: str
    section_type: str


@dataclass
class ContentTable:
    """내용 표 (다중 열/행)"""
    headers: list
    rows: list
    section_type: str


IRElement = MetaInfo | SectionHeader | NumberedParagraph | ContinuationText | ContentTable

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 섹션 감지 매핑 (우선순위: 구체적 -> 일반적)
_SECTION_TEXT_MAP = [
    ("결론도출근거", "bc"),
    ("적용지침", "ag"),
    ("부록 B", "ag"),
    ("부록 A", "ag"),
    ("사례", "ie"),
    ("본 문", "main"),
    ("경과규정", "main"),
    ("시행일", "main"),
]

# 문단번호 파싱 정규식 (TAB/공백 이전 텍스트에서)
_PARA_NUMBER_RE = re.compile(
    r'^(한\s*\d+(?:\.\d+)*|\d+(?:\.\d+)*[A-Z]?|'
    r'AG\d+[A-Z]?(?:\.\d+)?|BC\d+[A-Z]?(?:\.\d+)?|BCE\.\d+[A-Z]?|'
    r'IE\d+[A-Z]?(?:\.\d+)?|B\d+(?:\.\d+)*[A-Z]?|C\d+[A-Z]?(?:\.\d+)?)$'
)

# 호/목 마커
_HO_MARKERS = set("⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽⑾⑿")
_MOK_MARKERS = set("㈎㈏㈐㈑㈒㈓㈔㈕㈖㈗")
_ALL_SUB_MARKERS = _HO_MARKERS | _MOK_MARKERS

# 저작권/영문 필터링
_COPYRIGHT_KEYWORDS = [
    "IFRS Foundation", "All rights reserved", "Copyright",
    "International Financial Reporting Standards",
    "Westferry Circus", "permitted to reproduce",
    "COPYRIGHT NOTICE",
    "모든 저작권은 보호됩니다",
    "www.ifrs.org",
]

# 비표준 파일 ID 매핑
_ETC_ID_MAP = {
    "경영진설명서_작성을_위한_개념체계_번역서": ("경영진설명서 개념체계", "KIFRS_CF_MgtCommentary"),
    "국제회계기준_실무서_2_중요성에_대한_판단_번역서": ("실무서 2 중요성", "KIFRS_PS2_Materiality"),
    "시행중_K-IFRS_재무보고를_위한_개념체계": ("재무보고 개념체계", "KIFRS_CF"),
}

# ---------------------------------------------------------------------------
# DOCX 파일 열기 (백슬래시 경로 수정)
# ---------------------------------------------------------------------------


# XML 1.0 유효하지 않은 문자 (python-docx/lxml 파싱 오류 방지)
_INVALID_XML_RE = re.compile(
    '[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f'
    '\ud800-\udfff\ufdd0-\ufddf\ufffe\uffff]'
)


def _open_docx(docx_path: str) -> Document:
    """DOCX 파일 열기. 백슬래시 경로 수정 + XML 유효하지 않은 문자 정제."""
    buf = io.BytesIO()
    with zipfile.ZipFile(docx_path, 'r') as zin:
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                fixed_name = item.filename.replace('\\', '/')
                if fixed_name.endswith('.xml') or fixed_name.endswith('.rels'):
                    text = data.decode('utf-8', errors='replace')
                    text = _INVALID_XML_RE.sub('', text)
                    data = text.encode('utf-8')
                item.filename = fixed_name
                zout.writestr(item, data)
    buf.seek(0)
    return Document(buf)

# ---------------------------------------------------------------------------
# XML 유틸리티
# ---------------------------------------------------------------------------


def _xml_para_text(p_elem) -> str:
    """<w:p> 요소에서 전체 텍스트 추출 (탭/줄바꿈 포함)."""
    parts: list[str] = []
    for r_elem in p_elem.findall(qn('w:r')):
        for child in r_elem:
            if child.tag == qn('w:t'):
                parts.append(child.text or '')
            elif child.tag == qn('w:tab'):
                parts.append('\t')
            elif child.tag in (qn('w:br'), qn('w:cr')):
                parts.append('\n')
    return ''.join(parts)


def _xml_para_style(p_elem) -> Optional[str]:
    """<w:p> 요소에서 스타일 ID 추출 (custom0, custom1 등)."""
    pPr = p_elem.find(qn('w:pPr'))
    if pPr is not None:
        pStyle = pPr.find(qn('w:pStyle'))
        if pStyle is not None:
            return pStyle.get(qn('w:val'))
    return None


def _get_unique_cells(row):
    """행에서 중복 셀(병합) 제거."""
    seen = set()
    cells = []
    for cell in row.cells:
        tc_id = id(cell._tc)
        if tc_id not in seen:
            seen.add(tc_id)
            cells.append(cell)
    return cells

# ---------------------------------------------------------------------------
# 메타데이터 유틸리티
# ---------------------------------------------------------------------------


def _extract_title_from_filename(filename: str) -> str:
    """파일명에서 기준서 제목 부분 추출."""
    m = re.search(r'제\d+호[_\s]*([^(]+)', filename)
    if m:
        return m.group(1).strip().rstrip('_')
    return ""


def _make_meta_from_filename(filename: str) -> MetaInfo:
    """파일명에서 MetaInfo 생성."""
    stem = Path(filename).stem

    # 표준 기준서 (제XXXX호)
    m = re.search(r'제(\d+)호', filename)
    if m:
        number = m.group(1)
        title = _extract_title_from_filename(filename)
        return MetaInfo(
            standard_number=number,
            standard_title=title,
            display_id=f"K-IFRS {number}",
            normalized_id=f"KIFRS{number}",
        )

    # 비표준 파일
    for key, (display, normalized) in _ETC_ID_MAP.items():
        if key in stem:
            return MetaInfo(
                standard_number="",
                standard_title=display,
                display_id=display,
                normalized_id=normalized,
            )

    # 폴백
    return MetaInfo(
        standard_number="",
        standard_title=stem[:40],
        display_id=stem[:40],
        normalized_id=re.sub(r'[^\w]', '_', stem[:40]),
    )

# ---------------------------------------------------------------------------
# 분류 로직
# ---------------------------------------------------------------------------


def _detect_section_from_text(text: str) -> Optional[str]:
    """1x1 표 텍스트에서 섹션 타입 감지."""
    text_clean = text.strip()
    for keyword, section_type in _SECTION_TEXT_MAP:
        if keyword in text_clean:
            return section_type
    if "부록" in text_clean:
        return "ag"
    return None


def _is_copyright(text: str) -> bool:
    return any(kw in text for kw in _COPYRIGHT_KEYWORDS)


def _is_revision_table(all_text: str, n_rows: int) -> bool:
    """개정이력 표 감지."""
    revision_kw = ["수정목록", "개정 및 수정", "제⋅개정", "제·개정", "제/개정"]
    if any(kw in all_text for kw in revision_kw):
        return True
    hit = sum(1 for kw in ["개정", "제정", "공표", "시행일"] if kw in all_text)
    return hit >= 2 and n_rows >= 3


def _is_meta_or_toc_table(all_text: str, seen_section: bool) -> bool:
    """메타/표지/목차 표 감지. seen_section=True이면 건너뜀."""
    if seen_section:
        return False
    if "목차" in all_text or "목 차" in all_text:
        return True
    meta_kw = ["기업회계기준서", "한국채택국제회계기준", "기업회계기준해석서"]
    hit = sum(1 for kw in meta_kw if kw in all_text)
    return hit >= 1 and len(all_text) < 500


def _classify_paragraph(raw_text: str, current_section_type: str):
    """문단 텍스트를 IR 요소로 분류.

    Returns: NumberedParagraph | SubItem | ContinuationText | None
    """
    if not raw_text or not raw_text.strip():
        return None

    if _is_copyright(raw_text):
        return None

    stripped = raw_text.strip()

    # --- Tab 기반 분류 ---
    if '\t' in raw_text:
        first_tab = raw_text.index('\t')
        before_tab = raw_text[:first_tab].strip()
        after_tab = raw_text[first_tab + 1:]

        if before_tab:
            # 번호 + TAB + 내용: "1\t이 기준서의..."
            if _PARA_NUMBER_RE.match(before_tab):
                return NumberedParagraph(
                    para_number=before_tab.replace(' ', ''),
                    section_type=current_section_type,
                    content=after_tab.strip(),
                )
            # 마커 + TAB + 내용: "⑴\t조건1"
            if len(before_tab) == 1 and before_tab in _ALL_SUB_MARKERS:
                return SubItem(marker=before_tab, content=after_tab.strip())
        else:
            # 선행 TAB → 호/목 후보
            inner = after_tab.lstrip('\t ')
            if inner and inner[0] in _ALL_SUB_MARKERS:
                marker = inner[0]
                rest = inner[1:].lstrip('\t ').strip()
                return SubItem(marker=marker, content=rest)

    # --- Fallback: 공백 기준 문단번호 ---
    parts = stripped.split(None, 1)
    if len(parts) == 2 and _PARA_NUMBER_RE.match(parts[0]):
        return NumberedParagraph(
            para_number=parts[0].replace(' ', ''),
            section_type=current_section_type,
            content=parts[1],
        )

    # --- 마커로 시작 (탭 없는 경우) ---
    if stripped and stripped[0] in _ALL_SUB_MARKERS:
        marker = stripped[0]
        rest = stripped[1:].lstrip('\t ').strip()
        return SubItem(marker=marker, content=rest)

    # --- ContinuationText ---
    return ContinuationText(content=stripped, section_type=current_section_type)


def _classify_table(table: DocxTable, current_section_type: str,
                    stats: dict, seen_section: bool):
    """표를 IR 요소로 분류.

    Returns: SectionHeader | ContentTable | None
    """
    rows = list(table.rows)
    if not rows:
        return None

    first_cells = _get_unique_cells(rows[0])
    n_rows = len(rows)
    n_cols = len(first_cells)

    # --- 1행 1열: 섹션 헤더 후보 ---
    if n_rows == 1 and n_cols == 1:
        text = first_cells[0].text.strip()
        if not text:
            return None

        # 너무 긴 텍스트 → 전면/메타 (스킵)
        if len(text) > 100:
            stats["skipped_long_1x1"] = stats.get("skipped_long_1x1", 0) + 1
            return None

        # 섹션 타입 변경 감지
        section_type = _detect_section_from_text(text)
        if section_type is not None and len(text) < 50:
            return SectionHeader(text=text, level=2, section_type=section_type)

        # 짧은 텍스트 → 하위 섹션 헤더
        if len(text) < 30:
            return SectionHeader(text=text, level=3, section_type=current_section_type)

        # 중간 길이 → 스킵
        stats["skipped_medium_1x1"] = stats.get("skipped_medium_1x1", 0) + 1
        return None

    # --- 다중 행/열 ---
    all_text = " ".join(c.text for r in rows for c in r.cells)

    # 개정이력
    if _is_revision_table(all_text, n_rows):
        stats["revision_tables"] = stats.get("revision_tables", 0) + 1
        return None

    # 메타/목차 (첫 섹션 헤더 이전만)
    if _is_meta_or_toc_table(all_text, seen_section):
        stats["meta_tables"] = stats.get("meta_tables", 0) + 1
        return None

    # 저작권 표
    if _is_copyright(all_text):
        stats["copyright_tables"] = stats.get("copyright_tables", 0) + 1
        return None

    # --- 내용 표 ---
    headers = [c.text.strip().replace('\n', ' ') for c in first_cells]
    data_rows = []
    for row in rows[1:]:
        cells = _get_unique_cells(row)
        data_rows.append([c.text.strip().replace('\n', ' ') for c in cells])

    return ContentTable(headers=headers, rows=data_rows,
                        section_type=current_section_type)


# ---------------------------------------------------------------------------
# 메인 API
# ---------------------------------------------------------------------------


def parse_docx(docx_path: str) -> tuple[list[IRElement], dict]:
    """DOCX 파일을 파싱하여 (IR 요소 리스트, 통계 dict) 반환."""
    doc = _open_docx(docx_path)
    path = Path(docx_path)
    meta = _make_meta_from_filename(path.name)

    elements: list[IRElement] = [meta]
    current_section = "main"
    last_numbered: Optional[NumberedParagraph] = None
    seen_section = False

    stats: dict = defaultdict(int)
    style_dist: dict = defaultdict(int)

    body = doc.element.body
    for child in body:
        tag = child.tag

        # ---- Paragraph ----
        if tag == qn('w:p'):
            raw = _xml_para_text(child)
            style_id = _xml_para_style(child)

            style_dist[style_id or "(none)"] += 1
            stats["total_paragraphs"] += 1

            if not raw or not raw.strip():
                stats["empty_paragraphs"] += 1
                continue

            el = _classify_paragraph(raw, current_section)
            if el is None:
                stats["filtered_paragraphs"] += 1
                continue

            if isinstance(el, SubItem):
                if last_numbered is not None:
                    if el.marker in _MOK_MARKERS:
                        if last_numbered.sub_items:
                            last_numbered.sub_items[-1].sub_sub_items.append(el)
                        else:
                            last_numbered.sub_items.append(el)
                    else:
                        last_numbered.sub_items.append(el)
                    stats["sub_items"] += 1
                else:
                    elements.append(ContinuationText(
                        content=f"{el.marker} {el.content}",
                        section_type=current_section,
                    ))
                    stats["orphan_sub_items"] += 1
                continue

            if isinstance(el, NumberedParagraph):
                el.section_type = current_section
                elements.append(el)
                last_numbered = el
                stats["numbered_paragraphs"] += 1

            elif isinstance(el, ContinuationText):
                el.section_type = current_section
                elements.append(el)
                stats["continuation_texts"] += 1

        # ---- Table ----
        elif tag == qn('w:tbl'):
            stats["total_tables"] += 1
            tbl = DocxTable(child, body)
            el = _classify_table(tbl, current_section, stats, seen_section)

            if el is None:
                continue

            if isinstance(el, SectionHeader):
                current_section = el.section_type
                elements.append(el)
                last_numbered = None
                seen_section = True
                stats["section_headers"] += 1

            elif isinstance(el, ContentTable):
                el.section_type = current_section
                elements.append(el)
                stats["content_tables"] += 1

        # ---- Structured Document Tag (SDT) ----
        elif tag == qn('w:sdt'):
            sdt_content = child.find(qn('w:sdtContent'))
            if sdt_content is None:
                continue
            for sub in sdt_content:
                if sub.tag == qn('w:p'):
                    raw = _xml_para_text(sub)
                    if raw and raw.strip():
                        el = _classify_paragraph(raw, current_section)
                        if isinstance(el, NumberedParagraph):
                            el.section_type = current_section
                            elements.append(el)
                            last_numbered = el
                            stats["numbered_paragraphs"] += 1
                        elif isinstance(el, ContinuationText):
                            el.section_type = current_section
                            elements.append(el)
                            stats["continuation_texts"] += 1
                        elif isinstance(el, SubItem) and last_numbered:
                            if el.marker in _MOK_MARKERS and last_numbered.sub_items:
                                last_numbered.sub_items[-1].sub_sub_items.append(el)
                            else:
                                last_numbered.sub_items.append(el)
                            stats["sub_items"] += 1

    stats["style_distribution"] = dict(style_dist)
    return elements, dict(stats)


def render_markdown(elements: list[IRElement]) -> str:
    """IR 요소 리스트를 검수용 Markdown으로 렌더링."""
    lines: list[str] = []

    for el in elements:
        if isinstance(el, MetaInfo):
            lines.append(f"# {el.display_id} {el.standard_title}")
            lines.append("")

        elif isinstance(el, SectionHeader):
            prefix = "#" * el.level
            lines.append(f"{prefix} {el.text}")
            lines.append("")

        elif isinstance(el, NumberedParagraph):
            lines.append(f"{el.para_number}\t{el.content}")
            for si in el.sub_items:
                lines.append(f"\t{si.marker}\t{si.content}")
                for ssi in si.sub_sub_items:
                    lines.append(f"\t\t{ssi.marker}\t{ssi.content}")
            lines.append("")

        elif isinstance(el, ContinuationText):
            lines.append(el.content)
            lines.append("")

        elif isinstance(el, ContentTable):
            if not el.headers:
                continue
            n = len(el.headers)
            lines.append("| " + " | ".join(el.headers) + " |")
            lines.append("| " + " | ".join(["---"] * n) + " |")
            for row in el.rows:
                padded = (row + [""] * n)[:n]
                lines.append("| " + " | ".join(padded) + " |")
            lines.append("")

    return "\n".join(lines)
