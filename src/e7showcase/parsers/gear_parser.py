"""Assemblage d'une pièce d'équipement à partir de textes OCR (libellés en toutes lettres).

Utilisé pour les écrans qui affichent les libellés (infobulle d'objet) ; la fiche
« Infos de héros » utilise des icônes, voir scanner/hero_scanner.py."""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from e7showcase.models.gear import FIXED_MAIN_STAT, Gear, GearSet, GearSlot
from e7showcase.parsers.stat_parser import StatParseError, parse_stat_block, parse_stat_line
from e7showcase.reference import load, normalize

_ENHANCE_RE = re.compile(r"\+\s*(\d{1,2})")
_LEVEL_RE = re.compile(r"(\d{2,3})")


def parse_set(text: str, lang: str = "fr") -> GearSet | None:
    sets = load("sets")
    choices = {normalize(v[lang]): k for k, v in sets.items()}
    choices.update({normalize(v["en"]): k for k, v in sets.items()})
    cleaned = normalize(text)
    for prefix in ("set ", "ensemble ", "ensemble de "):
        cleaned = cleaned.removeprefix(prefix)
    cleaned = cleaned.removesuffix(" set")
    match = process.extractOne(cleaned, choices.keys(), scorer=fuzz.WRatio, score_cutoff=70)
    return GearSet(choices[match[0]]) if match else None


def parse_gear(
    slot: GearSlot,
    *,
    main_text: str,
    substat_lines: list[str],
    set_text: str | None = None,
    enhance_text: str | None = None,
    level_text: str | None = None,
    lang: str = "fr",
) -> Gear:
    main = parse_stat_line(main_text, lang)
    expected = FIXED_MAIN_STAT.get(slot)
    if expected is not None and main.stat != expected:
        raise StatParseError(f"Stat principale {main.stat} incohérente pour {slot}")

    enhance = 0
    if enhance_text and (m := _ENHANCE_RE.search(enhance_text)):
        enhance = min(int(m.group(1)), 15)
    level = None
    if level_text and (m := _LEVEL_RE.search(level_text)):
        level = int(m.group(1))

    return Gear(
        slot=slot,
        set=parse_set(set_text, lang) if set_text else None,
        enhance=enhance,
        level=level,
        main=main,
        substats=parse_stat_block(substat_lines, lang)[:4],
    )
