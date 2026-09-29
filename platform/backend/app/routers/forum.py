"""Forum de guilde : sujets (épinglés, verrouillés, catégories) et réponses."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.deps import current_user, get_db
from app.models import ForumPost, Guild, GuildRole, Thread, User
from app.schemas.guilds import (
    ForumPostIn,
    ForumPostOut,
    ThreadDetail,
    ThreadIn,
    ThreadOut,
    ThreadUpdate,
)
from app.services import get_guild, public, require_role

router = APIRouter(prefix="/api", tags=["forum"])


def thread_out(db: Session, t: Thread) -> ThreadOut:
    replies = (
        db.scalar(select(func.count()).select_from(ForumPost).where(ForumPost.thread_id == t.id))
        or 1
    ) - 1
    return ThreadOut(
        id=t.id,
        title=t.title,
        category=t.category,
        author=public(db.get(User, t.author_id) if t.author_id else None),
        pinned=t.pinned,
        locked=t.locked,
        created_at=t.created_at,
        last_post_at=t.last_post_at,
        replies=replies,
    )


def post_out(db: Session, p: ForumPost) -> ForumPostOut:
    return ForumPostOut(
        id=p.id,
        author=public(db.get(User, p.author_id) if p.author_id else None),
        body=p.body,
        created_at=p.created_at,
        edited_at=p.edited_at,
    )


def _thread(db: Session, user: User, thread_id: int) -> tuple[Thread, Guild]:
    thread = db.get(Thread, thread_id)
    guild = db.get(Guild, thread.guild_id) if thread else None
    if thread is None or guild is None:
        raise HTTPException(404, "Sujet introuvable.")
    require_role(db, user, guild)
    return thread, guild


@router.get("/guilds/{tag}/threads", response_model=list[ThreadOut])
def threads(
    tag: str,
    category: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ThreadOut]:
    guild = get_guild(db, tag)
    require_role(db, user, guild)
    query = select(Thread).where(Thread.guild_id == guild.id)
    if category:
        query = query.where(Thread.category == category)
    rows = db.scalars(query.order_by(Thread.pinned.desc(), Thread.last_post_at.desc()).limit(100))
    return [thread_out(db, t) for t in rows]


@router.post("/guilds/{tag}/threads", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
def create_thread(
    tag: str, data: ThreadIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ThreadOut:
    guild = get_guild(db, tag)
    member = require_role(db, user, guild)
    category = data.category.strip().lower() or "général"
    if category == "annonces" and member.role.rank < GuildRole.OFFICER.rank:
        raise HTTPException(403, "Seuls les officiers publient dans « annonces ».")
    thread = Thread(
        guild_id=guild.id, author_id=user.id, title=data.title.strip(), category=category
    )
    db.add(thread)
    db.flush()
    db.add(ForumPost(thread_id=thread.id, author_id=user.id, body=data.body.strip()))
    db.commit()
    return thread_out(db, thread)


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
def get_thread(
    thread_id: int,
    before: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ThreadDetail:
    thread, _ = _thread(db, user, thread_id)
    query = select(ForumPost).where(ForumPost.thread_id == thread.id)
    if before:
        query = query.where(ForumPost.id < before)
    posts = list(db.scalars(query.order_by(ForumPost.id).limit(limit)))
    return ThreadDetail(thread=thread_out(db, thread), posts=[post_out(db, p) for p in posts])


@router.post(
    "/threads/{thread_id}/posts", response_model=ForumPostOut, status_code=status.HTTP_201_CREATED
)
def reply(
    thread_id: int,
    data: ForumPostIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ForumPostOut:
    thread, guild = _thread(db, user, thread_id)
    member = require_role(db, user, guild)
    if thread.locked and member.role.rank < GuildRole.OFFICER.rank:
        raise HTTPException(403, "Ce sujet est verrouillé.")
    post = ForumPost(thread_id=thread.id, author_id=user.id, body=data.body.strip())
    thread.last_post_at = utcnow()
    db.add(post)
    db.commit()
    return post_out(db, post)


@router.patch("/threads/{thread_id}", response_model=ThreadOut)
def moderate(
    thread_id: int,
    data: ThreadUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ThreadOut:
    thread, guild = _thread(db, user, thread_id)
    require_role(db, user, guild, GuildRole.OFFICER)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(thread, key, value)
    db.commit()
    return thread_out(db, thread)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    thread, guild = _thread(db, user, thread_id)
    member = require_role(db, user, guild)
    if thread.author_id != user.id and member.role.rank < GuildRole.OFFICER.rank:
        raise HTTPException(403, "Seul l'auteur ou un officier peut supprimer ce sujet.")
    db.delete(thread)
    db.commit()
