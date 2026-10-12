"""Lecture d'une infobulle d'objet (inventaire) : emplacement, set, rang, amélioration, stats.

Entrée : les lignes de texte OCR de la capture, de haut en bas. Le module est pur (aucune
I/O) : l'import (app/importer.py) lui passe le texte lu sur la capture entière.

Disposition de l'infobulle en jeu : en-tête « +15 Arme Épique » (ordre variable), niveau,
stat principale, jusqu'à 4 stats secondaires, puis le set (« Set Vitesse ») et la description
de son effet — les lignes après le set (« Vitesse +25 % ») ne sont pas des stats de l'objet.
"""

from __future__ import annotations

import re

from e7showcase.models.gear import FIXED_MAIN_STAT, Gear, GearRank, GearSlot, StatLine
from e7showcase.parsers.gear_parser import parse_set
from e7showcase.parsers.stat_parser import StatParseError, parse_stat_line
from e7showcase.reference import normalize

SLOT_WORDS: dict[str, GearSlot] = {
    "arme": GearSlot.WEAPON,
    "weapon": GearSlot.WEAPON,
    "casque": GearSlot.HELMET,
    "helmet": GearSlot.HELMET,
    "armure": GearSlot.ARMOR,
    "armor": GearSlot.ARMOR,
    "collier": GearSlot.NECKLACE,
    "necklace": GearSlot.NECKLACE,
    "bague": GearSlot.RING,
    "anneau": GearSlot.RING,
    "ring": GearSlot.RING,
    "bottes": GearSlot.BOOTS,
    "boots": GearSlot.BOOTS,
}
RANK_WORDS: dict[str, GearRank] = {
    "epique": GearRank.EPIC,
    "epic": GearRank.EPIC,
    "heroique": GearRank.HEROIC,
    "heroic": GearRank.HEROIC,
    "rare": GearRank.RARE,
    "bon": GearRank.GOOD,
    "good": GearRank.GOOD,
    "normal": GearRank.NORMAL,
}
_ENHANCE_RE = re.compile(r"\+\s*(\d{1,2})\b")
_LEVEL_RE = re.compile(r"\b(?:niv|lv|lvl|niveau)\.?\s*(\d{2,3})\b")
_SET_RE = re.compile(r"^(?:set|ensemble)\b|\bset$")
# Lignes d'en-tête qui contiennent un mot d'emplacement sans être une stat (« Arme épique »)
_MAX_HEADER_WORDS = 4


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", normalize(text))


def parse_item_lines(lines: list[str], lang: str = "fr") -> Gear | None:
    """Objet décrit par une infobulle, ou None si le texte n'en est pas une."""
    slot: GearSlot | None = None
    rank: GearRank | None = None
    enhance = 0
    level: int | None = None
    gear_set = None
    stats: list[StatLine] = []
    for raw in lines:
        text = raw.strip()
        if not text:
            continue
        norm = normalize(text)
        words = _words(text)
        if gear_set is None and _SET_RE.search(norm):
            gear_set = parse_set(text, lang)
            if gear_set is not None:
                continue
        if gear_set is not None:
            continue  # description de l'effet du set : pas des stats de l'objet
        if slot is None and len(words) <= _MAX_HEADER_WORDS:
            found = next((SLOT_WORDS[w] for w in words if w in SLOT_WORDS), None)
            if found is not None:
                slot = found
                rank = rank or next((RANK_WORDS[w] for w in words if w in RANK_WORDS), None)
                if m := _ENHANCE_RE.search(text):
                    enhance = min(int(m.group(1)), 15)
                continue
        if rank is None and len(words) <= 2 and any(w in RANK_WORDS for w in words):
            rank = next(RANK_WORDS[w] for w in words if w in RANK_WORDS)
            continue
        if level is None and (m := _LEVEL_RE.search(norm)):
            level = int(m.group(1))
            continue
        if not enhance and re.fullmatch(r"\+\s*\d{1,2}", text):
            enhance = min(int(text.lstrip("+ ")), 15)
            continue
        try:
            stats.append(parse_stat_line(text, lang))
        except StatParseError:
            continue
    if slot is None or not stats:
        return None
    main, subs = stats[0], stats[1:5]
    expected = FIXED_MAIN_STAT.get(slot)
    if expected is not None and main.stat != expected:
        return None  # lecture incohérente : mieux vaut ignorer la capture
    return Gear(
        slot=slot,
        set=gear_set,
        rank=rank,
        level=level if level is not None and level <= 100 else None,
        enhance=enhance,
        main=main,
        substats=subs,
    )
