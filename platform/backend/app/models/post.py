from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class PostKind(enum.StrEnum):
    TEXT = "text"
    VITRINE = "vitrine"  # instantané de roster (format e7showcase)
    CLIP = "clip"  # vidéo
    ACHIEVEMENT = "achievement"  # succès en jeu (rang RTA, étage d'Abysse…)


class Visibility(enum.StrEnum):
    PUBLIC = "public"
    FRIENDS = "friends"
    GUILD = "guild"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[PostKind] = mapped_column(Enum(PostKind, native_enum=False))
    title: Mapped[str] = mapped_column(String(120), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str | None] = mapped_column(String(500), default=None)
    media_type: Mapped[str | None] = mapped_column(String(60), default=None)
    roster_json: Mapped[str | None] = mapped_column(Text, default=None)
    meta_json: Mapped[str | None] = mapped_column(Text, default=None)  # détails d'un succès
    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, native_enum=False), default=Visibility.PUBLIC
    )
    guild_id: Mapped[int | None] = mapped_column(
        ForeignKey("guilds.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class PostLike(Base):
    __tablename__ = "post_likes"

    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
