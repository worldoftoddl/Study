"""
설정 및 환경변수 관리.

.env 파일 또는 환경변수에서 API 키를 로드합니다.
dotenv가 설치되어 있으면 자동으로 .env를 읽습니다.
"""
import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Settings:
    """프로젝트 전역 설정. 환경변수에서 읽거나 직접 주입 가능."""

    # LLM API Keys
    anthropic_api_key: str | None = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY")
    )
    openai_api_key: str | None = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )

    # Tool API Keys
    tavily_api_key: str | None = field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY")
    )

    # External Data
    database_dir: str | None = field(
        default_factory=lambda: os.getenv("DATABASE_DIR")
    )

    # Agent Defaults
    default_provider: str = field(
        default_factory=lambda: os.getenv("DEFAULT_PROVIDER", "anthropic")
    )
    default_model: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5-20250929")
    )

    # DeepAgent 설정
    max_iterations: int = 25  # 에이전트 최대 반복 횟수

    def validate(self) -> list[str]:
        """필수 키가 설정되었는지 검증. 누락된 키 이름 리스트 반환."""
        missing = []
        if self.default_provider == "anthropic" and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if self.default_provider == "openai" and not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        return missing


# 싱글턴 인스턴스 — 대부분의 경우 이걸 import해서 사용
settings = Settings()
