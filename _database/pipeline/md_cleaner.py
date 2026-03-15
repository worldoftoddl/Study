"""
K-IFRS raw markdown 후처리 모듈

pymupdf4llm이 생성한 raw markdown의 품질 문제를 정제:
  1. 저작권/영문 보일러플레이트 제거
  2. 페이지 번호 아티팩트 제거
  3. PDF 줄바꿈을 논리적 문단으로 병합
  4. 테이블 <br> 태그 정리
  5. 과도한 빈줄 축소

Usage:
    python pipeline/md_cleaner.py                       # 전체 배치
    python pipeline/md_cleaner.py --single FILE.md      # 단일 파일
    python pipeline/md_cleaner.py --dry-run              # 통계만 출력
    python pipeline/md_cleaner.py --fix-spacing          # 띄어쓰기 교정 포함
"""

import re
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# 정규식 패턴
# ---------------------------------------------------------------------------

# 페이지 번호: "    - 8    " 등
PAGE_NUM_RE = re.compile(r'^\s*-\s*\d+\s*$')

# 마크다운 헤딩
HEADING_RE = re.compile(r'^#{1,6}\s')

# 문단 번호 시작 (새 문단의 시작을 나타냄)
PARA_START_RE = re.compile(
    r'^('
    r'\d+(?:\.\d+)*'           # 1, 1.1, 2.1.1
    r'|한\s*\d+(?:\.\d+)*'     # 한1, 한 2.1
    r'|AG\d+[A-Z]?'            # AG12, AG12A
    r'|BC\d+[A-Z]?'            # BC3, BC28A
    r'|BCE\.\d+'               # BCE.2 (IFRS 9 원가효익분석)
    r'|IE\d+[A-Z]?'            # IE5
    r'|SP\d+\.\d+'             # SP1.1
    r'|B\d+(?:\.\d+)*'         # B2, B4.1.7
    r'|C\d+[A-Z]?(?:\.\d+)?'  # C3, C5A (경과규정)
    r')\s'
)

# 원문자 리스트 시작
CIRCLED_NUM_RE = re.compile(r'^[⑴⑵⑶⑷⑸⑹⑺⑻⑼⑽㈎㈏㈐㈑㈒]')

# 각주 시작: "1) ", "[1] "
FOOTNOTE_RE = re.compile(r'^(\d+\)|\[\d+\])\s')

# Ÿ 불릿 (해석서에서 사용)
BULLET_RE = re.compile(r'^Ÿ\s')

# 문장 종결 패턴 (마침표 앞에 공백이 있는 경우도 포함)
SENTENCE_END_RE = re.compile(r'[.。!?]\s*$')

# 테이블 행
TABLE_ROW_RE = re.compile(r'^\|')

# <br> 태그
BR_TAG_RE = re.compile(r'<br\s*/?>')

# 보일러플레이트 끝 마커
BOILERPLATE_END_RE = re.compile(r'^#\s*본\s*문\s*$')

# 보일러플레이트 키워드 (non-standard 파일용)
BOILERPLATE_KEYWORDS = [
    "IFRS Foundation",
    "All rights reserved",
    "Copyright ©",
    "Westferry Circus",
    "International Financial Reporting",
    "kasb.or.kr",
    "ifrs.org",
    "integral part of the standards",
]


# ---------------------------------------------------------------------------
# Step 1: 보일러플레이트 제거
# ---------------------------------------------------------------------------

def remove_boilerplate(text: str) -> str:
    """저작권/영문 블록 제거. '# 본 문' 이전 또는 보일러플레이트 키워드 이후."""
    lines = text.split('\n')

    # "# 본 문" 찾기
    cut_idx = None
    for i, line in enumerate(lines):
        if BOILERPLATE_END_RE.match(line.strip()):
            cut_idx = i + 1  # "# 본 문" 다음부터
            break

    if cut_idx is not None:
        return '\n'.join(lines[cut_idx:])

    # "# 본 문" 없는 경우 (경영진설명서, 실무서 등):
    # 저작권 블록은 파일 시작 ~ 영문 copyright 종료 구간에 존재.
    # 영문 저작권 블록 종료 후 첫 번째 헤딩부터 보존.
    # 전략: 처음 150줄 내에서 마지막 키워드 라인을 찾고, 그 이후 첫 헤딩부터 보존
    last_bp_idx = 0
    search_limit = min(200, len(lines))
    for i in range(search_limit):
        for kw in BOILERPLATE_KEYWORDS:
            if kw in lines[i]:
                last_bp_idx = i
                break

    if last_bp_idx > 0:
        # 키워드 이후 첫 번째 헤딩부터 보존
        for i in range(last_bp_idx + 1, len(lines)):
            if HEADING_RE.match(lines[i].strip()):
                return '\n'.join(lines[i:])
        # 헤딩 없으면 키워드 다음부터
        return '\n'.join(lines[last_bp_idx + 1:])

    return text


