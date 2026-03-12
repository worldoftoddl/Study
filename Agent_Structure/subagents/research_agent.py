"""
리서치 서브에이전트 예시.

메인 에이전트가 깊은 조사가 필요할 때 이 서브에이전트에 위임합니다.
서브에이전트는 독립된 컨텍스트에서 실행되므로,
메인 에이전트의 컨텍스트 윈도우를 오염시키지 않습니다.

새 서브에이전트 추가 방법:
    1. 이 파일을 복사
    2. config dict 수정
    3. subagent_registry.register(config) 호출
    4. subagents/__init__.py에 import 추가
"""
from .registry import subagent_registry

# 도구는 런타임에 tools/ 에서 가져와도 되고,
# 서브에이전트 전용 도구를 여기서 직접 정의해도 됩니다.

research_agent_config = {
    "name": "research-agent",
    "description": "심층 리서치가 필요한 질문을 조사합니다. 웹 검색과 자료 분석에 특화.",
    "system_prompt": (
        "당신은 전문 리서처입니다. "
        "주어진 주제에 대해 체계적으로 조사하고, "
        "핵심 내용을 구조화된 형태로 정리합니다. "
        "출처를 명확히 밝히세요."
    ),
    # tools는 agent_factory에서 주입 가능 (아래는 빈 리스트)
    # 실제로는 web_search 등을 넣어줍니다
    "tools": [],
    # model은 생략하면 메인 에이전트의 모델을 상속
    # "model": "openai:gpt-4o",
}

subagent_registry.register(research_agent_config)
