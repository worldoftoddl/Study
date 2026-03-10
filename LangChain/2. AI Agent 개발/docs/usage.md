# Tax Agent Pipeline 사용법

## 프로젝트 구조

```
agent/                  # 핵심 파이프라인 모듈
├── config.py           # 환경변수 기반 설정 + 팩토리 함수
├── state.py            # SelfRagState, RealEstateTaxState
├── prompts.py          # 인라인 프롬프트 + LangSmith lazy-pull
├── graders.py          # 조건부 엣지 함수 (관련성, 환각, 유용성 평가)
├── nodes.py            # Self-RAG 노드 (retrieve, rewrite, generate)
├── graph.py            # Self-RAG 그래프 조립
├── real_estate.py      # 종합부동산세 계산 그래프
└── __init__.py         # public API re-export

data/                   # 데이터 파싱 (agent/와 독립)
├── tax_xml_parser.py   # 법령정보센터 XML → LangChain Document
├── law_xml/            # 소득세법 XML 원본
└── __init__.py         # re-export parse_xml_law
```

## 환경 설정

```bash
# 1. 가상환경 생성
python3 -m venv .venv && source .venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력
```

## 사용법

### Self-RAG (세법 Q&A)

```python
from agent import self_rag_graph

result = self_rag_graph.invoke({"query": "프리랜서 종합소득세 신고 방법"})
print(result["answer"])
```

### 종합부동산세 계산

```python
from agent import real_estate_graph

result = real_estate_graph.invoke({
    "query": "공시가격 15억원 주택 1채 보유"
})
print(result["answer"])
```

### 개별 컴포넌트 사용

```python
from agent.config import get_llm, get_retriever

# LLM 티어 선택: "smart" | "default" | "small"
llm = get_llm("small")

# Retriever (기본: Self-RAG용 Chroma)
retriever = get_retriever()

# 부동산세용 Retriever
from agent.config import RE_COLLECTION_NAME, RE_DB_PERSIST_DIR
re_retriever = get_retriever(
    collection_name=RE_COLLECTION_NAME,
    persist_directory=RE_DB_PERSIST_DIR,
    k=4, fetch_k=10,
)
```

## 환경변수 레퍼런스

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SMART_LLM_MODEL` | claude-opus-4-5-20251101 | 고성능 LLM |
| `LLM_MODEL` | claude-sonnet-4-5-20250929 | 기본 LLM |
| `SMALL_LLM_MODEL` | claude-haiku-4-5-20251001 | 경량 LLM |
| `LLM_TEMPERATURE` | 0.1 | LLM 온도 |
| `EMBEDDING_MODEL` | solar-embedding-1-large | 임베딩 모델 |
| `COLLECTION_NAME` | chroma-tax | Self-RAG Chroma 컬렉션 |
| `DB_PERSIST_DIR` | ./preprocessed-upstage | Self-RAG DB 경로 |
| `RE_COLLECTION_NAME` | real_estate_tax | 부동산세 Chroma 컬렉션 |
| `RE_DB_PERSIST_DIR` | ./real_estate_tax_collection | 부동산세 DB 경로 |
| `RETRIEVER_SEARCH_TYPE` | mmr | 검색 전략 (mmr/similarity) |
| `RETRIEVER_K` | 10 | 반환 문서 수 |
| `RETRIEVER_FETCH_K` | 50 | MMR 후보 문서 수 |
| `RETRIEVER_LAMBDA_MULT` | 0.6 | MMR 다양성 가중치 |

## 의존성 그래프

```
.env
  │
  ▼
config.py  ◄── 단일 설정 소스
  │
  ├──────┬──────┐
  ▼      ▼      ▼
prompts  state   (독립)
  │      │
  ▼      ▼
nodes   graders
  │      │
  ▼      ▼
graph   real_estate
  │      │
  ▼      ▼
__init__.py (public API)
```

`data/` 모듈은 `agent/`와 완전히 독립적이다.
