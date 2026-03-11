# K-IFRS RAG 파이프라인 — 현재 상태 및 다음 단계

## 완료된 작업

### 1. 교차참조 추출 파이프라인 전면 수정
- `pipeline/kifrs_chunker.py`: broken 패턴 2개 교체 + 8개 신규 패턴 추가
- `search/xref_resolver.py`: 새 참조 형식에 맞게 파싱 패턴 동기화
- `search/embedder.py`, `search/retriever.py`: `referenced_standards` 필드 관통 전달
- 청크 JSON 63개 전체 패치 완료

### 2. Qdrant payload 적재 완료
- `search/embedder.py`에 `update_payloads()` 함수 추가 (`--update-payload` CLI)
- 벡터 변경 없이 `cross_refs`, `referenced_standards` 메타데이터만 갱신
- 적재 결과:

| 지표 | 수치 |
|------|------|
| 총 Qdrant child 포인트 | 12,313 |
| cross_refs 있는 포인트 | 5,743 (46.6%) |
| referenced_standards 있는 포인트 | 2,799 (22.7%) |
| 기준서 간 고유 그래프 엣지 | 924 |

---

## 다음 작업: 메타데이터 기반 검색 고도화

Qdrant에 `cross_refs`와 `referenced_standards`가 적재되었으므로, 이 메타데이터를 **검색 단계에서 직접 활용**하는 새로운 검색 방법을 작성해야 한다.

### 현재 검색 흐름 (search/ 모듈 구조)
```
query
  → query_router.classify_query()         # 5-way 분류 → QueryPlan (규칙 기반)
  → retriever.QdrantDenseRetriever        # 벡터 검색 (Qdrant cosine)
  + retriever.load_child_documents → BM25  # 키워드 검색 (rank_bm25 + kiwipiepy)
  → reranker.get_reranker().rerank()      # cross-encoder rerank (BGE/Cohere)
  → query_router.apply_authority_boost()  # bc/ie 점수 감쇠
  → xref_resolver.resolve_cross_refs()   # cross_refs → 문단 수준 참조 청크 fetch (post-retrieval)
  → terms_resolver.inject_term_definitions()  # 용어정의 주입
  → LLM 응답
```

### 개선 방향

1. **`referenced_standards` 기반 관련 기준서 확장 검색**
   - 검색된 청크의 `referenced_standards`를 보고, 관련 기준서의 핵심 청크(Scope, 정의)를 자동 fetch
   - 예: IFRS 15 문단에서 `referenced_standards: ["1109"]`면 → IFRS 9의 금융상품 정의 청크를 함께 가져옴
   - 현재 xref_resolver는 `cross_refs`의 문단 수준 참조만 해소. `referenced_standards`는 미활용

2. **Qdrant 필터 기반 역방향 검색**
   - `referenced_standards` 필드로 Qdrant 필터링: "특정 기준서를 참조하는 모든 청크" 검색
   - 예: `FieldCondition(key="referenced_standards", match=MatchAny(any=["1109"]))`
   - comparative 쿼리("IFRS 16과 IFRS 15의 관계")에서 두 기준서 교차점 탐색

3. **Graph 기반 multi-hop 검색**
   - `referenced_standards` 924개 엣지로 기준서 간 관계 그래프 구축 (NetworkX)
   - 1-hop: 직접 참조, 2-hop: 간접 참조 기준서까지 확장
   - 예: "리스 회계처리" → IFRS 16 → IFRS 15, IAS 36, IFRS 9 → 관련 문단

4. **query_router 개선**
   - 현재 규칙 기반 5-way 분류에 `referenced_standards` 활용 로직 추가
   - inter-standard 쿼리 감지 시 graph expansion 자동 활성화

---

## 핵심 파일 위치

### search/ — 검색 엔진 모듈
- `search/__init__.py` — 패키지 exports (모든 공개 인터페이스)
- `search/config.py` — 경로, 컬렉션명, `chunk_id_to_int()`
- `search/retriever.py` — `QdrantDenseRetriever`, `load_child_documents`, `search_with_parent`, `get_authority_filter`
- `search/reranker.py` — `LocalReranker`(BGE), `CohereReranker`, `get_reranker()`
- `search/query_router.py` — `classify_query()` → `QueryPlan`, `apply_authority_boost()`
- `search/xref_resolver.py` — `resolve_cross_refs()` (cross_refs → chunk_id → Qdrant fetch)
- `search/terms_resolver.py` — `inject_term_definitions()` (기준서별 용어정의 주입)
- `search/embedder.py` — Qdrant 적재 + `update_payloads()`

### pipeline/ — 문서 처리
- `pipeline/kifrs_chunker.py` — 청킹 + 교차참조 추출 (`extract_cross_refs`, `extract_referenced_standards`)

### 데이터
- `output/chunks/*.json` — 패치된 청크 데이터 (63개 기준서)
- `output/terms_index.json` — 기준서별 용어정의 청크 매핑
- `qdrant_storage/` — Qdrant 로컬 벡터DB

### 평가 / 문서
- `eval/evaluator.py` — RAG 평가기 (DRM, xref coverage, authority accuracy)
- `eval/test_cases.json` — 평가 테스트 케이스
- `docs/cross_refs.md` — 교차참조 파이프라인 상세 문서
- `docs/search.md` — 검색 파이프라인 아키텍처 문서
- `how_to_read_IFRS.md` — IFRS 해독법 + RAG 설계 전략 레퍼런스

## Qdrant payload 스키마 (child 컬렉션: kifrs_chunks)
```json
{
  "chunk_id": "KIFRS1016_main_62",
  "parent_id": "KIFRS1016_main_sec_후속측정",
  "content": "문단 본문 텍스트...",
  "standard_id": "K-IFRS 1016",
  "section_type": "main | ag | bc | ie",
  "para_number": "62",
  "cross_refs": ["문단31~40", "제1036호", "AG12~AG15"],
  "referenced_standards": ["1036", "1038"],
  "has_table": false,
  "has_example": false
}
```

## 환경
- Python 3.12.3, `.venv` 가상환경 (`python3`만 사용, `python` 없음)
- Qdrant 로컬 파일 모드 (`./qdrant_storage`)
- 임베딩: Upstage Solar (`solar-embedding-1-large`, 4096차원)
- Reranker: `dragonkue/bge-reranker-v2-m3-ko` (로컬) 또는 Cohere API
- WSL2 (Linux 6.6)
