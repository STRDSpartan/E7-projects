"""Profils publics, recherche de joueurs, édition du profil, export et suppression (RGPD)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, optional_user
from app.models import (
    AuthSession,
    Comment,
    ForumPost,
    Friendship,
    Guild,
    GuildMember,
    GuildRole,
    Message,
    Post,
    User,
)
from app.schemas.users import (
    SERVERS,
    DeleteAccountIn,
    GuildBadge,
    ProfileOut,
    ProfileUpdate,
    UserMe,
    UserPublic,
)
from app.security import verify_password
from app.services import friend_ids, get_user_by_username, membership, relationship

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/search", response_model=list[UserPublic])
def search(
    q: str = Query(min_length=2, max_length=40), db: Session = Depends(get_db)
) -> list[User]:
    """Recherche par pseudo du site ou pseudo en jeu (préfixe prioritaire, puis contenu)."""
    needle = q.strip().lower()
    pattern = f"%{needle.replace('%', '').replace('_', '')}%"
    users = db.scalars(
        select(User)
        .where(
            User.is_active,
            or_(
                User.username_key.like(pattern),
                func.lower(User.display_name).like(pattern),
            ),
        )
        .limit(50)
    ).all()
    return sorted(
        users,
        key=lambda u: (
            not u.username_key.startswith(needle) and not u.display_name.lower().startswith(needle),
            u.username_key,
        ),
    )[:20]


@router.get("/{username}", response_model=ProfileOut)
def profile(
    username: str, db: Session = Depends(get_db), viewer: User | None = Depends(optional_user)
) -> ProfileOut:
    user = get_user_by_username(db, username)
    member = membership(db, user.id)
    badge = None
    if member is not None:
        guild = db.get(Guild, member.guild_id)
        if guild:
            badge = GuildBadge(tag=guild.tag, name=guild.name, role=member.role.value)
    return ProfileOut(
        user=UserPublic.model_validate(user),
        friends_count=len(friend_ids(db, user.id)),
        posts_count=db.scalar(
            select(func.count()).select_from(Post).where(Post.author_id == user.id)
        )
        or 0,
        guild=badge,
        relationship=relationship(db, viewer, user),
    )


@router.patch("/me", response_model=UserMe)
def update_me(
    data: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> User:
    changes = data.model_dump(exclude_unset=True)
    if "server" in changes and changes["server"] not in (*SERVERS, None):
        raise HTTPException(422, f"Serveur inconnu (valeurs : {', '.join(SERVERS)}).")
    for key, value in changes.items():
        setattr(user, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    return user


@router.get("/me/export")
def export_me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Portabilité des données (RGPD, art. 20) : tout ce que le compte a produit."""
    return {
        "user": UserMe.model_validate(user).model_dump(mode="json"),
        "posts": [
            {
                "id": p.id,
                "kind": p.kind.value,
                "title": p.title,
                "body": p.body,
                "media_url": p.media_url,
                "roster": json.loads(p.roster_json) if p.roster_json else None,
                "visibility": p.visibility.value,
                "created_at": p.created_at.isoformat(),
            }
            for p in db.scalars(select(Post).where(Post.author_id == user.id))
        ],
        "comments": [
            {"post_id": c.post_id, "body": c.body, "created_at": c.created_at.isoformat()}
            for c in db.scalars(select(Comment).where(Comment.author_id == user.id))
        ],
        "friends": sorted(
            u.username for u in db.scalars(select(User).where(User.id.in_(friend_ids(db, user.id))))
        ),
        "messages": [
            {"channel_id": m.channel_id, "body": m.body, "created_at": m.created_at.isoformat()}
            for m in db.scalars(select(Message).where(Message.author_id == user.id))
        ],
        "forum_posts": [
            {"thread_id": f.thread_id, "body": f.body, "created_at": f.created_at.isoformat()}
            for f in db.scalars(select(ForumPost).where(ForumPost.author_id == user.id))
        ],
    }


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    data: DeleteAccountIn,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """Droit à l'effacement (RGPD, art. 17) : chat/forum anonymisés, le reste supprimé."""
    if not verify_password(user.password_hash, data.password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe incorrect.")
    member = membership(db, user.id)
    if member is not None and member.role == GuildRole.LEADER:
        others = db.scalar(
            select(func.count())
            .select_from(GuildMember)
            .where(GuildMember.guild_id == member.guild_id, GuildMember.user_id != user.id)
        )
        if others:
            raise HTTPException(
                409, "Transmettez d'abord la direction de votre guilde à un autre membre."
            )
        guild = db.get(Guild, member.guild_id)
        if guild:
            db.delete(guild)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(
        delete(Friendship).where(
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id)
        )
    )
    db.delete(user)
    db.commit()
    response.delete_cookie("e7s_session", path="/")


@router.get("/{username}/friends", response_model=list[UserPublic])
def friends_of(username: str, db: Session = Depends(get_db)) -> list[User]:
    user = get_user_by_username(db, username)
    ids = friend_ids(db, user.id)
    return (
        list(db.scalars(select(User).where(User.id.in_(ids)).order_by(User.username_key)))
        if ids
        else []
    )
