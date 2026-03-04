"""
K-IFRS PDF → Parent-Child JSON 청킹 파이프라인

Usage:
    python kifrs_chunker.py --single "IFRS + 개념체계/시행중_K-IFRS_제1016호_유형자산(...).pdf"
    python kifrs_chunker.py  # 전체 배치
"""

import re
import json
import argparse
import unicodedata
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pymupdf4llm

# ---------------------------------------------------------------------------
# 상수: 정규식
# ---------------------------------------------------------------------------

PARA_PATTERNS = {
    # main: 숫자/한X.X 뒤에 반드시 한글 또는 ( 이 와야 함 (영문 주소 등 오탐 방지)
    "main": re.compile(r'^(한\s*\d+(?:\.\d+)*|\d+(?:\.\d+)*)\s+(?=[가-힣(])'),
    "ag":   re.compile(r'^(AG\d+[A-Z]?(?:\.\d+)?)\s'),
    "bc":   re.compile(r'^(BC\d+[A-Z]?(?:\.\d+)?)\s'),
    "ie":   re.compile(r'^(IE\d+[A-Z]?(?:\.\d+)?)\s'),
}

CROSS_REF_PATTERNS = [
    re.compile(r'AG\d+[A-Z]?(?:~AG\d+[A-Z]?)?'),
    re.compile(r'BC\d+[A-Z]?'),
    re.compile(r'IE\d+[A-Z]?'),
    re.compile(r'기준서\s+\d+호'),
    re.compile(r'해석서\s+\d+호'),
]

HEADING_RE = re.compile(r'^(#{1,6})\s')

# 저작권/영문 notice 필터링 키워드
COPYRIGHT_KEYWORDS = [
    "IFRS Foundation",
    "All rights reserved",
    "Copyright",
    "International Financial Reporting Standards",
    "Westferry Circus",
    "permitted to reproduce",
]

# 한X.X 문단번호 복원용 패턴
HAN_PARA_RE = re.compile(r'^한\s*(\d+(?:\.\d+)*)')

# ---------------------------------------------------------------------------
# 데이터 클래스
# ---------------------------------------------------------------------------

@dataclass
class ParentChunk:
    chunk_id: str
    heading_text: str
    section_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ChildChunk:
    chunk_id: str
    parent_id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ParserState:
    section_type: str = "main"
    current_parent: Optional[ParentChunk] = None
    current_para_lines: list = field(default_factory=list)
    current_para_number: Optional[str] = None
    parents: list = field(default_factory=list)
    children: list = field(default_factory=list)
    slug_counts: dict = field(default_factory=dict)
    unk_counter: int = 0


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def extract_standard_id(filename: str) -> tuple:
    """파일명에서 기준서 번호 추출. 반환: (display, normalized)"""
    match = re.search(r'제(\d+)호', filename)
    if not match:
        raise ValueError(f"기준서 번호 추출 실패: {filename}")
    number = match.group(1)
    return f"K-IFRS {number}", f"KIFRS{number}"


def slugify(text: str) -> str:
    """헤딩 텍스트를 ID-safe 슬러그로 변환"""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'^#+\s*', '', text).strip()
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ\-]', '', text)
    return text[:60]


def detect_section_type(heading_text: str, current: str) -> str:
    """헤딩 텍스트로부터 섹션 타입 판별"""
    cleaned = re.sub(r'^#+\s*', '', heading_text).strip()
    if '적용지침' in cleaned:
        return 'ag'
    if '결론도출근거' in cleaned:
        return 'bc'
    if '사례' in cleaned and len(cleaned) < 20:
        # '사례' 단독 헤딩만 IE로 처리 (본문 내 '사례' 언급 제외)
        return 'ie'
    return current


def extract_para_number(line: str, section_type: str) -> Optional[str]:
    """라인에서 문단 번호 추출. 테이블 행은 제외."""
    if line.startswith('|'):
        return None
    pattern = PARA_PATTERNS.get(section_type)
    if not pattern:
        return None
    match = pattern.match(line)
    if match:
        return match.group(1).replace(' ', '')  # '한 2.1' → '한2.1' 정규화
    return None


def extract_cross_refs(content: str) -> list:
    """본문에서 상호참조 패턴 추출"""
    refs = set()
    for pattern in CROSS_REF_PATTERNS:
        for m in pattern.finditer(content):
            refs.add(m.group(0))
    return sorted(refs)


