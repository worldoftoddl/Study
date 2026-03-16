# K-IFRS RAG 파이프라인 — 현재 상태 및 다음 단계

## 완료된 작업

### 1. 교차참조 추출 파이프라인 전면 수정
- `pipeline/kifrs_chunker.py`: broken 패턴 2개 교체 + 8개 신규 패턴 추가
- `search/xref_resolver.py`: 새 참조 형식에 맞게 파싱 패턴 동기화
- `search/embedder.py`, `search/retriever.py`: `referenced_standards` 필드 관통 전달
- 청크 JSON 63개 전체 패치 완료

### 2. Qdrant payload 적재 완료 (이전 — PostgreSQL로 전환됨)
- 적재 결과 (이전 Qdrant 기준):

| 지표 | 수치 |
|------|------|
| 총 child 포인트 | 12,313 |
| cross_refs 있는 포인트 | 5,743 (46.6%) |
| referenced_standards 있는 포인트 | 2,799 (22.7%) |
| 기준서 간 고유 그래프 엣지 | 924 |

### 3. terms_index 커버리지 확장 (21 → 40 기준서)
- `pipeline/terms_index.py`: 2-pass 탐지 로직으로 전면 개편
- 1039 제외: 자체 정의 없이 1032/1109/1113 참조만

### 4. Agentic Tool 완전 전환
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

### 5. Raw Markdown 정제 + 재청킹 (2026-03-15)
- **`pipeline/md_cleaner.py` 신규 생성** — pymupdf4llm 출력 후처리 모듈
  - 5단계 순차 정제: 보일러플레이트 제거 → 페이지 번호 제거 → PDF 줄바꿈 병합 → 테이블 `<br>` 정리 → 빈줄 축소
  - CLI: `python pipeline/md_cleaner.py` (전체 배치), `--single`, `--dry-run`, `--fix-spacing` 옵션
  - 출력: `output/clean_md/` (원본 `output/raw_md/` 보존)
- **`pipeline/kifrs_chunker.py` 수정**
  - `pymupdf4llm` 지연 임포트 (모듈 레벨 → `convert_pdf_to_markdown()` 내부)
  - `process_single_pdf()`에 `clean_markdown()` 호출 삽입
  - `PARA_PATTERNS` 확장: B-prefix (`B2`, `B4.1.1`), C-series (`C3`, `C5A`), BCE (`BCE.2`) 추가
  - `extract_para_number()`: 현재 섹션 패턴 실패 시 다른 섹션 패턴도 시도 (cross-section 매칭)
- **`pipeline/etc_chunker.py` 수정** — `clean_markdown()` 호출 삽입
- **정제 결과**:

| 지표 | Raw MD | Clean MD | 변화 |
|------|--------|----------|------|
| 총 라인 수 | 523,513 | 118,185 | **-77.4%** |
| 보일러플레이트 | 있음 | 제거됨 | |
| 페이지 번호 아티팩트 | 있음 | 제거됨 | |
| PDF 줄바꿈 | 문장 중간 끊김 | 논리적 문단 병합 | |

- **청크 재생성 결과**:

| 지표 | 이전 (raw MD 기반) | 현재 (clean MD 기반) | 변화 |
|------|-------------------|---------------------|------|
| 총 child 청크 | 12,457 | **15,839** | +27% |
| 빈 청크 / 50자 미만 | 존재 | **0개** | |
| 5K+ unk 청크 | 다수 (최대 81K) | **8개** (최대 15K) | |
| 3K+ 청크 | 미측정 | **84개** (0.5%) | |
| 평균 청크 길이 | 미측정 | 359자 (중앙값 257자) | |

### 6. 저가치 BC 청크 정리 (2026-03-16)
- **`pipeline/bc_chunk_cleaner.py` 신규 생성** — BC 보일러플레이트 청크 제거 스크립트
  - 6개 규칙: unk_5k_bc(4), meta_disclaimer(17), admin_intro(49), amendment(62), dissenting(49), ias_relation(73)
  - `prune_orphaned_parents()`: 자식 없어진 parent 자동 정리 (446개)
  - CLI: `--dry-run`, `--single FILE.json`, `--out-dir DIR` (미지정 시 in-place)
  - 멱등성 보장: 2회 실행 시 제거 0개
- **결과**: 15,838 → 15,587 children (-251개, 1.6%)
- **안전성 검증**: K-IFRS 1113 공정가치 BC 261개 등 실질 BC 청크 전량 보존 확인

### 7. 벡터DB 전환: Qdrant → PostgreSQL + pgvector (2026-03-16)
- **코드 전환 완료** — search/ 모듈 전체를 Qdrant에서 PostgreSQL + pgvector로 마이그레이션
- 수정된 파일 13개:
  - `search/config.py` — `QDRANT_PATH` → `DATABASE_URL`, `chunk_id_to_int()` 제거
  - `search/db.py` — **[신규]** `psycopg_pool` 커넥션 풀 + `build_where_clause()` 필터 빌더
  - `search/embedder.py` — Qdrant upsert → PostgreSQL DDL + INSERT (HNSW 벡터 인덱스 포함)
  - `search/query_router.py` — Qdrant `Filter` 객체 → dict 기반 필터
  - `search/retriever.py` — `QdrantDenseRetriever` → `PgVectorRetriever` (pgvector `<=>` cosine)
  - `search/standards_expander.py` — `client: QdrantClient` 제거, SQL 직접 쿼리
  - `search/tools.py` — 4개 executor 모두 client 파라미터 제거, SQL 조회
  - `search/xref_resolver.py` — DEPRECATED 모듈 최소 수정
  - `search/__init__.py` — exports 업데이트
  - `tools_for_agent/_resources.py` — `QdrantClient` 제거, `KifrsResources.client` 필드 제거
  - `tools_for_agent/tools.py` — `res.client` 참조 제거
  - `search_test_hybrid.py` — pgvector 기반으로 전환
  - `requirements.txt` — `qdrant-client` → `psycopg[binary]`, `psycopg-pool`, `pgvector`
