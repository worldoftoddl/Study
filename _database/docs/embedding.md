K-IFRS JSON 청크 파일을 KURE-v1으로 임베딩해서 Qdrant 로컬 파일 모드에 적재해줘.

## 환경
- 임베딩 모델: nlpai-lab/KURE-v1 (sentence-transformers)
- 벡터 DB: Qdrant 로컬 파일 모드 (qdrant-client 설치 완료)
- 입력: output/chunks/ 폴더 내 JSON 파일들

## Qdrant 설정
- 저장 경로: ./qdrant_storage
- 컬렉션명: kifrs_chunks
- vector_size: 1024
- distance: COSINE

## 적재 대상
Child 청크만 임베딩해서 적재 (Parent는 벡터 없이 payload로만 저장)

각 Qdrant point 구조:
- id: chunk_id를 정수 해시로 변환 (uuid도 가능)
- vector: content 임베딩 벡터
- payload:
    - chunk_id
    - parent_id
    - content
    - standard_id
    - section_type
    - para_number
    - cross_refs
    - has_table
    - has_example

Parent는 별도 컬렉션 kifrs_parents 에 payload only로 저장
(vector 없이 parent_id로 조회하기 위해)

## 구현 파일
- embedder.py: 임베딩 + Qdrant 적재 로직
- search_test.py: 적재 완료 후 검색 테스트용

## 주의사항
- 모델 최초 로딩 시 HuggingFace에서 다운로드 발생 (수GB)
- 배치 임베딩 사용할 것 (batch_size=32) — 메모리 효율
- 진행상황 tqdm으로 표시
- 적재 완료 후 총 포인트 수 출력해서 확인

## 적재 완료 후 검색 테스트 (search_test.py)
아래 쿼리 5개로 Child 검색 → Parent 조회 흐름 검증 (다양한 기준서 커버):
1. "유형자산 감가상각 방법" (IAS 16)
2. "금융자산의 기대신용손실 측정" (IFRS 9)
3. "수행의무 식별과 거래가격 배분" (IFRS 15)
4. "사용권자산과 리스부채의 최초 측정" (IFRS 16)
5. "연결재무제표 작성 시 지배력 판단 기준" (IFRS 10)

각 쿼리마다 출력:
- 매칭된 Child chunk_id, para_number, score
- 해당 Parent의 heading_text
- Child content 앞 100자