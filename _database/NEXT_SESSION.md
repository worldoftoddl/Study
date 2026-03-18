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
| 3K+ 청크 | 미측정 | **84개** (0.5%) → 재청킹 후 **0개** | |
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
- 수정된 파일 13개 (상세 내역 생략)
- **import 검증 완료**: 모든 모듈 Qdrant 참조 0건, import 정상

### 8. 3K+ 대형 청크 재청킹 (2026-03-16)
- **`pipeline/kifrs_chunker.py` 수정** — `split_large_content()` 함수 추가
- **결과**: 15,587 → **16,052** children (+465)
  - 3K+ 청크: 83 → **0** (최대 2,983자)

### 9. PostgreSQL 임베딩 적재 + pgvector 업그레이드 (2026-03-16)
- `python -m search.embedder` 실행 완료
- **적재 결과**: Children 15,550 (고유 chunk_id 기준), Parents 2,004
  - JSON 내 16,052 children 중 268개 중복 chunk_id → ON CONFLICT 처리
- pgvector 0.6.0 → **0.8.0** 소스 빌드 업그레이드
- **HNSW 인덱스 미생성**: pgvector HNSW 최대 4,000차원 < Solar 4,096차원
  - 15,550행 소규모 → 순차 스캔(brute-force cosine)으로 충분
  - `embedder.py`에 graceful fallback 추가 (인덱스 실패 시 경고만 출력)

### 10. Agentic 파이프라인 재설계: Parent-Grouped Retrieval (2026-03-16)
- **문제**: 청크가 평균 349자로 세분화 → 기존 top-5 리랭크로는 ~1,750자 컨텍스트만 확보 → 불충분
- **해결**: child 검색 → parent 그룹핑 → sibling 확장으로 ~6,000~15,000자 컨텍스트 확보
- **새 체인 구조**:
  ```
  query
    → classify_query()                        # 5-way 분류 → QueryPlan (필터/boost 결정)
    → Hybrid Retrieval (Dense + BM25, K=30)   # query_filter 적용 (normative→main+ag)
    → Rerank (top-15) + Authority Boost       # bc/ie 점수 0.85 감쇠
    → ★ expand_parents                        # parent 그룹핑 + sibling 확장
        - reranked children을 parent_id로 그룹핑
        - best_score 순 상위 parent 선택
        - fetch_siblings()로 형제 children 전체 로드
        - MAX_CONTEXT_CHARS(12,000) 예산 내에서 추가
    → Parent-Grouped Context 포맷팅           # ★ 매칭 문단 표시 + heading 포함
    → LLM Generate ⇄ Tool Loop (최대 3회)
    → 최종 응답
  ```
- **수정 파일**:
  - `search/retriever.py` — `expand_to_parents()`, `format_parent_context()` 추가
  - `search/__init__.py` — 새 함수 export
  - `kifrs_rag_agentic.ipynb` — Qdrant→pgvector 전환 + 체인 전면 재설계
- **검증 결과**:

| 쿼리 | Parent 그룹 | 총 컨텍스트 |
|------|------------|------------|
| 수익인식 5단계 | 1개 (1115 main 인식 35건) | 11,751자 |
| 기대신용손실 측정 | 1개 (1109 ag 측정 50건) | 15,839자 |
| 유형자산 감가상각 | 3개 (1016 main + 공시 + 1038) | 11,463자 |
| 지배력 판단 | 3개 (1110 + 1114 + 1028) | 6,708자 |

### 11. DOCX 기반 청킹 파이프라인 v2 (Step 0-3) (2026-03-17)
- **동기**: PDF→MD 변환(pymupdf4llm) 한계 — unk 문자 5.9%, 표 구조 손실, 줄바꿈 아티팩트
- **해결**: DOCX 원본 직접 파싱으로 전환
- **신규 파일**:
  - `pipeline/docx_parser.py` — python-docx 기반 DOCX→MD 변환 (표 구조 보존)
  - `pipeline/docx_chunker.py` — DOCX MD 전용 청커
  - `pipeline/docx_pipeline.py` — 전체 배치 파이프라인 (parse → chunk → validate)
- **결과**: 63/63 파일 성공, `output/chunks_v2/`에 **15,060 children** 생성

| 지표 | v1 (PDF 기반) | v2 (DOCX 기반) | 변화 |
|------|--------------|---------------|------|
| unk 문자 비율 | 5.9% | 3.2% | -46% |
| <100자 청크 | 1,396 | 76 | -95% |
| >5000자 청크 | 0 | 0 | 유지 |
| 교차참조 추출 | 41.5% | 48.9% | +18% |
| 최대 청크 | - | 4,998자 | target_max_chars=5,000 이내 |

