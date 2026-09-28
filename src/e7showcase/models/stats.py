"""Types de statistiques d'Epic Seven."""

from __future__ import annotations

from enum import StrEnum


class StatType(StrEnum):
    ATK = "atk"
    ATK_PCT = "atk_pct"
    HP = "hp"
    HP_PCT = "hp_pct"
    DEF = "def"
    DEF_PCT = "def_pct"
    SPD = "spd"
    CRIT_CHANCE = "crit_chance"
    CRIT_DMG = "crit_dmg"
    EFFECTIVENESS = "effectiveness"
    EFFECT_RES = "effect_res"
    DUAL_ATTACK = "dual_attack"

    @property
    def is_percent(self) -> bool:
        return self not in {StatType.ATK, StatType.HP, StatType.DEF, StatType.SPD}

    @property
    def label(self) -> str:
        return STAT_LABELS_FR[self]


STAT_LABELS_FR: dict[StatType, str] = {
    StatType.ATK: "Attaque",
    StatType.ATK_PCT: "Attaque %",
    StatType.HP: "PV",
    StatType.HP_PCT: "PV %",
    StatType.DEF: "Défense",
    StatType.DEF_PCT: "Défense %",
    StatType.SPD: "Vitesse",
    StatType.CRIT_CHANCE: "Chances crit.",
    StatType.CRIT_DMG: "Dégâts crit.",
    StatType.EFFECTIVENESS: "Efficacité",
    StatType.EFFECT_RES: "Résistance",
    StatType.DUAL_ATTACK: "Attaque double",
}
