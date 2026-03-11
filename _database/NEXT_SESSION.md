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

### 3. 메타데이터 기반 검색 고도화

4가지 Enhancement 모두 구현 완료:

#### 3-1. `referenced_standards` 기반 순방향 확장 검색
- `search/standards_expander.py`: `expand_referenced_standards()`
- 검색 결과의 referenced_standards에서 고유 기준서 번호 수집 → 빈도순 → 용어정의 청크 자동 fetch
- metadata `fetched_by_std_ref=True`로 태깅

#### 3-2. Qdrant 필터 기반 역방향 검색
- `search/standards_expander.py`: `reverse_lookup_chunks()`
- `FieldCondition(key="referenced_standards", match=MatchAny(any=[...]))` 필터
- query_vector 제공 시 벡터 유사도 정렬, 없으면 scroll
- metadata `fetched_by_reverse_lookup=True`로 태깅

#### 3-3. Graph 기반 multi-hop 검색
- `search/standards_graph.py`: NetworkX DiGraph 싱글턴 (81 노드, 906 엣지)
- `get_neighbors(std, hops=N)`: 1-hop 직접 참조, 2-hop 간접 참조 (가중치 감쇠 x0.3)
- `search/standards_expander.py`: `graph_expand()` — 그래프 탐색 → 용어정의 fetch
- metadata `fetched_by_graph=True`, `graph_hop=N`으로 태깅

#### 3-4. query_router 개선
- `search/query_router.py`: `_detect_standards()` 헬퍼 추가
- 패턴: "제1109호", "K-IFRS 1109", "IFRS 9", "IAS 16" 등 감지
- `QueryPlan`에 `expand_standards: bool`, `detected_standards: list[str]` 필드 추가
- COMPARATIVE는 항상 expand, NORMATIVE/INTERPRETIVE/EXAMPLE은 기준서 감지 시 expand

### 4. terms_index 커버리지 확장 (21 → 40 기준서)
- `pipeline/terms_index.py`: 2-pass 탐지 로직으로 전면 개편
  - Pass 1: `parent_id` 기반 구조적 탐지 (`_PARENT_TERM_RE`) — 39개 매칭
  - Pass 2: `content` 기반 fallback (`_TERM_INTRO_RE` 확장) — 1개 추가 (해석서 2123)
- 누락 원인별 대응:
  - 부록 형식 15개 (1102~1117): `parent_id`에 `부록_용어의_정의` 포함 → Pass 1로 해결
  - 피동태 1개 (1020): `사용되는` → Pass 1 parent_id로 해결
  - AG 섹션 1개 (1032): `ag_h_용어의_정의_문단` → Pass 1로 해결
  - 개념체계 1개: `KIFRS_CF_main_h_용어의_정의` → Pass 1로 해결
  - 해석서 1개 (2123): content fallback으로 해결
- 1039 제외: 자체 정의 없이 1032/1109/1113 참조만 (`_XREF_ONLY_RE` 필터)
- 기존 21개 chunk_id 모두 불변 확인 완료
- `search/terms_resolver.py`, `search/standards_expander.py` 변경 불필요 (스키마 동일)

### 5. 파이프라인 오케스트레이션 통합 (노트북)
- `rag_pipeline_test.ipynb`의 `run_pipeline()` 함수에 `enable_expansion` 파라미터 추가
- Stage 7로 Standards Expansion 통합:
  - 7a: 순방향 — `expand_referenced_standards()` (참조 기준서 용어정의 fetch, max 5)
  - 7b: 역방향 — `reverse_lookup_chunks()` (나를 참조하는 청크, query_vector 기반 정렬, max 5)
  - 7c: 그래프 — `graph_expand()` (1-hop 확장, max 3)
- `plan.expand_standards` 플래그에 따라 자동 활성화/비활성화
- import에 `expand_referenced_standards, reverse_lookup_chunks, graph_expand` 추가

### 6. Qdrant payload 인덱스 CLI 추가
- `search/embedder.py`에 `create_payload_indexes()` 함수 추가
- `--create-index` CLI 옵션으로 실행 가능
- `referenced_standards` 필드에 keyword 인덱스 생성 (역방향 검색 성능 최적화)
- **상태**: 코드 작성 완료, 아직 실행하지 않음 (uncommitted)

