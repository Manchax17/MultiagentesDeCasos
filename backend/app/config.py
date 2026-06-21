from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API keys (opcionales — el sistema funciona sin ellas usando Ollama)
    groq_api_key: str = ""
    gemini_api_key: str = ""
    hf_api_token: str = ""

    # ── Modelo por defecto ──────────────────────
    # Ollama corre local, no requiere API key, y es el default.
    default_model: str = "auto"
    default_ollama_model: str = "deepseek-r1:1.5b"

    # ── Ollama config ───────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 300  # segundos — modelos locales pueden tardar
    ollama_num_ctx: int = 8192  # contexto amplio para prompts HPN

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

import sys
