# K-IFRS 교차참조 추출 파이프라인

## 개요

K-IFRS 기준서 본문에 포함된 교차참조(cross-reference)를 자동으로 추출하여
청크 메타데이터에 저장한다. 두 가지 필드를 생성한다:

| 필드 | 용도 | 예시 |
|------|------|------|
| `cross_refs` | 문단 수준 정밀 참조 (xref_resolver에서 청크 해소) | `["AG12~AG15", "제1109호", "문단35"]` |
| `referenced_standards` | 기준서 수준 그래프 엣지 (Graph RAG용) | `["1109", "1016"]` |

## 추출 패턴 (CROSS_REF_PATTERNS)

### 동일 기준서 내부 참조

| 패턴 | 예시 | 비고 |
|------|------|------|
| `AG\d+[A-Z]?` (단일/범위) | AG12, AG12~AG15, AG12~15 | 축약 범위 지원 |
| `BC\d+[A-Z]?` (단일/범위) | BC3, BC28~BC31 | |
| `IE\d+[A-Z]?` (단일/범위) | IE5, IE74∼IE123 | ∼ (U+223C) 지원 |
| `B\d+.\d+` (IFRS 9 스타일) | B4.1.7, B3.1.1~B3.1.6 | |
| `문단 XX` | 문단 35, 문단 35~40 | |

### 기준서 간 참조

| 패턴 | 예시 | 비고 |
|------|------|------|
| `제\s*\d{3,4}\s*호` | 제 1109 호, 제1016호 | 공백 유연 매칭 |
| `해석서\s*제\s*\d{3,4}\s*호` | 기업회계기준해석서 제 2121 호 | |
| `개념\s*체계` | 재무보고를 위한 개념체계 | |

### referenced_standards 전용 (IFRS/IAS 영문 매핑)

| 패턴 | 매핑 | 비고 |
|------|------|------|
| `IFRS N` → `11XX` | IFRS 9 → 1109, IFRS 15 → 1115 | BC 섹션에서 주로 출현 |
| `IAS N` → `10XX` | IAS 16 → 1016, IAS 28 → 1028 | `_IFRS_MAP` 딕셔너리 사용 |

## 범위 구분자

3종 모두 지원: `~` (U+007E), `∼` (U+223C), `-` (U+002D)

## 정규화 규칙

추출된 참조는 공백을 모두 제거하여 정규화:
- `제 1109 호` → `제1109호`
- `AG12 ~ AG15` → `AG12~AG15`
- `문단 35` → `문단35`

## 자기참조 필터링

- `cross_refs`: 자기 기준서 번호 단독 참조 (`제1016호`) 제거. combo (`제1016호문단XX`)는 유지
- `referenced_standards`: 자기 기준서 번호 제거
- 문단번호 자기참조: `para_number`와 동일한 값 제거

## 파이프라인 데이터 흐름

```
kifrs_chunker.py          →  output/chunks/*.json (cross_refs + referenced_standards)
    ↓
embedder.py               →  Qdrant payload에 두 필드 모두 저장
    ↓
retriever.py              →  Document.metadata로 전달
    ↓
xref_resolver.py          →  cross_refs 파싱 → chunk_id 생성 → Qdrant에서 fetch
```

## xref_resolver 해소 규칙

| 참조 형태 | 처리 |
|-----------|------|
| `AG12~AG15` | 범위 확장 → 개별 chunk_id로 fetch |
| `제1109호문단4.1.2` | `KIFRS1109_main_4.1.2` chunk_id 생성 → fetch |
| `제1109호` (문단 없음) | **skip** — 범위가 너무 넓음 |
| `문단35` | 동일 기준서 내 `{std}_main_35` chunk_id 생성 → fetch |
| `B4.1.7` | `{std}_ag_B4.1.7` chunk_id 생성 → fetch |
| `개념체계` | **skip** — 특정 청크 해소 불가 |

## 통계 (2026-03-11 패치 기준)

| 지표 | 수치 |
|------|------|
| 총 청크 | 12,457 |
| cross_refs 있는 청크 | 5,818 (46.7%) |
| cross_refs 총 항목 수 | 13,755 |
| referenced_standards 있는 청크 | 2,833 (22.7%) |
| 기준서 간 고유 그래프 엣지 | 924 |

### cross_refs 패턴별 분포

| 패턴 | 항목 수 |
|------|---------|
| 문단XX | 5,220 |
| BC (단일/범위) | 3,629 |
| 제XXXX호 | 2,071 |
| IE (단일/범위) | 1,408 |
| B숫자.숫자 | 591 |
| 개념체계 | 554 |
| AG (단일/범위) | 144 |
| 해석서 | ~130 |

## 관련 파일

- `pipeline/kifrs_chunker.py` — `extract_cross_refs()`, `extract_referenced_standards()`
- `search/xref_resolver.py` — `resolve_cross_refs()`, `_build_chunk_ids_from_refs()`
- `search/embedder.py` — Qdrant payload 구성
- `search/retriever.py` — Document metadata 매핑

## 변경 이력

- **2026-03-11**: 교차참조 패턴 전면 수정. broken 패턴 2개 교체, 8개 신규 패턴 추가.
  `referenced_standards` 필드 신설. cross_refs 22.9%→46.7%, 그래프 엣지 343→924.
