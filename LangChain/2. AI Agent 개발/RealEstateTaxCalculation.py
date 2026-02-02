from langchain_upstage import UpstageEmbeddings
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic
from langsmith import Client
from typing_extensions import TypedDict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_community.tools import TavilySearchResults
from datetime import date
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv

load_dotenv()

embedding = UpstageEmbeddings(model="solar-embedding-1-large")

database = Chroma(
    embedding_function = embedding,
    collection_name = 'real_estate_tax',
    persist_directory = './real_estate_tax_collection'
)
retriever = database.as_retriever(
    search_type= 'mmr',
    search_kwargs={
        'k': 4,
        'fetch_k': 10,
        'lambda_mult': 0.6
    }
)

client = Client()

smart_llm = ChatAnthropic(
    model= 'claude-opus-4-5-20251101',
    temperature= 0.1
)

llm = ChatAnthropic(
    model= 'claude-sonnet-4-5-20250929',
    temperature= 0.1
)

small_llm = ChatAnthropic(
    model= 'claude-haiku-4-5-20251001',
    temperature= 0.1
)

class AgentState(TypedDict):
    query: str # 사용자 질문
    answer: str # 세율
    tax_base_equation: str # 과세표준 계산 수식 
    tax_deduction: str # 공제액 
    market_ratio: str # 공정시장가액비율
    tax_base: str # 과세표준 계산
    

generate_prompt = client.pull_prompt("rlm/rag-prompt")

tax_base_retrieval_chain = (
    {'context': retriever, 'question': RunnablePassthrough()} 
    | generate_prompt 
    | small_llm 
    | StrOutputParser()
)

tax_base_equation_prompt = ChatPromptTemplate.from_messages([
    ('system', '사용자의 질문에서 과세표준을 계산하는 방법을 수식으로 나타내주세요. 부연설명 없이 수식만 리턴해주세요'),
    ('human', '{tax_base_equation_information}')
])

tax_base_equation_chain = (
    {'tax_base_equation_information': RunnablePassthrough()}
    | tax_base_equation_prompt
    | small_llm
    | StrOutputParser()
)

tax_base_chain = {'tax_base_equation_information' : tax_base_retrieval_chain} | tax_base_equation_chain

def get_tax_base_equation(state: AgentState) -> AgentState:
    """
    종합부동산세 과세표준을 계산하는 수식을 가져옵니다.
    `node`로 활용되기 때문에 `state`를 인자로 받지만, 
    고정된 기능을 수행하기 때문에 `state`를 활용하지는 않습니다.

    Args:
        state (AgentState): 현재 에이전트의 상태를 나타내는 객체입니다.

    Returns:
        AgentState: 'tax_base_equation' 키를 포함하는 새로운 `state`를 반환합니다.
    """
    # 과세표준을 계산하는 방법을 묻는 질문을 정의합니다.
    tax_base_equation_question = '주택에 대한 종합부동산세 계산시 과세표준을 계산하는 방법을 수식으로 표현해서 알려주세요'
    
    # tax_base_chain을 사용하여 질문을 실행하고 결과를 얻습니다.
    tax_base_equation = tax_base_chain.invoke(tax_base_equation_question)
    
    # state에서 'tax_base_equation' 키에 대한 값을 반환합니다.
    return {'tax_base_equation': tax_base_equation}

tax_deduction_chain = (
    {
        'context': RunnableLambda(lambda x: x['search_query']) | retriever,
        'question': RunnableLambda(lambda x: x['full_prompt']) 
    } 
    | generate_prompt 
    | small_llm 
    | StrOutputParser()
)

def get_tax_deduction(state: AgentState) -> AgentState:
    """
    종합부동산세 공제금액에 관한 정보를 가져옵니다.
    `node`로 활용되기 때문에 `state`를 인자로 받지만, 
    고정된 기능을 수행하기 때문에 `state`를 활용하지는 않습니다.

    Args:
        state (AgentState): 현재 에이전트의 state를 나타내는 객체입니다.

    Returns:
        AgentState: 'tax_deduction' 키를 포함하는 새로운 state를 반환합니다.
    """
    # 공제금액을 묻는 질문을 정의합니다.
    tax_deduction_question ={
    'search_query': '납세의무자 유형별 종합부동산세 공제금액',
    'full_prompt': '종합부동산세 공제금액을 납세의무자 유형별로 정리하세요. 반드시 다음 형식으로...'
}
    
    # tax_deduction_chain을 사용하여 질문을 실행하고 결과를 얻습니다.
    tax_deduction = tax_deduction_chain.invoke(tax_deduction_question)

    # state에서 'tax_deduction' 키에 대한 값을 반환합니다.
    return {'tax_deduction': tax_deduction}

