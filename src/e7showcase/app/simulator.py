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


# Héros adverse connu par son seul nom (défense ennemie en GvG) : stats types d'un héros équipé
# pour le JcJ, selon sa classe (ordre de grandeur, signalé « estimé » dans le résultat)
_STAT_KEYS = ("atk", "hp", "def", "spd", "cc", "cd", "eff", "res")
ESTIMATED_STATS: dict[str, dict[str, float]] = {
    role: dict(zip(_STAT_KEYS, values, strict=True))
    for role, values in {
        "warrior": (4000, 17000, 1000, 230, 70, 250, 0, 50),
        "knight": (1800, 25000, 1800, 210, 15, 150, 50, 100),
        "thief": (3800, 15000, 850, 260, 80, 260, 0, 50),
        "ranger": (3800, 15500, 900, 240, 75, 250, 50, 50),
        "mage": (3800, 14500, 850, 230, 70, 250, 80, 50),
        "soul-weaver": (1500, 20000, 1300, 250, 15, 150, 150, 150),
    }.items()
}


class SimError(ValueError):
    pass


def estimated_fighter(name: str) -> Fighter:
    """Combattant adverse aux stats types de sa classe (compétences réelles du héros)."""
    from e7showcase.reference import hero_info

    info = hero_info(name) or {}
    data = skills_of(name) or {}
    if not data:
        raise SimError(f"héros inconnu ou non simulable : {name}")
    role = str(data.get("class") or info.get("role") or "warrior")
    s = ESTIMATED_STATS.get(role, ESTIMATED_STATS["warrior"])
    return Fighter(
        name=f"{info.get('fr') or info.get('en') or name} (estimé)",
        atk=s["atk"],
        hp=s["hp"],
        defense=s["def"],
        spd=s["spd"],
        crit_chance=s["cc"],
        crit_dmg=s["cd"],
        element=data.get("element") or info.get("element"),
        skills=data.get("skills", {}),
        effectiveness=s["eff"],
        effect_res=s["res"],
        role=role,
    )


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
        team = [
            estimated_fighter(str(r.get("name", ""))[:40])
            if isinstance(r, dict) and r.get("estimate")
            else fighter(_hero(store, r))
            for r in refs
        ]
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
