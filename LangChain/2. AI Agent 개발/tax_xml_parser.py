"""
국가법령정보센터 Open API XML 기반 법률 파서
=============================================
API XML의 구조화된 조-항-호-목 태그를 직접 활용하므로
정규식 파싱이 불필요하고, 수식도 텍스트로 온전히 보존됨.

사용법:
    from tax_xml_parser import parse_xml_law
    docs = parse_xml_law('incomelaw.xml', source='소득세법')
"""

import re
import xml.etree.ElementTree as ET
from langchain_core.documents import Document


# ── 항번호 원문자 → 정수 매핑 ──
_PARA_MAP = {
    '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
    '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
    '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
    '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20,
}


# ── 분수/다단 수식 → 자연어 교체 (┌...┘ 부분만 교체) ──
# key: (조문번호, 항번호, 호번호 or None)
# value: 교체할 자연어 수식 텍스트
FORMULA_OVERRIDES = {
    # 제22조③: 임원 퇴직소득 한도 (항 본문 수식)
    ('제22조', 3, None): (
        "[산식]\n"
        "한도액 = A + B\n"
        "A = 2019.12.31부터 소급하여 3년간(2012.1.1~2019.12.31, "
        "3년 미만이면 해당 근무기간) 지급받은 총급여의 연평균환산액 "
        "× 1/10 × 근무월수/12 × 3\n"
        "B = 퇴직한 날부터 소급하여 3년간(2020.1.1 이후 근무기간, "
        "3년 미만이면 해당 근무기간) 지급받은 총급여의 연평균환산액 "
        "× 1/10 × 근무월수/12 × 2"
    ),
    # 제65조⑧ 3호: 중간예납추계액 (호 수식)
    ('제65조', 8, '3'): (
        "[산식]\n"
        "중간예납추계액 = (종합소득산출세액 / 2) "
        "- (중간예납기간 종료일까지의 종합소득에 대한 "
        "감면세액·세액공제액, 토지등 매매차익 예정신고 "
        "산출세액, 수시부과세액 및 원천징수세액)"
    ),
    # 제81조의9② 1호: 현금영수증 미가입 가산세 (호 수식)
    ('제81조의9', 2, '1'): (
        "[산식]\n"
        "가산세 = A × (B / C) × 1/100\n"
        "A: 해당 과세기간의 수입금액(현금영수증가맹점 가입대상인 "
        "업종의 수입금액만 해당하며, 제163조에 따른 계산서 및 "
        "「부가가치세법」 제32조에 따른 세금계산서 발급분 등 "
        "대통령령으로 정하는 수입금액은 제외한다)\n"
        "B: 미가입기간(제162조의3제1항에 따른 가입기한의 다음 날부터 "
        "가입일 전날까지의 일수를 말하며, 미가입기간이 2개 이상의 "
        "과세기간에 걸쳐 있으면 각 과세기간별로 미가입기간을 적용한다)\n"
        "C: 365(윤년에는 366으로 한다)"
    ),
}


# ============================================================
#  Public API
# ============================================================

