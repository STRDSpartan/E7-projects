"""Point d'entrée de l'API : `uvicorn app.main:app --reload`."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import (
    __version__,
    models,  # noqa: F401  (enregistre les tables)
)
from app.config import Settings, get_settings
from app.db import Base, Database
from app.realtime import ChannelHub
from app.routers import auth, chat, forum, friends, guilds, media, notifications, posts, users


def create_app(settings: Settings | None = None, *, create_tables: bool = False) -> FastAPI:
    settings = settings or get_settings()
    api = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="API de la plateforme communautaire Epic Seven.",
    )
    api.state.settings = settings
    api.state.db = Database(settings.database_url)
    api.state.hub = ChannelHub()
    if create_tables:  # développement et tests ; en production : `alembic upgrade head`
        Base.metadata.create_all(api.state.db.engine)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (auth, users, friends, posts, media, notifications, guilds, chat, forum):
        api.include_router(module.router)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    api.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

    @api.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return api


app = create_app(create_tables=get_settings().database_url.startswith("sqlite"))
