"""Mots de passe (Argon2) et jetons de session (aléatoires, seul le hash est stocké)."""

from __future__ import annotations

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_problem(password: str) -> str | None:
    """Règles minimales ; None si le mot de passe est acceptable."""
    if len(password) < 10:
        return "Le mot de passe doit contenir au moins 10 caractères."
    if len(password) > 128:
        return "Le mot de passe ne doit pas dépasser 128 caractères."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Le mot de passe doit contenir au moins une lettre et un chiffre."
    return None


def new_session_token() -> tuple[str, str]:
    """(jeton pour le cookie, hash à stocker)."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
