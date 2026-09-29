from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class FriendshipStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"


class Friendship(Base):
    """Demande d'ami (requester → addressee) ; devient une amitié une fois acceptée."""

    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    addressee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, native_enum=False), default=FriendshipStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(default=None)
