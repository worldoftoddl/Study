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

### 3. terms_index 커버리지 확장 (21 → 40 기준서)
- `pipeline/terms_index.py`: 2-pass 탐지 로직으로 전면 개편
- 1039 제외: 자체 정의 없이 1032/1109/1113 참조만

### 4. Qdrant payload 인덱스 CLI 추가
- `search/embedder.py`에 `create_payload_indexes()` 함수 추가
- `--create-index` CLI 옵션으로 실행 가능
- **상태**: 코드 작성 완료, 아직 실행하지 않음

### 5. Agentic Tool 완전 전환
- **자동 확장 → LLM 주도 tool calling으로 전환 완료**
- 삭제된 자동 오케스트레이션 함수:
  - `xref_resolver.resolve_cross_refs()` — deprecated (파싱 로직은 보존)
  - `standards_expander.expand_referenced_standards()` — 삭제
  - `standards_expander.graph_expand()` — 삭제
  - `terms_resolver.inject_term_definitions()` — 삭제
- tool 백엔드로 보존된 함수:
  - `standards_expander.reverse_lookup_chunks()` — `find_referencing_chunks` tool
  - `standards_expander._fetch_definition_chunk()` — `fetch_term_definitions`, `explore_related_standards` tool
- 새 tool 추가: `fetch_term_definitions` (기준서 용어정의 Appendix A 조회)
- Agentic 노트북: rerank 후 용어정의 자동 주입 제거, `RERANK_TOP_N = 5`로 조정
- `rag_pipeline_test.ipynb`: 순수 baseline 파이프라인으로 전환 (Route → Retrieve → Rerank → Boost)

---

## 다음 작업

### 1. Qdrant payload 인덱스 실행
- `python3 -m search.embedder --create-index` 실행하여 `referenced_standards` keyword 인덱스 생성
- 역방향 검색(`reverse_lookup_chunks`) 성능 최적화

### 2. Agentic 파이프라인 통합 테스트
- `kifrs_rag_agentic.ipynb` 실행하여 4개 tool 동작 검증
- LLM이 `fetch_term_definitions`를 적절히 호출하는지 확인
- K=3 설정에서 tool 호출 빈도/패턴 분석

### 3. Agentic vs Baseline 평가
- 동일 22개 테스트 케이스로 Agentic(tool calling) vs Baseline(retrieve+rerank only) 비교
- DRM/Auth Accuracy/MRR 지표 분석

---

## 핵심 파일 위치

### search/ — 검색 엔진 모듈
- `search/__init__.py` — 패키지 exports
- `search/config.py` — 경로, 컬렉션명, `chunk_id_to_int()`
- `search/retriever.py` — `QdrantDenseRetriever`, `load_child_documents`, `search_with_parent`
- `search/reranker.py` — `LocalReranker`(BGE), `CohereReranker`, `get_reranker()`
- `search/query_router.py` — `classify_query()` → `QueryPlan`, `apply_authority_boost()`
- `search/tools.py` — **4개 Agentic tool** 스키마 + executor + `dispatch_tool()`
  - `fetch_paragraphs`: 특정 문단 직접 조회
  - `find_referencing_chunks`: 역방향 검색
  - `explore_related_standards`: 그래프 탐색 + 용어정의
  - `fetch_term_definitions`: 기준서 용어정의 조회
- `search/standards_graph.py` — NetworkX 기준서 참조 그래프 (81노드, 906엣지)
- `search/standards_expander.py` — tool 백엔드 (`reverse_lookup_chunks`, `_fetch_definition_chunk`)
- `search/terms_resolver.py` — 용어 인덱스 로더 (`_load_terms_index`)
- `search/xref_resolver.py` — [DEPRECATED] 교차참조 파싱 로직 보존
- `search/embedder.py` — Qdrant 적재 + `update_payloads()` + `create_payload_indexes()`

### pipeline/ — 문서 처리
- `pipeline/kifrs_chunker.py` — 청킹 + 교차참조 추출
- `pipeline/terms_index.py` — 용어정의 인덱스 빌더

### 데이터
- `output/chunks/*.json` — 패치된 청크 데이터 (63개 기준서)
- `output/terms_index.json` — 기준서별 용어정의 청크 매핑 (40개 기준서)
- `qdrant_storage/` — Qdrant 로컬 벡터DB

### 평가 / 문서
- `eval/evaluator.py` — RAG 평가기 (DRM, xref coverage, authority accuracy)
- `eval/test_cases.json` — 평가 테스트 케이스 (22개)
- `how_to_read_IFRS.md` — IFRS 해독법 + RAG 설계 전략 레퍼런스

## 검색 파이프라인 전체 흐름

### Agentic 파이프라인 (주력: `kifrs_rag_agentic.ipynb`)
```
query
  → Hybrid Retrieval (Dense + BM25, K=30)
  → Reranker (Top-5)
  → LLM Generate ⇄ Tool Loop (최대 3회)
      ├─ fetch_paragraphs: 교차참조 문단 조회
      ├─ find_referencing_chunks: 역방향 검색
      ├─ explore_related_standards: 그래프 탐색
      └─ fetch_term_definitions: 용어정의 조회
  → 최종 응답
```

### Baseline 파이프라인 (`rag_pipeline_test.ipynb`)
```
query
  → query_router.classify_query()         # 5-way 분류 → QueryPlan
  → retriever.QdrantDenseRetriever        # 벡터 검색 (Qdrant cosine)
  → reranker.get_reranker().rerank()      # cross-encoder rerank
  → query_router.apply_authority_boost()  # bc/ie 점수 감쇠
  → 최종 문서 리스트
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
