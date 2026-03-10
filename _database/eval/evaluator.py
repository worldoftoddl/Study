"""K-IFRS RAG 파이프라인 평가 모듈.

검색 결과의 품질을 정량적으로 측정하는 평가 프레임워크.
how_to_read_IFRS.md에서 제안한 3가지 핵심 지표를 구현한다:

1. DRM (Document-Level Retrieval Mismatch): 잘못된 기준서에서 검색된 비율
2. Cross-reference Coverage: 참조 조문 포함률
3. Authority Accuracy: 권위수준 적합도

추가 지표:
4. Recall@K: 기대 청크 포함률
5. MRR: 첫 관련 청크의 역순위 평균

Usage:
    python -m eval.evaluator                    # 전체 테스트 실행
    python -m eval.evaluator --test tc01        # 특정 테스트만 실행
    python -m eval.evaluator --compare A B      # A/B 비교 (미구현)
"""

import json
import os
import sys
from dataclasses import dataclass, field

from langchain_core.documents import Document


@dataclass
class TestCase:
    id: str
    query: str
    query_type: str
    expected_standards: list[str]
    expected_chunks: list[str]
    expected_section_types: list[str]
    requires_cross_refs: list[str]
    answer_must_contain: list[str]


@dataclass
class EvalResult:
    test_id: str
    query: str
    drm: float  # Document-level Retrieval Mismatch (0=perfect, 1=all wrong)
    xref_coverage: float  # Cross-reference coverage (1=all refs found)
    authority_accuracy: float  # Authority-level accuracy (1=all correct type)
    recall_at_k: float  # Recall@K (1=all expected found)
    mrr: float  # Mean Reciprocal Rank
    retrieved_count: int
    details: dict = field(default_factory=dict)


