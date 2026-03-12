"""
모델 프로바이더 추상화 계층.

ABC(Abstract Base Class)를 통해 어떤 LLM이든 갈아끼울 수 있는 구조.

설계 의도:
    - get_llm()이 반환하는 객체는 LangChain의 BaseChatModel을 따릅니다.
    - deepagents의 create_deep_agent(model=...)에 직접 전달 가능합니다.
    - 새 프로바이더 추가 시 이 파일에 클래스 하나만 추가하면 됩니다.

사용 예시:
    provider = AnthropicProvider(model_name="claude-sonnet-4-5-20250929")
    llm = provider.get_llm()
    agent = create_deep_agent(model=llm, ...)
"""
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel


class ModelProvider(ABC):
    """
    LLM 프로바이더 인터페이스.

    모든 프로바이더는 이 클래스를 상속하고 get_llm()을 구현해야 합니다.
    get_llm()은 LangChain BaseChatModel 호환 객체를 반환합니다.
    """

    def __init__(self, model_name: str, **kwargs: Any):
        """
        Args:
            model_name: 모델 식별자 (예: "claude-sonnet-4-5-20250929", "gpt-4o")
            **kwargs: 프로바이더별 추가 설정 (temperature, max_tokens 등)
        """
        self.model_name = model_name
        self.kwargs = kwargs

    @abstractmethod
    def get_llm(self) -> BaseChatModel:
        """LangChain 호환 LLM 인스턴스를 반환합니다."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name})"


# ──────────────────────────────────────────────
# 구현체들
# ──────────────────────────────────────────────

class AnthropicProvider(ModelProvider):
    """Anthropic Claude 모델 프로바이더."""

    def __init__(self, model_name: str = "claude-sonnet-4-5-20250929", **kwargs: Any):
        super().__init__(model_name, **kwargs)

    def get_llm(self) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=self.model_name, **self.kwargs)


class OpenAIProvider(ModelProvider):
    """OpenAI GPT 모델 프로바이더."""

    def __init__(self, model_name: str = "gpt-4o", **kwargs: Any):
        super().__init__(model_name, **kwargs)

    def get_llm(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=self.model_name, **self.kwargs)


class UpstageProvider(ModelProvider):
    """
    Upstage Solar 모델 프로바이더.

    한국어 특화 모델이 필요할 때 사용.
    Solar 임베딩과는 별개 — 이건 Chat 모델용입니다.
    """

    def __init__(self, model_name: str = "solar-pro", **kwargs: Any):
        super().__init__(model_name, **kwargs)

    def get_llm(self) -> BaseChatModel:
        from langchain_upstage import ChatUpstage
        return ChatUpstage(model=self.model_name, **self.kwargs)


# ──────────────────────────────────────────────
# 팩토리 함수 — 문자열 키로 프로바이더 생성
# ──────────────────────────────────────────────

_PROVIDER_MAP: dict[str, type[ModelProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "upstage": UpstageProvider,
}


def get_provider(provider_name: str, model_name: str | None = None, **kwargs: Any) -> ModelProvider:
    """
    문자열 키로 프로바이더 인스턴스를 생성합니다.

    Args:
        provider_name: "anthropic", "openai", "upstage" 중 하나
        model_name: 모델 식별자. None이면 프로바이더 기본값 사용.
        **kwargs: 프로바이더에 전달할 추가 인자 (temperature 등)

    Returns:
        ModelProvider 인스턴스

    Raises:
        ValueError: 알 수 없는 provider_name

    사용 예시:
        provider = get_provider("anthropic", temperature=0.7)
        llm = provider.get_llm()
    """
    cls = _PROVIDER_MAP.get(provider_name)
    if cls is None:
        available = ", ".join(_PROVIDER_MAP.keys())
        raise ValueError(
            f"알 수 없는 프로바이더: '{provider_name}'. "
            f"사용 가능: {available}"
        )
    if model_name:
        return cls(model_name=model_name, **kwargs)
    return cls(**kwargs)


def register_provider(name: str, cls: type[ModelProvider]) -> None:
    """
    커스텀 프로바이더를 런타임에 등록합니다.

    사용 예시:
        class MyProvider(ModelProvider):
            def get_llm(self):
                ...

        register_provider("my_provider", MyProvider)
        provider = get_provider("my_provider")
    """
    _PROVIDER_MAP[name] = cls
