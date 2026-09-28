"""Gear score (convention communautaire, identique à Fribbels E7 Optimizer).

score = atk% + def% + hp% + eff + res
        + spd * 8/4 + crit_chance * 8/5 + crit_dmg * 8/7
        + atk_flat * 3.46/39 + def_flat * 4.99/31 + hp_flat * 3.09/174

Les poids sont exposés pour permettre une personnalisation par guilde.
"""

from __future__ import annotations

from e7showcase.models.gear import Gear
from e7showcase.models.stats import StatType

WEIGHTS: dict[StatType, float] = {
    StatType.ATK_PCT: 1.0,
    StatType.DEF_PCT: 1.0,
    StatType.HP_PCT: 1.0,
    StatType.EFFECTIVENESS: 1.0,
    StatType.EFFECT_RES: 1.0,
    StatType.SPD: 8 / 4,
    StatType.CRIT_CHANCE: 8 / 5,
    StatType.CRIT_DMG: 8 / 7,
    StatType.ATK: 3.46 / 39,
    StatType.DEF: 4.99 / 31,
    StatType.HP: 3.09 / 174,
    StatType.DUAL_ATTACK: 0.0,
}


def gear_score(gear: Gear, weights: dict[StatType, float] | None = None) -> float:
    w = weights or WEIGHTS
    return round(sum(s.value * w.get(s.stat, 0.0) for s in gear.substats), 1)


def roster_gear_score(gears: list[Gear]) -> float:
    return round(sum(gear_score(g) for g in gears), 1)
