"""agent/prompts.py -- 모든 프롬프트 정의 (인라인 + LangSmith lazy-pull)."""

import functools

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate

from agent.config import get_langsmith_client

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Self-RAG 프롬프트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REWRITE_PROMPT = PromptTemplate.from_template("""
당신은 한국 세법 전문가입니다.
사용자의 질문을 소득세법 문서 검색에 최적화된 형태로 다시 작성하세요.

규칙:
1. 일상 용어를 법률 용어로 변환 (예: 월급 → 근로소득)
2. 모호한 표현을 구체화
3. 검색에 필요한 핵심 키워드 포함

예시:
    소득 관련
    '월급, 급여 -> 근로소득',
    '집 팔 때 세금, 부동산 양도 -> 양도소득세',
    '이자, 배당 -> 금융소득',
    '프리랜서 수입, 외주 -> 사업소득',
    '강연료, 원고료 -> 기타소득',

    공제 관련
    '부양가족 공제 -> 인적공제',
    '카드 공제 -> 신용카드 소득공제',
    '의료비 공제 -> 의료비 세액공제',

    일반 표현
    '세금 돌려받기 -> 환급',
    '세금 신고 -> 확정신고',
    '직장인 연말 세금 -> 연말정산'

원본 질문: {query}
Retrieve 최적화된 질문:
""")


HALLUCINATION_CHECK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 AI 답변의 정확성을 평가하는 검증자입니다.

주어진 context(참고 문서)만을 기준으로, 생성된 답변이 hallucination(환각)을 포함하는지 판단하세요.

평가 기준:
1. 답변의 모든 정보가 context에 근거하는가?
2. context에 없는 내용을 지어내지 않았는가?
3. 숫자, 날짜, 법조항 등 구체적 정보가 정확한가?

Score 기준:
- 1: 답변이 context에 충실함 (hallucination 없음)
- 0: 답변에 context에 없는 정보가 포함됨 (hallucination 있음)
"""),
    ("human", """
Context:
{context}

생성된 답변:
{answer}

위 답변이 context에 충실한지 평가해주세요.
""")
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 부동산세 프롬프트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TAX_BASE_EQUATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "사용자의 질문에서 과세표준을 계산하는 방법을 수식으로 나타내주세요. 부연설명 없이 수식만 리턴해주세요"),
    ("human", "{tax_base_equation_information}")
])

TAX_MARKET_RATIO_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "아래 정보를 기반으로 공정시장 가액비율을 계산해주세요\n\nContext:\n{context}"),
    ("human", "{query}")
])

TAX_BASE_CALCULATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
당신의 역할은 종합부동산세 **과세표준만** 계산하는 것입니다.
세율 적용, 세액 계산은 절대 하지 마세요.
제공되지 않은 정보는 절대 추측하지 마세요.

## 과세표준 계산 공식
{tax_base_equation}

## 공제금액 (반드시 아래 값을 사용할 것)
{tax_deduction}

## 공정시장가액비율 (반드시 아래 값을 사용할 것)
{market_ratio}

## 출력 형식
1. 납세의무자 유형 판단
2. 적용할 공제금액과 공정시장가액비율 명시
3. 과세표준 계산 과정
4. 최종 과세표준 금액

과세표준 계산까지만 하고 멈추세요."""),
    ("human", "사용자 주택 공시가격 정보: {query}")
])

TAX_CALCULATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신의 역할은 종합부동산세 **세액만** 계산하는 것입니다.
제공된 과세표준과 세율표만 사용하세요.
제공되지 않은 정보는 절대 추측하지 마세요.
절세 팁, 추가 조언 등은 작성하지 마세요.

## 세율표 (반드시 아래 세율만 사용할 것)
{context}

## 출력 형식
1. 납세의무자 유형 확인 (주택 수 기준)
2. 적용할 세율표 선택
3. 과세표준 구간별 누진 계산 과정
4. 최종 종합부동산세 산출세액

세액 계산까지만 하고 멈추세요."""),
    ("human", """과세표준과 사용자가 소지한 주택의 수가 아래와 같을 때 종합부동산세를 계산해 주세요.

과세표준: {tax_base}
주택 수: {query}""")
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LangSmith lazy-pull 프롬프트 (import 시 네트워크 호출 방지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@functools.cache
def get_relevance_check_prompt():
    """문서 관련성 평가 프롬프트 (langchain-ai/rag-document-relevance)."""
    return get_langsmith_client().pull_prompt("langchain-ai/rag-document-relevance")


@functools.cache
def get_generate_prompt():
    """RAG 답변 생성 프롬프트 (rlm/rag-prompt)."""
    return get_langsmith_client().pull_prompt("rlm/rag-prompt")


@functools.cache
def get_helpfulness_prompt():
    """답변 유용성 평가 프롬프트 (langchain-ai/rag-answer-helpfulness)."""
    return get_langsmith_client().pull_prompt("langchain-ai/rag-answer-helpfulness")
