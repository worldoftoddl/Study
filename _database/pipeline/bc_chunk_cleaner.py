"""
K-IFRS 저가치 BC 청크 제거

BC(결론도출근거) 중 RAG 검색 가치가 없는 보일러플레이트 청크를 제거:
  1. unk_5k_bc      — 문단번호 없는 5KB 이상 BC 청크 (OCR 쓰레기)
  2. meta_disclaimer — "이 결론도출근거는 ... 기준서의 일부를 구성하는 것은 아니다"
  3. admin_intro     — 한국회계기준원 제정 경과 안내문
  4. amendment       — 제·개정 경과 섹션
  5. dissenting      — 소수의견 섹션
  6. ias_relation    — 국제회계기준과의 관계 섹션

Usage:
    python pipeline/bc_chunk_cleaner.py --dry-run         # 통계만 출력
    python pipeline/bc_chunk_cleaner.py                   # in-place 제거
    python pipeline/bc_chunk_cleaner.py --single FILE.json --dry-run
    python pipeline/bc_chunk_cleaner.py --out-dir output/chunks_clean
"""

import json
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# 6개 규칙 함수 (chunk → bool)
# ---------------------------------------------------------------------------

def is_unk_5k_bc(chunk: dict) -> bool:
    """문단번호 없는 5KB 이상 BC 청크"""
    cid = chunk["chunk_id"]
    return "_bc_" in cid and "_unk_" in cid and len(chunk["content"]) >= 5000


def is_meta_disclaimer(chunk: dict) -> bool:
    """결론도출근거 면책문구"""
    c = chunk["content"]
    return "이 결론도출근거는" in c and "기준서의 일부를 구성하는 것은 아니다" in c


def is_admin_intro(chunk: dict) -> bool:
    """한국회계기준원 제정 경과 안내문"""
    return "한국회계기준원은 한국채택국제회계기준 제정시 기준서를 제정한 과정" in chunk["content"]


def is_amendment_history(chunk: dict) -> bool:
    """제·개정 경과 섹션 하위 청크"""
    return "제_개정_경과" in chunk.get("parent_id", "")


def is_dissenting_opinion(chunk: dict) -> bool:
    """소수의견 섹션 하위 청크"""
    return "소수의견" in chunk.get("parent_id", "")


def is_ias_relation(chunk: dict) -> bool:
    """국제회계기준과의 관계 섹션 하위 청크"""
    return "국제회계기준과의_관계" in chunk.get("parent_id", "")


# ---------------------------------------------------------------------------
# 규칙 레지스트리
# ---------------------------------------------------------------------------

REMOVAL_RULES = [
    ("unk_5k_bc",       is_unk_5k_bc),
    ("meta_disclaimer", is_meta_disclaimer),
    ("admin_intro",     is_admin_intro),
    ("amendment",       is_amendment_history),
    ("dissenting",      is_dissenting_opinion),
    ("ias_relation",    is_ias_relation),
]


# ---------------------------------------------------------------------------
# 핵심 함수
# ---------------------------------------------------------------------------

def classify_chunk(chunk: dict) -> list[str]:
    """매칭되는 규칙명 리스트 반환. 빈 리스트 = 유지."""
    return [name for name, fn in REMOVAL_RULES if fn(chunk)]


def prune_orphaned_parents(parents: list, children: list) -> tuple[list, int]:
    """남은 children이 참조하지 않는 parent 제거."""
    referenced = {c["parent_id"] for c in children}
    kept = [p for p in parents if p["chunk_id"] in referenced]
    return kept, len(parents) - len(kept)


def clean_json_file(src: Path, dst: Path, dry_run: bool) -> dict:
    """단일 JSON 파일의 저가치 BC 청크 제거."""
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    original_children = data["children"]
    original_count = len(original_children)

    by_rule = {name: 0 for name, _ in REMOVAL_RULES}
    kept_children = []

    for child in original_children:
        matched = classify_chunk(child)
        if matched:
            for rule_name in matched:
                by_rule[rule_name] += 1
        else:
            kept_children.append(child)

    removed_count = original_count - len(kept_children)

    # parent 정리
    pruned_parents, orphaned_count = prune_orphaned_parents(
        data["parents"], kept_children
    )

    if not dry_run and removed_count > 0:
        data["parents"] = pruned_parents
        data["children"] = kept_children
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "filename": src.name,
        "original_children": original_count,
        "removed_children": removed_count,
        "remaining_children": len(kept_children),
        "orphaned_parents": orphaned_count,
        "by_rule": by_rule,
    }


def clean_all(chunks_dir: str, out_dir: str | None, dry_run: bool) -> None:
    """전체 배치 처리."""
    src_dir = Path(chunks_dir)
    files = sorted(src_dir.glob("*.json"))

    total_orig = 0
    total_removed = 0
    total_orphaned = 0
    total_by_rule = {name: 0 for name, _ in REMOVAL_RULES}

    action = "[dry-run]" if dry_run else "[clean]"

    for f in files:
        dst = (Path(out_dir) / f.name) if out_dir else f
        stats = clean_json_file(f, dst, dry_run)

        total_orig += stats["original_children"]
        total_removed += stats["removed_children"]
        total_orphaned += stats["orphaned_parents"]
        for rule_name, count in stats["by_rule"].items():
            total_by_rule[rule_name] += count

        # 변경 없는 파일은 출력 생략
        if stats["removed_children"] > 0:
            print(f"  {action} {stats['filename'][:70]:70s}  "
                  f"{stats['original_children']} → {stats['remaining_children']} children "
                  f"(-{stats['removed_children']}, {stats['orphaned_parents']} parents pruned)")

    remaining = total_orig - total_removed
    print(f"\n합계: {total_orig:,} → {remaining:,} children "
          f"(-{total_removed:,}), orphaned parents: {total_orphaned:,}")
    rule_str = "  ".join(f"{k}={v}" for k, v in total_by_rule.items())
    print(f"규칙별: {rule_str}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-IFRS 저가치 BC 청크 제거")
    parser.add_argument("--single", help="단일 JSON 파일 경로")
    parser.add_argument("--chunks-dir", default="output/chunks")
    parser.add_argument("--out-dir", default=None,
                        help="출력 디렉토리 (미지정 시 in-place)")
    parser.add_argument("--dry-run", action="store_true",
                        help="파일 쓰기 없이 통계만 출력")
    args = parser.parse_args()

    if args.single:
        src = Path(args.single)
        dst = (Path(args.out_dir) / src.name) if args.out_dir else src
        stats = clean_json_file(src, dst, args.dry_run)
        action = "[dry-run]" if args.dry_run else "[clean]"
        print(f"{action} {stats['filename']}")
        print(f"  {stats['original_children']} → {stats['remaining_children']} children "
              f"(-{stats['removed_children']}, {stats['orphaned_parents']} parents pruned)")
        rule_str = "  ".join(f"{k}={v}" for k, v in stats['by_rule'].items())
        print(f"  규칙별: {rule_str}")
    else:
        clean_all(
            chunks_dir=args.chunks_dir,
            out_dir=args.out_dir,
            dry_run=args.dry_run,
        )
