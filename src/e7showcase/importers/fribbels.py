"""Import d'un export JSON de Fribbels E7 Optimizer (« Save/Export » de l'optimiseur).

Beaucoup de joueurs ont déjà leur inventaire dans Fribbels : cet import donne une
vitrine immédiate sans passer par le scan OCR. Le parseur est tolérant car le
format a évolué selon les versions — le valider avec un export réel
(tests/fixtures/fribbels_export.json est un échantillon minimal).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e7showcase.models.gear import Gear, GearRank, GearSet, GearSlot, StatLine
from e7showcase.models.hero import Hero, HeroStats
from e7showcase.models.roster import Roster
from e7showcase.models.stats import StatType

STAT_MAP: dict[str, StatType] = {
    "Attack": StatType.ATK,
    "AttackPercent": StatType.ATK_PCT,
    "Health": StatType.HP,
    "HealthPercent": StatType.HP_PCT,
    "Defense": StatType.DEF,
    "DefensePercent": StatType.DEF_PCT,
    "Speed": StatType.SPD,
    "CriticalHitChancePercent": StatType.CRIT_CHANCE,
    "CriticalHitDamagePercent": StatType.CRIT_DMG,
    "EffectivenessPercent": StatType.EFFECTIVENESS,
    "EffectResistancePercent": StatType.EFFECT_RES,
}
SLOT_MAP = {s.value.capitalize(): s for s in GearSlot}


def _stat(raw: dict[str, Any]) -> StatLine | None:
    stat = STAT_MAP.get(raw.get("type", ""))
    if stat is None:
        return None
    return StatLine(
        stat=stat,
        value=float(raw.get("value", 0)),
        rolls=raw.get("rolls"),
        modified=bool(raw.get("modified", False)),
    )


def _gear(item: dict[str, Any]) -> Gear | None:
    slot = SLOT_MAP.get(item.get("gear", ""))
    main = _stat(item.get("main", {}))
    if slot is None or main is None:
        return None
    set_name = str(item.get("set", "")).removesuffix("Set").lower()
    rank = str(item.get("rank", "")).lower()
    return Gear(
        slot=slot,
        set=GearSet(set_name) if set_name in GearSet._value2member_map_ else None,
        rank=GearRank(rank) if rank in GearRank._value2member_map_ else None,
        level=item.get("level"),
        enhance=int(item.get("enhance", 0)),
        main=main,
        substats=[s for s in (_stat(x) for x in item.get("substats", [])) if s][:4],
        reforged=bool(item.get("reforgeable") is False and item.get("level") == 90),
    )


def _hero_stats(hero: dict[str, Any]) -> HeroStats:
    # Fribbels stocke parfois les stats calculées sous "stats" ou "equippedStats"
    s = hero.get("equippedStats") or hero.get("stats") or {}
    return HeroStats.model_validate(
        {
            "atk": int(s.get("atk", 0)),
            "hp": int(s.get("hp", 0)),
            "def": int(s.get("def", 0)),
            "spd": int(s.get("spd", 0)),
            "crit_chance": float(s.get("cr", 0)),
            "crit_dmg": float(s.get("cd", 0)),
            "effectiveness": float(s.get("eff", 0)),
            "effect_res": float(s.get("res", 0)),
            "dual_attack": float(s.get("dac", 0)),
        }
    )


def parse_fribbels(data: dict[str, Any], player: str = "Unknown") -> Roster:
    items = data.get("items", [])
    by_owner: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        owner = item.get("equippedById")
        if owner:
            by_owner.setdefault(str(owner), []).append(item)

    roster = Roster(player=player)
    for raw in data.get("heroes", []):
        hero = Hero(
            name=raw.get("name", "Inconnu"),
            stars=raw.get("stars"),
            level=raw.get("level") or None,
            element=raw.get("element"),
            role=raw.get("role"),
            artifact=raw.get("artifactName"),
            stats=_hero_stats(raw),
            source="fribbels",
        )
        for item in by_owner.get(str(raw.get("id")), []):
            if gear := _gear(item):
                hero.gear[gear.slot] = gear
        roster.upsert(hero)
    return roster


def import_file(path: Path, player: str = "Unknown") -> Roster:
    with path.open(encoding="utf-8") as f:
        return parse_fribbels(json.load(f), player)
