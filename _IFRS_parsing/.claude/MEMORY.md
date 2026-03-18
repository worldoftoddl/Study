# K-IFRS RAG Pipeline Project Memory

## Project Overview
- K-IFRS(한국채택국제회계기준) 문서에 대한 RAG(Retrieval-Augmented Generation) 파이프라인
- Python 3.12, `.venv` 가상환경 (`python3`만 사용)
- WSL2 Linux 환경

## Architecture
- **Vector DB**: PostGreSQL
- **Embedding**: Upstage Solar (`solar-embedding-1-large`, 4096차원)
- **Reranker**: BGE (`dragonkue/bge-reranker-v2-m3-ko`) 또는 Cohere API
- **Korean NLP**: kiwipiepy (형태소 분석)
- **Framework**: LangChain + LangGraph

## Key Directories
- `search/` — 검색 엔진 모듈 (11개 .py)
- `pipeline/` — 문서 처리 (chunker, terms_index)
- `output/chunks/` — 청크 JSON (63개 기준서)
- `data/raw/` — 원본 PDF/DOCX (IFRS, 감사기준, 외부감사법)
- `docs/` — 아키텍처 문서

## Status (as of NEXT_SESSION.md)
- 교차참조 파이프라인, payload 적재, 메타데이터 검색 고도화, terms_index 확장 완료
- 다음: 파이프라인 오케스트레이션 통합, 평가 벤치마크 생성
