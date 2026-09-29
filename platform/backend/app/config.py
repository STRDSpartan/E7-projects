"""Configuration de l'API (variables d'environnement préfixées E7S_)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="E7S_", env_file=".env", extra="ignore")

    app_name: str = "E7 Social"
    database_url: str = "sqlite:///./var/e7social.db"
    # Origines autorisées à appeler l'API avec les cookies (site React en développement)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    session_days: int = 30
    session_cookie: str = "e7s_session"
    cookie_secure: bool = False  # True en production (HTTPS obligatoire)
    media_dir: Path = Path("./var/media")
    max_image_mb: int = 8
    max_video_mb: int = 60
    max_roster_kb: int = 2048  # instantané de vitrine (roster JSON)
    messages_page: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
