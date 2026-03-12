"""Research Agent - Standalone script for LangGraph deployment.

This module creates a deep research agent with custom tools and prompts
for conducting web research with strategic thinking and context management.
"""

import os
from datetime import datetime

from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
from deepagents import create_deep_agent

from research_agent.prompts import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from research_agent.kifrs_search import kifrs_search
from research_agent.tools import tavily_search, think_tool

# Limits
max_concurrent_research_units = 3
max_researcher_iterations = 3

# Get current date
current_date = datetime.now().strftime("%Y-%m-%d")

# Combine orchestrator instructions (RESEARCHER_INSTRUCTIONS only for sub-agents)
INSTRUCTIONS = (
    RESEARCH_WORKFLOW_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
        max_concurrent_research_units=max_concurrent_research_units,
        max_researcher_iterations=max_researcher_iterations,
    )
)

# Create research sub-agent
research_sub_agent = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
    "tools": [tavily_search, think_tool, kifrs_search],
}

# Model Gemini 3
# model = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.0)

# Model Claude 4.5
# ANTHROPIC_AUTH_TOKEN이 설정되면 게이트웨이 사용, 없으면 기본 ANTHROPIC_API_KEY 사용
_gateway_kwargs = {}
if os.getenv("ANTHROPIC_AUTH_TOKEN"):
    _gateway_kwargs["api_key"] = os.environ["ANTHROPIC_AUTH_TOKEN"]
    if os.getenv("ANTHROPIC_BASE_URL"):
        _gateway_kwargs["base_url"] = os.environ["ANTHROPIC_BASE_URL"]

model = init_chat_model(
    model="anthropic:claude-sonnet-4-5-20250929",
    temperature=0.0,
    **_gateway_kwargs,
)

# Create the agent
agent = create_deep_agent(
    model=model,
    tools=[tavily_search, think_tool, kifrs_search],
    system_prompt=INSTRUCTIONS,
    subagents=[research_sub_agent],
)
