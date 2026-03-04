# K-IFRS PDF 파싱/청킹 파이프라인 구현 계획

## 목적

K-IFRS 기준서 PDF를 Vector DB에 적재할 수 있도록
**파싱 → 청킹 → JSON 저장**까지의 파이프라인을 구축한다.

Qdrant 적재 및 임베딩은 이번 범위에서 제외.
중간 산출물은 JSON으로 저장하여 이후 단계에서 재사용 가능하도록 한다.

---

## 디렉토리 구조

```
project/
├── data/
│   └── raw/              # 원본 PDF 파일 저장 위치
├── output/
│   └── chunks/           # 최종 JSON 청크 저장 위치
├── kifrs_parser.py       # PDF 파싱 모듈
├── kifrs_chunker.py      # 청킹 모듈
└── pipeline.py           # 전체 파이프라인 실행 스크립트
```

---

## 설치 패키지

```bash
pip install pymupdf4llm pymupdf kiwipiepy
```

- `pymupdf4llm`: PDF → Markdown 변환 (표, 헤딩 구조 보존)
- `pymupdf (fitz)`: PDF 메타정보 추출 보조
- `kiwipiepy`: 한국어 문장 분리 (BM25 하이브리드 검색 대비)

---

## 1단계: PDF → Markdown 변환 (`kifrs_parser.py`)

### 역할
PDF를 pymupdf4llm으로 Markdown 텍스트로 변환한다.

### 구현 사항

```python
# kifrs_parser.py

import pymupdf4llm
from pathlib import Path

def pdf_to_markdown(pdf_path: str) -> str:
    """
    PDF 파일을 Markdown 텍스트로 변환한다.
    
    Returns:
        str: 마크다운 형식의 전체 텍스트
    """
    ...
```

### 주의사항
- `pymupdf4llm.to_markdown(pdf_path)` 호출 시 `page_chunks=False`로 설정
  (페이지 단위 분리 불필요, 전체 텍스트를 하나의 문자열로)
- 변환 결과를 `output/raw_md/` 에 `.md` 파일로 저장해 중간 확인 가능하게 할 것

---

## 2단계: 섹션 감지 (`kifrs_parser.py` 내 함수)

### K-IFRS 기준서의 섹션 구조

K-IFRS PDF는 하나의 파일 안에 아래 4개 섹션이 존재한다.
각 섹션은 별도의 문단 번호 체계를 가진다.

| 섹션 | 약어 | 문단번호 패턴 예시 |
|------|------|-------------------|
| 기준서 본문 | MAIN | `문단 1`, `문단 4.1.2` |
| 적용지침 | AG | `AG1`, `AG72` |
| 결론도출근거 | BC | `BC1`, `BC45` |
| 사례 | IE | `IE1`, `IE12` |

### 구현 사항

```python
import re
from enum import Enum

class SectionType(Enum):
    MAIN = "main"           # 기준서 본문
    APP_GUIDANCE = "ag"     # 적용지침
    BASIS = "bc"            # 결론도출근거
    ILLUSTRATIVE = "ie"     # 사례

def detect_section_type(text_block: str) -> SectionType:
    """
    텍스트 블록을 보고 어느 섹션에 해당하는지 판별한다.
    
    판별 기준:
    - 헤딩에 '적용지침' 포함 → AG
    - 헤딩에 '결론도출근거' 포함 → BC
    - 헤딩에 '사례' 포함 → IE
    - 그 외 → MAIN
    """
    ...
```

---

## 3단계: 문단 번호 기반 분리 및 메타데이터 추출 (`kifrs_parser.py`)

### 문단 번호 패턴 (정규식)

```python
# 기준서 본문 문단 번호 패턴
MAIN_PARA_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)\s+')  # 예: "4.1.2 "

# 적용지침 문단 번호 패턴
AG_PARA_PATTERN = re.compile(r'^(AG\d+)\s+')            # 예: "AG72 "

# 결론도출근거 문단 번호 패턴
BC_PARA_PATTERN = re.compile(r'^(BC\d+)\s+')            # 예: "BC45 "

# 사례 문단 번호 패턴
IE_PARA_PATTERN = re.compile(r'^(IE\d+)\s+')            # 예: "IE12 "

# 상호참조 패턴 (본문 내 다른 문단/기준서 참조)
CROSS_REF_PATTERN = re.compile(
    r'(문단\s*\d+(?:\.\d+)*|AG\d+|BC\d+|IE\d+|기준서\s*\d+호?)'
)
```

### 각 문단에서 추출할 메타데이터

```python
{
    "standard_id": "K-IFRS 1109",   # 기준서 번호 (파일명 또는 헤더에서 추출)
    "standard_name": "금융상품",      # 기준서 명칭
    "section_type": "main",          # main / ag / bc / ie
    "para_number": "4.1.2",          # 문단 번호
    "cross_refs": ["AG72", "기준서 1032호"],  # 본문에서 발견된 상호참조 목록
    "has_table": False,              # 표 포함 여부
    "has_example": False,            # 사례 포함 여부
}
```

---

## 4단계: Parent-Child 청크 구성 (`kifrs_chunker.py`)

### 개념 설명

| 레벨 | 단위 | 용도 |
|------|------|------|
| Parent | 섹션 (예: "분류" 전체) | 넓은 맥락 제공용 |
| Child | 개별 문단 (예: "문단 4.1.2") | 실제 검색 및 Retrieve 단위 |

검색 시 Child 청크로 Hit하고, Parent를 함께 반환해 맥락을 보존하는 구조.
(LangChain의 `ParentDocumentRetriever` 패턴과 동일한 아이디어)

