"""Règles métier partagées par les routes : amitiés, droits de guilde, visibilité, notifications."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    Friendship,
    FriendshipStatus,
    Guild,
    GuildMember,
    GuildRole,
    Notification,
    Post,
    User,
    Visibility,
)
from app.schemas.users import UserPublic


def public(user: User | None) -> UserPublic | None:
    return UserPublic.model_validate(user) if user else None


def get_user_by_username(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username_key == username.lower(), User.is_active))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Joueur introuvable.")
    return user


# --- amitiés -----------------------------------------------------------------------------
def friendship_between(db: Session, a: int, b: int) -> Friendship | None:
    return db.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            )
        )
    )


def friend_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    ).all()
    return {b if a == user_id else a for a, b in rows}


def relationship(db: Session, viewer: User | None, other: User) -> str:
    if viewer is None:
        return "none"
    if viewer.id == other.id:
        return "self"
    f = friendship_between(db, viewer.id, other.id)
    if f is None:
        return "none"
    if f.status == FriendshipStatus.ACCEPTED:
        return "friends"
    return "request_sent" if f.requester_id == viewer.id else "request_received"


# --- guildes -----------------------------------------------------------------------------
def membership(db: Session, user_id: int) -> GuildMember | None:
    return db.get(GuildMember, user_id)


def get_guild(db: Session, tag: str) -> Guild:
    guild = db.scalar(select(Guild).where(Guild.tag == tag.upper()))
    if guild is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Guilde introuvable.")
    return guild


def require_role(
    db: Session, user: User, guild: Guild, minimum: GuildRole = GuildRole.MEMBER
) -> GuildMember:
    member = membership(db, user.id)
    if member is None or member.guild_id != guild.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux membres de la guilde.")
    if member.role.rank < minimum.rank:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Droits insuffisants dans la guilde.")
    return member


# --- visibilité des publications ---------------------------------------------------------
def visible_posts_clause(db: Session, viewer: User | None) -> ColumnElement[bool]:
    """Condition SQL : publications que `viewer` a le droit de voir."""
    clauses: list[ColumnElement[bool]] = [Post.visibility == Visibility.PUBLIC]
    if viewer is not None:
        clauses.append(Post.author_id == viewer.id)
        friends = friend_ids(db, viewer.id)
        if friends:
            clauses.append(and_(Post.visibility == Visibility.FRIENDS, Post.author_id.in_(friends)))
        member = membership(db, viewer.id)
        if member is not None:
            clauses.append(
                and_(Post.visibility == Visibility.GUILD, Post.guild_id == member.guild_id)
            )
    return or_(*clauses)


def can_see_post(db: Session, viewer: User | None, post: Post) -> bool:
    return (
        db.scalar(select(Post.id).where(Post.id == post.id, visible_posts_clause(db, viewer)))
        is not None
    )


# --- notifications -----------------------------------------------------------------------
def notify(db: Session, user_id: int, kind: str, **payload: Any) -> None:
    db.add(
        Notification(user_id=user_id, kind=kind, payload=json.dumps(payload, ensure_ascii=False))
    )
