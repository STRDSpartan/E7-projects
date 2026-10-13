"""Écrans de la guerre de guilde : carte (guildes, forteresses) et forteresse (joueurs).

- Carte : pour chaque guilde, nom, serveur, Ravage, tickets d'attaque et membres (la nôtre en
  haut, l'adverse en bas) ; temps restant ; forteresses (nom, défenses restantes « x/y » et
  position à l'écran).
- Forteresse : pseudos des joueurs en défense et leur position (normalisée 0–1), pour
  reproduire la disposition du jeu.

Repères uniquement textuels (boîtes de l'OCR), positions rendues relatives à l'image.
Fonctions pures, sans I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from e7showcase.reference import normalize
from e7showcase.vision.ocr import OcrLine

FORTRESS_RE = re.compile(r"^(forteresse|fortress|stronghold)\s*(.*)$", re.I)
RAVAGE_RE = re.compile(r"^(ravage|destruction|devastation)\s*[:：]?\s*(\d{1,6})$", re.I)
RATIO_RE = re.compile(r"^(\d{1,3})\s*/\s*(\d{1,3})$")
SERVERS = {"europe", "global", "asia", "asie", "korea", "coree", "japan", "japon"}
# libellés de l'interface (et de la barre des tâches) qui ne sont pas des pseudos
UI_WORDS = {"guerre", "war", "ravage", "destruction", "rechercher", "fra", "eclaircies"}
NAME_MIN_CONF = 0.8


@dataclass
class Guild:
    name: str = ""
    server: str = ""
    ravage: int | None = None
    tickets: tuple[int, int] | None = None
    members: tuple[int, int] | None = None


@dataclass
class Fortress:
    name: str
    left: int | None = None
    total: int | None = None
    x: float = 0.5  # centre, relatif à l'image
    y: float = 0.5


@dataclass
class WarMap:
    ours: Guild
    enemy: Guild
    fortresses: list[Fortress] = field(default_factory=list)
    ends_in: str = ""


@dataclass
class Player:
    name: str
    x: float
    y: float


def _box(b: OcrLine) -> tuple[float, float, float, float]:
    assert b.box is not None
    return b.box


def _cx(b: OcrLine) -> float:
    x0, _, x1, _ = _box(b)
    return (x0 + x1) / 2


def _cy(b: OcrLine) -> float:
    _, y0, _, y1 = _box(b)
    return (y0 + y1) / 2


def _ratio(text: str) -> tuple[int, int] | None:
    m = RATIO_RE.match(re.sub(r"[^\d/]", "", text))
    return (int(m[1]), int(m[2])) if m else None


def parse_war_map(lines: list[OcrLine], size: tuple[int, int]) -> WarMap | None:
    boxes = [b for b in lines if b.box]
    w, h = size
    ravages = sorted((b for b in boxes if RAVAGE_RE.match(b.text.replace(" ", ""))), key=_cy)
    fortresses = []
    for b in boxes:
        if not (m := FORTRESS_RE.match(b.text.strip())):
            continue
        rest = m[2].strip()
        name = f"{m[1][0].upper()}{m[1][1:].lower()} {rest}".strip()
        line_h = _box(b)[3] - _box(b)[1]
        above = [  # « x/y » dans le cercle, juste au-dessus du nom
            r
            for r in boxes
            if (ratio := _ratio(r.text))
            and 0 < _cy(b) - _cy(r) < 3 * line_h
            and abs(_cx(r) - _cx(b)) < (_box(b)[2] - _box(b)[0])
        ]
        ratio = _ratio(min(above, key=lambda r: _cy(b) - _cy(r)).text) if above else None
        anchor = min(above, key=lambda r: _cy(b) - _cy(r)) if above else b
        fortresses.append(
            Fortress(
                name=name,
                left=ratio[0] if ratio else None,
                total=ratio[1] if ratio else None,
                x=round(_cx(b) / w, 4),
                y=round(_cy(anchor) / h, 4),
            )
        )
    if not ravages and not fortresses:
        return None
    guilds = [_guild(boxes, r) for r in ravages[:2]]
    while len(guilds) < 2:
        guilds.append(Guild())
    ends = next((b for b in boxes if re.match(r"^(dans|in)\s+\d", b.text.strip(), re.I)), None)
    fortresses.sort(key=lambda f: f.x)
    return WarMap(
        ours=guilds[0], enemy=guilds[1], fortresses=fortresses, ends_in=ends.text if ends else ""
    )


def _guild(boxes: list[OcrLine], ravage: OcrLine) -> Guild:
    m = RAVAGE_RE.match(ravage.text.replace(" ", ""))
    g = Guild(ravage=int(m[2]) if m else None)
    x0, y0, _, y1 = _box(ravage)
    line_h = y1 - y0
    above = [
        b
        for b in boxes
        if 0 < y0 - _cy(b) < 2 * line_h and _box(b)[0] < x0 + 6 * line_h and b is not ravage
    ]
    for b in sorted(above, key=lambda b: _box(b)[0]):
        word = normalize(b.text)
        if word in SERVERS:
            g.server = b.text.strip()
        elif not g.name and len(word) >= 2:
            g.name = b.text.strip()
    below = sorted((b for b in boxes if 0 < _cy(b) - y1 < 3.5 * line_h and _ratio(b.text)), key=_cy)
    if below:
        g.tickets = _ratio(below[0].text)
    if len(below) > 1:
        g.members = _ratio(below[1].text)
    return g


def parse_fortress(lines: list[OcrLine], size: tuple[int, int]) -> list[Player]:
    """Pseudos des joueurs d'une forteresse ; la jauge de Ravage (à gauche), le titre et
    la barre des tâches de Windows (en bas) sont écartés."""
    w, h = size
    out = []
    for b in lines:
        if b.box is None or b.confidence < NAME_MIN_CONF:
            continue
        text = b.text.strip()
        word = normalize(text)
        x, y = _cx(b) / w, _cy(b) / h
        if not 0.12 < y < 0.955 or x < 0.09:
            continue
        if len(text) < 3 or word in UI_WORDS or not re.search(r"[^\W\d_]", text):
            continue
        if re.fullmatch(r"[\d\s:/.,%°c]+", word):
            continue
        out.append(Player(name=text, x=round(x, 4), y=round(y, 4)))
    return sorted(out, key=lambda p: (p.y, p.x))


# Cases du fort (vue d'une forteresse), en coordonnées normalisées de l'image de fond du fort
# (`app/media/gvg-fort.webp`, 2000 x 1066, sans le HUD du jeu).
FORT_SLOTS: list[tuple[float, float]] = [
    (390 / 2000, 297 / 1066),
    (777 / 2000, 290 / 1066),
    (1388 / 2000, 300 / 1066),
    (1045 / 2000, 520 / 1066),
    (1773 / 2000, 493 / 1066),
    (343 / 2000, 578 / 1066),
    (808 / 2000, 682 / 1066),
    (1468 / 2000, 663 / 1066),
    (578 / 2000, 820 / 1066),
    (350 / 2000, 847 / 1066),
    (1635 / 2000, 803 / 1066),
    (1050 / 2000, 897 / 1066),
    (1433 / 2000, 935 / 1066),
]
# pseudo → case : le portrait (sur la case) est au-dessus du pseudo, un peu à droite
NAME_TO_SLOT = (0.02, -0.065)
SLOT_MAX_DIST = 0.12


def assign_slots(players: list[Player]) -> list[int | None]:
    """Case du fort occupée par chaque joueur (la plus proche, sans doublon), ou None."""
    dx, dy = NAME_TO_SLOT
    pairs = sorted(
        (((p.x + dx - sx) ** 2 + ((p.y + dy - sy) * 0.53) ** 2) ** 0.5, i, k)
        for i, p in enumerate(players)
        for k, (sx, sy) in enumerate(FORT_SLOTS)
    )
    out: list[int | None] = [None] * len(players)
    used: set[int] = set()
    for dist, i, k in pairs:
        if dist > SLOT_MAX_DIST or out[i] is not None or k in used:
            continue
        out[i] = k
        used.add(k)
    return out
