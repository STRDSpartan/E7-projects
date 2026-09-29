from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class Channel(Base):
    """Salon de discussion d'une guilde (#général, #gvg…)."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(32))
    topic: Mapped[str] = mapped_column(String(200), default="")
    position: Mapped[int] = mapped_column(default=0)
    officers_only: Mapped[bool] = mapped_column(default=False)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    edited_at: Mapped[datetime | None] = mapped_column(default=None)
