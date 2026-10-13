"""Fiche de profil d'un joueur (écran « Profil » du jeu) : texte OCR → pseudo, serveur, guilde,
rang, et position du cadre de profil (visage du héros favori) à découper.

Repère : la ligne « Serveur Europe | 123456789 ». Le pseudo est juste dessous, le rang
(« S.Rank.20 ») ensuite ; la guilde est écrite sous son blason, à gauche ; le cadre de profil
est encore à gauche, à hauteur du pseudo. Les distances sont exprimées en hauteurs de la ligne
du serveur, pour ne dépendre ni de la résolution ni du recadrage. L'identifiant numérique du
joueur n'est pas conservé.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from e7showcase.reference import normalize
from e7showcase.vision.ocr import OcrLine

SERVERS = {
    "europe": "europe",
    "global": "global",
    "asie": "asia",
    "asia": "asia",
    "coree": "korea",
    "korea": "korea",
    "japon": "japan",
    "japan": "japan",
}
SERVER_RE = re.compile(r"serveur\s*([a-z]+)", re.I)
RANK_RE = re.compile(r"rank\W*(\d{1,3})", re.I)
UI_WORDS = {"amis", "infos de la saison", "meilleurs", "classements"}
# cadre de profil, en hauteurs de la ligne du serveur depuis son coin gauche (centre vertical)
AVATAR_DX, AVATAR_DY, AVATAR_R = -11.06, 2.3, 3.75


@dataclass
class ProfileCard:
    player: str
    server: str | None
    guild: str | None
    rank: int | None
    avatar: tuple[float, float, float]  # centre x, y et rayon du cadre, en pixels


def _cy(b: OcrLine) -> float:
    assert b.box is not None
    return (b.box[1] + b.box[3]) / 2


def parse_profile_card(lines: list[OcrLine]) -> ProfileCard | None:
    boxed = [b for b in lines if b.box is not None and b.text.strip()]
    anchor = next((b for b in boxed if SERVER_RE.search(normalize(b.text))), None)
    if anchor is None or anchor.box is None:
        return None
    x0, y0, x1, y1 = anchor.box
    h = max(y1 - y0, 1.0)
    server_word = SERVER_RE.search(normalize(anchor.text))
    server = SERVERS.get(server_word[1].lower()) if server_word else None
    below = sorted(
        (b for b in boxed if b is not anchor and abs(b.box[0] - x0) < 2 * h and _cy(b) > y1),  # type: ignore[index]
        key=_cy,
    )
    if not below or _cy(below[0]) - y1 > 3 * h:
        return None
    player = below[0].text.strip()[:40]
    rank = next(
        (int(m[1]) for b in below[1:3] if (m := RANK_RE.search(b.text.replace(" ", "")))), None
    )
    guild = next(
        (
            b.text.strip()[:40]
            for b in sorted(boxed, key=_cy)
            if b.box is not None
            and b.box[2] < x0
            and y0 < _cy(b) < y0 + 7 * h
            and normalize(b.text) not in UI_WORDS
            and re.search(r"[^\W\d_]{2}", b.text)
        ),
        None,
    )
    cy = (y0 + y1) / 2
    avatar = (x0 + AVATAR_DX * h, cy + AVATAR_DY * h, AVATAR_R * h)
    return ProfileCard(player=player, server=server, guild=guild, rank=rank, avatar=avatar)
