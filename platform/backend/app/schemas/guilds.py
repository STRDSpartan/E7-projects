from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.users import UserPublic


class GuildIn(BaseModel):
    name: str = Field(min_length=3, max_length=40)
    tag: str = Field(min_length=2, max_length=6, pattern="^[A-Za-z0-9]+$")
    description: str = Field(default="", max_length=2000)
    server: str | None = None
    is_open: bool = False


class GuildUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    emblem_url: str | None = Field(default=None, max_length=500)
    is_open: bool | None = None


class GuildOut(BaseModel):
    tag: str
    name: str
    description: str
    server: str | None
    emblem_url: str | None
    is_open: bool
    members_count: int
    created_at: datetime
    my_role: str | None = None  # rôle de l'utilisateur connecté, s'il est membre


class MemberOut(BaseModel):
    user: UserPublic
    role: str
    joined_at: datetime


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(officer|member|leader)$")


class JoinRequestIn(BaseModel):
    message: str = Field(default="", max_length=300)


class JoinRequestOut(BaseModel):
    id: int
    user: UserPublic
    message: str
    created_at: datetime


class ChannelIn(BaseModel):
    name: str = Field(min_length=1, max_length=32, pattern="^[a-z0-9àâäéèêëîïôöùûüç_-]+$")
    topic: str = Field(default="", max_length=200)
    officers_only: bool = False


class ChannelOut(BaseModel):
    id: int
    name: str
    topic: str
    officers_only: bool


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    channel_id: int
    author: UserPublic | None
    body: str
    created_at: datetime


class ThreadIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    body: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="général", max_length=32)


class ThreadOut(BaseModel):
    id: int
    title: str
    category: str
    author: UserPublic | None
    pinned: bool
    locked: bool
    created_at: datetime
    last_post_at: datetime
    replies: int


class ThreadUpdate(BaseModel):
    pinned: bool | None = None
    locked: bool | None = None


class ForumPostIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class ForumPostOut(BaseModel):
    id: int
    author: UserPublic | None
    body: str
    created_at: datetime
    edited_at: datetime | None


class ThreadDetail(BaseModel):
    thread: ThreadOut
    posts: list[ForumPostOut]
