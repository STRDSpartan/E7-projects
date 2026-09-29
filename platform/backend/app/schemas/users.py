from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

SERVERS = ("global", "europe", "asia", "korea", "japan")


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    display_name: str
    avatar_url: str | None = None
    banner_url: str | None = None
    bio: str = ""
    server: str | None = None
    favorite_hero: str | None = None
    created_at: datetime


class UserMe(UserPublic):
    email: str


class RegisterIn(BaseModel):
    username: str = Field(
        min_length=3, max_length=24, description="Pseudo du site (lettres, chiffres, _ . -)"
    )
    email: EmailStr
    password: str
    display_name: str = Field(default="", max_length=40, description="Pseudo en jeu")


class LoginIn(BaseModel):
    login: str = Field(description="Pseudo ou adresse e-mail")
    password: str


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=40)
    bio: str | None = Field(default=None, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    server: str | None = None
    favorite_hero: str | None = Field(default=None, max_length=60)


class GuildBadge(BaseModel):
    tag: str
    name: str
    role: str


class ProfileOut(BaseModel):
    user: UserPublic
    friends_count: int
    posts_count: int
    guild: GuildBadge | None = None
    # none | self | friends | request_sent | request_received
    relationship: str = "none"


class DeleteAccountIn(BaseModel):
    password: str
