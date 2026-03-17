"""KURE-v1 토큰 수 검증 — output/chunks_v2 children 전체 대상."""

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from transformers import AutoTokenizer


def load_children(chunks_dir: Path) -> list[dict]:
    """chunks_dir/*.json에서 모든 children을 로드한다."""
    children = []
    for fp in sorted(chunks_dir.glob("*.json")):
        data = json.loads(fp.read_text(encoding="utf-8"))
        for child in data.get("children", []):
            child["_file"] = fp.name
            children.append(child)
    return children


def main():
    parser = argparse.ArgumentParser(description="KURE-v1 토큰 수 검증")
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("output/chunks_v2"),
        help="청크 JSON 디렉토리 (default: output/chunks_v2)",
    )
    parser.add_argument(
        "--model",
        default="nlpai-lab/KURE-v1",
        help="토크나이저 모델 (default: nlpai-lab/KURE-v1)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8192,
        help="토큰 상한 (default: 8192)",
    )
    args = parser.parse_args()

    # 1. 토크나이저 로드
    print(f"Loading tokenizer: {args.model} ...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    print(f"  vocab_size={tokenizer.vocab_size}, model_max_length={tokenizer.model_max_length}")

    # 2. 청크 로드
    children = load_children(args.chunks_dir)
    print(f"Loaded {len(children):,} children from {args.chunks_dir}\n")
    if not children:
        print("No children found. Exiting.")
        return

    # 3. 토큰화 (배치)
    texts = [c["content"] for c in children]
    char_lens = [len(t) for t in texts]

    print("Tokenizing (truncation=False) ...")
    encoded = tokenizer(texts, truncation=False, add_special_tokens=True)
    token_lens = [len(ids) for ids in encoded["input_ids"]]

    # 4. 기본 통계
    print("\n=== Token Length Statistics ===")
    print(f"  Total chunks : {len(token_lens):,}")
    print(f"  Min          : {min(token_lens):,}")
    print(f"  Max          : {max(token_lens):,}")
    print(f"  Mean         : {statistics.mean(token_lens):,.1f}")
    print(f"  Median       : {statistics.median(token_lens):,.1f}")
    sorted_lens = sorted(token_lens)
    p95_idx = int(len(sorted_lens) * 0.95)
    p99_idx = int(len(sorted_lens) * 0.99)
    print(f"  P95          : {sorted_lens[p95_idx]:,}")
    print(f"  P99          : {sorted_lens[p99_idx]:,}")

    # 5. 초과 청크
    over = [(children[i], token_lens[i], char_lens[i])
            for i in range(len(children)) if token_lens[i] > args.limit]
    print(f"\n=== Over {args.limit} tokens: {len(over)} chunks ===")
    for child, tlen, clen in over:
        print(f"  {child['chunk_id']}  tokens={tlen:,}  chars={clen:,}  file={child['_file']}")

    # 6. 구간별 분포
    bins = [(0, 100), (100, 500), (500, 1000), (1000, 2000),
            (2000, 4000), (4000, 8000), (8000, float("inf"))]
    bin_labels = ["0-100", "100-500", "500-1K", "1K-2K", "2K-4K", "4K-8K", "8K+"]
    bin_counts = [0] * len(bins)
    for tl in token_lens:
        for j, (lo, hi) in enumerate(bins):
            if lo <= tl < hi:
                bin_counts[j] += 1
                break

    print("\n=== Token Distribution ===")
    for label, cnt in zip(bin_labels, bin_counts):
        pct = cnt / len(token_lens) * 100
        bar = "#" * int(pct / 2)
        print(f"  {label:>7s}: {cnt:>6,} ({pct:5.1f}%) {bar}")

    # 7. section_type별 평균
    by_section: dict[str, list[int]] = defaultdict(list)
    for i, child in enumerate(children):
        st = child.get("metadata", {}).get("section_type", "unknown")
        by_section[st].append(token_lens[i])

    print("\n=== Avg Tokens by section_type ===")
    for st in sorted(by_section, key=lambda k: -statistics.mean(by_section[k])):
        vals = by_section[st]
        print(f"  {st:>20s}: mean={statistics.mean(vals):,.1f}  max={max(vals):,}  n={len(vals):,}")

    # 8. has_table 비교
    table_lens = [token_lens[i] for i, c in enumerate(children)
                  if c.get("metadata", {}).get("has_table")]
    no_table_lens = [token_lens[i] for i, c in enumerate(children)
                     if not c.get("metadata", {}).get("has_table")]
    print("\n=== has_table Token Comparison ===")
    if table_lens:
        print(f"  has_table=True : mean={statistics.mean(table_lens):,.1f}  max={max(table_lens):,}  n={len(table_lens):,}")
    if no_table_lens:
        print(f"  has_table=False: mean={statistics.mean(no_table_lens):,.1f}  max={max(no_table_lens):,}  n={len(no_table_lens):,}")

    # 9. chars/token 비율
    ratios = [char_lens[i] / token_lens[i] for i in range(len(children)) if token_lens[i] > 0]
    print("\n=== Chars/Token Ratio ===")
    print(f"  Mean   : {statistics.mean(ratios):.3f}")
    print(f"  Median : {statistics.median(ratios):.3f}")
    print(f"  Min    : {min(ratios):.3f}")
    print(f"  Max    : {max(ratios):.3f}")
    implied_max_chars = int(args.limit * statistics.mean(ratios))
    print(f"  → Implied safe max_chars at {args.limit} tokens: ~{implied_max_chars:,}")

    # 10. 최종 판정
    print("\n" + "=" * 50)
    if not over:
        print(f"PASS: 모든 {len(children):,} 청크가 {args.limit} 토큰 이내")
        print("→ target_max_chars=5,000 유지")
    else:
        print(f"FAIL: {len(over)} 청크가 {args.limit} 토큰 초과")
        print("→ target_max_chars 하향 조정 필요")


if __name__ == "__main__":
    main()
