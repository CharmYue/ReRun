"""Configuration management using pydantic-settings."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"


class Language(StrEnum):
    CN = "cn"
    EN = "en"


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ---
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.9, ge=0.0, le=2.0)

    # --- Game ---
    game_language: Language = Language.CN
    typewriter_speed: float = Field(default=0.03, ge=0.0)

    # --- Recording ---
    record: bool = False

    # --- Debug ---
    debug: bool = False

    @property
    def is_offline(self) -> bool:
        """True when no API key is configured — forces offline mode."""
        return not self.openai_api_key


def get_settings(**overrides) -> Settings:
    """Create a Settings instance. Accepts keyword overrides for testing."""
    return Settings(**overrides)
