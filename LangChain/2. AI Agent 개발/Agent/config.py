from langchain_upstage import UpstageEmbeddings
from langchain_anthropic import ChatAnthropic
from langsmith import Client
from dotenv import load_dotenv

load_dotenv()

EMBEDDING = UpstageEmbeddings(model="solar-embedding-1-large")
CLIENT = Client()
SMART_LLM = ChatAnthropic(
    model='claude-opus-4-5-20251101',
    temperature= 0
)
LLM = ChatAnthropic(
    model='claude-sonnet-4-5-20250929',
    temperature= 0
)
SMALL_LLM = ChatAnthropic(
    model='claude-haiku-4-5-20251001',
    temperature= 0
)