# ---------------------------------------------------------------------------
# Step 2: 페이지 번호 제거
# ---------------------------------------------------------------------------

def remove_page_numbers(text: str) -> str:
    """페이지 번호 아티팩트 라인 제거."""
    lines = text.split('\n')
    return '\n'.join(line for line in lines if not PAGE_NUM_RE.match(line))


# ---------------------------------------------------------------------------
# Step 3: PDF 줄바꿈 병합 (핵심)
# ---------------------------------------------------------------------------

def _is_protected(line: str) -> bool:
    """병합하면 안 되는 라인 유형 판별."""
    stripped = line.strip()
    if not stripped:
        return True
    if HEADING_RE.match(stripped):
        return True
    if TABLE_ROW_RE.match(stripped):
        return True
    if PAGE_NUM_RE.match(line):
        return True
    return False


def _starts_new_block(line: str) -> bool:
    """새 논리 블록(문단/리스트)을 시작하는 라인인지 판별."""
    stripped = line.strip()
    if not stripped:
        return False
    if PARA_START_RE.match(stripped):
        return True
    if CIRCLED_NUM_RE.match(stripped):
        return True
    if FOOTNOTE_RE.match(stripped):
        return True
    if BULLET_RE.match(stripped):
        return True
    if HEADING_RE.match(stripped):
        return True
    if TABLE_ROW_RE.match(stripped):
        return True
    return False


def join_pdf_line_breaks(text: str) -> str:
    """PDF 물리적 줄바꿈을 논리적 문단으로 병합.

    알고리즘:
    - 텍스트 라인을 순회하며, 보호 대상이 아닌 연속 텍스트 라인을 수집
    - 빈줄 1~2개를 사이에 두고 있어도, 다음 텍스트가 새 블록이 아니고
      이전 라인이 문장 종결이 아니면 → 같은 문단으로 병합
    - 빈줄 3개 이상이면 문단 구분으로 판단
    """
    lines = text.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 빈줄 또는 보호 대상 → 그대로 출력
        if not stripped or _is_protected(line):
            result.append(line)
            i += 1
            continue

        # 텍스트 라인: 문단 수집 시작
        para_parts = [stripped]
        i += 1

        while i < len(lines):
            # 빈줄 건너뛰기 (1~2개까지)
            blank_count = 0
            j = i
            while j < len(lines) and not lines[j].strip():
                blank_count += 1
                j += 1

            # 빈줄 3개 이상 → 문단 경계
            if blank_count >= 3:
                break

            # 파일 끝
            if j >= len(lines):
                break

            next_line = lines[j]
            next_stripped = next_line.strip()

            # 다음 라인이 보호 대상이거나 새 블록 시작 → 병합 중단
            if _is_protected(next_line) or _starts_new_block(next_line):
                break

            # 이전 라인이 문장 종결 → 병합 중단
            if SENTENCE_END_RE.search(para_parts[-1]):
                break

            # 병합: 빈줄 건너뛰고 다음 텍스트를 현재 문단에 추가
            para_parts.append(next_stripped)
            i = j + 1
            continue

        # 수집된 문단 출력
        result.append(' '.join(para_parts))

    return '\n'.join(result)


# ---------------------------------------------------------------------------
# Step 4: 테이블 <br> 정리
# ---------------------------------------------------------------------------

def clean_table_br(text: str) -> str:
    """테이블 셀 내 <br> 태그를 공백으로 치환."""
    lines = text.split('\n')
    result = []
    for line in lines:
        if TABLE_ROW_RE.match(line.strip()):
            line = BR_TAG_RE.sub(' ', line)
            line = re.sub(r'  +', ' ', line)
        result.append(line)
    return '\n'.join(result)


# ---------------------------------------------------------------------------
# Step 5: 과도한 빈줄 축소
# ---------------------------------------------------------------------------

def collapse_blank_lines(text: str) -> str:
    """연속 3개 이상 빈줄을 2개로 축소."""
    return re.sub(r'\n{4,}', '\n\n\n', text)


