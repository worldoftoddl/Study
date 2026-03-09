import os

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.memory import MemorySaver

from Agent.config import LLM, SMALL_LLM
from Agent.tools import ALL_TOOLS, kifrs_search, calculator
from Agent.prompts import SYSTEM_PROMPT

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
backend = FilesystemBackend(root_dir=PROJECT_ROOT)

kifrs_expert = SubAgent(
    name="kifrs-expert",
    description=(
        "K-IFRS 회계기준서 개별 분석 에이전트. "
        "교차참조가 필요할 때 기준서별로 각각 스폰하세요.\n\n"
        "## 스폰 방법\n"
        "task에 반드시 다음을 명시하세요:\n"
        "1. 분석 대상 기준서 번호 (예: 1115호)\n"
        "2. 분석 관점/질문 (예: '계약체결 증분원가의 자산 인식 요건')\n"
        "3. 질의에서 추출한 관련 조건 (예: '일정 기간 경과 후 지급')\n\n"
        "## 스폰 예시\n"
        "교차참조가 필요한 질의라면 기준서별로 각각 스폰:\n"
        "- 서브에이전트 1: task='1115호 관점에서 계약체결 증분원가의 "
        "자산 인식 요건을 분석하라'\n"
        "- 서브에이전트 2: task='1037호 관점에서 이 거래의 부채 인식 "
        "시점을 분석하라. 특히 일정 기간 경과 후 지급 조건이 "
        "현재의무에 해당하는지 판단하라'"
    ),
    system_prompt=(
        "당신은 K-IFRS 회계기준서 분석 전문가입니다.\n"
        "메인 에이전트가 지정한 특정 기준서와 분석 관점에 집중하세요.\n\n"
        "## 작업 절차\n"
        "1. task에 명시된 기준서 번호로 kifrs_search를 호출합니다 "
        "(standard_id 필터 필수)\n"
        "2. task에 명시된 분석 관점에 따라 관련 문단을 선별합니다\n"
        "3. task에 포함된 조건(시점, 지급방식, 해지조항 등)이 "
        "기준서 요건을 충족하는지 판단합니다\n"
        "4. 분석 결과를 /memo/{기준서번호}_analysis.md에 저장합니다\n"
        "5. 최종 요약을 반환합니다 (판단 근거 문단 번호 필수 포함)\n\n"
        "## 원칙\n"
        "- 기준서 번호와 문단 번호를 반드시 인용하세요\n"
        "- 지정된 기준서 범위를 벗어난 판단은 하지 마세요 "
        "(교차참조 종합은 메인 에이전트가 수행합니다)\n"
        "- 조건 충족 여부가 불확실하면 '불확실' 로 명시하세요\n"
        "- 한국어로 답변하세요"
    ),
    tools=[kifrs_search, calculator],
    model=SMALL_LLM,
)

react_agent = create_deep_agent(
    model=LLM,
    tools=ALL_TOOLS,
    system_prompt=SYSTEM_PROMPT,
    subagents=[kifrs_expert],
    skills=["skills"],
    backend=backend,
    checkpointer=MemorySaver(),
)
