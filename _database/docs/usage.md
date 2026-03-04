# K-IFRS 벡터 DB 사용 가이드

## 개요

K-IFRS(한국채택국제회계기준) 전문을 벡터 검색할 수 있는 Qdrant 로컬 DB입니다.
약 50개 기준서 PDF에서 추출한 12,300+ 문단이 임베딩되어 있습니다.

## DB 스펙

| 항목 | 값 |
|---|---|
| 벡터 DB | Qdrant 로컬 파일 모드 |
| 저장 경로 | `./qdrant_storage` (457MB) |
| 임베딩 모델 | Upstage `solar-embedding-1-large` |
| 벡터 차원 | 4096 |
| 거리 함수 | Cosine |
| Child 포인트 | 12,313개 (벡터 + payload) |
| Parent 포인트 | 2,231개 (payload only, 벡터 없음) |

## 컬렉션 구조

### `kifrs_chunks` (Child 컬렉션)

문단 단위 청크. 벡터 검색 대상.

```
vector: 4096차원 (content 임베딩)
payload:
  chunk_id       : str   # "KIFRS1016_main_62"
  parent_id      : str   # "KIFRS1016_main_h_인식후의_감가상각_측정"
  content        : str   # 문단 전체 텍스트
  standard_id    : str   # "K-IFRS 1016"
  section_type   : str   # "main" | "ag" | "bc" | "ie"
  para_number    : str?  # "62", "5.5.16", "AG72", "한2.1" (null 가능)
  cross_refs     : list  # ["AG72", "기준서 1032호"]
  has_table      : bool  # 표 포함 여부
  has_example    : bool  # 사례/예시 포함 여부
```

**section_type 설명:**
- `main` : 기준서 본문 (문단번호: 1, 4.1.2, 한2.1)
- `ag` : 적용지침 (문단번호: AG1, AG72)
- `bc` : 결론도출근거 (문단번호: BC1, BC45)
- `ie` : 사례 (문단번호: IE1, IE12)

### `kifrs_parents` (Parent 컬렉션)

헤딩 단위 상위 구조. 벡터 없이 payload만 저장. Child의 `parent_id`로 조회하여 문맥(어떤 챕터에 속하는지)을 파악하는 용도.

```
payload:
  chunk_id       : str   # "KIFRS1016_main_h_인식후의_감가상각_측정"
  heading_text   : str   # "인식후의 감가상각 측정"
  section_type   : str   # "main" | "ag" | "bc" | "ie"
  standard_id    : str   # "K-IFRS 1016"
```

## 필수 패키지

```bash
pip install qdrant-client langchain-upstage python-dotenv
```

## 환경 변수

`.env` 파일 또는 시스템 환경변수에 Upstage API 키 설정:

```
UPSTAGE_API_KEY=up_xxxxxxxxxxxxxxxxxxxx
```

## 사용법

### 1. 기본 벡터 검색

```python
import os
import hashlib
from dotenv import load_dotenv
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient

load_dotenv()

# 초기화
client = QdrantClient(path="./qdrant_storage")
embeddings = UpstageEmbeddings(
    model="solar-embedding-1-large",
    upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
)

# 쿼리 임베딩 → 검색
query = "유형자산 감가상각 방법"
q_vec = embeddings.embed_query(query)

results = client.query_points(
    collection_name="kifrs_chunks",
    query=q_vec,
    limit=5,
    with_payload=True,
).points

for hit in results:
    p = hit.payload
    print(f"[{hit.score:.4f}] {p['standard_id']} {p['para_number']} - {p['content'][:80]}")

client.close()
```

### 2. Child → Parent 조회 (문맥 파악)

검색된 Child가 어떤 챕터에 속하는지 확인:

```python
def chunk_id_to_int(chunk_id: str) -> int:
    h = hashlib.md5(chunk_id.encode("utf-8")).hexdigest()
    return int(h[:15], 16)

def get_parent_heading(client, parent_id: str) -> str:
    pid = chunk_id_to_int(parent_id)
    points = client.retrieve(
        collection_name="kifrs_parents",
        ids=[pid],
        with_payload=True,
    )
    if points:
        return points[0].payload.get("heading_text", "")
    return ""

# 검색 결과에서 parent 조회
for hit in results:
    heading = get_parent_heading(client, hit.payload["parent_id"])
    print(f"{hit.payload['standard_id']} > {heading} > 문단 {hit.payload['para_number']}")
    # 예: K-IFRS 1016 > 인식후의 감가상각 측정 > 문단 62
```

### 3. 필터 검색 (특정 기준서/섹션만)

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

