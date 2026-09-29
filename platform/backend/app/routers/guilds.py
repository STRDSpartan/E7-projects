"""Guildes : création, recherche, adhésion, rôles, départ."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import current_user, get_db, optional_user
from app.models import (
    Channel,
    ForumPost,
    Guild,
    GuildJoinRequest,
    GuildMember,
    GuildRole,
    Thread,
    User,
)
from app.schemas.guilds import (
    GuildIn,
    GuildOut,
    GuildUpdate,
    JoinRequestIn,
    JoinRequestOut,
    MemberOut,
    RoleUpdate,
)
from app.schemas.users import SERVERS, UserPublic
from app.services import get_guild, get_user_by_username, membership, notify, require_role

router = APIRouter(prefix="/api/guilds", tags=["guilds"])

DEFAULT_CHANNELS = (
    ("général", "Discussions de la guilde"),
    ("gvg", "Préparation des guerres de guilde"),
    ("builds", "Équipements et conseils"),
)


def to_out(db: Session, guild: Guild, viewer: User | None) -> GuildOut:
    count = (
        db.scalar(
            select(func.count()).select_from(GuildMember).where(GuildMember.guild_id == guild.id)
        )
        or 0
    )
    role = None
    if viewer is not None and (m := membership(db, viewer.id)) and m.guild_id == guild.id:
        role = m.role.value
    return GuildOut(
        tag=guild.tag,
        name=guild.name,
        description=guild.description,
        server=guild.server,
        emblem_url=guild.emblem_url,
        is_open=guild.is_open,
        members_count=count,
        created_at=guild.created_at,
        my_role=role,
    )


def _join(db: Session, guild: Guild, user: User, role: GuildRole = GuildRole.MEMBER) -> None:
    db.add(GuildMember(user_id=user.id, guild_id=guild.id, role=role))


@router.post("", response_model=GuildOut, status_code=status.HTTP_201_CREATED)
def create(
    data: GuildIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> GuildOut:
    if membership(db, user.id) is not None:
        raise HTTPException(409, "Quittez votre guilde actuelle avant d'en créer une.")
    if data.server not in (*SERVERS, None):
        raise HTTPException(422, "Serveur inconnu.")
    tag, key = data.tag.upper(), data.name.strip().lower()
    if db.scalar(select(Guild.id).where((Guild.tag == tag) | (Guild.name_key == key))):
        raise HTTPException(409, "Ce nom ou ce tag de guilde est déjà pris.")
    guild = Guild(
        name=data.name.strip(),
        name_key=key,
        tag=tag,
        description=data.description.strip(),
        server=data.server,
        is_open=data.is_open,
    )
    db.add(guild)
    db.flush()
    _join(db, guild, user, GuildRole.LEADER)
    for position, (name, topic) in enumerate(DEFAULT_CHANNELS):
        db.add(Channel(guild_id=guild.id, name=name, topic=topic, position=position))
    welcome = Thread(
        guild_id=guild.id,
        author_id=user.id,
        title="Bienvenue dans la guilde !",
        category="annonces",
        pinned=True,
    )
    db.add(welcome)
    db.flush()
    db.add(
        ForumPost(
            thread_id=welcome.id,
            author_id=user.id,
            body=f"Bienvenue chez {guild.name} ! Présentez-vous ici.",
        )
    )
    db.commit()
    return to_out(db, guild, user)


@router.get("", response_model=list[GuildOut])
def search(
    q: str = Query("", max_length=40),
    viewer: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> list[GuildOut]:
    query = select(Guild)
    if q.strip():
        pattern = f"%{q.strip().lower()}%"
        query = query.where((Guild.name_key.like(pattern)) | (func.lower(Guild.tag).like(pattern)))
    return [to_out(db, g, viewer) for g in db.scalars(query.order_by(Guild.name_key).limit(30))]


@router.get("/{tag}", response_model=GuildOut)
def get(
    tag: str, viewer: User | None = Depends(optional_user), db: Session = Depends(get_db)
) -> GuildOut:
    return to_out(db, get_guild(db, tag), viewer)


@router.patch("/{tag}", response_model=GuildOut)
def update(
    tag: str, data: GuildUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> GuildOut:
    guild = get_guild(db, tag)
    require_role(db, user, guild, GuildRole.OFFICER)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(guild, key, value)
    db.commit()
    return to_out(db, guild, user)


@router.get("/{tag}/members", response_model=list[MemberOut])
def members(tag: str, db: Session = Depends(get_db)) -> list[MemberOut]:
    guild = get_guild(db, tag)
    rows = db.execute(
        select(GuildMember, User)
        .join(User, User.id == GuildMember.user_id)
        .where(GuildMember.guild_id == guild.id)
    ).all()
    rows = sorted(rows, key=lambda r: (-r[0].role.rank, r[1].username_key))
    return [
        MemberOut(user=UserPublic.model_validate(u), role=m.role.value, joined_at=m.joined_at)
        for m, u in rows
    ]


@router.post("/{tag}/join", response_model=dict[str, str])
def join(
    tag: str, data: JoinRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    """Guilde ouverte : adhésion immédiate. Sinon : demande à valider par un officier."""
    guild = get_guild(db, tag)
    if membership(db, user.id) is not None:
        raise HTTPException(409, "Vous êtes déjà membre d'une guilde.")
    if guild.is_open:
        _join(db, guild, user)
        db.commit()
        return {"status": "member"}
    if db.scalar(
        select(GuildJoinRequest.id).where(
            GuildJoinRequest.guild_id == guild.id, GuildJoinRequest.user_id == user.id
        )
    ):
        raise HTTPException(409, "Demande déjà envoyée.")
    db.add(GuildJoinRequest(guild_id=guild.id, user_id=user.id, message=data.message.strip()))
    officers = db.scalars(
        select(GuildMember.user_id).where(
            GuildMember.guild_id == guild.id, GuildMember.role != GuildRole.MEMBER
        )
    )
    for officer_id in officers:
        notify(db, officer_id, "guild_join_request", username=user.username, guild=guild.tag)
    db.commit()
    return {"status": "requested"}


@router.get("/{tag}/requests", response_model=list[JoinRequestOut])
def requests(
    tag: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[JoinRequestOut]:
    guild = get_guild(db, tag)
    require_role(db, user, guild, GuildRole.OFFICER)
    rows = db.execute(
        select(GuildJoinRequest, User)
        .join(User, User.id == GuildJoinRequest.user_id)
        .where(GuildJoinRequest.guild_id == guild.id)
        .order_by(GuildJoinRequest.id)
    ).all()
    return [
        JoinRequestOut(
            id=r.id, user=UserPublic.model_validate(u), message=r.message, created_at=r.created_at
        )
        for r, u in rows
    ]


def _request(db: Session, guild: Guild, request_id: int) -> GuildJoinRequest:
    req = db.get(GuildJoinRequest, request_id)
    if req is None or req.guild_id != guild.id:
        raise HTTPException(404, "Demande introuvable.")
    return req


@router.post("/{tag}/requests/{request_id}/accept", response_model=dict[str, str])
def accept(
    tag: str, request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    guild = get_guild(db, tag)
    require_role(db, user, guild, GuildRole.OFFICER)
    req = _request(db, guild, request_id)
    applicant = db.get(User, req.user_id)
    db.delete(req)
    if applicant is None or membership(db, applicant.id) is not None:
        db.commit()
        raise HTTPException(409, "Ce joueur a entre-temps rejoint une autre guilde.")
    _join(db, guild, applicant)
    notify(db, applicant.id, "guild_accepted", guild=guild.tag)
    db.commit()
    return {"status": "member"}


@router.post("/{tag}/requests/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline(
    tag: str, request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    guild = get_guild(db, tag)
    require_role(db, user, guild, GuildRole.OFFICER)
    db.delete(_request(db, guild, request_id))
    db.commit()


@router.post("/{tag}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave(tag: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    guild = get_guild(db, tag)
    member = require_role(db, user, guild)
    others = (
        db.scalar(
            select(func.count())
            .select_from(GuildMember)
            .where(GuildMember.guild_id == guild.id, GuildMember.user_id != user.id)
        )
        or 0
    )
    if member.role == GuildRole.LEADER and others:
        raise HTTPException(409, "Nommez un autre chef avant de quitter la guilde.")
    db.delete(member)
    if not others:  # dernier membre : la guilde disparaît avec son chat et son forum
        db.delete(guild)
    db.commit()


@router.patch("/{tag}/members/{username}", response_model=MemberOut)
def set_role(
    tag: str,
    username: str,
    data: RoleUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MemberOut:
    guild = get_guild(db, tag)
    me = require_role(db, user, guild, GuildRole.LEADER)
    target_user = get_user_by_username(db, username)
    target = membership(db, target_user.id)
    if target is None or target.guild_id != guild.id or target_user.id == user.id:
        raise HTTPException(404, "Membre introuvable.")
    new_role = GuildRole(data.role)
    if new_role == GuildRole.LEADER:  # transfert de la direction
        me.role = GuildRole.OFFICER
    target.role = new_role
    db.commit()
    return MemberOut(
        user=UserPublic.model_validate(target_user),
        role=target.role.value,
        joined_at=target.joined_at,
    )


@router.delete("/{tag}/members/{username}", status_code=status.HTTP_204_NO_CONTENT)
def kick(
    tag: str, username: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    guild = get_guild(db, tag)
    me = require_role(db, user, guild, GuildRole.OFFICER)
    target_user = get_user_by_username(db, username)
    target = membership(db, target_user.id)
    if target is None or target.guild_id != guild.id or target_user.id == user.id:
        raise HTTPException(404, "Membre introuvable.")
    if target.role.rank >= me.role.rank:
        raise HTTPException(403, "Vous ne pouvez exclure qu'un membre de rang inférieur.")
    db.delete(target)
    notify(db, target_user.id, "guild_kicked", guild=guild.tag)
    db.commit()
