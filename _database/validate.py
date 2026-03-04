"""
K-IFRS 파이프라인 검증 모듈

5가지 검증 체크를 수행하고 리포트를 생성한다.
1. 섹션 분리 정확도
2. 문단 번호 추출률
3. 상호참조 추출
4. 청크 크기 분포
5. Parent-Child 연결 무결성
"""

import json
import logging
import argparse
import statistics
from pathlib import Path
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# Check 1: 섹션 분리 정확도
# ============================================================

def check_section_separation(data: dict) -> dict:
    """MAIN/AG/BC/IE 섹션이 올바르게 분리됐는지 확인한다."""
    sections_found = set()
    for child in data["children"]:
        sections_found.add(child["metadata"]["section_type"])

    result = {
        "standard_id": data["standard_id"],
        "sections_found": sorted(sections_found),
        "has_main": "main" in sections_found,
        "has_ag": "ag" in sections_found,
        "has_bc": "bc" in sections_found,
        "has_ie": "ie" in sections_found,
        "section_count": len(sections_found),
    }

    if not result["has_main"]:
        result["warning"] = "MAIN 섹션 누락!"

    return result


# ============================================================
# Check 2: 문단 번호 추출률
# ============================================================

def check_para_number_coverage(data: dict) -> dict:
    """para_number 필드가 누락된 child 청크 비율을 확인한다."""
    total = len(data["children"])
    if total == 0:
        return {"standard_id": data["standard_id"], "error": "no_children"}

    with_para = sum(
        1 for c in data["children"]
        if c["metadata"].get("para_number")
    )
    missing_rate = (total - with_para) / total

    return {
        "standard_id": data["standard_id"],
        "total_children": total,
        "with_para_number": with_para,
        "missing_para_number": total - with_para,
        "missing_rate": round(missing_rate, 4),
        "ok": missing_rate < 0.05,
    }


# ============================================================
# Check 3: 상호참조 추출
# ============================================================

def check_cross_references(data: dict) -> dict:
    """cross_refs 필드가 빈 배열인 비율을 확인한다."""
    total = len(data["children"])
    if total == 0:
        return {"standard_id": data["standard_id"], "error": "no_children"}

    with_refs = sum(
        1 for c in data["children"]
        if c["metadata"].get("cross_refs")
    )
    empty_rate = (total - with_refs) / total

    all_refs = set()
    for c in data["children"]:
        for ref in c["metadata"].get("cross_refs", []):
            all_refs.add(ref)

    return {
        "standard_id": data["standard_id"],
        "total_children": total,
        "with_cross_refs": with_refs,
        "empty_cross_refs_rate": round(empty_rate, 4),
        "unique_cross_refs": len(all_refs),
        "sample_refs": sorted(all_refs)[:10],
    }


# ============================================================
# Check 4: 청크 크기 분포
# ============================================================

def check_chunk_sizes(data: dict) -> dict:
    """child 청크 길이의 min/max/평균을 출력하고 이상치를 플래그한다."""
    sizes = [len(c["content"]) for c in data["children"]]

    if not sizes:
        return {"standard_id": data["standard_id"], "error": "no_children"}

    result = {
        "standard_id": data["standard_id"],
        "count": len(sizes),
        "min": min(sizes),
        "max": max(sizes),
        "mean": round(statistics.mean(sizes), 1),
        "median": round(statistics.median(sizes), 1),
        "stdev": round(statistics.stdev(sizes), 1) if len(sizes) > 1 else 0,
    }

    oversized = [c["chunk_id"] for c in data["children"] if len(c["content"]) > 2000]
    tiny = [c["chunk_id"] for c in data["children"] if len(c["content"]) < 10]

    result["oversized_chunks"] = oversized[:5]
    result["oversized_count"] = len(oversized)
    result["tiny_chunks"] = tiny[:5]
    result["tiny_count"] = len(tiny)

    return result


# ============================================================
# Check 5: Parent-Child 연결 무결성
# ============================================================

