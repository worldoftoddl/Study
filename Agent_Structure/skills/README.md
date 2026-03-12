# DeepAgent Skeleton

확장 가능한 DeepAgents 기반 에이전트 뼈대 프로젝트.

## 프로젝트 구조

```
agent_skeleton/
├── config/
│   ├── __init__.py
│   └── settings.py          # 환경변수, API 키 관리
├── core/
│   ├── __init__.py
│   ├── model_provider.py     # ABC 기반 모델 프로바이더 (갈아끼우기 가능)
│   └── agent_factory.py      # create_deep_agent 래핑 + 조립 팩토리
├── tools/
│   ├── __init__.py
│   ├── base.py               # 커스텀 도구 등록용 베이스/레지스트리
│   ├── web_search.py         # Tavily 웹 검색 도구
│   └── _template.py          # 새 도구 만들 때 복사할 템플릿
├── subagents/
│   ├── __init__.py
│   ├── registry.py           # 서브에이전트 정의 레지스트리
│   └── research_agent.py     # 예시: 리서치 서브에이전트
├── skills/
│   └── README.md             # 스킬 폴더 설명
├── main.py                   # FastAPI 서버 (추후 확장)
├── run_notebook.py           # ipynb에서 import해서 쓸 진입점
├── requirements.txt
└── README.md
```

## 핵심 설계 원칙

1. **모델 교체 가능**: `ModelProvider` ABC → `AnthropicProvider`, `OpenAIProvider` 등 구현체 교체
2. **도구 플러그인**: `tools/` 폴더에 함수 추가 → `ToolRegistry`에 등록 → 자동 주입
3. **서브에이전트 분리**: `subagents/` 폴더에 정의 → 메인 에이전트에 조립
4. **환경 분리**: ipynb 실험 ↔ FastAPI 서빙 동일 코어 사용

## Quick Start (노트북)

```python
from agent_skeleton.run_notebook import create_agent, run

agent = create_agent()
result = run(agent, "K-IFRS 제1001호에 대해 조사해줘")
print(result)
```

## Quick Start (FastAPI)

```bash
cd agent_skeleton
uvicorn main:app --reload
```