# K-IFRS 1109(금융상품)의 본문만 검색
results = client.query_points(
    collection_name="kifrs_chunks",
    query=q_vec,
    query_filter=Filter(
        must=[
            FieldCondition(key="standard_id", match=MatchValue(value="K-IFRS 1109")),
            FieldCondition(key="section_type", match=MatchValue(value="main")),
        ]
    ),
    limit=5,
    with_payload=True,
).points
```

### 4. 적용지침(AG)만 검색

```python
results = client.query_points(
    collection_name="kifrs_chunks",
    query=q_vec,
    query_filter=Filter(
        must=[
            FieldCondition(key="section_type", match=MatchValue(value="ag")),
        ]
    ),
    limit=5,
    with_payload=True,
).points
```

### 5. 표 포함 문단만 검색

```python
results = client.query_points(
    collection_name="kifrs_chunks",
    query=q_vec,
    query_filter=Filter(
        must=[
            FieldCondition(key="has_table", match=MatchValue(value=True)),
        ]
    ),
    limit=5,
    with_payload=True,
).points
```

### 6. cross_refs로 관련 문단 추적

검색된 문단이 참조하는 다른 문단(AG, BC 등)을 따라가기:

```python
hit = results[0]
refs = hit.payload.get("cross_refs", [])
print(f"이 문단이 참조하는 항목: {refs}")
# 예: ['AG72', 'AG73', '기준서 1032호']

# 참조된 AG72 문단을 ID로 직접 조회
ref_id = chunk_id_to_int("KIFRS1109_ag_AG72")  # standard_id + section + para_number
ref_points = client.retrieve(
    collection_name="kifrs_chunks",
    ids=[ref_id],
    with_payload=True,
)
if ref_points:
    print(ref_points[0].payload["content"])
```

### 7. RAG 파이프라인에서 사용 (LLM 연동)

```python
def retrieve_context(query: str, top_k: int = 5) -> str:
    q_vec = embeddings.embed_query(query)
    results = client.query_points(
        collection_name="kifrs_chunks",
        query=q_vec,
        limit=top_k,
        with_payload=True,
    ).points

    context_parts = []
    for hit in results:
        p = hit.payload
        heading = get_parent_heading(client, p["parent_id"])
        context_parts.append(
            f"[{p['standard_id']} > {heading} > 문단 {p.get('para_number', '?')}]\n"
            f"{p['content']}"
        )
    return "\n\n---\n\n".join(context_parts)

# LLM에 전달할 컨텍스트 생성
context = retrieve_context("리스부채의 재측정")
prompt = f"""다음 K-IFRS 기준서 내용을 바탕으로 질문에 답하세요.

{context}

질문: 리스부채는 언제 재측정하나요?
"""
```

## chunk_id 체계

```
{normalized_standard_id}_{section_type}_{para_number_or_slug}
```

예시:
- `KIFRS1016_main_62` — K-IFRS 1016호 본문 문단 62
- `KIFRS1109_ag_AG72` — K-IFRS 1109호 적용지침 AG72
- `KIFRS1115_bc_BC25` — K-IFRS 1115호 결론도출근거 BC25
- `KIFRS1016_main_한2.1` — K-IFRS 1016호 본문 한국 추가 문단
- `KIFRS1016_main_unk_3` — 문단번호 추출 실패한 3번째 청크

## 수록 기준서 목록

본문 (제1001호~제1117호):
- 제1001호 재무제표 표시, 제1002호 재고자산, 제1007호 현금흐름표
- 제1008호 회계정책, 제1010호 보고기간후사건, 제1012호 법인세
- 제1016호 유형자산, 제1019호 종업원급여, 제1020호 정부보조금
- 제1021호 환율변동효과, 제1023호 차입원가, 제1024호 특수관계자공시
- 제1026호 퇴직급여제도, 제1027호 별도재무제표
- 제1028호 관계기업과 공동기업, 제1029호 초인플레이션
- 제1032호 금융상품 표시, 제1033호 주당이익, 제1034호 중간재무보고
- 제1036호 자산손상, 제1037호 충당부채, 제1038호 무형자산
- 제1039호 금융상품 인식과 측정, 제1040호 투자부동산, 제1041호 농림어업
- 제1101호 최초채택, 제1102호 주식기준보상, 제1103호 사업결합
- 제1105호 매각예정비유동자산, 제1106호 광물자원
- 제1107호 금융상품 공시, 제1108호 영업부문
- 제1109호 금융상품, 제1110호 연결재무제표, 제1111호 공동약정
- 제1112호 타 기업에 대한 지분의 공시, 제1113호 공정가치 측정
- 제1114호 규제이연계정, 제1115호 수익, 제1116호 리스, 제1117호 보험계약

해석서 (제2010호~제2123호):
- 제2010호, 제2025호, 제2029호, 제2032호, 제2101호~제2123호

기타:
- 재무보고를 위한 개념체계
- 경영진설명서 작성을 위한 개념체계
- 실무서 2 중요성에 대한 판단

## 주의사항

- Qdrant를 로컬 파일 모드로 사용하므로 **동시에 하나의 프로세스만** 접근 가능
- `client.close()`를 반드시 호출하여 락 해제 필요
- 4000자 초과 청크는 임베딩 시 잘림 처리됨 (124개, 전체 1%)
- `para_number`가 null인 청크가 약 8~10% 존재 (문단번호 추출 실패)
- 임베딩 재생성 시 `python search/embedder.py` 실행 (약 35분 소요)