### 12. KURE-v1 토큰 수 검증 (Step 4) (2026-03-17)
- **목적**: target_max_chars=5,000이 KURE-v1(8192 토큰) 한도 내인지 실측 검증
- **`verify_tokens.py` 신규 생성** — 전체 children 토큰화 + 통계 출력
- **결과: PASS — 8192 초과 0건, target_max_chars=5,000 유지**

| 지표 | 값 |
|------|-----|
| 8192 초과 | **0건** |
| Max 토큰 | 3,193 (한도의 39%) |
| P99 | 1,498 |
| P95 | 433 |
| Mean | 196.5 |
| chars/token 비율 | **1.873** (가정 1.5 대비 높음 → 안전 마진 ↑) |
| has_table 평균 | 738 (일반 180 대비 4x, 그래도 한도 내) |

- **핵심 발견**: chars/token 실측치 1.873 → `5,000 / 1.873 ≈ 2,669` 토큰 최대 → 8,192 대비 67% 여유
- 분포의 96%가 500 토큰 미만

### 13. DOCX MD 검수 + 보일러플레이트 정제 (2026-03-18)
- **저작권 섹션 일괄 삭제**: 63개 파일 전체에서 65개 저작권 보일러플레이트 블록 제거
  - 시작 마커: `^저작권법?$`, 끝 마커: `Reproduction of the integral part...`
  - 제1027호, 제1033호: 중복 블록 2개씩 삭제
  - 제2101호: `저작권법` 변형 마커 대응
  - 본문 속 회계 용어("저작권, 특허권" 등)는 보존 확인
- **목차 테이블 삭제 + 별도 저장**: 3개 파일에서 10개 목차 테이블 제거
  - `_TOC_경영진설명서_...md`, `_TOC_실무서_2_...md`, `_TOC_개념체계_...md` 생성
  - 개념체계 목차: 원본 DOCX에서 XML 파싱으로 8개 장 구조 + 문단번호 복원
- **빈 테이블 복원**: 실무서 2 "그림 2— 회계정책 정보가 중요한지를 판단함"
  - 원본 DOCX에서 플로차트형 판단 다이어그램 추출 → 3열 표 구조로 복원
- **authority boost 삭제**: `apply_authority_boost()` 함수 및 `QueryPlan.authority_boost` 필드 제거
  - MD 검수 후 재청킹 예정이므로 점수 감쇠 임시방편 불필요
  - `AUTHORITY_FILTERS` / `get_authority_filter()`는 검색 필터 용도로 유지

### 14. DOCX MD 시행일·의결문·메타 섹션 일괄 삭제 (2026-03-18)
- **`pipeline/md_section_cleaner.py` 신규 생성** — MD 보일러플레이트 섹션 삭제 스크립트
- **삭제 대상 4종**:
  - `## 시행일*` 섹션 (개정이력: "XXXX년에 문단 XX가 개정되었다" 등 변경 로그)
  - 의결문 블록 (166건, "회계기준위원회의 의결" + 위원 명단)
  - `### 기타 참고사항` 섹션 (국제기준 대응 관계, 준수 설명 등)
  - `제·개정 경과` 섹션
- **보존 대상**:
  - `### 경과 규정` (12개 파일) — 전환 방법 등 실질 회계 지침
  - `정의된 용어들` / `부록` 등 본문 콘텐츠
- **결과**: 63개 파일, **12,244줄 삭제** (77,791 → 65,423줄, -15.9%)
  - 멱등성: 2회 실행 시 삭제 0줄

---

## 다음 작업

### 1. Agentic 파이프라인 LLM 응답 품질 검증
- `kifrs_rag_agentic.ipynb` 전체 실행 (5개 테스트 쿼리)
- tool calling 동작 확인 (교차참조 해소, 용어정의 조회)

### 2. 중복 chunk_id 정리
- JSON 내 268개 중복 chunk_id 조사 (다른 기준서 간 동일 ID 충돌 가능성)
- 필요 시 chunker 수정으로 chunk_id 유일성 보장

### 3. Agentic vs Baseline 평가
- 동일 22개 테스트 케이스로 Agentic(tool calling) vs Baseline(retrieve+rerank only) 비교
- DRM/Auth Accuracy/MRR 지표 분석

