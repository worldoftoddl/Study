"""agent/config.py -- 환경변수 기반 설정 상수 + 팩토리 함수."""

import os
import functools

from dotenv import load_dotenv

load_dotenv()

# ── LLM 모델 ──────────────────────────────────────────────
SMART_LLM_MODEL = os.getenv("SMART_LLM_MODEL", "claude-opus-4-5-20251101")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")
SMALL_LLM_MODEL = os.getenv("SMALL_LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))


# ── 팩토리 함수 ──────────────────────────────────────────

_LLM_TIERS = {
    "smart": SMART_LLM_MODEL,
    "default": LLM_MODEL,
    "small": SMALL_LLM_MODEL,
}


def get_llm(tier: str = "default", **kwargs):
    """ChatAnthropic 인스턴스를 반환한다.

    Args:
        tier: "smart" | "default" | "small"
        **kwargs: ChatAnthropic 추가 인자 (temperature 등)
    """
    from langchain_anthropic import ChatAnthropic

    model = _LLM_TIERS.get(tier, LLM_MODEL)
    temperature = kwargs.pop("temperature", LLM_TEMPERATURE)
    return ChatAnthropic(model=model, temperature=temperature, **kwargs)


@functools.cache
def get_langsmith_client():
    """LangSmith Client 싱글턴을 반환한다."""
    from langsmith import Client

    return Client()
