# 저가치 BC 청크 정리 스크립트

## Context
K-IFRS RAG 파이프라인의 청크 데이터(15,838개) 중 BC(결론도출근거)가 8,976개(56.7%)를 차지한다. 대부분의 BC는 기준서 해석에 유용하지만, 약 250개는 행정 안내·면책문구·대응표·소수의견·제개정 경과 등 RAG 검색 가치가 없는 보일러플레이트다. 이를 정리하여 벡터DB 품질을 높인다.

## 신규 파일
`pipeline/bc_chunk_cleaner.py` — 청크 JSON 후처리 스크립트

## 제거 대상 (6가지 규칙)

| 규칙 | 판별 로직 | 예상 |
|------|----------|------|
| `unk_5k_bc` | `_bc_` + `_unk_` in chunk_id, len(content) >= 5000 | ~8 |
| `meta_disclaimer` | content에 "이 결론도출근거는" + "기준서의 일부를 구성하는 것은 아니다" | ~16 |
| `admin_intro` | content에 "한국회계기준원은 한국채택국제회계기준 제정시 기준서를 제정한 과정" | ~49 |
| `amendment` | parent_id에 "제_개정_경과" | ~62 |
| `dissenting` | parent_id에 "소수의견" | ~45 |
| `ias_relation` | parent_id에 "국제회계기준과의_관계" | ~73 |

총 ~247개 (중복 제거 후), 전체의 1.6%

## 구현 구조

```python
# pipeline/bc_chunk_cleaner.py
# CLI: --dry-run, --single FILE.json, --out-dir DIR

REMOVAL_RULES = [
    ("unk_5k_bc",       is_unk_5k_bc),
    ("meta_disclaimer", is_meta_disclaimer),
    ("admin_intro",     is_admin_intro),
    ("amendment",       is_amendment_history),
    ("dissenting",      is_dissenting_opinion),
    ("ias_relation",    is_ias_relation),
]

def classify_chunk(chunk) -> list[str]   # 매칭되는 규칙 이름 반환
def clean_json_file(path, out_path, dry_run) -> stats_dict
def prune_orphaned_parents(parents, children) -> (pruned, count)
def clean_all(chunks_dir, out_dir, dry_run) -> None
```

## 핵심 단계

1. 6개 boolean 규칙 함수 구현
2. `classify_chunk` — 각 child에 규칙 적용, 매칭 시 제거 대상
3. `prune_orphaned_parents` — 자식이 없어진 parent 제거
4. `clean_json_file` — JSON 읽기 → 필터링 → 쓰기
5. CLI (argparse) — md_cleaner.py 패턴 따름
6. 요약 리포트 출력

## 참조 파일
- `pipeline/md_cleaner.py` — CLI 패턴, argparse 구조 참고
- `pipeline/kifrs_chunker.py` — JSON 출력 형식, 청크 구조 참고
- `output/chunks/*.json` — 대상 63개 파일
- `eval/test_cases.json` — tc06 (interpretive BC 쿼리) 검증 필요

## 검증
1. `--dry-run`으로 제거 대상 확인 (예상 ~247개)
2. 실행 후 총 children 수: 15,838 → ~15,591
3. 문단번호 있는 실질적 BC(BC1, BC28A 등)가 제거되지 않았는지 확인
4. tc06 테스트 케이스 ("왜 IFRS는 공정가치 측정을 요구하는가?") 정상 동작 확인
