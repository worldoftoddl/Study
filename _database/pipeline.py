"""
K-IFRS PDF 파싱/청킹 파이프라인

전체 실행 스크립트. PDF → Markdown → 문단 추출 → Parent-Child 청크 → JSON 저장.
"""

import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

from kifrs_parser import pdf_to_markdown, extract_paragraphs, extract_metadata_from_filename
from kifrs_chunker import build_parent_child_chunks

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_SOURCE_DIR = r"c:\_database\IFRS + 개념체계"
DEFAULT_OUTPUT_DIR = "output"


def process_single_pdf(
    pdf_path: Path,
    output_dir: Path,
    save_markdown: bool = True,
) -> dict:
    """
    단일 K-IFRS PDF에 대해 전체 파이프라인을 실행한다.

    Returns:
        처리 결과 요약 dict
    """
    logger.info(f"처리 시작: {pdf_path.name}")

    # 1. 파일명에서 메타데이터 추출
    metadata = extract_metadata_from_filename(pdf_path)
    standard_id = metadata["standard_id"]
    logger.info(f"  ID: {standard_id}, 이름: {metadata['standard_name']}")

    # 2. PDF → Markdown 변환
    md_text = pdf_to_markdown(str(pdf_path))

    if not md_text or not md_text.strip():
        logger.warning(f"  빈 마크다운 출력: {pdf_path.name}")
        return {
            "standard_id": standard_id,
            "parents": 0,
            "children": 0,
            "error": "empty_markdown",
        }

    # 2a. 중간 마크다운 저장
    if save_markdown:
        md_dir = output_dir / "raw_md"
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / f"{standard_id}.md"
        md_path.write_text(md_text, encoding="utf-8")
        logger.info(f"  마크다운 저장: {md_path}")

    # 3. 문단 추출
    paragraphs = extract_paragraphs(md_text, metadata)

    if not paragraphs:
        logger.warning(f"  문단 추출 실패: {pdf_path.name}")
        return {
            "standard_id": standard_id,
            "parents": 0,
            "children": 0,
            "error": "no_paragraphs",
        }

    # 4. Parent-Child 청크 구성
    parents, children = build_parent_child_chunks(paragraphs)

    # 5. JSON 저장
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    output_data = {
        "standard_id": standard_id,
        "standard_name": metadata["standard_name"],
        "source_file": metadata["source_file"],
        "processed_at": datetime.now().isoformat(),
        "stats": {
            "total_paragraphs": len(paragraphs),
            "total_parents": len(parents),
            "total_children": len(children),
        },
        "parents": [asdict(p) for p in parents],
        "children": [asdict(c) for c in children],
    }

    json_path = chunks_dir / f"{standard_id}.json"
    json_path.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"  JSON 저장: {json_path} ({len(parents)} parents, {len(children)} children)")

    return {
        "standard_id": standard_id,
        "parents": len(parents),
        "children": len(children),
    }


def run_pipeline(source_dir: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> None:
    """
    소스 디렉토리 내 모든 K-IFRS PDF에 대해 파이프라인을 실행한다.
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)

    if not source_path.exists():
        raise FileNotFoundError(f"소스 디렉토리를 찾을 수 없음: {source_path}")

    pdf_files = sorted(source_path.glob("*.pdf"))
    logger.info(f"{len(pdf_files)}개 PDF 발견: {source_path}")

    results = []
    errors = []

    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"[{i}/{len(pdf_files)}] {pdf_file.name}")
        try:
            result = process_single_pdf(pdf_file, output_path)
            results.append(result)
        except Exception as e:
            logger.error(f"  실패: {e}", exc_info=True)
            errors.append({"file": pdf_file.name, "error": str(e)})

    # 전체 요약
    total_parents = sum(r.get("parents", 0) for r in results)
    total_children = sum(r.get("children", 0) for r in results)

    logger.info("=" * 60)
    logger.info("파이프라인 완료")
    logger.info(f"  처리: {len(results)} / {len(pdf_files)} 파일")
    logger.info(f"  총 Parents: {total_parents}")
    logger.info(f"  총 Children: {total_children}")
    if errors:
        logger.warning(f"  오류: {len(errors)}건")
        for err in errors:
            logger.warning(f"    {err['file']}: {err['error']}")

    # 요약 JSON 저장
    summary_path = output_path / "pipeline_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "processed_at": datetime.now().isoformat(),
                "total_files": len(pdf_files),
                "successful": len(results),
                "failed": len(errors),
                "total_parents": total_parents,
                "total_children": total_children,
                "results": results,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(f"  요약 저장: {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-IFRS PDF 파싱/청킹 파이프라인")
    parser.add_argument(
        "--source", "-s",
        default=DEFAULT_SOURCE_DIR,
        help="K-IFRS PDF 파일이 있는 소스 디렉토리",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help="출력 디렉토리 (기본: output)",
    )
    parser.add_argument(
        "--single",
        help="단일 PDF 파일 처리 (전체 경로)",
    )
    parser.add_argument(
        "--no-markdown",
        action="store_true",
        help="중간 마크다운 파일 저장 생략",
    )

    args = parser.parse_args()

    if args.single:
        process_single_pdf(
            Path(args.single),
            Path(args.output),
            save_markdown=not args.no_markdown,
        )
    else:
        run_pipeline(args.source, args.output)