def load_test_cases(path: str = "eval/test_cases.json") -> list[TestCase]:
    """테스트 케이스를 로드한다."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [TestCase(**tc) for tc in data["test_cases"]]


def evaluate_retrieval(
    test_case: TestCase,
    retrieved_docs: list[Document],
) -> EvalResult:
    """단일 테스트 케이스에 대한 검색 결과를 평가한다.

    Args:
        test_case: 평가 기준이 되는 테스트 케이스.
        retrieved_docs: 검색 파이프라인이 반환한 Document 리스트.

    Returns:
        EvalResult with all metrics computed.
    """
    if not retrieved_docs:
        return EvalResult(
            test_id=test_case.id,
            query=test_case.query,
            drm=1.0, xref_coverage=0.0, authority_accuracy=0.0,
            recall_at_k=0.0, mrr=0.0, retrieved_count=0,
        )

    # 검색 결과 메타데이터 추출
    retrieved_stds = [d.metadata.get("standard_id", "") for d in retrieved_docs]
    retrieved_chunks = [d.metadata.get("chunk_id", "") for d in retrieved_docs]
    retrieved_sections = [d.metadata.get("section_type", "") for d in retrieved_docs]
    retrieved_xrefs = set()
    for d in retrieved_docs:
        for ref in d.metadata.get("cross_refs", []):
            retrieved_xrefs.add(ref)
        # xref로 확장된 문서의 chunk_id에서 참조 추출
        cid = d.metadata.get("chunk_id", "")
        parts = cid.split("_")
        if len(parts) >= 3:
            retrieved_xrefs.add(parts[-1])  # 예: "AG12"

    # ── 1. DRM (Document-Level Retrieval Mismatch) ──
    if test_case.expected_standards:
        wrong_count = sum(
            1 for std in retrieved_stds
            if std and std not in test_case.expected_standards
        )
        drm = wrong_count / len(retrieved_docs) if retrieved_docs else 1.0
    else:
        drm = 0.0  # 기대 기준서 미지정 → skip

    # ── 2. Cross-reference Coverage ──
    if test_case.requires_cross_refs:
        found_refs = sum(
            1 for ref in test_case.requires_cross_refs
            if ref in retrieved_xrefs
        )
        xref_coverage = found_refs / len(test_case.requires_cross_refs)
    else:
        xref_coverage = 1.0  # 교차참조 불필요 → 만점

    # ── 3. Authority Accuracy ──
    if test_case.expected_section_types:
        correct_authority = sum(
            1 for st in retrieved_sections
            if st in test_case.expected_section_types
        )
        authority_accuracy = correct_authority / len(retrieved_docs)
    else:
        authority_accuracy = 1.0

    # ── 4. Recall@K ──
    if test_case.expected_chunks:
        found_chunks = sum(
            1 for eid in test_case.expected_chunks
            if eid in retrieved_chunks
        )
        recall_at_k = found_chunks / len(test_case.expected_chunks)
    else:
        recall_at_k = -1.0  # 기대 청크 미지정 → N/A

    # ── 5. MRR (Mean Reciprocal Rank) ──
    if test_case.expected_chunks:
        mrr = 0.0
        for eid in test_case.expected_chunks:
            if eid in retrieved_chunks:
                rank = retrieved_chunks.index(eid) + 1
                mrr = max(mrr, 1.0 / rank)
    else:
        # 기대 청크 대신 기대 기준서로 MRR 계산
        mrr = 0.0
        if test_case.expected_standards:
            for i, std in enumerate(retrieved_stds):
                if std in test_case.expected_standards:
                    mrr = 1.0 / (i + 1)
                    break

    details = {
        "retrieved_standards": retrieved_stds,
        "retrieved_chunks": retrieved_chunks[:10],
        "retrieved_sections": retrieved_sections,
        "found_xrefs": list(retrieved_xrefs)[:20],
    }

    return EvalResult(
        test_id=test_case.id,
        query=test_case.query,
        drm=round(drm, 4),
        xref_coverage=round(xref_coverage, 4),
        authority_accuracy=round(authority_accuracy, 4),
        recall_at_k=round(recall_at_k, 4) if recall_at_k >= 0 else -1.0,
        mrr=round(mrr, 4),
        retrieved_count=len(retrieved_docs),
        details=details,
    )


def print_eval_summary(results: list[EvalResult]) -> None:
    """평가 결과 요약을 출력한다."""
    print(f"\n{'='*80}")
    print(f"{'K-IFRS RAG 평가 결과':^80}")
    print(f"{'='*80}")
    print(f"\n{'Test ID':<25} {'DRM↓':>6} {'XRef↑':>6} {'Auth↑':>6} {'R@K':>6} {'MRR↑':>6} {'#Docs':>6}")
    print(f"{'-'*25} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")

    for r in results:
        recall_str = f"{r.recall_at_k:.2f}" if r.recall_at_k >= 0 else "N/A"
        print(
            f"{r.test_id:<25} "
            f"{r.drm:>6.2f} "
            f"{r.xref_coverage:>6.2f} "
            f"{r.authority_accuracy:>6.2f} "
            f"{recall_str:>6} "
            f"{r.mrr:>6.2f} "
            f"{r.retrieved_count:>6}"
        )

    # 집계
    valid_results = [r for r in results if r.retrieved_count > 0]
    if valid_results:
        avg_drm = sum(r.drm for r in valid_results) / len(valid_results)
        avg_xref = sum(r.xref_coverage for r in valid_results) / len(valid_results)
        avg_auth = sum(r.authority_accuracy for r in valid_results) / len(valid_results)
        recall_results = [r for r in valid_results if r.recall_at_k >= 0]
        avg_recall = sum(r.recall_at_k for r in recall_results) / len(recall_results) if recall_results else -1.0
        avg_mrr = sum(r.mrr for r in valid_results) / len(valid_results)

        recall_str = f"{avg_recall:.2f}" if avg_recall >= 0 else "N/A"
        print(f"{'-'*25} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
        print(
            f"{'AVERAGE':<25} "
            f"{avg_drm:>6.2f} "
            f"{avg_xref:>6.2f} "
            f"{avg_auth:>6.2f} "
            f"{recall_str:>6} "
            f"{avg_mrr:>6.2f} "
        )

    print(f"\n지표 설명:")
    print(f"  DRM↓  = Document-level Retrieval Mismatch (0=완벽, 낮을수록 좋음)")
    print(f"  XRef↑ = Cross-reference Coverage (1=모든 참조 포함)")
    print(f"  Auth↑ = Authority-level Accuracy (1=모든 문서가 올바른 section_type)")
    print(f"  R@K   = Recall@K (1=모든 기대 청크 포함, N/A=기대 청크 미지정)")
    print(f"  MRR↑  = Mean Reciprocal Rank (1=첫 번째에 관련 문서)")
    print()


if __name__ == "__main__":
    # 기본 실행: 테스트 케이스 로드 및 형식 검증만 수행
    test_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--test" and i + 1 < len(sys.argv):
            test_filter = sys.argv[i + 1]

    cases = load_test_cases()
    if test_filter:
        cases = [tc for tc in cases if tc.id == test_filter]

    print(f"로드된 테스트 케이스: {len(cases)}개")
    for tc in cases:
        print(f"  [{tc.id}] {tc.query_type}: {tc.query[:50]}...")

    print(f"\n평가를 실행하려면 검색 파이프라인과 함께 evaluate_retrieval()을 호출하세요.")
    print(f"예시:")
    print(f"  from eval.evaluator import load_test_cases, evaluate_retrieval, print_eval_summary")
    print(f"  cases = load_test_cases()")
    print(f"  results = [evaluate_retrieval(tc, pipeline.search(tc.query)) for tc in cases]")
    print(f"  print_eval_summary(results)")