# ---------------------------------------------------------------------------
# 통합 정제 함수
# ---------------------------------------------------------------------------

def clean_markdown(text: str, fix_spacing: bool = False) -> str:
    """모든 정제 단계를 순차 적용."""
    text = remove_boilerplate(text)
    text = remove_page_numbers(text)
    text = collapse_blank_lines(text)      # 페이지 번호 제거 후 빈줄 정리
    text = join_pdf_line_breaks(text)
    text = clean_table_br(text)
    text = collapse_blank_lines(text)      # 최종 빈줄 정리

    if fix_spacing:
        text = fix_korean_spacing(text)

    return text.strip() + '\n'


# ---------------------------------------------------------------------------
# (선택) 띄어쓰기 교정
# ---------------------------------------------------------------------------

def fix_korean_spacing(text: str) -> str:
    """kiwipiepy로 한국어 띄어쓰기 교정. 헤딩/테이블은 제외."""
    from kiwipiepy import Kiwi
    kiwi = Kiwi()

    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        # 헤딩, 테이블, 빈줄은 건너뜀
        if not stripped or HEADING_RE.match(stripped) or TABLE_ROW_RE.match(stripped):
            result.append(line)
            continue
        result.append(kiwi.space(stripped))
    return '\n'.join(result)


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def clean_single_file(src: Path, dst: Path,
                      dry_run: bool = False,
                      fix_spacing: bool = False) -> dict:
    """단일 .md 파일 정제. 통계 dict 반환."""
    original = src.read_text(encoding='utf-8')
    cleaned = clean_markdown(original, fix_spacing=fix_spacing)

    original_lines = original.count('\n')
    cleaned_lines = cleaned.count('\n')

    stats = {
        "filename": src.name,
        "original_lines": original_lines,
        "cleaned_lines": cleaned_lines,
        "reduction_pct": round((1 - cleaned_lines / max(original_lines, 1)) * 100, 1),
    }

    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(cleaned, encoding='utf-8')

    return stats


def clean_all(raw_md_dir: str = "output/raw_md",
              clean_md_dir: str = "output/clean_md",
              dry_run: bool = False,
              fix_spacing: bool = False) -> None:
    """전체 배치 처리."""
    src_dir = Path(raw_md_dir)
    dst_dir = Path(clean_md_dir)
    files = sorted(src_dir.glob("*.md"))

    print(f"처리할 파일: {len(files)}개\n")

    total_orig = 0
    total_clean = 0

    for f in files:
        dst = dst_dir / f.name
        stats = clean_single_file(f, dst, dry_run=dry_run, fix_spacing=fix_spacing)
        total_orig += stats["original_lines"]
        total_clean += stats["cleaned_lines"]
        action = "[dry-run]" if dry_run else "[clean]"
        print(f"  {action} {stats['filename'][:60]:60s}  "
              f"{stats['original_lines']:>5d} → {stats['cleaned_lines']:>5d} "
              f"({stats['reduction_pct']:+.1f}%)")

    reduction = round((1 - total_clean / max(total_orig, 1)) * 100, 1)
    print(f"\n합계: {total_orig:,} → {total_clean:,} lines ({reduction:+.1f}%)")
    if not dry_run:
        print(f"출력: {dst_dir}/")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-IFRS raw markdown 후처리")
    parser.add_argument("--single", help="단일 .md 파일 경로")
    parser.add_argument("--raw-md-dir", default="output/raw_md")
    parser.add_argument("--clean-md-dir", default="output/clean_md")
    parser.add_argument("--dry-run", action="store_true",
                        help="파일 쓰기 없이 통계만 출력")
    parser.add_argument("--fix-spacing", action="store_true",
                        help="kiwipiepy 한국어 띄어쓰기 교정 적용")
    args = parser.parse_args()

    if args.single:
        src = Path(args.single)
        dst = Path(args.clean_md_dir) / src.name
        stats = clean_single_file(src, dst,
                                  dry_run=args.dry_run,
                                  fix_spacing=args.fix_spacing)
        action = "[dry-run]" if args.dry_run else "[clean]"
        print(f"{action} {stats['filename']}")
        print(f"  {stats['original_lines']} → {stats['cleaned_lines']} lines "
              f"({stats['reduction_pct']:+.1f}%)")
        if not args.dry_run:
            print(f"  → {dst}")
    else:
        clean_all(
            raw_md_dir=args.raw_md_dir,
            clean_md_dir=args.clean_md_dir,
            dry_run=args.dry_run,
            fix_spacing=args.fix_spacing,
        )
