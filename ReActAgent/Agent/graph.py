from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

from Agent.config import LLM
from Agent.tools import ALL_TOOLS
from Agent.prompts import SYSTEM_PROMPT

checkpointer = MemorySaver()

react_agent = create_deep_agent(
    model=LLM,
    tools=ALL_TOOLS,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)