### 4. 적용사례(IE) few-shot 분리
- 적용사례는 벡터스토어 청킹과 궁합이 안 맞음 (표/분개/계산 과정이 청킹되면 맥락 끊김, 숫자 위주 데이터는 임베딩 유사도 검색에 약함)
- **벡터스토어**: 본문 문단 + 부록 적용지침(AG) + 결론도출근거(BC) → "규정이 뭔지" 검색용
- **few-shot bank**: 적용사례(IE) + 사례별 표/분개 → "어떻게 적용하는지" 예시 주입용
- 적용사례를 기준서별로 별도 파일/DB 테이블로 분리 관리, 질문 의도가 "계산/적용 방법"일 때 관련 사례를 선택적으로 context에 주입

### 5. BM25 query_filter 미적용 이슈
- 현재 BM25Retriever는 query_filter를 지원하지 않음 (전체 16,052문서 대상 검색)
- Dense에만 필터 적용 중 → Hybrid 결과에 bc/ie 문서가 BM25 경유로 유입 가능
- 해결 방안: BM25 인덱스를 section_type별로 분리 빌드, 또는 ensemble 후 필터링

---

## 핵심 파일 위치

### pipeline/ — 문서 처리
- `pipeline/md_cleaner.py` — raw MD 후처리 (5단계 정제 + CLI)
- `pipeline/kifrs_chunker.py` — 청킹 + 교차참조 추출 (B/C/BCE 패턴 확장됨)
- `pipeline/etc_chunker.py` — 비표준 문서 청킹 (개념체계, 실무서)
- `pipeline/bc_chunk_cleaner.py` — 저가치 BC 청크 제거 (6개 규칙 + CLI)
- `pipeline/md_section_cleaner.py` — 시행일/의결문/기타참고사항 섹션 삭제 (경과규정 보존)
- `pipeline/terms_index.py` — 용어정의 인덱스 빌더

### search/ — 검색 엔진 모듈 (PostgreSQL + pgvector)
- `search/__init__.py` — 패키지 exports
- `search/config.py` — `DATABASE_URL`, 테이블명, 임베딩 모델 설정
- `search/db.py` — `psycopg_pool` 커넥션 풀, `build_where_clause()` 필터 빌더
- `search/retriever.py` — `PgVectorRetriever`, `expand_to_parents`, `format_parent_context`, `load_child_documents`, `search_with_parent`
- `search/reranker.py` — `LocalReranker`(BGE), `CohereReranker`, `get_reranker()`
- `search/query_router.py` — `classify_query()` → `QueryPlan`
- `search/tools.py` — **4개 Agentic tool** 스키마 + executor + `dispatch_tool()`
  - `fetch_paragraphs`: 특정 문단 직접 조회
  - `find_referencing_chunks`: 역방향 검색
  - `explore_related_standards`: 그래프 탐색 + 용어정의
  - `fetch_term_definitions`: 기준서 용어정의 조회
- `search/standards_graph.py` — NetworkX 기준서 참조 그래프 (81노드, 906엣지)
- `search/standards_expander.py` — tool 백엔드 (`reverse_lookup_chunks`, `_fetch_definition_chunk`)
- `search/terms_resolver.py` — 용어 인덱스 로더 (`_load_terms_index`)
- `search/xref_resolver.py` — [DEPRECATED] 교차참조 파싱 로직 보존
- `search/embedder.py` — PostgreSQL 적재 + Upstage Solar 임베딩 (HNSW graceful fallback)

### 데이터
- `output/raw_md/*.md` — pymupdf4llm 원본 마크다운 (63개, 보존용)
- `output/clean_md/*.md` — 정제된 마크다운 (63개)
- `output/chunks/*.json` — v1 청크 (PDF 기반, 16,052 children) — **DEPRECATED**
- `output/chunks_v2/*.json` — **v2 청크 (DOCX 기반, 15,060 children)** ← 현재 사용
- `output/docx_md/*.md` — DOCX→MD 변환 결과 (63개, 저작권/목차/시행일/의결문 정제 완료, 65,423줄)
- `output/docx_md/_TOC_*.md` — 목차 별도 저장 (3개)
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
  → classify_query()                          # 5-way 분류 → QueryPlan
  → Hybrid Retrieval (Dense pgvector + BM25, K=30, query_filter 적용)
  → Reranker (Top-15)
  → expand_parents                            # parent 그룹핑 + sibling 확장 (~12K자)
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
--         벡터 인덱스 없음 (pgvector HNSW 4000차원 제한 > Solar 4096차원, 순차 스캔 사용)
```

## 환경
- Python 3.12.3, `.venv` 가상환경
- PostgreSQL 16 + pgvector 0.8.0 (`kifrs_rag` 데이터베이스)
- 임베딩: Upstage Solar (`solar-embedding-1-large`, 4096차원)
- Reranker: `dragonkue/bge-reranker-v2-m3-ko` (로컬) 또는 Cohere API
- WSL2 (Linux 6.6)