### 7. A/B 평가 프레임워크 작성
- `rag_pipeline_test.ipynb`에 Section 11 추가: Baseline vs Standards Expansion A/B 비교
- `run_eval_suite()` 헬퍼: 22개 테스트 케이스 일괄 실행 (enable_expansion 토글)
- Per-case 비교 테이블 (DRM, Auth, MRR, #docs) + Summary 출력
- **상태**: 코드 작성 완료, 아직 실행하지 않음 (uncommitted)

---

## 다음 작업

### 1. Qdrant payload 인덱스 실행
- `python3 -m search.embedder --create-index` 실행하여 `referenced_standards` keyword 인덱스 생성
- 역방향 검색(`reverse_lookup_chunks`) 성능 최적화

### 2. A/B 평가 벤치마크 실행
- `rag_pipeline_test.ipynb` Section 11 셀 실행
- Baseline vs Expansion 성능 비교 결과 확인
- DRM/XRef Coverage/Auth Accuracy/MRR 지표 분석

### 3. 파이프라인 오케스트레이션 모듈화
- 현재 노트북 `run_pipeline()` 안에 expansion 로직이 인라인으로 작성됨
- `search/` 패키지 내 독립 함수 (`search_with_expansion()` 등)로 추출 검토
- 에이전트(LangGraph)에서 직접 호출 가능한 형태로 정리

---

## 핵심 파일 위치

### search/ — 검색 엔진 모듈
- `search/__init__.py` — 패키지 exports (모든 공개 인터페이스)
- `search/config.py` — 경로, 컬렉션명, `chunk_id_to_int()`
- `search/retriever.py` — `QdrantDenseRetriever`, `load_child_documents`, `search_with_parent`, `get_authority_filter`
- `search/reranker.py` — `LocalReranker`(BGE), `CohereReranker`, `get_reranker()`
- `search/query_router.py` — `classify_query()` → `QueryPlan`, `apply_authority_boost()`, `_detect_standards()`
- `search/xref_resolver.py` — `resolve_cross_refs()` (cross_refs → chunk_id → Qdrant fetch)
- `search/terms_resolver.py` — `inject_term_definitions()` (기준서별 용어정의 주입)
- `search/standards_graph.py` — **NEW** NetworkX 기준서 참조 그래프 (81노드, 906엣지)
- `search/standards_expander.py` — **NEW** 순방향/역방향/그래프 확장 검색
- `search/embedder.py` — Qdrant 적재 + `update_payloads()` + `create_payload_indexes()`

### pipeline/ — 문서 처리
- `pipeline/kifrs_chunker.py` — 청킹 + 교차참조 추출 (`extract_cross_refs`, `extract_referenced_standards`)
- `pipeline/terms_index.py` — 용어정의 인덱스 빌더 (2-pass: parent_id 구조 탐지 + content fallback)

### 데이터
- `output/chunks/*.json` — 패치된 청크 데이터 (63개 기준서)
- `output/terms_index.json` — 기준서별 용어정의 청크 매핑 (40개 기준서)
- `qdrant_storage/` — Qdrant 로컬 벡터DB

### 평가 / 문서
- `eval/evaluator.py` — RAG 평가기 (DRM, xref coverage, authority accuracy)
- `eval/test_cases.json` — 평가 테스트 케이스 (22개)
- `docs/cross_refs.md` — 교차참조 파이프라인 상세 문서
- `docs/search.md` — 검색 파이프라인 아키텍처 문서
- `how_to_read_IFRS.md` — IFRS 해독법 + RAG 설계 전략 레퍼런스

## 검색 파이프라인 전체 흐름

```
query
  → query_router.classify_query()         # 5-way 분류 + 기준서 감지 → QueryPlan
  → retriever.QdrantDenseRetriever        # 벡터 검색 (Qdrant cosine)
  + retriever.load_child_documents → BM25  # 키워드 검색 (rank_bm25 + kiwipiepy)
  → reranker.get_reranker().rerank()      # cross-encoder rerank (BGE/Cohere)
  → query_router.apply_authority_boost()  # bc/ie 점수 감쇠
  → xref_resolver.resolve_cross_refs()   # cross_refs → 문단 수준 참조 청크 fetch
  → terms_resolver.inject_term_definitions()  # 용어정의 주입
  → [if plan.expand_standards]
      → standards_expander.expand_referenced_standards()  # 참조 기준서 용어정의 fetch
      → standards_expander.reverse_lookup_chunks()        # 역방향 검색
      → standards_expander.graph_expand()                 # 그래프 1-hop 확장
  → LLM 응답
```

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