def check_parent_child_links(data: dict) -> dict:
    """모든 child의 parent_id가 실제 parent와 매칭되는지 확인한다."""
    parent_ids = {p["parent_id"] for p in data["parents"]}
    child_parent_refs = {c["parent_id"] for c in data["children"]}

    # 고아 참조 (존재하지 않는 parent를 참조하는 child)
    orphan_refs = child_parent_refs - parent_ids

    # 자식 없는 parent
    children_by_parent = Counter(c["parent_id"] for c in data["children"])
    empty_parents = [
        p["parent_id"] for p in data["parents"]
        if children_by_parent.get(p["parent_id"], 0) == 0
    ]

    # parent.children 리스트와 실제 child 매칭 확인
    mismatches = []
    for parent in data["parents"]:
        declared = set(parent["children"])
        actual = {
            c["chunk_id"] for c in data["children"]
            if c["parent_id"] == parent["parent_id"]
        }
        if declared != actual:
            mismatches.append({
                "parent_id": parent["parent_id"],
                "declared": len(declared),
                "actual": len(actual),
            })

    return {
        "standard_id": data["standard_id"],
        "total_parents": len(data["parents"]),
        "total_children": len(data["children"]),
        "orphan_child_refs": list(orphan_refs),
        "empty_parents": empty_parents[:5],
        "empty_parent_count": len(empty_parents),
        "children_list_mismatches": mismatches[:5],
        "ok": len(orphan_refs) == 0 and len(mismatches) == 0,
    }


# ============================================================
# 전체 검증 실행
# ============================================================

def validate_all(chunks_dir: str = "output/chunks") -> None:
    """모든 JSON 출력에 대해 5가지 검증 체크를 실행하고 리포트를 생성한다."""
    chunks_path = Path(chunks_dir)

    if not chunks_path.exists():
        logger.error(f"청크 디렉토리를 찾을 수 없음: {chunks_path}")
        return

    json_files = sorted(chunks_path.glob("*.json"))
    logger.info(f"{len(json_files)}개 JSON 파일 검증 시작: {chunks_path}")

    all_results = []

    for json_file in json_files:
        data = json.loads(json_file.read_text(encoding="utf-8"))

        result = {
            "standard_id": data["standard_id"],
            "sections": check_section_separation(data),
            "para_coverage": check_para_number_coverage(data),
            "cross_refs": check_cross_references(data),
            "chunk_sizes": check_chunk_sizes(data),
            "parent_child": check_parent_child_links(data),
        }
        all_results.append(result)

    # 요약 테이블 출력
    print("\n" + "=" * 85)
    print("검증 요약 (VALIDATION SUMMARY)")
    print("=" * 85)
    print(
        f"{'Standard':<16} {'Sections':<14} {'ParaCov':<10} "
        f"{'XRef%':<10} {'AvgSize':<10} {'P-C':<8}"
    )
    print("-" * 85)

    for r in all_results:
        sid = r["standard_id"]
        sects = ",".join(r["sections"]["sections_found"])
        para_ok = "OK" if r["para_coverage"].get("ok", False) else "WARN"
        xref_rate = f"{(1 - r['cross_refs'].get('empty_cross_refs_rate', 1))*100:.0f}%"
        avg_size = f"{r['chunk_sizes'].get('mean', 0):.0f}"
        pc_ok = "OK" if r["parent_child"].get("ok", False) else "FAIL"

        print(f"{sid:<16} {sects:<14} {para_ok:<10} {xref_rate:<10} {avg_size:<10} {pc_ok:<8}")

    # 전체 통계
    total_children = sum(r["chunk_sizes"].get("count", 0) for r in all_results)
    all_means = [
        r["chunk_sizes"]["mean"]
        for r in all_results
        if "mean" in r["chunk_sizes"]
    ]

    print("-" * 85)
    print(f"총 파일: {len(all_results)}")
    print(f"총 Children: {total_children}")
    if all_means:
        print(f"전체 평균 청크 크기: {statistics.mean(all_means):.0f}자")

    # 문제 있는 항목 하이라이트
    warnings = []
    for r in all_results:
        sid = r["standard_id"]
        if not r["sections"]["has_main"]:
            warnings.append(f"  {sid}: MAIN 섹션 누락")
        if not r["para_coverage"].get("ok", True):
            rate = r["para_coverage"].get("missing_rate", 0)
            warnings.append(f"  {sid}: 문단번호 누락률 {rate*100:.1f}%")
        if not r["parent_child"].get("ok", True):
            orphans = len(r["parent_child"].get("orphan_child_refs", []))
            warnings.append(f"  {sid}: P-C 연결 오류 (고아 참조 {orphans}건)")
        if r["chunk_sizes"].get("oversized_count", 0) > 0:
            cnt = r["chunk_sizes"]["oversized_count"]
            warnings.append(f"  {sid}: 2000자 초과 청크 {cnt}개")

    if warnings:
        print(f"\n경고 ({len(warnings)}건):")
        for w in warnings:
            print(w)
    else:
        print("\n모든 검증 통과!")

    # 상세 리포트 JSON 저장
    report_path = chunks_path.parent / "validation_report.json"
    report_path.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n상세 리포트 저장: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="K-IFRS 파이프라인 출력 검증")
    parser.add_argument("--dir", default="output/chunks", help="청크 JSON 디렉토리")
    args = parser.parse_args()
    validate_all(args.dir)
