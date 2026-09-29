"""Migrations Alembic : `alembic upgrade head` (URL lue dans E7S_DATABASE_URL)."""

from __future__ import annotations

from alembic import context
from app import models  # noqa: F401  (enregistre les tables)
from app.config import get_settings
from app.db import Base, make_engine

target_metadata = Base.metadata


def run_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = make_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