tavily_search_tool = TavilySearchResults(
    max_results=7,
    search_depth='advanced',
    include_answer=True,
    include_raw_content=True,
    include_images=False
    # include_domains=
    # exclude_domains=
    # name=
    # description=
    # args_schema=
)

tax_market_ratio_prompt = ChatPromptTemplate.from_messages([
    ('system', f'아래 정보를 기반으로 공정시장 가액비율을 계산해주세요\n\nContext:\n{{context}}'),
    ('human', '{query}')
])

def get_market_ratio(state: AgentState) -> AgentState:
    """
    web 검색을 통해 주택 공시가격에 대한 공정시장가액비율을 가져옵니다.
    `node`로 활용되기 때문에 `state`를 인자로 받지만, 
    고정된 기능을 수행하기 때문에 `state`를 활용하지는 않습니다.
    
    Args:
        state (AgentState): 현재 에이전트의 state를 나타내는 객체입니다.

    Returns:
        AgentState: 'market_ratio' 키를 포함하는 새로운 state를 반환합니다.
    """
    # 오늘 날짜에 해당하는 공정시장가액비율을 묻는 쿼리를 정의합니다.
    query = f'오늘 날짜:({date.today()})에 해당하는 주택 공시가격 공정시장가액비율은 몇%인가요?'
    
    # tavily_search_tool을 사용하여 쿼리를 실행하고 컨텍스트를 얻습니다.
    context = tavily_search_tool.invoke(query)
    
    # tax_market_ratio_chain을 구성하여 쿼리와 컨텍스트를 처리합니다.
    tax_market_ratio_chain = (
        tax_market_ratio_prompt
        | small_llm
        | StrOutputParser()
    )
    
    # tax_market_ratio_chain을 사용하여 시장 비율을 계산합니다.
    market_ratio = tax_market_ratio_chain.invoke({'context': context, 'query': query})
    
    # state에서 'market_ratio' 키에 대한 값을 반환합니다.
    return {'market_ratio': market_ratio}

tax_base_calculate_prompt = ChatPromptTemplate.from_messages(
    [
        ('system', """
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
        ('human', '사용자 주택 공시가격 정보: {query}')
    ]
)

def calculate_tax_base(state: AgentState)-> dict[str, str]:
    tax_base_equation = state['tax_base_equation']
    tax_deduction = state['tax_deduction']
    market_ratio = state['market_ratio']
    query = state['query']
    
    tax_base_calculate_chain = (
        tax_base_calculate_prompt
        | llm
        | StrOutputParser()
    )
    
    tax_base = tax_base_calculate_chain.invoke({
        'tax_base_equation': tax_base_equation,
        'tax_deduction': tax_deduction,
        'market_ratio': market_ratio,
        'query': query
    })

    
    return {'tax_base': tax_base}

tax_calculate_prompt = ChatPromptTemplate.from_messages([
    ('system', """당신의 역할은 종합부동산세 **세액만** 계산하는 것입니다.
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
    ('human', """과세표준과 사용자가 소지한 주택의 수가 아래와 같을 때 종합부동산세를 계산해 주세요.

과세표준: {tax_base}
주택 수: {query}""")
])

tax_calculate_chain = (
    tax_calculate_prompt
    | llm
    | StrOutputParser()
)

def calculate_tax(state: AgentState) -> dict[str, str]:
    query = state['query']
    tax_base = state['tax_base']
    context = retriever.invoke('종합부동산세 제9조 주택 세율표 2주택 3주택')

    tax = tax_calculate_chain.invoke({
        'query': query,
        'tax_base': tax_base,
        'context': context
    })
    
    return {'answer': tax}

graph_builder = StateGraph(AgentState)


graph_builder.add_node('get_tax_base_equation', get_tax_base_equation)
graph_builder.add_node('get_tax_deduction', get_tax_deduction)
graph_builder.add_node('get_market_ratio', get_market_ratio)
graph_builder.add_node('calculate_tax_base', calculate_tax_base)
graph_builder.add_node('calculate_tax', calculate_tax)


graph_builder.add_edge(START, 'get_tax_base_equation')
graph_builder.add_edge(START, 'get_tax_deduction')
graph_builder.add_edge(START, 'get_market_ratio')

graph_builder.add_edge('get_tax_base_equation', 'calculate_tax_base')
graph_builder.add_edge('get_tax_deduction', 'calculate_tax_base')
graph_builder.add_edge('get_market_ratio', 'calculate_tax_base')


graph_builder.add_edge('calculate_tax_base', 'calculate_tax')
graph_builder.add_edge('calculate_tax', END)


graph = graph_builder.compile()
