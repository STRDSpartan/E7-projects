from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class GuildRole(enum.StrEnum):
    LEADER = "leader"
    OFFICER = "officer"
    MEMBER = "member"

    @property
    def rank(self) -> int:
        return {"leader": 3, "officer": 2, "member": 1}[self.value]


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    name_key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    tag: Mapped[str] = mapped_column(String(6), unique=True, index=True)  # identifiant d'URL
    description: Mapped[str] = mapped_column(Text, default="")
    server: Mapped[str | None] = mapped_column(String(16), default=None)
    emblem_url: Mapped[str | None] = mapped_column(String(500), default=None)
    is_open: Mapped[bool] = mapped_column(default=False)  # adhésion sans validation
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class GuildMember(Base):
    """Un joueur n'appartient qu'à une guilde à la fois (comme dans le jeu)."""

    __tablename__ = "guild_members"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"), index=True)
    role: Mapped[GuildRole] = mapped_column(
        Enum(GuildRole, native_enum=False), default=GuildRole.MEMBER
    )
    joined_at: Mapped[datetime] = mapped_column(default=utcnow)


class GuildJoinRequest(Base):
    __tablename__ = "guild_join_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
