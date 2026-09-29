from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.users import UserPublic


class FriendRequestIn(BaseModel):
    username: str


class FriendRequestOut(BaseModel):
    id: int
    user: UserPublic  # l'autre personne
    direction: str  # incoming | outgoing
    created_at: datetime


class PostIn(BaseModel):
    kind: str = Field(pattern="^(text|vitrine|clip|achievement)$")
    title: str = Field(default="", max_length=120)
    body: str = Field(default="", max_length=5000)
    visibility: str = Field(default="public", pattern="^(public|friends|guild)$")
    media_url: str | None = Field(default=None, max_length=500)
    roster: dict[str, Any] | None = Field(default=None, description="Roster e7showcase (vitrine)")
    achievement: dict[str, Any] | None = Field(default=None, description="Détails du succès")


class PostOut(BaseModel):
    id: int
    author: UserPublic
    kind: str
    title: str
    body: str
    media_url: str | None
    media_type: str | None
    roster: dict[str, Any] | None
    achievement: dict[str, Any] | None
    visibility: str
    created_at: datetime
    likes: int
    liked_by_me: bool
    comments: int


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: int
    author: UserPublic
    body: str
    created_at: datetime


class NotificationOut(BaseModel):
    id: int
    kind: str
    payload: dict[str, Any]
    read: bool
    created_at: datetime


class MediaOut(BaseModel):
    url: str
    media_type: str
    size: int
