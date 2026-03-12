"""
FastAPI 서버 — 추후 확장용.

현재는 최소한의 엔드포인트만 제공합니다.
ipynb에서 충분히 검증한 뒤 이쪽으로 옮기세요.

실행:
    uvicorn agent_skeleton.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .core.agent_factory import build_agent
from .run_notebook import arun


# ── 앱 상태 (에이전트 인스턴스 캐싱) ──
_agent_cache: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 기본 에이전트를 미리 빌드합니다."""
    _agent_cache["default"] = build_agent(
        system_prompt="당신은 도움이 되는 AI 어시스턴트입니다."
    )
    yield
    _agent_cache.clear()


app = FastAPI(
    title="DeepAgent API",
    version="0.1.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "api-default"


class ChatResponse(BaseModel):
    response: str
    thread_id: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """에이전트에 메시지를 보내고 응답을 받습니다."""
    agent = _agent_cache["default"]
    response_text = await arun(agent, req.message, thread_id=req.thread_id)
    return ChatResponse(response=response_text, thread_id=req.thread_id)


@app.get("/health")
async def health():
    return {"status": "ok", "agents_loaded": list(_agent_cache.keys())}
