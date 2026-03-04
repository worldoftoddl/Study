K-IFRS 기준서 PDF를 파싱해서 Parent-Child 청크 구조의 JSON으로 변환하는 파이프라인을 구현해줘.

## 목표
`IFRS + 개념체계/` 안의 PDF 파일들을 읽어서 `output/chunks/{파일명}.json`으로 저장

## 기술 스택
- pymupdf4llm 0.3.4 (PDF → Markdown 변환)
- kiwipiepy (500자 초과 청크 문장 분리)

## K-IFRS PDF 구조 이해
하나의 PDF 안에 4개 섹션이 존재하고 각각 문단 번호 체계가 다름:
- 기준서 본문 (MAIN): `1`, `4.1.2`, `한2.1` 패턴
- 적용지침 (AG): `AG1`, `AG72` 패턴
- 결론도출근거 (BC): `BC1`, `BC45` 패턴
- 사례 (IE): `IE1`, `IE12` 패턴

헤딩에 '적용지침'/'결론도출근거'/'사례' 텍스트가 등장하면 해당 섹션 시작으로 판단.

## PDF → Markdown 변환 주의사항
- `page_chunks=False` 필수 (K-IFRS 문단이 페이지 경계를 넘어 이어지므로)
- Layout 모드 사용 금지 (page_chunks 무시되는 버그 있음)
- 변환 결과를 `output/raw_md/`에 .md로 중간 저장할 것

## 청킹 구조

Parent: Markdown 헤딩(## ###) 단위 or 섹션 타입 변경 시 새로 시작
Child: 문단 번호로 시작하는 개별 문단

Child 데이터 모델:
{
  "chunk_id": "KIFRS1109_main_4.1.1",   # {standard_id}_{section_type}_{para_number}
  "parent_id": "KIFRS1109_main_4.1",
  "content": "문단 텍스트",
  "metadata": {
    "standard_id": "K-IFRS 1109",
    "section_type": "main",             # main / ag / bc / ie
    "para_number": "4.1.1",             # 추출 실패 시 null
    "cross_refs": ["AG72", "기준서 1032호"],  # 본문 내 상호참조 패턴 추출
    "has_table": false,
    "has_example": false
  }
}

## 출력 JSON 형식
{
  "standard_id": "K-IFRS 1109",
  "processed_at": "ISO 형식",
  "parents": [...],
  "children": [...]
}

## 검증 스크립트 (validate.py)
파이프라인 완료 후 아래 항목 출력:
1. 전체 parent / child 수
2. 섹션별(main/ag/bc/ie) child 수
3. para_number 유실 비율 (null인 child / 전체)
4. `한 ` 으로 시작하는 content 중 para_number가 null인 것 (한X.X 유실 의심)
5. child 텍스트 길이 min/max/평균
6. cross_refs 비어있는 child 비율

## 실행 순서
1. PDF 1개만 먼저 돌려서 raw_md 결과 확인 후 진행
2. 문단 번호 정규식이 실제 텍스트에 맞는지 확인
3. 전체 배치 실행

---

## 구현 현황

### 생성된 파일
- `kifrs_chunker.py` — 메인 파이프라인 (PDF→MD→JSON)
- `validate.py` — 6가지 검증 항목 출력
- `output/raw_md/` — 중간 마크다운 캐시 (재실행 시 PDF 변환 스킵)
- `output/chunks/` — 최종 JSON 출력

### CLI 사용법
```bash
# 단일 PDF 테스트
python kifrs_chunker.py --single "IFRS + 개념체계/시행중_K-IFRS_제1016호_유형자산(...).pdf"
# 전체 배치
python kifrs_chunker.py
# 검증
python validate.py
python validate.py --file "output/chunks/시행중_K-IFRS_제1016호_유형자산(...).json"
```

### 적용된 후처리 필터
1. **저작권/영문 notice 제거**: IFRS Foundation, All rights reserved, Westferry Circus 등 포함 child 필터
2. **50자 미만 content 제거**: 페이지 번호(`- 25`), 짧은 잔여 텍스트 등 노이즈 제거
3. **cross_refs 자기참조 제거**: 문단 BC1의 cross_refs에서 'BC1' 자체를 제외
4. **한X.X 문단번호 복원**: para_number=null이고 content가 `한\d+`로 시작하면 자동 복원

### K-IFRS 1016 테스트 결과 (2026-03-04)
- Parents: 44, Children: 244
- main=72, ag=0(정상-1016에 AG 없음), bc=172, ie=0
- para_number null 비율: 8.6% (목표 <20%)
- content 길이: min=50, max=6,245, avg=345.4

### 확인된 이슈 / 개선 여지
- main 정규식에 한글 lookahead `(?=[가-힣(])` 추가하여 영문 주소 오탐(7 Westferry Circus) 방지 완료
- 표준번호 오탐: `1105호가 적용하지 않는다` → 문단 1105로 오인 (1건, minor)
- cross_refs 패턴이 `제\d+호` 형태를 아직 캡처하지 않음 → 추후 개선 가능