from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Pseudo affiché tel que saisi ; unicité insensible à la casse via username_key
    username: Mapped[str] = mapped_column(String(24))
    username_key: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(40), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)
    banner_url: Mapped[str | None] = mapped_column(String(500), default=None)
    server: Mapped[str | None] = mapped_column(String(16), default=None)  # global, europe, asia…
    favorite_hero: Mapped[str | None] = mapped_column(String(60), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)


class AuthSession(Base):
    """Session de connexion ; seul le hash du jeton est stocké (le jeton vit dans le cookie)."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
