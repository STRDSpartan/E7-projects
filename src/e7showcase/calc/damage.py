"""Simulateur de dégâts : formule communautaire d'Epic Seven (celle du calculateur E7Calc).

    attaque  = attaque finale × (1 + buffs d'attaque)
    offensif = ((attaque × taux + bonus fixe) × 1,871) × puissance × (1 + amélioration)
               × avantage élémentaire (1,1) × (1 + bonus de dégâts)
    défensif = (1 − réduction) / ((déf. cible × (1 + mod. déf.) / 300) × (1 − pénétration) + 1)
    normal = offensif × défensif ; critique = normal × dégâts critiques (plafond 350 %) ;
    écrasant = normal × 1,3 ; raté = normal × 0,75.

Les multiplicateurs de chaque compétence viennent de data/reference/skills.json
(scripts/update_skills.py). Les bonus conditionnels propres à certains héros (cible avec un
buff, PV restants...) ne sont pas appliqués : la compétence est alors marquée `conditional`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from e7showcase.reference import hero_info, load

DAMAGE_CONSTANT = 1.871
ELEMENTAL_ADVANTAGE = 1.1
CRIT_DAMAGE_CAP = 3.5
PENETRATION_SET = 0.15
ATTACK_BUFFS = {"none": 0.0, "up": 0.5, "great": 0.75, "down": -0.5}
DEFENSE_BUFFS = {"none": 0.0, "up": 0.6, "down": -0.7}
ADVANTAGE = {"fire": "earth", "earth": "ice", "ice": "fire", "light": "dark", "dark": "light"}


def _key(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    key = re.sub(r"[^a-z0-9]", "", ascii_text.replace("&", "and"))
    return ALIASES.get(key, key)


# Noms différents entre le référentiel (e7codex) et E7Calc
ALIASES = {"summersdisciplealexa": "summerdisciplealexa", "elphelt": "elpheltvalentine"}


@cache
def _skills_by_key() -> dict[str, dict[str, Any]]:
    return {_key(k): v for k, v in load("skills")["heroes"].items()}


def hero_skills(name: str) -> dict[str, Any] | None:
    """Données de compétences d'un héros (nom FR ou EN)."""
    info = hero_info(name) or {}
    for candidate in (info.get("en"), name, info.get("fr")):
        if candidate and (data := _skills_by_key().get(_key(candidate))):
            return data
    return None


@dataclass
class Fighter:
    """Statistiques finales (affichées en jeu) d'un combattant."""

    name: str
    atk: float
    hp: float
    defense: float
    spd: float = 100
    crit_chance: float = 15  # %
    crit_dmg: float = 150  # %
    element: str | None = None
    skills: dict[str, Any] = field(default_factory=dict)
    effectiveness: float = 0  # %
    effect_res: float = 0  # %


@dataclass
class Options:
    attack_buff: str = "none"  # none | up | great | down
    target_defense_buff: str = "none"  # none | up | down
    damage_increase: float = 0.0  # % (bonus de dégâts divers)
    damage_reduction: float = 0.0  # % (réduction de dégâts de la cible)
    soulburn: bool = False
    molagoras: bool = True  # compétences améliorées au maximum
    elemental_advantage: bool | None = None  # None : déduit des éléments
    penetration_set: bool = False
    rage_set: bool = False  # cible affaiblie
    torrent_set: bool = False


def _enhance(skill: dict[str, Any], opts: Options) -> float:
    return 1 + (sum(skill.get("enhance", [])) if opts.molagoras else 0)


def skill_damage(
    attacker: Fighter, skill: dict[str, Any], target: Fighter, opts: Options | None = None
) -> dict[str, float | None]:
    """Dégâts d'une frappe : normal, critique, écrasant, raté et espérance (selon les chances)."""
    o = opts or Options()
    burn = o.soulburn and skill.get("rate_sb") is not None
    rate = float(skill["rate_sb"] if burn else skill["rate"])
    pow_ = float(skill.get("pow_sb", skill.get("pow", 1)) if burn else skill.get("pow", 1))
    stats = {
        "caster_MaxHP": attacker.hp,
        "caster_Defense": attacker.defense,
        "caster_Speed": attacker.spd,
        "target_MaxHP": target.hp,
    }
    flat = sum(ratio * stats.get(stat, 0) for stat, ratio in (skill.get("flat") or {}).items())
    atk = attacker.atk * (1 + ATTACK_BUFFS.get(o.attack_buff, 0))
    advantage = (
        o.elemental_advantage
        if o.elemental_advantage is not None
        else target.element is not None and ADVANTAGE.get(attacker.element or "") == target.element
    )
    bonus = 1 + o.damage_increase / 100 + (0.3 if o.rage_set else 0) + (0.1 if o.torrent_set else 0)
    offensive = (
        (atk * rate + flat)
        * DAMAGE_CONSTANT
        * pow_
        * _enhance(skill, o)
        * (ELEMENTAL_ADVANTAGE if advantage else 1)
        * bonus
    )
    pen = 1 - float(skill.get("pen", 0) or 0)
    if o.penetration_set and skill.get("single"):
        pen *= 1 - PENETRATION_SET
    defense = target.defense * (1 + DEFENSE_BUFFS.get(o.target_defense_buff, 0))
    defensive = (1 - o.damage_reduction / 100) / ((defense / 300) * max(pen, 0) + 1)
    normal = offensive * defensive
    crit = None if skill.get("no_crit") else normal * min(attacker.crit_dmg / 100, CRIT_DAMAGE_CAP)
    cc = 0 if crit is None else min(max(attacker.crit_chance, 0), 100) / 100
    expected = cc * (crit or 0) + (1 - cc) * normal
    return {
        "normal": round(normal),
        "crit": round(crit) if crit is not None else None,
        "crush": round(normal * 1.3),
        "miss": round(normal * 0.75),
        "expected": round(expected),
    }


def damage_table(
    attacker: Fighter, target: Fighter, opts: Options | None = None
) -> list[dict[str, Any]]:
    """Une ligne par compétence offensive (et sa version âme brûlée si elle existe)."""
    o = opts or Options()
    rows: list[dict[str, Any]] = []
    for sid, skill in sorted(attacker.skills.items()):
        if skill.get("rate") is None:
            continue  # compétence sans dégâts (soin, buff...)
        variants = [False, True] if skill.get("rate_sb") is not None else [False]
        for burn in variants:
            opt = Options(**{**o.__dict__, "soulburn": burn})
            row: dict[str, Any] = {"skill": sid.upper() + (" (âme brûlée)" if burn else "")}
            row.update(skill_damage(attacker, skill, target, opt))
            row["aoe"] = bool(skill.get("aoe"))
            row["conditional"] = skill.get("conditional") or []
            rows.append(row)
    return rows
