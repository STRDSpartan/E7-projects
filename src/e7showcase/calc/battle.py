"""Simulateur de combat simplifié : deux équipes (1 à 4 héros) s'affrontent jusqu'à la mort.

Modèle :
- jauge de combat : chaque héros avance de sa vitesse ; il joue quand elle atteint 100 %
  (le plus rapide joue le plus souvent, comme en jeu) ;
- compétences : S3 dès qu'elle est disponible, sinon S2 offensive, sinon S1 ; temps de
  recharge par défaut S2 = 3 tours, S3 = 4 tours (modifiables) ;
- cible : l'ennemi vivant aux PV les plus bas (les compétences de zone touchent tout le monde) ;
- dégâts : formule de calc/damage.py, coup critique tiré selon les chances de critique.

Non simulé : soins, barrières, buffs et débuffs appliqués par les compétences, effets
passifs, artefacts, contre-attaques, esquive. Le résultat donne un ordre de grandeur, pas
une prédiction exacte d'un combat réel. Plusieurs milliers de combats (graine aléatoire
fixe) donnent un taux de victoire reproductible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from e7showcase.calc.damage import Fighter, Options, skill_damage

MAX_ACTIONS = 300
DEFAULT_COOLDOWNS = {"s1": 0, "s2": 3, "s3": 4}


@dataclass
class _Unit:
    fighter: Fighter
    team: int
    hp: float
    gauge: float = 0.0
    cooldowns: dict[str, int] = field(default_factory=dict)

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class BattleResult:
    winner: int | None  # 0, 1, ou None (match nul / limite atteinte)
    actions: int
    log: list[str]
    remaining_hp: list[list[float]]


def _choose(unit: _Unit) -> str | None:
    for sid in ("s3", "s2", "s1"):
        if sid in unit.fighter.skills and unit.cooldowns.get(sid, 0) <= 0:
            return sid
    return None


def fight(
    team_a: list[Fighter],
    team_b: list[Fighter],
    *,
    rng: random.Random | None = None,
    cooldowns: dict[str, int] | None = None,
    options: Options | None = None,
    keep_log: bool = True,
) -> BattleResult:
    rng = rng or random.Random(0)
    cds = {**DEFAULT_COOLDOWNS, **(cooldowns or {})}
    opts = options or Options()
    units = [_Unit(f, 0, f.hp) for f in team_a] + [_Unit(f, 1, f.hp) for f in team_b]
    for u in units:  # départ : la jauge de chacun démarre au hasard entre 0 et 5 % (comme en jeu)
        u.gauge = rng.uniform(0, 5)
    log: list[str] = []
    actions = 0
    while actions < MAX_ACTIONS:
        alive = [u for u in units if u.alive]
        if len({u.team for u in alive}) < 2:
            break
        actor = max(alive, key=lambda u: (u.gauge - 100) / u.fighter.spd)
        wait = (100 - actor.gauge) / actor.fighter.spd
        for u in alive:
            u.gauge += u.fighter.spd * wait
        actor.gauge = 0
        actions += 1
        sid = _choose(actor)
        foes = [u for u in alive if u.team != actor.team]
        if sid is None or not foes:
            continue
        skill = actor.fighter.skills[sid]
        targets = foes if skill.get("aoe") else [min(foes, key=lambda u: u.hp)]
        hits = []
        for target in targets:
            dmg = skill_damage(actor.fighter, skill, target.fighter, opts)
            crit = dmg["crit"] is not None and rng.random() < actor.fighter.crit_chance / 100
            amount = float(dmg["crit"] if crit and dmg["crit"] is not None else dmg["normal"] or 0)
            target.hp = max(0.0, target.hp - amount)
            hits.append(
                f"{target.fighter.name} −{amount:,.0f}".replace(",", "\u202f")
                + (" (critique)" if crit else "")
                + (" ✝" if not target.alive else "")
            )
        for k in actor.cooldowns:
            actor.cooldowns[k] = max(0, actor.cooldowns[k] - 1)
        actor.cooldowns[sid] = cds.get(sid, 0)
        if keep_log:
            log.append(f"{actions:>3}. {actor.fighter.name} ({sid.upper()}) → " + ", ".join(hits))
    teams = {u.team for u in units if u.alive}
    winner = teams.pop() if len(teams) == 1 else None
    return BattleResult(
        winner=winner,
        actions=actions,
        log=log,
        remaining_hp=[[round(u.hp) for u in units if u.team == t] for t in (0, 1)],
    )


def simulate(
    team_a: list[Fighter],
    team_b: list[Fighter],
    runs: int = 1000,
    seed: int = 7,
    cooldowns: dict[str, int] | None = None,
    options: Options | None = None,
) -> dict[str, Any]:
    """Taux de victoire sur `runs` combats et le journal détaillé d'un combat type."""
    rng = random.Random(seed)
    wins = [0, 0]
    draws = 0
    total_actions = 0
    for _ in range(runs):
        res = fight(team_a, team_b, rng=rng, cooldowns=cooldowns, options=options, keep_log=False)
        total_actions += res.actions
        if res.winner is None:
            draws += 1
        else:
            wins[res.winner] += 1
    sample = fight(team_a, team_b, rng=random.Random(seed), cooldowns=cooldowns, options=options)
    return {
        "runs": runs,
        "win_rate": [round(100 * w / runs, 1) for w in wins],
        "draws": round(100 * draws / runs, 1),
        "avg_actions": round(total_actions / runs, 1),
        "sample": {
            "winner": sample.winner,
            "log": sample.log,
            "remaining_hp": sample.remaining_hp,
        },
    }