def detect_has_table(content: str) -> bool:
    return bool(re.search(r'^\|.+\|', content, re.MULTILINE))


def detect_has_example(content: str) -> bool:
    return bool(re.search(r'(사례\s*\d+|예시\s*\d+|예\s*\d+)', content))


def split_into_sentences(content: str, kiwi) -> list:
    """kiwipiepy로 문장 분리"""
    result = kiwi.split_into_sents(content)
    return [s.text.strip() for s in result if s.text.strip()]


# ---------------------------------------------------------------------------
# ID 생성
# ---------------------------------------------------------------------------

def make_parent_id(normalized_id: str, section_type: str,
                   heading_line: str, slug_counts: dict) -> str:
    slug = slugify(heading_line)
    count = slug_counts.get(slug, 0)
    slug_counts[slug] = count + 1
    if count == 0:
        return f"{normalized_id}_{section_type}_h_{slug}"
    return f"{normalized_id}_{section_type}_h_{slug}_{count + 1}"


def make_child_id(normalized_id: str, section_type: str,
                  para_number: Optional[str], unk_counter: int) -> str:
    if para_number:
        return f"{normalized_id}_{section_type}_{para_number}"
    return f"{normalized_id}_{section_type}_unk_{unk_counter}"


# ---------------------------------------------------------------------------
# 핵심 파싱
# ---------------------------------------------------------------------------

def flush_paragraph(state: ParserState, normalized_id: str,
                    display_id: str, kiwi) -> None:
    """누적된 문단을 ChildChunk로 변환하여 state.children에 추가"""
    if not state.current_para_lines:
        return

    content = "\n".join(state.current_para_lines).strip()
    content = re.sub(r'\n{3,}', '\n\n', content)

    if not content:
        state.current_para_lines = []
        state.current_para_number = None
        return

    # --- 필터 1: 저작권/영문 notice 제거 ---
    if any(kw in content for kw in COPYRIGHT_KEYWORDS):
        state.current_para_lines = []
        state.current_para_number = None
        return

    # --- 필터 2: 50자 미만 content 제거 ---
    if len(content) < 50:
        state.current_para_lines = []
        state.current_para_number = None
        return

    para_num = state.current_para_number

    # --- 한X.X 문단번호 복원 시도 ---
    if para_num is None and content.startswith("한"):
        han_match = HAN_PARA_RE.match(content)
        if han_match:
            para_num = "한" + han_match.group(1)

    if para_num is None:
        state.unk_counter += 1

    child_id = make_child_id(normalized_id, state.section_type,
                             para_num, state.unk_counter)

    parent_id = (state.current_parent.chunk_id
                 if state.current_parent
                 else f"{normalized_id}_{state.section_type}_h_root")

    cross_refs = extract_cross_refs(content)

    # --- cross_refs 자기참조 제거 ---
    if para_num and para_num in cross_refs:
        cross_refs = [r for r in cross_refs if r != para_num]

    has_table = detect_has_table(content)
    has_example = detect_has_example(content)

    metadata = {
        "standard_id": display_id,
        "section_type": state.section_type,
        "para_number": para_num,
        "cross_refs": cross_refs,
        "has_table": has_table,
        "has_example": has_example,
    }

    if kiwi and len(content) > 500:
        metadata["sentences"] = split_into_sentences(content, kiwi)

    state.children.append(ChildChunk(
        chunk_id=child_id,
        parent_id=parent_id,
        content=content,
        metadata=metadata,
    ))

    state.current_para_lines = []
    state.current_para_number = None


