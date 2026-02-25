# prompts.py
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langsmith import Client

client = Client()

rewrite_prompt = PromptTemplate.from_template("""당신은 한국 세법 전문가입니다...""")

hallucination_check_prompt = ChatPromptTemplate.from_messages([...])

# LangSmith에서 pull하는 것들도 여기서
relevance_check_prompt = client.pull_prompt('langchain-ai/rag-document-relevance')
generate_prompt = client.pull_prompt("rlm/rag-prompt")
helpfulness_prompt = client.pull_prompt("langchain-ai/rag-answer-helpfulness")