def parse_xml_law(
    xml_path: str,
    source: str = "소득세법",
    min_chunk_length: int = 200,
) -> list[Document]:
    """
    국가법령정보센터 API XML → LangChain Document 리스트.

    Parameters
    ----------
    xml_path : str
        XML 파일 경로 (lawService.do?target=law&type=XML 응답)
    source : str
        법률명 (metadata['source']에 기록)
    min_chunk_length : int
        호 분할 시 최소 청크 길이. 이 길이 미만이면 다음 호와 병합.

    Returns
    -------
    list[Document]
        page_content + metadata 가 채워진 Document 리스트.
        삭제 조문·삭제 항은 제외됨.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 장/절/관 추적 변수
    cur_chapter = None       # 제○장
    cur_section = None       # 제○절
    cur_subsection = None    # 제○관

    all_docs: list[Document] = []

    for jo in root.find('조문').findall('조문단위'):
        jo_type = jo.findtext('조문여부', '').strip()

        # ────────────────────────────────────
        #  전문(편/장/절/관 헤더) → 위치 추적만
        # ────────────────────────────────────
        if jo_type == '전문':
            raw = _clean(jo.findtext('조문내용', ''))
            m_ch  = re.search(r'제\d+장(?:의\d+)?', raw)
            m_sec = re.search(r'제\d+절', raw)
            m_sub = re.search(r'제\d+관', raw)
            if m_ch:
                cur_chapter = m_ch.group()
                cur_section = None
                cur_subsection = None
            elif m_sec:
                cur_section = m_sec.group()
                cur_subsection = None
            elif m_sub:
                cur_subsection = m_sub.group()
            continue

        if jo_type != '조문':
            continue

        # ────────────────────────────────────
        #  조문 기본 정보
        # ────────────────────────────────────
        jo_num    = jo.findtext('조문번호', '').strip()
        jo_branch = jo.findtext('조문가지번호', '').strip()
        jo_title  = _clean(jo.findtext('조문제목', ''))
        eff_date  = jo.findtext('조문시행일자', '').strip()
        changed   = jo.findtext('조문변경여부', '').strip()  # Y/N

        # 조문 식별자: "제1조" 또는 "제1조의2"
        article_id = f"제{jo_num}조" + (f"의{jo_branch}" if jo_branch else "")
        title_str  = f"({jo_title})" if jo_title else None
        header     = f"{article_id}{title_str}" if title_str else article_id

        # 삭제 조문 스킵
        raw_content = _clean(jo.findtext('조문내용', ''))
        if _is_deleted(raw_content, jo_title):
            continue

        # 공통 메타데이터
        base_meta = {
            'source':         source,
            'chapter':        cur_chapter,
            'section':        cur_section,
            'subsection':     cur_subsection,
            'article':        article_id,
            'title':          title_str,
            'effective_date': eff_date,
        }

        # ────────────────────────────────────
        #  항이 없는 조문 → 단일 Document
        # ────────────────────────────────────
        hangs = jo.findall('항')
        if not hangs:
            body = _strip_header(raw_content)
            meta = {**base_meta, 'paragraph': None}
            all_docs.append(Document(page_content=body, metadata=meta))
            continue

        # ────────────────────────────────────
        #  항이 있는 조문 → 항별 처리
        # ────────────────────────────────────
        for hang in hangs:
            para_sym = _clean(hang.findtext('항번호', '')).strip()
            para_num = _PARA_MAP.get(para_sym)
            para_body = _clean(hang.findtext('항내용', ''))

            # ── 삭제된 항 스킵 ──
            if _is_deleted_paragraph(para_body):
                continue

            para_meta = {**base_meta, 'paragraph': para_num}
            hos = hang.findall('호')

            if not hos:
                # 호가 없는 항 → 단일 Document
                # 분수 수식 교체 (제22조③ 등)
                para_body = _replace_box_formula(para_body, (article_id, para_num, None))
                content = f"{header} {para_body}"
                all_docs.append(Document(page_content=content, metadata=para_meta))
            else:
                # 호가 있는 항 → min_chunk_length 기반 그룹핑
                ho_items = [h for h in (_build_ho(ho) for ho in hos) if h is not None]
                # 분수 수식 교체 (제65조⑧3호, 제81조의9②1호 등)
                ho_items = [
                    (num, _replace_box_formula(txt, (article_id, para_num, num)))
                    for num, txt in ho_items
                ]
                # 항 본문에도 수식이 있을 수 있음
                para_body = _replace_box_formula(para_body, (article_id, para_num, None))
                intro    = f"{header} {para_body}"
                split_header = f"{header} {para_sym}"

                chunks = _group_hos(intro, split_header, ho_items,
                                    para_meta, min_chunk_length)
                all_docs.extend(chunks)

    return all_docs


# ============================================================
#  Internal helpers
# ============================================================

def _clean(text: str) -> str:
    """
    XML 텍스트 정리.
    
    - img 태그 제거 (수식 박스 텍스트는 보존)
    - 개정·신설·삭제 이력 태그 제거
    - 박스 문자(┌┐└┘─│)는 유지 → 분수 수식 레이아웃 보존
    - 연속 공백/탭 정리
    """
    if not text:
        return ""
    # img 태그 (수식 이미지 링크) 제거  —  박스 텍스트는 보존
    text = re.sub(r'<img\s[^>]*>', '', text)
    text = text.replace('</img>', '')
    # 개정·신설·삭제 이력 태그 제거
    text = re.sub(r'<(?:개정|신설|삭제|시행일)[^>]*>', '', text)
    # 탭 → 공백 변환 (들여쓰기 정리하되 줄바꿈은 보존)
    text = text.replace('\t', ' ')
    # 각 줄 내 연속 공백 축소 (줄 구조는 보존)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = re.sub(r'  +', ' ', line).strip()
        if line:
            cleaned.append(line)
    text = '\n'.join(cleaned)
    return text.strip()


def _replace_box_formula(text: str, key: tuple) -> str:
    """
    텍스트 내 박스 수식(┌...┘)을 FORMULA_OVERRIDES의 자연어 수식으로 교체.
    key가 FORMULA_OVERRIDES에 없거나, ┌...┘가 없으면 원문 그대로 반환.
    """
    if key not in FORMULA_OVERRIDES:
        return text
    if '┌' not in text:
        return text
    replacement = FORMULA_OVERRIDES[key]
    return re.sub(r'┌[^┘]*┘', replacement, text, flags=re.DOTALL)


def _strip_header(content: str) -> str:
    """조문내용에서 '제○조(제목)' 헤더를 제거하고 본문만 반환."""
    body = re.sub(r'^제\d+조(?:의\d+)?(?:\([^)]*\))?\s*', '', content).strip()
    return body if body else content


def _is_deleted(content: str, title: str) -> bool:
    """삭제된 조문인지 판별."""
    if title == '삭제':
        return True
    if re.match(r'^제\d+조(?:의\d+)?\s*삭제', content):
        return True
    return False


def _is_deleted_paragraph(para_body: str) -> bool:
    """삭제된 항인지 판별. '⑤ 삭제 <2013.1.1>' 등"""
    stripped = para_body.strip()
    # 원문자 뒤에 "삭제" + 선택적 날짜태그만 남은 경우
    if re.match(r'^[①-⑳]?\s*삭제\s*(<[^>]*>)?\s*$', stripped):
        return True
    return False


def _build_ho(ho_el) -> tuple[str, str] | None:
    """
    호 Element → (호번호, 호+목 합친 텍스트) 튜플.
    삭제된 호는 None 반환.
    """
    ho_num_raw = ho_el.findtext('호번호', '').strip().rstrip('. ')
    # "8의2." → "8의2"
    ho_num = re.match(r'(\d+(?:의\d+)?)', ho_num_raw)
    ho_num = ho_num.group(1) if ho_num else ho_num_raw

    ho_text = _clean(ho_el.findtext('호내용', ''))

    # 삭제된 호 스킵: "10. 삭제 <2013.1.1>" 등
    if re.match(r'^\d+(?:의\d+)?\.\s*삭제', ho_text):
        return None

    # 하위 목 텍스트 합치기
    for mok in ho_el.findall('목'):
        mok_text = _clean(mok.findtext('목내용', ''))
        if mok_text:
            ho_text += '\n' + mok_text

    return ho_num, ho_text


def _group_hos(
    intro: str,
    split_header: str,
    ho_items: list[tuple[str, str]],
    base_meta: dict,
    min_length: int,
) -> list[Document]:
    """
    호 리스트를 min_length 기준으로 그룹핑하여 Document 리스트 생성.

    - intro: 항 전체 텍스트 (헤더 + 항 본문)  → 첫 청크 시작점
    - split_header: 2번째 청크부터 붙일 헤더 (예: "제2조(납세의무) ②")
    - ho_items: [(호번호, 호텍스트), ...]
    """
    if not ho_items:
        return [Document(page_content=intro, metadata=base_meta)]

    docs: list[Document] = []
    chunk = intro
    ho_start = None
    ho_end   = None

    for ho_num, ho_text in ho_items:
        # 현재 청크가 충분히 길면 → 잘라서 Document 생성
        if len(chunk) >= min_length and ho_start is not None:
            docs.append(Document(
                page_content=chunk,
                metadata={**base_meta, 'ho_range': f"{ho_start}~{ho_end}호"},
            ))
            chunk    = split_header + "\n" + ho_text
            ho_start = ho_num
            ho_end   = ho_num
        else:
            chunk += '\n' + ho_text
            if ho_start is None:
                ho_start = ho_num
            ho_end = ho_num

    # 마지막 청크
    if chunk:
        if ho_start is not None:
            docs.append(Document(
                page_content=chunk,
                metadata={**base_meta, 'ho_range': f"{ho_start}~{ho_end}호"},
            ))
        else:
            docs.append(Document(page_content=chunk, metadata=base_meta))

    return docs