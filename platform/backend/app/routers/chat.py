"""Salons de discussion de guilde : liste, création, historique, envoi, temps réel (WebSocket)."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import current_user, get_db, user_from_token
from app.models import Channel, Guild, GuildRole, Message, User
from app.realtime import ChannelHub
from app.schemas.guilds import ChannelIn, ChannelOut, MessageIn, MessageOut
from app.services import get_guild, membership, public, require_role

router = APIRouter(prefix="/api", tags=["chat"])


def _channel_for(db: Session, user: User, channel_id: int) -> Channel:
    channel = db.get(Channel, channel_id)
    guild = db.get(Guild, channel.guild_id) if channel else None
    if channel is None or guild is None:
        raise HTTPException(404, "Salon introuvable.")
    member = require_role(db, user, guild)
    if channel.officers_only and member.role.rank < GuildRole.OFFICER.rank:
        raise HTTPException(403, "Salon réservé aux officiers.")
    return channel


def to_out(db: Session, m: Message) -> MessageOut:
    author = db.get(User, m.author_id) if m.author_id else None
    return MessageOut(
        id=m.id,
        channel_id=m.channel_id,
        author=public(author),
        body=m.body,
        created_at=m.created_at,
    )


@router.get("/guilds/{tag}/channels", response_model=list[ChannelOut])
def channels(
    tag: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ChannelOut]:
    guild = get_guild(db, tag)
    member = require_role(db, user, guild)
    rows = db.scalars(
        select(Channel).where(Channel.guild_id == guild.id).order_by(Channel.position, Channel.id)
    )
    return [
        ChannelOut(id=c.id, name=c.name, topic=c.topic, officers_only=c.officers_only)
        for c in rows
        if not c.officers_only or member.role.rank >= GuildRole.OFFICER.rank
    ]


@router.post(
    "/guilds/{tag}/channels", response_model=ChannelOut, status_code=status.HTTP_201_CREATED
)
def create_channel(
    tag: str, data: ChannelIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ChannelOut:
    guild = get_guild(db, tag)
    require_role(db, user, guild, GuildRole.OFFICER)
    if db.scalar(select(Channel.id).where(Channel.guild_id == guild.id, Channel.name == data.name)):
        raise HTTPException(409, "Un salon porte déjà ce nom.")
    count = len(db.scalars(select(Channel.id).where(Channel.guild_id == guild.id)).all())
    channel = Channel(
        guild_id=guild.id,
        name=data.name,
        topic=data.topic,
        officers_only=data.officers_only,
        position=count,
    )
    db.add(channel)
    db.commit()
    return ChannelOut(
        id=channel.id, name=channel.name, topic=channel.topic, officers_only=channel.officers_only
    )


@router.get("/channels/{channel_id}/messages", response_model=list[MessageOut])
def history(
    channel_id: int,
    before: int | None = None,
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    """Messages du plus ancien au plus récent (page de `limit` messages avant `before`)."""
    channel = _channel_for(db, user, channel_id)
    query = select(Message).where(Message.channel_id == channel.id)
    if before:
        query = query.where(Message.id < before)
    rows = list(db.scalars(query.order_by(Message.id.desc()).limit(limit)))
    return [to_out(db, m) for m in reversed(rows)]


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send(
    channel_id: int,
    data: MessageIn,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    channel = _channel_for(db, user, channel_id)
    message = Message(channel_id=channel.id, author_id=user.id, body=data.body.strip())
    db.add(message)
    db.commit()
    out = to_out(db, message)
    hub: ChannelHub = request.app.state.hub
    await hub.broadcast(channel.id, {"type": "message", "message": out.model_dump(mode="json")})
    return out


@router.websocket("/ws/channels/{channel_id}")
async def channel_socket(websocket: WebSocket, channel_id: int) -> None:
    """Flux temps réel d'un salon. Authentification par le cookie de session du site."""
    settings: Settings = websocket.app.state.settings
    hub: ChannelHub = websocket.app.state.hub
    allowed = False
    for db in websocket.app.state.db.session():
        user = user_from_token(db, websocket.cookies.get(settings.session_cookie))
        channel = db.get(Channel, channel_id)
        if user and channel and (m := membership(db, user.id)) and m.guild_id == channel.guild_id:
            allowed = not channel.officers_only or m.role.rank >= GuildRole.OFFICER.rank
    if not allowed:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    await hub.join(channel_id, websocket)
    try:
        while True:
            await (
                websocket.receive_text()
            )  # le client n'envoie que des pings ; l'envoi passe par POST
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(channel_id, websocket)
