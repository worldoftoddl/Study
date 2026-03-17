"""
K-IFRS DOCX 파이프라인 오케스트레이터

DOCX -> parse_docx() -> IR
                       |-> render_markdown() -> output/docx_md/*.md
                       +-> chunk_elements()  -> output/chunks_v2/*.json

Usage:
    python -m pipeline.docx_pipeline                                    # 전체 63개
    python -m pipeline.docx_pipeline --single "data/raw/IFRS_docx/...docx"
    python -m pipeline.docx_pipeline --dry-run                          # 파싱+통계만
"""

import argparse
import json
import sys
from pathlib import Path

from pipeline.docx_parser import parse_docx, render_markdown, MetaInfo
from pipeline.docx_chunker import chunk_elements

DOCX_DIR = Path("data/raw/IFRS_docx")
MD_DIR = Path("output/docx_md")
CHUNKS_DIR = Path("output/chunks_v2")


def process_single(docx_path: Path, dry_run: bool = False) -> dict:
    """단일 DOCX 처리. 반환: 통계 dict."""
    print(f"\n[{docx_path.name}]")

    # 1. Parse
    elements, stats = parse_docx(str(docx_path))
    meta = next((e for e in elements if isinstance(e, MetaInfo)), None)

    np = stats.get("numbered_paragraphs", 0)
    ct = stats.get("continuation_texts", 0)
    si = stats.get("sub_items", 0)
    orphan = stats.get("orphan_sub_items", 0)

    print(f"  paragraphs={stats.get('total_paragraphs', 0)} "
          f"(numbered={np}, continuation={ct}, sub_items={si}, "
          f"filtered={stats.get('filtered_paragraphs', 0)}, "
          f"empty={stats.get('empty_paragraphs', 0)})")
    print(f"  tables={stats.get('total_tables', 0)} "
          f"(sections={stats.get('section_headers', 0)}, "
          f"content={stats.get('content_tables', 0)}, "
          f"revision={stats.get('revision_tables', 0)}, "
          f"meta={stats.get('meta_tables', 0)})")

    # 스타일 분포 로깅
    style_dist = stats.get("style_distribution", {})
    total_paras = stats.get("total_paragraphs", 1)
    if style_dist:
        top3 = sorted(style_dist.items(), key=lambda x: x[1], reverse=True)[:3]
        top3_str = ", ".join(f"{k}:{v}({v/total_paras:.0%})" for k, v in top3)
        print(f"  styles top3: {top3_str}")

    # 경고: para_number null 비율
    total_content = np + ct + orphan
    null_ratio = (ct + orphan) / total_content if total_content else 0
    if null_ratio > 0.3:
        print(f"  WARNING: para_number null ratio={null_ratio:.1%} "
              f"(continuation={ct}, orphan={orphan})")

    if orphan > 0:
        print(f"  WARNING: orphan sub_items={orphan}")

    if dry_run:
        return stats

    # 2. Render Markdown
    MD_DIR.mkdir(parents=True, exist_ok=True)
    md_text = render_markdown(elements)
    md_path = MD_DIR / (docx_path.stem + ".md")
    md_path.write_text(md_text, encoding="utf-8")
    print(f"  MD: {md_path.name} ({len(md_text):,} chars)")

    # 3. Chunk
    if meta is None:
        print("  [SKIP] MetaInfo not found")
        return stats

    output = chunk_elements(elements, meta)
    n_parents = len(output["parents"])
    n_children = len(output["children"])

    # 4. Save JSON
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = CHUNKS_DIR / (docx_path.stem + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 청크 크기 통계
    lengths = [len(c["content"]) for c in output["children"]]
    avg_len = sum(lengths) / len(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0
    small = sum(1 for l in lengths if l < MIN_CHUNK_CHARS)

    print(f"  chunks: parents={n_parents}, children={n_children}")
    print(f"  size: avg={avg_len:.0f}, max={max_len}, <100chars={small}")

    return {**stats, "n_parents": n_parents, "n_children": n_children,
            "avg_chunk_len": avg_len, "max_chunk_len": max_len}


# Import after definition to avoid circular
from pipeline.docx_chunker import MIN_CHUNK_CHARS


def process_all(docx_dir: Path = DOCX_DIR, dry_run: bool = False,
                single_file: str | None = None) -> None:
    """전체 배치 처리."""
    if single_file:
        files = [Path(single_file)]
    else:
        files = sorted(docx_dir.glob("*.docx"))

    if not files:
        print(f"DOCX files not found in: {docx_dir}")
        return

    mode = " (dry-run)" if dry_run else ""
    print(f"Processing {len(files)} DOCX files{mode}")

    all_stats: list[dict] = []
    failures: list[dict] = []

    for f in files:
        try:
            stats = process_single(f, dry_run=dry_run)
            all_stats.append({"file": f.name, **stats})
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            failures.append({"file": f.name, "error": str(e)})

    # ---- 전체 요약 ----
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"  Success: {len(all_stats)}, Failed: {len(failures)}")

    if all_stats:
        total_np = sum(s.get("numbered_paragraphs", 0) for s in all_stats)
        total_ct = sum(s.get("continuation_texts", 0) for s in all_stats)
        total_si = sum(s.get("sub_items", 0) for s in all_stats)
        total_tbl = sum(s.get("content_tables", 0) for s in all_stats)
        total_sec = sum(s.get("section_headers", 0) for s in all_stats)
        total_orphan = sum(s.get("orphan_sub_items", 0) for s in all_stats)

        print(f"  Numbered paragraphs: {total_np}")
        print(f"  Continuation texts:  {total_ct}")
        print(f"  Sub-items attached:  {total_si}")
        print(f"  Orphan sub-items:    {total_orphan}")
        print(f"  Content tables:      {total_tbl}")
        print(f"  Section headers:     {total_sec}")

        overall_null = (total_ct + total_orphan) / (total_np + total_ct + total_orphan) \
            if (total_np + total_ct + total_orphan) else 0
        print(f"  Overall null ratio:  {overall_null:.1%}")

        if not dry_run:
            total_parents = sum(s.get("n_parents", 0) for s in all_stats)
            total_children = sum(s.get("n_children", 0) for s in all_stats)
            avg_sizes = [s.get("avg_chunk_len", 0) for s in all_stats
                         if s.get("avg_chunk_len")]
            overall_avg = sum(avg_sizes) / len(avg_sizes) if avg_sizes else 0
            print(f"\n  Total parents:       {total_parents}")
            print(f"  Total children:      {total_children}")
            print(f"  Avg chunk size:      {overall_avg:.0f} chars")

    # 경고 파일
    warnings = []
    for s in all_stats:
        orphan = s.get("orphan_sub_items", 0)
        if orphan > 5:
            warnings.append(f"  {s['file']}: orphan_sub_items={orphan}")
        np = s.get("numbered_paragraphs", 0)
        ct = s.get("continuation_texts", 0)
        total = np + ct
        if total and ct / total > 0.5:
            warnings.append(
                f"  {s['file']}: high null ratio "
                f"({ct}/{total}={ct/total:.0%})")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(w)

    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print(f"  {f['file']}: {f['error']}")

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="K-IFRS DOCX chunking pipeline")
    parser.add_argument("--single", help="Single DOCX file path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse + stats only (no chunk generation)")
    parser.add_argument("--docx-dir", default=str(DOCX_DIR),
                        help="DOCX directory")
    args = parser.parse_args()

    process_all(
        docx_dir=Path(args.docx_dir),
        dry_run=args.dry_run,
        single_file=args.single,
    )