### 데이터 모델

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ChildChunk:
    chunk_id: str              # "{standard_id}_{section_type}_{para_number}"
    parent_id: str             # "{standard_id}_{section_type}_{section_heading}"
    content: str               # 문단 텍스트
    metadata: dict             # 위에서 정의한 메타데이터 딕셔너리

@dataclass
class ParentChunk:
    parent_id: str
    section_heading: str       # 섹션 헤딩 텍스트 (예: "4.1 금융자산의 분류")
    children: list[str]        # child_id 리스트
    metadata: dict
```

### 구현 사항

```python
# kifrs_chunker.py

def build_parent_child_chunks(
    paragraphs: list[dict]     # 3단계에서 추출한 문단+메타데이터 리스트
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    """
    문단 리스트를 받아 Parent-Child 청크 구조를 생성한다.
    
    Parent 경계 판단 기준:
    - Markdown 헤딩(# ## ###) 등장 시 새 Parent 시작
    - 섹션 타입 변경 시 (main → ag 등) 새 Parent 시작
    
    Returns:
        (parent_chunks, child_chunks) 튜플
    """
    ...
```

---

## 5단계: 문장 분리 적용 (`kifrs_chunker.py`)

### 목적
Child 청크가 지나치게 길 경우 kiwipiepy로 문장 단위 분리.
BM25 인덱싱 및 임베딩 품질 개선 목적.

### 기준
- Child 청크가 **500자 초과** 시 문장 분리 적용
- 문장 분리 후에도 메타데이터(para_number 등)는 상속

```python
from kiwipiepy import Kiwi

kiwi = Kiwi()

def split_into_sentences(text: str) -> list[str]:
    """
    kiwipiepy로 한국어 문장 분리.
    500자 이하 텍스트는 분리하지 않고 그대로 반환.
    """
    if len(text) <= 500:
        return [text]
    
    result = kiwi.split_into_sents(text)
    return [sent.text for sent in result]
```

---

## 6단계: JSON 저장 (`pipeline.py`)

### 출력 파일 형식

`output/chunks/{standard_id}.json`

```json
{
  "standard_id": "K-IFRS 1109",
  "standard_name": "금융상품",
  "processed_at": "2025-03-04T00:00:00",
  "parents": [
    {
      "parent_id": "KIFRS1109_main_4.1",
      "section_heading": "4.1 금융자산의 분류",
      "children": ["KIFRS1109_main_4.1.1", "KIFRS1109_main_4.1.2"],
      "metadata": { "section_type": "main" }
    }
  ],
  "children": [
    {
      "chunk_id": "KIFRS1109_main_4.1.1",
      "parent_id": "KIFRS1109_main_4.1",
      "content": "금융자산은 후속적으로...",
      "metadata": {
        "standard_id": "K-IFRS 1109",
        "section_type": "main",
        "para_number": "4.1.1",
        "cross_refs": ["AG4B", "기준서 1032호"],
        "has_table": false,
        "has_example": false
      }
    }
  ]
}
```

---

## 전체 파이프라인 실행 (`pipeline.py`)

```python
# pipeline.py

from pathlib import Path
from kifrs_parser import pdf_to_markdown, extract_paragraphs
from kifrs_chunker import build_parent_child_chunks
import json
from datetime import datetime

def run_pipeline(pdf_path: str) -> None:
    """
    단일 K-IFRS PDF에 대해 전체 파이프라인 실행.
    """
    pdf_path = Path(pdf_path)
    standard_id = pdf_path.stem  # 파일명을 standard_id로 사용

    # 1. PDF → Markdown
    markdown_text = pdf_to_markdown(str(pdf_path))
    
    # 2~3. 섹션 감지 + 문단 분리 + 메타데이터 추출
    paragraphs = extract_paragraphs(markdown_text, standard_id)
    
    # 4~5. Parent-Child 청크 구성 + 문장 분리
    parents, children = build_parent_child_chunks(paragraphs)
    
    # 6. JSON 저장
    output = {
        "standard_id": standard_id,
        "processed_at": datetime.now().isoformat(),
        "parents": [p.__dict__ for p in parents],
        "children": [c.__dict__ for c in children],
    }
    
    output_path = Path("output/chunks") / f"{standard_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"완료: {len(parents)} parents, {len(children)} children → {output_path}")


if __name__ == "__main__":
    # data/raw/ 내 모든 PDF 처리
    for pdf_file in Path("data/raw").glob("*.pdf"):
        run_pipeline(str(pdf_file))
```

---

## 검증 체크리스트 (파이프라인 완료 후 Claude Code가 확인할 사항)

1. **섹션 분리 정확도**: main / ag / bc / ie 4개 섹션이 모두 분리됐는가?
2. **문단 번호 추출**: `para_number` 필드가 누락된 child 청크 비율은?
3. **상호참조 추출**: `cross_refs` 필드가 빈 배열인 비율이 지나치게 높지 않은가?
4. **청크 크기 분포**: child 청크 길이의 min/max/평균을 출력해 비정상적으로 큰 청크 확인
5. **Parent-Child 연결**: 모든 child의 `parent_id`가 실제 존재하는 parent와 매칭되는가?

검증용 스크립트를 `validate.py`로 별도 작성할 것.

---

## 이번 범위에서 제외된 것 (다음 단계)

- 임베딩 모델 선택 및 벡터 생성 (KURE-v1 vs BGE-M3 벤치마크)
- Qdrant 적재 및 컬렉션 스키마 설계
- BM25 인덱스 구축 (kiwipiepy 토크나이저 연동)
- 하이브리드 검색 (BM25 0.4 + Dense 0.6) 구현
- 상호참조 그래프 룩업 구현
