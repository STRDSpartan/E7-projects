"""Équipements : pièces, sets, statistiques principales et secondaires."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from e7showcase.models.stats import StatType


class GearSlot(StrEnum):
    WEAPON = "weapon"
    HELMET = "helmet"
    ARMOR = "armor"
    NECKLACE = "necklace"
    RING = "ring"
    BOOTS = "boots"


# Statistique principale imposée par emplacement (gauche de l'inventaire)
FIXED_MAIN_STAT: dict[GearSlot, StatType] = {
    GearSlot.WEAPON: StatType.ATK,
    GearSlot.HELMET: StatType.HP,
    GearSlot.ARMOR: StatType.DEF,
}


class GearSet(StrEnum):
    SPEED = "speed"
    ATTACK = "attack"
    HEALTH = "health"
    DEFENSE = "defense"
    CRITICAL = "critical"
    HIT = "hit"
    RESIST = "resist"
    DESTRUCTION = "destruction"
    LIFESTEAL = "lifesteal"
    COUNTER = "counter"
    UNITY = "unity"
    IMMUNITY = "immunity"
    RAGE = "rage"
    PENETRATION = "penetration"
    INJURY = "injury"
    PROTECTION = "protection"
    TORRENT = "torrent"
    REVENGE = "revenge"
    WARFARE = "warfare"
    PURSUIT = "pursuit"
    RIPOSTE = "riposte"
    REVERSAL = "reversal"
    WEAKENING = "weakening"  # « Affaiblissement » (client FR) — nom anglais à confirmer


class GearRank(StrEnum):
    NORMAL = "normal"
    GOOD = "good"
    RARE = "rare"
    HEROIC = "heroic"
    EPIC = "epic"


class StatLine(BaseModel):
    stat: StatType
    value: float
    rolls: int | None = Field(
        default=None, description="Nombre d'améliorations tombées sur la stat"
    )
    modified: bool = Field(default=False, description="Stat modifiée (pierre de réforge/modif)")


class Gear(BaseModel):
    slot: GearSlot
    set: GearSet | None = None
    rank: GearRank | None = None
    level: int | None = Field(default=None, ge=0, le=100)
    enhance: int = Field(default=0, ge=0, le=15)
    main: StatLine
    substats: list[StatLine] = Field(default_factory=list, max_length=4)
    reforged: bool = False
    score: int | None = Field(default=None, description="Score de la pièce affiché en jeu")
