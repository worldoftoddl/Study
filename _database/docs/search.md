# K-IFRS 검색 가이드

## 개요

K-IFRS 벡터 DB에 대해 3가지 검색 방식을 지원한다.

| 방식 | 원리 | 장점 | 단점 |
|---|---|---|---|
| **Dense** | 쿼리를 임베딩하여 벡터 유사도로 검색 | 의미 기반 검색, 동의어/유사 표현에 강함 | 키워드 정확 매칭이 약할 수 있음 |
| **BM25** | 형태소 토큰의 TF-IDF 기반 키워드 매칭 | 정확한 용어 매칭에 강함, 임베딩 불필요 | 의미적 유사성 파악 불가 |
| **Hybrid** | Dense + BM25 가중 결합 | 의미 + 키워드 장점 결합 | 두 인덱스 모두 필요, 초기화 느림 |

## 환경 설정

### 필수 패키지

```bash
pip install langchain-upstage langchain-qdrant langchain-community langchain-classic kiwipiepy qdrant-client python-dotenv
```

### 환경 변수

`.env` 파일에 Upstage API 키 설정:

```
UPSTAGE_API_KEY=up_xxxxxxxxxxxxxxxxxxxx
```

### 인프라 스펙

| 항목 | 값 |
|---|---|
| Qdrant 저장 경로 | `./qdrant_storage` |
| Child 컬렉션 | `kifrs_chunks` (12,313 포인트, 벡터 포함) |
| Parent 컬렉션 | `kifrs_parents` (2,231 포인트, payload only) |
| 임베딩 모델 | Upstage `solar-embedding-1-large` (4096차원) |
| BM25 토크나이저 | kiwipiepy (NNG, NNP, VV, VA, SN 태그) |
| BM25 인덱스 소스 | `./output/chunks/*.json` (child 청크) |

---

## 1. Dense 검색 (벡터 유사도)

Qdrant에 저장된 임베딩 벡터를 cosine 유사도로 검색한다.

### 기본 사용법

```python
import os
from dotenv import load_dotenv
from langchain_upstage import UpstageEmbeddings
from qdrant_client import QdrantClient

load_dotenv()

client = QdrantClient(path="./qdrant_storage")
embeddings = UpstageEmbeddings(
    model="solar-embedding-1-large",
    upstage_api_key=os.getenv("UPSTAGE_API_KEY"),
)

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
    print(f"[{hit.score:.4f}] {p['standard_id']} 문단 {p['para_number']} ({p['section_type']})")
    print(f"  {p['content'][:80]}")

client.close()
```

### 필터 검색

Qdrant의 payload 필터를 조합하여 검색 범위를 좁힐 수 있다.

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

# 특정 기준서 + 특정 섹션만 검색
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

자주 쓰는 필터 조합:

| 필터 | 용도 |
|---|---|
| `standard_id = "K-IFRS 1109"` | 특정 기준서만 검색 |
| `section_type = "main"` | 본문만 (AG/BC/IE 제외) |
| `section_type = "ag"` | 적용지침만 |
| `has_table = True` | 표 포함 문단만 |
| `has_example = True` | 사례/예시 포함 문단만 |

### 테스트 결과 (cosine score 참고 범위)

| 쿼리 | Top-1 기준서 | Top-1 문단 | score |
|---|---|---|---|
| 유형자산 감가상각 방법 | K-IFRS 1016 | 62 (main) | 0.549 |
| 금융자산의 기대신용손실 측정 | K-IFRS 1109 | 5.5.16 (main) | 0.532 |
| 수행의무 식별과 거래가격 배분 | K-IFRS 1115 | 74 (main) | 0.507 |
| 사용권자산과 리스부채의 최초 측정 | K-IFRS 1116 | (main) | 0.644 |
| 연결재무제표 작성 시 지배력 판단 | K-IFRS 1110 | (bc) | 0.588 |

score 0.50 이상이면 관련성 높은 결과로 볼 수 있다.

---

## 2. BM25 검색 (키워드 매칭)

`output/chunks/*.json`에서 child 청크를 로딩하여 BM25 인덱스를 구축한다. 한국어 특성상 kiwipiepy 형태소 분석기를 사용하여 의미 있는 토큰만 추출한다.

### kiwipiepy 토크나이저

```python
from kiwipiepy import Kiwi

kiwi = Kiwi()
ALLOWED_TAGS = {"NNG", "NNP", "VV", "VA", "SN"}

def kiwi_tokenize(text: str) -> list[str]:
    tokens = kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in ALLOWED_TAGS]
```

추출하는 품사 태그:

| 태그 | 의미 | 예시 |
|---|---|---|
| NNG | 일반 명사 | 자산, 측정, 감가상각 |
| NNP | 고유 명사 | IASB, IFRS |
| VV | 동사 | 인식하다, 측정하다 |
| VA | 형용사 | 유의적이다, 공정하다 |
| SN | 숫자 | 1016, 62, 4096 |

