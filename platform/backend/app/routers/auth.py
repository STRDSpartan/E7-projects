"""Inscription, connexion, déconnexion, utilisateur courant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import current_user, get_db, get_settings_dep
from app.models import AuthSession, User
from app.schemas.users import LoginIn, RegisterIn, UserMe
from app.security import (
    USERNAME_RE,
    hash_password,
    new_session_token,
    password_problem,
    token_hash,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _open_session(db: Session, response: Response, user: User, settings: Settings) -> None:
    token, hashed = new_session_token()
    expires = datetime.now(UTC) + timedelta(days=settings.session_days)
    db.add(AuthSession(token_hash=hashed, user_id=user.id, expires_at=expires))
    db.commit()
    response.set_cookie(
        settings.session_cookie,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserMe, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    if not USERNAME_RE.fullmatch(data.username):
        raise HTTPException(422, "Pseudo : 3 à 24 caractères parmi lettres, chiffres, _ . -")
    if problem := password_problem(data.password):
        raise HTTPException(422, problem)
    email = data.email.lower()
    if db.scalar(select(User.id).where(User.username_key == data.username.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce pseudo est déjà pris.")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cette adresse.")
    user = User(
        username=data.username,
        username_key=data.username.lower(),
        email=email,
        password_hash=hash_password(data.password),
        display_name=data.display_name.strip() or data.username,
    )
    db.add(user)
    db.commit()
    _open_session(db, response, user, settings)
    return user


@router.post("/login", response_model=UserMe)
def login(
    data: LoginIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    key = data.login.strip().lower()
    user = db.scalar(
        select(User).where(or_(User.username_key == key, User.email == key), User.is_active)
    )
    # Même message que le compte existe ou non (pas d'énumération des comptes)
    if user is None or not verify_password(user.password_hash, data.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants incorrects.")
    _open_session(db, response, user, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    token = request.cookies.get(settings.session_cookie)
    if token and (session := db.get(AuthSession, token_hash(token))):
        db.delete(session)
        db.commit()
    response.delete_cookie(settings.session_cookie, path="/")


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(current_user)) -> User:
    return user
