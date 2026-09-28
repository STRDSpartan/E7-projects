"""Parsing de la fiche de stats d'un héros (onglet détails)."""

from __future__ import annotations

from rapidfuzz import fuzz, process

from e7showcase.models.hero import HeroStats
from e7showcase.models.stats import StatType
from e7showcase.parsers.stat_parser import parse_stat_block
from e7showcase.reference import hero_names

_FIELD = {
    StatType.ATK: "atk",
    StatType.HP: "hp",
    StatType.DEF: "defense",
    StatType.SPD: "spd",
    StatType.CRIT_CHANCE: "crit_chance",
    StatType.CRIT_DMG: "crit_dmg",
    StatType.EFFECTIVENESS: "effectiveness",
    StatType.EFFECT_RES: "effect_res",
    StatType.DUAL_ATTACK: "dual_attack",
}


def parse_hero_stats(lines: list[str], lang: str = "fr") -> HeroStats:
    """Sur la fiche héros, ATK/PV/DEF sont des valeurs absolues même sans '%'."""
    stats = HeroStats()
    for line in parse_stat_block(lines, lang):
        # Sur la fiche, 'Attaque' n'est jamais un pourcentage
        stat = {
            StatType.ATK_PCT: StatType.ATK,
            StatType.HP_PCT: StatType.HP,
            StatType.DEF_PCT: StatType.DEF,
        }.get(line.stat, line.stat)
        field = _FIELD.get(stat)
        if field:
            value = line.value if stat.is_percent else int(line.value)
            setattr(stats, field, value)
    return stats


def match_hero_name(ocr_text: str, lang: str = "fr", score_cutoff: float = 70) -> str | None:
    """Associe un nom OCR bruité au nom de référence le plus proche."""
    names = hero_names(lang) + hero_names("en")
    match = process.extractOne(
        ocr_text.strip(), names, scorer=fuzz.WRatio, score_cutoff=score_cutoff
    )
    return match[0] if match else None