- **import 검증 완료**: 모든 모듈 Qdrant 참조 0건, import 정상
- **PostgreSQL 16 + pgvector 0.6.0 설치 완료**, DB `kifrs_rag` 생성 완료, `.env` 설정 완료
- **상태: 3K+ 대형 청크 재청킹 후 임베딩 적재 필요**

---

## 다음 작업

### 1. 3K+ 대형 청크 재청킹
- 현재 3,000자 초과 청크 84개 존재 (64개 문단번호 있음, 20개 unk)
- 재청킹하여 3,000자 이하로 분할
- 재청킹 후 `python -m search.embedder` 실행 → PostgreSQL 적재

### 2. Agentic 파이프라인 통합 테스트
- `kifrs_rag_agentic.ipynb` 실행하여 4개 tool 동작 검증
- LLM이 `fetch_term_definitions`를 적절히 호출하는지 확인

### 3. Agentic vs Baseline 평가
- 동일 22개 테스트 케이스로 Agentic(tool calling) vs Baseline(retrieve+rerank only) 비교
- DRM/Auth Accuracy/MRR 지표 분석

---

## 핵심 파일 위치

### pipeline/ — 문서 처리
- `pipeline/md_cleaner.py` — raw MD 후처리 (5단계 정제 + CLI)
- `pipeline/kifrs_chunker.py` — 청킹 + 교차참조 추출 (B/C/BCE 패턴 확장됨)
- `pipeline/etc_chunker.py` — 비표준 문서 청킹 (개념체계, 실무서)
- `pipeline/bc_chunk_cleaner.py` — 저가치 BC 청크 제거 (6개 규칙 + CLI)
- `pipeline/terms_index.py` — 용어정의 인덱스 빌더

### search/ — 검색 엔진 모듈 (PostgreSQL + pgvector)
- `search/__init__.py` — 패키지 exports
- `search/config.py` — `DATABASE_URL`, 테이블명, 임베딩 모델 설정
- `search/db.py` — **[신규]** `psycopg_pool` 커넥션 풀, `build_where_clause()` 필터 빌더
- `search/retriever.py` — `PgVectorRetriever`, `load_child_documents`, `search_with_parent`
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
- `search/embedder.py` — PostgreSQL 적재 + Upstage Solar 임베딩 + HNSW 인덱스

### 데이터
- `output/raw_md/*.md` — pymupdf4llm 원본 마크다운 (63개, 보존용)
- `output/clean_md/*.md` — 정제된 마크다운 (63개)
- `output/chunks/*.json` — 재생성된 청크 데이터 (63개 기준서, 15,587 children — BC 정리 후)
- `output/terms_index.json` — 기준서별 용어정의 청크 매핑 (40개 기준서)
- `qdrant_storage/` — **[DEPRECATED]** 이전 Qdrant 로컬 벡터DB (삭제 가능)

### 평가 / 문서
- `eval/evaluator.py` — RAG 평가기 (DRM, xref coverage, authority accuracy)
- `eval/test_cases.json` — 평가 테스트 케이스 (22개)
- `how_to_read_IFRS.md` — IFRS 해독법 + RAG 설계 전략 레퍼런스

## 검색 파이프라인 전체 흐름

### Agentic 파이프라인 (주력: `kifrs_rag_agentic.ipynb`)
```
query
  → Hybrid Retrieval (Dense pgvector + BM25, K=30)
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
  → retriever.PgVectorRetriever           # 벡터 검색 (pgvector cosine)
  → reranker.get_reranker().rerank()      # cross-encoder rerank
  → query_router.apply_authority_boost()  # bc/ie 점수 감쇠
  → 최종 문서 리스트
```

## PostgreSQL 스키마 (kifrs_children 테이블)
```sql
CREATE TABLE kifrs_children (
    chunk_id                TEXT PRIMARY KEY,
    parent_id               TEXT NOT NULL DEFAULT '',
    content                 TEXT NOT NULL DEFAULT '',
    standard_id             TEXT NOT NULL DEFAULT '',
    section_type            TEXT NOT NULL DEFAULT '',
    para_number             TEXT,
    cross_refs              TEXT[] NOT NULL DEFAULT '{}',
    referenced_standards    TEXT[] NOT NULL DEFAULT '{}',
    has_table               BOOLEAN NOT NULL DEFAULT FALSE,
    has_example             BOOLEAN NOT NULL DEFAULT FALSE,
    embedding               vector(4096)
);
-- 인덱스: parent_id, standard_id, section_type (btree)
--         referenced_standards, cross_refs (GIN)
--         embedding (HNSW vector_cosine_ops, m=16, ef_construction=128)
```

## 환경
- Python 3.12.3, `.venv` 가상환경 (`python3`만 사용, `python` 없음)
- PostgreSQL + pgvector (`kifrs_rag` 데이터베이스)
- 임베딩: Upstage Solar (`solar-embedding-1-large`, 4096차원)
- Reranker: `dragonkue/bge-reranker-v2-m3-ko` (로컬) 또는 Cohere API
- WSL2 (Linux 6.6)
