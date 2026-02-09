# nodes.py
from config import retriever, llm, small_llm
from state import AgentState
from prompts import (
    rewrite_prompt, hallucination_check_prompt,
    relevance_check_prompt, generate_prompt, helpfulness_prompt
)

def retrieve(state: AgentState):
    docs = retriever.invoke(state['query'])
    return {'context': docs}

def rewrite(state: AgentState):
    ...

def generate(state: AgentState):
    ...

# conditional edge 함수들도 여기에
def doc_relevance_check_grader(state: AgentState) -> Literal['relevant', 'irrelevant']:
    ...

def hallucination_check(state: AgentState) -> Literal['hallucinated', 'not hallucinated']:
    ...