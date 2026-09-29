"""Publications (vitrine, clip, succès, texte), fil d'actualité, j'aime, commentaires."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import current_user, get_db, get_settings_dep, optional_user
from app.models import Comment, Post, PostKind, PostLike, User, Visibility
from app.schemas.social import CommentIn, CommentOut, PostIn, PostOut
from app.schemas.users import UserPublic
from app.services import (
    can_see_post,
    friend_ids,
    get_user_by_username,
    membership,
    notify,
    visible_posts_clause,
)

router = APIRouter(prefix="/api", tags=["posts"])


def to_out(db: Session, post: Post, viewer: User | None) -> PostOut:
    author = db.get(User, post.author_id)
    assert author is not None
    likes = (
        db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id))
        or 0
    )
    comments = (
        db.scalar(select(func.count()).select_from(Comment).where(Comment.post_id == post.id)) or 0
    )
    liked = bool(viewer and db.get(PostLike, (post.id, viewer.id)))
    return PostOut(
        id=post.id,
        author=UserPublic.model_validate(author),
        kind=post.kind.value,
        title=post.title,
        body=post.body,
        media_url=post.media_url,
        media_type=post.media_type,
        roster=json.loads(post.roster_json) if post.roster_json else None,
        achievement=json.loads(post.meta_json) if post.meta_json else None,
        visibility=post.visibility.value,
        created_at=post.created_at,
        likes=likes,
        liked_by_me=liked,
        comments=comments,
    )


def _visible_post(db: Session, post_id: int, viewer: User | None) -> Post:
    post = db.get(Post, post_id)
    if post is None or not can_see_post(db, viewer, post):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Publication introuvable.")
    return post


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    data: PostIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> PostOut:
    kind = PostKind(data.kind)
    visibility = Visibility(data.visibility)
    roster_json = None
    if kind == PostKind.VITRINE:
        if not data.roster or not isinstance(data.roster.get("heroes"), list):
            raise HTTPException(422, "Une vitrine doit contenir un roster (liste « heroes »).")
        roster_json = json.dumps(data.roster, ensure_ascii=False)
        if len(roster_json.encode()) > settings.max_roster_kb * 1024:
            raise HTTPException(413, f"Roster trop volumineux (max {settings.max_roster_kb} Ko).")
    if kind == PostKind.CLIP and not data.media_url:
        raise HTTPException(422, "Un clip nécessite une vidéo (envoyez-la d'abord via /api/media).")
    if kind == PostKind.ACHIEVEMENT and not (data.title or data.achievement):
        raise HTTPException(422, "Décrivez le succès (titre ou détails).")
    if kind == PostKind.TEXT and not (data.body.strip() or data.title.strip()):
        raise HTTPException(422, "La publication est vide.")
    guild_id = None
    if visibility == Visibility.GUILD:
        member = membership(db, user.id)
        if member is None:
            raise HTTPException(422, "Rejoignez une guilde pour publier en visibilité « guilde ».")
        guild_id = member.guild_id
    media_type = None
    if data.media_url:
        if not data.media_url.startswith("/media/"):
            raise HTTPException(422, "Les médias doivent être envoyés sur le site (/api/media).")
        media_type = "video" if data.media_url.rsplit(".", 1)[-1] in ("mp4", "webm") else "image"
    post = Post(
        author_id=user.id,
        kind=kind,
        title=data.title.strip(),
        body=data.body.strip(),
        media_url=data.media_url,
        media_type=media_type,
        roster_json=roster_json,
        meta_json=json.dumps(data.achievement, ensure_ascii=False) if data.achievement else None,
        visibility=visibility,
        guild_id=guild_id,
    )
    db.add(post)
    db.commit()
    return to_out(db, post, user)


@router.get("/feed", response_model=list[PostOut])
def feed(
    before: int | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[PostOut]:
    """Mes publications, celles de mes amis et de ma guilde (du plus récent au plus ancien)."""
    authors = friend_ids(db, user.id) | {user.id}
    member = membership(db, user.id)
    query = select(Post).where(visible_posts_clause(db, user))
    if member is not None:
        query = query.where((Post.author_id.in_(authors)) | (Post.guild_id == member.guild_id))
    else:
        query = query.where(Post.author_id.in_(authors))
    if before:
        query = query.where(Post.id < before)
    posts = db.scalars(query.order_by(Post.id.desc()).limit(limit)).all()
    return [to_out(db, p, user) for p in posts]


@router.get("/explore", response_model=list[PostOut])
def explore(
    kind: str | None = None,
    before: int | None = None,
    limit: int = Query(20, ge=1, le=50),
    viewer: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> list[PostOut]:
    """Publications publiques de toute la communauté (filtrables par type)."""
    query = select(Post).where(Post.visibility == Visibility.PUBLIC)
    if kind:
        query = query.where(Post.kind == PostKind(kind))
    if before:
        query = query.where(Post.id < before)
    return [to_out(db, p, viewer) for p in db.scalars(query.order_by(Post.id.desc()).limit(limit))]


@router.get("/users/{username}/posts", response_model=list[PostOut])
def user_posts(
    username: str,
    before: int | None = None,
    limit: int = Query(20, ge=1, le=50),
    viewer: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> list[PostOut]:
    author = get_user_by_username(db, username)
    query = select(Post).where(Post.author_id == author.id, visible_posts_clause(db, viewer))
    if before:
        query = query.where(Post.id < before)
    return [to_out(db, p, viewer) for p in db.scalars(query.order_by(Post.id.desc()).limit(limit))]


@router.get("/posts/{post_id}", response_model=PostOut)
def get_post(
    post_id: int, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)
) -> PostOut:
    return to_out(db, _visible_post(db, post_id, viewer), viewer)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    post = db.get(Post, post_id)
    if post is None or post.author_id != user.id:
        raise HTTPException(404, "Publication introuvable.")
    db.delete(post)
    db.commit()


@router.post("/posts/{post_id}/like", response_model=PostOut)
def like(
    post_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> PostOut:
    post = _visible_post(db, post_id, user)
    if not db.get(PostLike, (post.id, user.id)):
        db.add(PostLike(post_id=post.id, user_id=user.id))
        if post.author_id != user.id:
            notify(db, post.author_id, "post_liked", username=user.username, post_id=post.id)
        db.commit()
    return to_out(db, post, user)


@router.delete("/posts/{post_id}/like", response_model=PostOut)
def unlike(
    post_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> PostOut:
    post = _visible_post(db, post_id, user)
    if existing := db.get(PostLike, (post.id, user.id)):
        db.delete(existing)
        db.commit()
    return to_out(db, post, user)


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
def comments(
    post_id: int, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)
) -> list[CommentOut]:
    post = _visible_post(db, post_id, viewer)
    out = []
    for c in db.scalars(select(Comment).where(Comment.post_id == post.id).order_by(Comment.id)):
        author = db.get(User, c.author_id)
        if author:
            out.append(
                CommentOut(
                    id=c.id,
                    author=UserPublic.model_validate(author),
                    body=c.body,
                    created_at=c.created_at,
                )
            )
    return out


@router.post(
    "/posts/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
def add_comment(
    post_id: int, data: CommentIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> CommentOut:
    post = _visible_post(db, post_id, user)
    comment = Comment(post_id=post.id, author_id=user.id, body=data.body.strip())
    db.add(comment)
    if post.author_id != user.id:
        notify(db, post.author_id, "post_commented", username=user.username, post_id=post.id)
    db.commit()
    return CommentOut(
        id=comment.id,
        author=UserPublic.model_validate(user),
        body=comment.body,
        created_at=comment.created_at,
    )