def parse_markdown_to_chunks(md_text: str, display_id: str,
                              normalized_id: str, kiwi) -> tuple:
    """
    Markdown 텍스트를 state machine으로 파싱하여 (parents, children) 반환.

    라인 분류:
      HEADING   → 문단 플러시 → 섹션 타입 갱신 → 새 Parent
      PARA_START → 문단 플러시 → 새 문단 누적 시작
      BLANK/CONT → 현재 문단에 append (빈 줄에서 플러시 안 함)
    """
    state = ParserState()

    # 첫 heading 전 고아 텍스트용 synthetic root parent
    root_parent = ParentChunk(
        chunk_id=f"{normalized_id}_main_h_root",
        heading_text="root",
        section_type="main",
        metadata={"standard_id": display_id, "section_type": "main"},
    )
    state.current_parent = root_parent
    state.parents.append(root_parent)

    for line in md_text.split('\n'):
        line = line.rstrip()

        heading_match = HEADING_RE.match(line)

        if heading_match:
            # HEADING: 플러시 → 섹션 타입 갱신 → 새 Parent
            flush_paragraph(state, normalized_id, display_id, kiwi)

            new_section = detect_section_type(line, state.section_type)
            state.section_type = new_section

            parent_id = make_parent_id(normalized_id, new_section,
                                       line, state.slug_counts)
            parent = ParentChunk(
                chunk_id=parent_id,
                heading_text=re.sub(r'^#+\s*', '', line).strip(),
                section_type=new_section,
                metadata={"standard_id": display_id, "section_type": new_section},
            )
            state.current_parent = parent
            state.parents.append(parent)

        else:
            para_num = extract_para_number(line, state.section_type)

            if para_num is not None:
                # PARA_START: 이전 문단 플러시 → 새 문단 시작
                flush_paragraph(state, normalized_id, display_id, kiwi)
                state.current_para_number = para_num
                state.current_para_lines = [line]
            else:
                # BLANK or CONTINUATION: 현재 문단에 append
                if state.current_para_lines:
                    state.current_para_lines.append(line)
                elif line.strip():
                    # 헤딩 직후 문단 번호 없는 텍스트 (introductory text)
                    state.current_para_lines.append(line)

    # 마지막 남은 문단 플러시
    flush_paragraph(state, normalized_id, display_id, kiwi)

    return state.parents, state.children


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def convert_pdf_to_markdown(pdf_path: str, raw_md_dir: str) -> str:
    """PDF → Markdown 변환. raw_md_dir에 캐시 저장."""
    pdf_path = Path(pdf_path)
    out_dir = Path(raw_md_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / (pdf_path.stem + ".md")

    if out_file.exists():
        print(f"  [cache] {out_file.name}")
        return out_file.read_text(encoding="utf-8")

    print(f"  [convert] {pdf_path.name} ...")
    md_text = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=False)
    out_file.write_text(md_text, encoding="utf-8")
    print(f"  [saved]  {out_file.name} ({len(md_text):,} chars)")
    return md_text


def process_single_pdf(pdf_path: str, raw_md_dir: str,
                       chunks_dir: str, kiwi) -> dict:
    """단일 PDF 처리 → JSON 저장"""
    pdf_path = Path(pdf_path)
    display_id, normalized_id = extract_standard_id(pdf_path.name)

    # 1. PDF → Markdown
    md_text = convert_pdf_to_markdown(str(pdf_path), raw_md_dir)

    # 2. Markdown → Chunks
    parents, children = parse_markdown_to_chunks(
        md_text, display_id, normalized_id, kiwi
    )

    # 3. 직렬화
    output = {
        "standard_id": display_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "parents": [dataclasses.asdict(p) for p in parents],
        "children": [dataclasses.asdict(c) for c in children],
    }

    # 4. 저장
    out_dir = Path(chunks_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / (pdf_path.stem + ".json")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [done] parents={len(parents)}, children={len(children)} → {out_file.name}")
    return output


def process_all_pdfs(input_dir: str = "data/raw/IFRS + 개념체계",
                     raw_md_dir: str = "output/raw_md",
                     chunks_dir: str = "output/chunks",
                     single_file: Optional[str] = None) -> None:
    """전체 배치 처리"""
    from kiwipiepy import Kiwi
    kiwi = Kiwi()

    if single_file:
        pdfs = [Path(single_file)]
    else:
        pdfs = sorted(Path(input_dir).glob("*.pdf"))

    print(f"처리할 PDF: {len(pdfs)}개\n")

    for pdf in pdfs:
        print(f"[{pdf.name}]")
        try:
            process_single_pdf(str(pdf), raw_md_dir, chunks_dir, kiwi)
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n완료.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-IFRS PDF 청킹 파이프라인")
    parser.add_argument("--single", help="단일 PDF 파일 경로")
    parser.add_argument("--input-dir", default="data/raw/IFRS + 개념체계")
    parser.add_argument("--raw-md-dir", default="output/raw_md")
    parser.add_argument("--chunks-dir", default="output/chunks")
    args = parser.parse_args()

    process_all_pdfs(
        input_dir=args.input_dir,
        raw_md_dir=args.raw_md_dir,
        chunks_dir=args.chunks_dir,
        single_file=args.single,
    )
