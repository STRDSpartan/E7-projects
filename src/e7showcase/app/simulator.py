"""Simulateurs de l'application : combattants construits à partir des héros des profils."""

from __future__ import annotations

from typing import Any

from e7showcase.app.profiles import ProfileStore
from e7showcase.calc.battle import simulate
from e7showcase.calc.damage import ATTACK_BUFFS, DEFENSE_BUFFS, Fighter, Options, damage_table
from e7showcase.calc.damage import hero_skills as skills_of
from e7showcase.models.hero import Hero

MAX_TEAM = 4
MAX_RUNS = 5000
LIFESTEAL_SET = 20  # % (sets.json : « Absorbs 20% of damage dealt as Health »)
COUNTER_SET_CHANCE = 30  # % (data/reference/sets.json : « 30% chance to counterattack »)


class SimError(ValueError):
    pass


def fighter(hero: Hero) -> Fighter:
    data = skills_of(hero.name) or {}
    s = hero.stats
    return Fighter(
        name=hero.name,
        atk=s.atk,
        hp=s.hp,
        defense=s.defense,
        spd=max(s.spd, 1),
        crit_chance=s.crit_chance,
        crit_dmg=s.crit_dmg or 150,
        element=hero.element or data.get("element"),
        skills=data.get("skills", {}),
        effectiveness=s.effectiveness,
        effect_res=s.effect_res,
        counter_chance=COUNTER_SET_CHANCE if "counter" in hero.sets else 0,
        lifesteal=LIFESTEAL_SET if "lifesteal" in hero.sets else 0,
        role=data.get("class"),
    )


def catalog(store: ProfileStore) -> list[dict[str, Any]]:
    """Héros de tous les profils (mes profils et vitrines reçues), utilisables en simulation."""
    out = []
    for info in store.list():
        for hero in store.load(info.id).heroes:
            out.append(
                {
                    "ref": f"{info.id}/{hero.name}",
                    "profile": info.player,
                    "name": hero.name,
                    "element": hero.element,
                    "atk": hero.stats.atk,
                    "hp": hero.stats.hp,
                    "def": hero.stats.defense,
                    "spd": hero.stats.spd,
                    "simulable": skills_of(hero.name) is not None,
                }
            )
    return out


def _hero(store: ProfileStore, ref: Any) -> Hero:
    if not isinstance(ref, str) or "/" not in ref:
        raise SimError("héros invalide")
    pid, name = ref.split("/", 1)
    try:
        roster = store.load(pid)
    except (KeyError, OSError) as exc:
        raise SimError("profil introuvable") from exc
    for hero in roster.heroes:
        if hero.name == name:
            return hero
    raise SimError(f"héros introuvable : {name}")


def _number(value: Any, low: float, high: float, default: float) -> float:
    try:
        return min(max(float(value), low), high)
    except (TypeError, ValueError):
        return default


def options(raw: Any) -> Options:
    r: dict[str, Any] = raw if isinstance(raw, dict) else {}
    adv = r.get("elemental_advantage")
    atk_buff = str(r.get("attack_buff", "none"))
    def_buff = str(r.get("target_defense_buff", "none"))
    return Options(
        attack_buff=atk_buff if atk_buff in ATTACK_BUFFS else "none",
        target_defense_buff=def_buff if def_buff in DEFENSE_BUFFS else "none",
        damage_increase=_number(r.get("damage_increase"), -100, 500, 0),
        damage_reduction=_number(r.get("damage_reduction"), 0, 100, 0),
        molagoras=bool(r.get("molagoras", True)),
        elemental_advantage=adv if isinstance(adv, bool) else None,
        penetration_set=bool(r.get("penetration_set")),
        rage_set=bool(r.get("rage_set")),
        torrent_set=bool(r.get("torrent_set")),
    )


def _target(store: ProfileStore, raw: Any) -> Fighter:
    if isinstance(raw, dict) and raw.get("ref"):
        return fighter(_hero(store, raw["ref"]))
    r = raw if isinstance(raw, dict) else {}
    return Fighter(
        name="Cible",
        atk=0,
        hp=_number(r.get("hp"), 1, 10**7, 20000),
        defense=_number(r.get("def"), 0, 20000, 1000),
        element=r.get("element") if isinstance(r.get("element"), str) else None,
    )


def damage(store: ProfileStore, body: dict[str, Any]) -> dict[str, Any]:
    attacker = fighter(_hero(store, body.get("attacker")))
    if not attacker.skills:
        raise SimError(f"multiplicateurs inconnus pour {attacker.name}")
    target = _target(store, body.get("target"))
    return {
        "attacker": attacker.name,
        "target": target.name,
        "rows": damage_table(attacker, target, options(body.get("options"))),
    }


def battle(store: ProfileStore, body: dict[str, Any]) -> dict[str, Any]:
    teams = []
    for key in ("team_a", "team_b"):
        refs = body.get(key)
        if not isinstance(refs, list) or not 1 <= len(refs) <= MAX_TEAM:
            raise SimError(f"chaque équipe compte de 1 à {MAX_TEAM} héros")
        team = [fighter(_hero(store, r)) for r in refs]
        if missing := [f.name for f in team if not f.skills]:
            raise SimError("multiplicateurs inconnus pour " + ", ".join(missing))
        teams.append(team)
    raw = body.get("cooldowns")
    raw_cd: dict[str, Any] = raw if isinstance(raw, dict) else {}
    cooldowns = {k: int(_number(raw_cd.get(k), 0, 10, d)) for k, d in (("s2", 3), ("s3", 4))}
    runs = int(_number(body.get("runs"), 1, MAX_RUNS, 1000))
    result = simulate(
        teams[0], teams[1], runs, cooldowns=cooldowns, options=options(body.get("options"))
    )
    result["teams"] = [[f.name for f in t] for t in teams]
    return result
