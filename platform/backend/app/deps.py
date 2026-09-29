"""Dépendances FastAPI : session de base de données et utilisateur connecté."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AuthSession, User
from app.security import token_hash


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.get(AuthSession, token_hash(token))
    if session is None:
        return None
    expires = (
        session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=UTC)
    )
    if expires < datetime.now(UTC):
        db.delete(session)
        db.commit()
        return None
    user = db.get(User, session.user_id)
    return user if user and user.is_active else None


def optional_user(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)
) -> User | None:
    return user_from_token(db, request.cookies.get(settings.session_cookie))


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Connexion requise.")
    return user
