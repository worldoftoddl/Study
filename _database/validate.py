"""
K-IFRS 청킹 결과 검증 스크립트

Usage:
    python validate.py --file "output/chunks/시행중_K-IFRS_제1016호_유형자산(...).json"
    python validate.py  # output/chunks/ 내 모든 JSON 검증
"""

import json
import statistics
import argparse
from pathlib import Path


def validate_single(json_file: Path) -> None:
    with open(json_file, encoding='utf-8') as f:
        data = json.load(f)

    parents = data.get("parents", [])
    children = data.get("children", [])

    # 1. 전체 parent / child 수
    print(f"\n[1] 전체 수")
    print(f"    Parents : {len(parents)}")
    print(f"    Children: {len(children)}")

    # 2. 섹션별 child 수
    section_counts: dict = {}
    for child in children:
        st = child["metadata"].get("section_type", "unknown")
        section_counts[st] = section_counts.get(st, 0) + 1

    print(f"\n[2] 섹션별 child 수")
    for sec in ["main", "ag", "bc", "ie"]:
        print(f"    {sec:6s}: {section_counts.get(sec, 0)}")
    for sec, cnt in section_counts.items():
        if sec not in ("main", "ag", "bc", "ie"):
            print(f"    {sec:6s}: {cnt}  ← 예상 외 섹션")

    # 3. para_number null 비율
    null_count = sum(
        1 for c in children if c["metadata"].get("para_number") is None
    )
    null_ratio = null_count / len(children) if children else 0.0
    print(f"\n[3] para_number null 비율")
    flag = "OK" if null_ratio < 0.2 else "WARNING: 20% 초과"
    print(f"    {null_count}/{len(children)} = {null_ratio:.1%}  [{flag}]")

    # 4. '한 '으로 시작하는 content 중 para_number가 null인 것 (한X.X 유실 의심)
    han_null = [
        c for c in children
        if c["content"].startswith("한 ")
        and c["metadata"].get("para_number") is None
    ]
    print(f"\n[4] content 시작='한 ' & para_number=null (한X.X 유실 의심)")
    print(f"    Count: {len(han_null)}")
    for c in han_null[:5]:
        print(f"    - chunk_id : {c['chunk_id']}")
        print(f"      preview  : {c['content'][:80]!r}")

    # 5. content 길이 통계
    lengths = [len(c["content"]) for c in children]
    if lengths:
        print(f"\n[5] content 길이 (chars)")
        print(f"    min  : {min(lengths)}")
        print(f"    max  : {max(lengths)}")
        print(f"    avg  : {statistics.mean(lengths):.1f}")
        print(f"    >500 : {sum(1 for l in lengths if l > 500)}")

    # 6. cross_refs 비어있는 child 비율
    empty_refs = sum(
        1 for c in children if not c["metadata"].get("cross_refs")
    )
    empty_ratio = empty_refs / len(children) if children else 0.0
    print(f"\n[6] cross_refs 비어있는 child 비율")
    print(f"    {empty_refs}/{len(children)} = {empty_ratio:.1%}")


def validate_all(chunks_dir: str = "output/chunks") -> None:
    json_files = sorted(Path(chunks_dir).glob("*.json"))
    if not json_files:
        print(f"JSON 파일 없음: {chunks_dir}")
        return
    for jf in json_files:
        print(f"\n{'=' * 60}")
        print(f"File: {jf.name}")
        print('=' * 60)
        validate_single(jf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-IFRS 청킹 결과 검증")
    parser.add_argument("--file", help="단일 JSON 파일 경로")
    parser.add_argument("--chunks-dir", default="output/chunks")
    args = parser.parse_args()

    if args.file:
        validate_single(Path(args.file))
    else:
        validate_all(args.chunks_dir)
