from __future__ import annotations

import json

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import Notification, User
from app.schemas.social import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[NotificationOut]:
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(50)
    )
    return [
        NotificationOut(
            id=n.id,
            kind=n.kind,
            payload=json.loads(n.payload),
            read=n.read,
            created_at=n.created_at,
        )
        for n in rows
    ]


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    db.execute(update(Notification).where(Notification.user_id == user.id).values(read=True))
    db.commit()
