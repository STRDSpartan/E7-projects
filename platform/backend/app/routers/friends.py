"""Demandes d'amis : envoyer, accepter, refuser, retirer un ami."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.deps import current_user, get_db
from app.models import Friendship, FriendshipStatus, User
from app.schemas.social import FriendRequestIn, FriendRequestOut
from app.schemas.users import UserPublic
from app.services import friend_ids, friendship_between, get_user_by_username, notify

router = APIRouter(prefix="/api/friends", tags=["friends"])


@router.get("", response_model=list[UserPublic])
def my_friends(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[User]:
    ids = friend_ids(db, user.id)
    return (
        list(db.scalars(select(User).where(User.id.in_(ids)).order_by(User.username_key)))
        if ids
        else []
    )


@router.get("/requests", response_model=list[FriendRequestOut])
def my_requests(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[FriendRequestOut]:
    pending = db.scalars(
        select(Friendship)
        .where(
            Friendship.status == FriendshipStatus.PENDING,
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        )
        .order_by(Friendship.created_at.desc())
    ).all()
    out = []
    for f in pending:
        incoming = f.addressee_id == user.id
        other = db.get(User, f.requester_id if incoming else f.addressee_id)
        if other:
            out.append(
                FriendRequestOut(
                    id=f.id,
                    user=UserPublic.model_validate(other),
                    direction="incoming" if incoming else "outgoing",
                    created_at=f.created_at,
                )
            )
    return out


@router.post("/requests", status_code=status.HTTP_201_CREATED, response_model=dict[str, str])
def send_request(
    data: FriendRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    other = get_user_by_username(db, data.username)
    if other.id == user.id:
        raise HTTPException(422, "Vous ne pouvez pas vous ajouter vous-même.")
    existing = friendship_between(db, user.id, other.id)
    if existing is not None:
        if existing.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(409, "Vous êtes déjà amis.")
        if existing.addressee_id == user.id:  # l'autre avait déjà demandé : on accepte
            existing.status = FriendshipStatus.ACCEPTED
            existing.responded_at = utcnow()
            notify(db, other.id, "friend_accepted", username=user.username)
            db.commit()
            return {"status": "friends"}
        raise HTTPException(409, "Demande déjà envoyée.")
    db.add(Friendship(requester_id=user.id, addressee_id=other.id))
    notify(db, other.id, "friend_request", username=user.username)
    db.commit()
    return {"status": "request_sent"}


def _incoming(db: Session, user: User, request_id: int) -> Friendship:
    f = db.get(Friendship, request_id)
    if f is None or f.addressee_id != user.id or f.status != FriendshipStatus.PENDING:
        raise HTTPException(404, "Demande introuvable.")
    return f


@router.post("/requests/{request_id}/accept", response_model=dict[str, str])
def accept(
    request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    f = _incoming(db, user, request_id)
    f.status = FriendshipStatus.ACCEPTED
    f.responded_at = utcnow()
    requester = db.get(User, f.requester_id)
    if requester:
        notify(db, requester.id, "friend_accepted", username=user.username)
    db.commit()
    return {"status": "friends"}


@router.post("/requests/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline(
    request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    db.delete(_incoming(db, user, request_id))
    db.commit()


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    username: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    """Retire un ami, ou annule une demande envoyée."""
    other = get_user_by_username(db, username)
    f = friendship_between(db, user.id, other.id)
    if f is None:
        raise HTTPException(404, "Aucune relation avec ce joueur.")
    db.delete(f)
    db.commit()