조사(JK*), 어미(E*), 부사(MAG), 접미사(XS*) 등은 제외하여 노이즈를 줄인다.

### JSON → LangChain Document 변환

```python
import json, glob, os
from langchain_core.documents import Document

def load_child_documents(chunks_dir: str) -> list[Document]:
    docs = []
    for fpath in sorted(glob.glob(os.path.join(chunks_dir, "*.json"))):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        standard_id = data.get("standard_id", "")
        for c in data.get("children", []):
            meta = c.get("metadata", {})
            docs.append(Document(
                page_content=c["content"],
                metadata={
                    "chunk_id": c["chunk_id"],
                    "parent_id": c.get("parent_id", ""),
                    "standard_id": meta.get("standard_id", standard_id),
                    "section_type": meta.get("section_type", ""),
                    "para_number": meta.get("para_number"),
                    "cross_refs": meta.get("cross_refs", []),
                    "has_table": meta.get("has_table", False),
                    "has_example": meta.get("has_example", False),
                },
            ))
    return docs
```

JSON의 child 구조:

```json
{
  "chunk_id": "KIFRS1016_main_62",
  "parent_id": "KIFRS1016_main_h_인식후의_감가상각_측정",
  "content": "62 유형자산의 감가상각대상금액을 ...",
  "metadata": {
    "standard_id": "K-IFRS 1016",
    "section_type": "main",
    "para_number": "62",
    "cross_refs": [],
    "has_table": false,
    "has_example": false
  }
}
```

### BM25 인덱스 생성

```python
from langchain_community.retrievers import BM25Retriever

docs = load_child_documents("./output/chunks")
bm25_retriever = BM25Retriever.from_documents(
    docs, preprocess_func=kiwi_tokenize, k=5
)

# 검색
results = bm25_retriever.invoke("유형자산 감가상각 방법")
for doc in results:
    m = doc.metadata
    print(f"{m['standard_id']} 문단 {m['para_number']} ({m['section_type']})")
    print(f"  {doc.page_content[:80]}")
```

BM25 인덱스 구축에 약 140초 소요 (12,400+ 문서 형태소 분석).

### Dense와의 차이점

BM25는 Dense가 놓치는 키워드 정확 매칭 결과를 보완한다.

예시 — "유형자산 감가상각 방법" 검색:
- **Dense Top-1**: K-IFRS 1016 문단 62 (감가상각 방법의 정의 — 의미적으로 가장 근접)
- **BM25에만 등장**: K-IFRS 1038 BC77A (무형자산 기준서에서 "감가상각 방법" 키워드 직접 언급)

---

## 3. Hybrid 검색 (BM25 + Dense 결합)

`EnsembleRetriever`로 BM25와 Dense 결과를 가중 결합한다.

### QdrantDenseRetriever (커스텀 retriever)

`langchain-qdrant`의 `QdrantVectorStore`는 payload가 flat 구조일 때 metadata를 올바르게 매핑하지 못하는 이슈가 있다. (`payload["metadata"]` 키를 찾는데, 실제 payload는 `chunk_id`, `para_number` 등이 최상위에 있음)

이를 해결하기 위해 `BaseRetriever`를 상속한 커스텀 retriever를 사용한다.

```python
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.retrievers import BaseRetriever

class QdrantDenseRetriever(BaseRetriever):
    """payload의 flat 구조를 Document metadata로 직접 매핑하는 retriever"""

    client: QdrantClient
    embeddings: UpstageEmbeddings
    collection_name: str = "kifrs_chunks"
    k: int = 5

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        q_vec = self.embeddings.embed_query(query)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=q_vec,
            limit=self.k,
            with_payload=True,
        ).points

        docs = []
        for hit in results:
            p = hit.payload
            docs.append(Document(
                page_content=p.get("content", ""),
                metadata={
                    "chunk_id": p.get("chunk_id", ""),
                    "parent_id": p.get("parent_id", ""),
                    "standard_id": p.get("standard_id", ""),
                    "section_type": p.get("section_type", ""),
                    "para_number": p.get("para_number"),
                    "cross_refs": p.get("cross_refs", []),
                    "has_table": p.get("has_table", False),
                    "has_example": p.get("has_example", False),
                },
            ))
        return docs
```

### Hybrid 구성

```python
from langchain_classic.retrievers import EnsembleRetriever

# BM25 retriever (위 섹션 참고)
bm25_retriever = BM25Retriever.from_documents(
    docs, preprocess_func=kiwi_tokenize, k=5
)

# Dense retriever (커스텀)
dense_retriever = QdrantDenseRetriever(
    client=client, embeddings=embeddings,
    collection_name="kifrs_chunks", k=5,
)

# Hybrid (BM25 0.4 + Dense 0.6)
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.4, 0.6],
)

results = ensemble_retriever.invoke("유형자산 감가상각 방법")
```

