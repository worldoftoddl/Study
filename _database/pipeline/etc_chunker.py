"""
제X호 패턴이 없는 K-IFRS 관련 PDF 청킹 스크립트
(개념체계, 실무서, 경영진설명서 등)

기존 kifrs_chunker.py 로직을 재사용하되, ID 생성만 별도 매핑.

Usage:
    python pipeline/etc_chunker.py
"""

import sys
from pathlib import Path

# kifrs_chunker 임포트를 위해 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kifrs_chunker import (
    convert_pdf_to_markdown,
    parse_markdown_to_chunks,
    flush_paragraph,
)

import re
import json
import dataclasses
from datetime import datetime, timezone

# ── 제X호가 없는 파일 → (display_id, normalized_id) 매핑 ──
FILENAME_ID_MAP = {
    "경영진설명서_작성을_위한_개념체계_번역서": ("경영진설명서 개념체계", "KIFRS_CF_MgtCommentary"),
    "국제회계기준_실무서_2_중요성에_대한_판단_번역서": ("실무서 2 중요성", "KIFRS_PS2_Materiality"),
    "시행중_K-IFRS_재무보고를_위한_개념체계": ("재무보고 개념체계", "KIFRS_CF"),
}


def match_id(filename: str) -> tuple:
    """파일명에서 매핑된 (display_id, normalized_id) 반환"""
    for key, ids in FILENAME_ID_MAP.items():
        if filename.startswith(key):
            return ids
    raise ValueError(f"매핑 없음: {filename}")


def process_single(pdf_path: Path, raw_md_dir: str, chunks_dir: str, kiwi):
    display_id, normalized_id = match_id(pdf_path.stem)

    md_text = convert_pdf_to_markdown(str(pdf_path), raw_md_dir)

    # Markdown 정제
    from pipeline.md_cleaner import clean_markdown
    md_text = clean_markdown(md_text)

    parents, children = parse_markdown_to_chunks(
        md_text, display_id, normalized_id, kiwi
    )

    output = {
        "standard_id": display_id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "parents": [dataclasses.asdict(p) for p in parents],
        "children": [dataclasses.asdict(c) for c in children],
    }

    out_dir = Path(chunks_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / (pdf_path.stem + ".json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  [done] parents={len(parents)}, children={len(children)} → {out_file.name}")


def main():
    from kiwipiepy import Kiwi
    kiwi = Kiwi()

    input_dir = Path("data/raw/IFRS")
    raw_md_dir = "output/raw_md"
    chunks_dir = "output/chunks"

    pdfs = [p for p in sorted(input_dir.glob("*.pdf"))
            if not re.search(r"제\d+호", p.name)]

    print(f"처리할 PDF: {len(pdfs)}개\n")

    for pdf in pdfs:
        print(f"[{pdf.name}]")
        try:
            process_single(pdf, raw_md_dir, chunks_dir, kiwi)
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n완료.")


if __name__ == "__main__":
    main()
