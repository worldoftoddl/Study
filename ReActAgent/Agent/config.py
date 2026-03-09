from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()

SMART_LLM = ChatAnthropic(
    model="claude-opus-4-5-20251101",
    temperature=0,
)
LLM = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0,
)
SMALL_LLM = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0,
)