### 가중치 설정 가이드

| BM25 | Dense | 특성 |
|---|---|---|
| 0.0 | 1.0 | Dense only — 의미 검색만 |
| 0.3 | 0.7 | Dense 위주, BM25로 키워드 보완 |
| **0.4** | **0.6** | **기본값** — 균형 잡힌 결합 |
| 0.5 | 0.5 | 동일 가중치 |
| 0.7 | 0.3 | 키워드 매칭 위주 |

K-IFRS처럼 전문 용어가 중요한 도메인에서는 BM25 가중치를 0.3~0.5로 설정하는 것이 효과적이다. 법률/회계 용어의 정확한 키워드 매칭이 의미 검색을 보완한다.

---

## 4. 검색 결과 활용

### Child → Parent 조회 (문맥 파악)

검색된 Child가 어떤 챕터에 속하는지 확인:

```python
import hashlib

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

# 사용 예시
heading = get_parent_heading(client, hit.payload["parent_id"])
# → "인식후의 감가상각 측정"
```

### cross_refs로 관련 문단 추적

검색된 문단이 참조하는 적용지침(AG), 결론도출근거(BC) 등을 따라갈 수 있다.

```python
refs = hit.payload.get("cross_refs", [])
# → ['AG72', 'AG73', '기준서 1032호']

# 참조된 AG72 문단 직접 조회
ref_id = chunk_id_to_int("KIFRS1109_ag_AG72")
ref_points = client.retrieve(
    collection_name="kifrs_chunks",
    ids=[ref_id],
    with_payload=True,
)
```

### RAG 파이프라인용 컨텍스트 생성

```python
def retrieve_context(query: str, retriever, client, top_k: int = 5) -> str:
    results = retriever.invoke(query)[:top_k]

    context_parts = []
    for doc in results:
        m = doc.metadata
        heading = get_parent_heading(client, m.get("parent_id", ""))
        context_parts.append(
            f"[{m.get('standard_id', '?')} > {heading} > 문단 {m.get('para_number', '?')}]\n"
            f"{doc.page_content}"
        )
    return "\n\n---\n\n".join(context_parts)

# Hybrid retriever로 컨텍스트 생성
context = retrieve_context("리스부채의 재측정", ensemble_retriever, client)
```

---

## 5. 테스트 실행

### 통합 테스트 스크립트

```bash
python search_test_hybrid.py
```

Dense / BM25 / Hybrid 3가지를 순서대로 실행하고, Dense vs Hybrid 결과 비교를 출력한다.

### 테스트 쿼리 (5개)

1. "유형자산 감가상각 방법" — K-IFRS 1016
2. "금융자산의 기대신용손실 측정" — K-IFRS 1109
3. "수행의무 식별과 거래가격 배분" — K-IFRS 1115
4. "사용권자산과 리스부채의 최초 측정" — K-IFRS 1116
5. "연결재무제표 작성 시 지배력 판단 기준" — K-IFRS 1110

### Dense vs Hybrid 비교 결과

5개 쿼리 모두에서 Dense와 Hybrid는 **동일한 Top-5 문서 구성**을 보였고, **순위만 차이**가 있었다. BM25 가중치(0.4)가 랭킹 재조정 역할을 한다.

| 쿼리 | 순위 변동 패턴 |
|---|---|
| 유형자산 감가상각 | Dense 1위(문단62)가 Hybrid에서 5위로 하락 |
| 기대신용손실 | Dense 1위(5.5.16)가 Hybrid에서 2위로 하락 |
| 수행의무/거래가격 | 순위 거의 동일 (BC25↔BC183 순서 변경) |
| 리스부채 최초측정 | 1~2위 동일, 3~5위 순서 변경 |
| 연결/지배력 | 1~2위 동일, 하위 순서 변경 |

---

## 주의사항

- Qdrant 로컬 파일 모드는 **동시에 하나의 프로세스만** 접근 가능. `client.close()` 필수.
- BM25 인덱스는 메모리에 구축되며, 12,400+ 문서 기준 약 **140초** 소요.
- `langchain-qdrant`의 `QdrantVectorStore`는 payload가 flat 구조일 때 metadata 누락 이슈가 있으므로 `QdrantDenseRetriever` 커스텀 클래스를 사용할 것.
- `EnsembleRetriever`는 `langchain-classic` 패키지에 있음 (`langchain-community`에는 없음).

## 관련 파일

| 파일 | 설명 |
|---|---|
| `search/embedder.py` | 임베딩 + Qdrant 적재 스크립트 |
| `search/search_test.py` | Dense 검색 기본 테스트 |
| `search_test_hybrid.py` | Dense / BM25 / Hybrid 통합 테스트 |
| `output/chunks/*.json` | BM25 인덱스 소스 (child 청크 JSON) |
| `docs/usage.md` | Qdrant DB 스펙 및 사용법 |
| `docs/embedding.md` | 임베딩 적재 가이드 |
