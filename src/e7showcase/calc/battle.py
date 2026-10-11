"""Simulateur de combat : deux équipes (1 à 4 héros) s'affrontent jusqu'à la mort.

Modèle :
- jauge de combat : chaque héros avance de sa vitesse ; il joue quand elle atteint 100 % ;
- compétences actives (S1 et compétences avec recharge ; les passifs ne sont pas joués) :
  soin prioritaire si un allié est sous 50 % de PV, sinon S3, S2, puis S1. Recharges réelles
  (base E7GW, améliorations comprises), sinon S2 = 3 et S3 = 4 tours ;
- dégâts : formule de calc/damage.py, critique tiré selon les chances de critique ; la
  barrière absorbe les dégâts avant les PV ;
- effets des compétences (data/reference/skills.json, `effects`) :
  soins, barrières, buffs (attaque +50 %, défense +60 %, vitesse +30 %, chances de critique
  +30 %, dégâts critiques +50 %, immunité, invincibilité, camouflage, immortalité),
  débuffs (défense −70 %, attaque −50 %, vitesse −30 %, étourdissement, sommeil, silence,
  provocation, anti-soin) avec chance de réussite selon efficacité / résistance, jauge de
  combat (+/−), retrait de buffs et de débuffs ;
- durées : décomptées à la fin du tour de celui qui porte l'effet (un effet reçu pendant son
  propre tour n'est pas décompté ce tour-là), comme en jeu.

Non simulé : passifs et déclencheurs (contre-attaque, attaque supplémentaire, résurrection),
artefacts, esquive, âme brûlée, effets propres à un héros. Le montant des soins et de
certaines barrières n'est pas chiffré dans les textes du jeu : valeur type (signalée
`estimated` dans les données). Le résultat reste un ordre de grandeur.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Any

from e7showcase.calc.damage import Fighter, Options, skill_damage

MAX_ACTIONS = 300
DEFAULT_COOLDOWNS = {"s1": 0, "s2": 3, "s3": 4}
BUFF_NAMES = {
    "atk_up": "Attaque +",
    "def_up": "Défense +",
    "spd_up": "Vitesse +",
    "cc_up": "Critique +",
    "cd_up": "Dégâts crit. +",
    "immunity": "Immunité",
    "invincible": "Invincibilité",
    "stealth": "Camouflage",
    "immortal": "Immortalité",
}
DEBUFF_NAMES = {
    "def_down": "Défense −",
    "atk_down": "Attaque −",
    "spd_down": "Vitesse −",
    "stun": "Étourdi",
    "sleep": "Endormi",
    "silence": "Silence",
    "provoke": "Provoqué",
    "unhealable": "Anti-soin",
}
MAX_RESIST = 85  # % : un débuff a toujours au moins 15 % de chances de passer


def _fmt(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


@dataclass
class _Unit:
    fighter: Fighter
    team: int
    hp: float
    gauge: float = 0.0
    cooldowns: dict[str, int] = field(default_factory=dict)
    buffs: dict[str, int] = field(default_factory=dict)
    debuffs: dict[str, int] = field(default_factory=dict)
    barrier: float = 0.0
    barrier_turns: int = 0
    provoker: _Unit | None = None
    fresh: set[str] = field(default_factory=set)  # effets reçus pendant son propre tour

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def name(self) -> str:
        return self.fighter.name

    @property
    def speed(self) -> float:
        mult = (
            1 + (0.3 if "spd_up" in self.buffs else 0) - (0.3 if "spd_down" in self.debuffs else 0)
        )
        return max(self.fighter.spd * mult, 1)

    def attacker_view(self) -> Fighter:
        """Combattant avec ses buffs de critique appliqués."""
        return replace(
            self.fighter,
            crit_chance=self.fighter.crit_chance + (30 if "cc_up" in self.buffs else 0),
            crit_dmg=self.fighter.crit_dmg + (50 if "cd_up" in self.buffs else 0),
        )


@dataclass
class BattleResult:
    winner: int | None  # 0, 1, ou None (match nul / limite atteinte)
    actions: int
    log: list[str]
    remaining_hp: list[list[float]]
    stats: dict[str, float] = field(default_factory=dict)


class _Battle:
    def __init__(
        self,
        team_a: list[Fighter],
        team_b: list[Fighter],
        rng: random.Random,
        cooldowns: dict[str, int],
        options: Options,
        keep_log: bool,
    ):
        self.units = [_Unit(f, 0, f.hp) for f in team_a] + [_Unit(f, 1, f.hp) for f in team_b]
        self.rng, self.cds, self.opts, self.keep_log = rng, cooldowns, options, keep_log
        self.log: list[str] = []
        self.stats = {"healed": 0.0, "shielded": 0.0, "buffs": 0.0, "debuffs": 0.0}
        self.current: _Unit | None = None
        for u in self.units:  # départ : jauge aléatoire entre 0 et 5 % (comme en jeu)
            u.gauge = rng.uniform(0, 5)

    # --- sélection
    def allies(self, u: _Unit) -> list[_Unit]:
        return [x for x in self.units if x.alive and x.team == u.team]

    def foes(self, u: _Unit) -> list[_Unit]:
        return [x for x in self.units if x.alive and x.team != u.team]

    def cooldown(self, sid: str, skill: dict[str, Any]) -> int:
        cd = skill.get("cooldown")
        return int(cd) if isinstance(cd, int) and cd > 0 else self.cds.get(sid, 0)

    def choose(self, u: _Unit) -> str | None:
        usable = [
            sid
            for sid in ("s3", "s2", "s1")
            if sid in u.fighter.skills
            and not u.fighter.skills[sid].get("passive")
            and u.cooldowns.get(sid, 0) <= 0
            and (sid == "s1" or not ({"silence", "provoke"} & set(u.debuffs)))
        ]
        allies = self.allies(u)
        hurt = any(a.hp < 0.5 * a.fighter.hp for a in allies)

        def worth(sid: str) -> bool:
            skill = u.fighter.skills[sid]
            if skill.get("rate") is not None:
                return True
            for e in skill.get("effects", []):
                if e["type"] == "heal" and any(a.hp < 0.8 * a.fighter.hp for a in allies):
                    return True
                if e["type"] == "cleanse" and any(a.debuffs for a in allies):
                    return True
                if e["type"] in ("buff", "debuff", "barrier", "gauge", "strip"):
                    return True
            return False

        useful = [sid for sid in usable if worth(sid)]
        if hurt:
            for sid in useful:
                if any(e["type"] == "heal" for e in u.fighter.skills[sid].get("effects", [])):
                    return sid
        return useful[0] if useful else None

    def main_target(self, u: _Unit, foes: list[_Unit]) -> _Unit:
        if "provoke" in u.debuffs and u.provoker and u.provoker.alive:
            return u.provoker
        visible = [f for f in foes if "stealth" not in f.buffs] or foes
        return min(visible, key=lambda f: f.hp)

    def resolve(self, actor: _Unit, who: str, hit: list[_Unit], kind: str) -> list[_Unit]:
        allies, foes = self.allies(actor), self.foes(actor)
        if who == "self":
            return [actor]
        if who == "allies":
            return allies
        if who == "ally":
            pool = [a for a in allies if a is not actor] or allies
            key = (
                (lambda a: a.hp / a.fighter.hp)
                if kind in ("heal", "barrier")
                else (lambda a: -a.fighter.atk)
            )
            return [min(pool, key=key)] if pool else []
        if who == "enemies":
            return foes
        return [t for t in hit if t.alive] or ([self.main_target(actor, foes)] if foes else [])

    # --- effets
    def mark(self, target: _Unit, name: str) -> None:
        if target is self.current:
            target.fresh.add(name)

    def apply(self, actor: _Unit, effect: dict[str, Any], hit: list[_Unit]) -> list[str]:
        kind = effect["type"]
        notes: list[str] = []
        stats = {"hp": actor.fighter.hp, "atk": actor.fighter.atk, "def": actor.fighter.defense}
        for t in self.resolve(actor, effect.get("target", "self"), hit, kind):
            if kind == "heal":
                if "unhealable" in t.debuffs:
                    continue
                amount = min(effect["ratio"] * stats[effect["stat"]], t.fighter.hp - t.hp)
                if amount > 0:
                    t.hp += amount
                    self.stats["healed"] += amount
                    notes.append(f"soin {t.name} +{_fmt(amount)}")
            elif kind == "barrier":
                amount = effect["ratio"] * stats[effect["stat"]]
                t.barrier = max(t.barrier, amount)
                t.barrier_turns = max(t.barrier_turns, int(effect.get("turns", 2)))
                self.mark(t, "barrier")
                self.stats["shielded"] += amount
                notes.append(f"barrière {t.name} {_fmt(amount)}")
            elif kind == "buff":
                name = effect["effect"]
                t.buffs[name] = max(t.buffs.get(name, 0), int(effect.get("turns", 2)))
                self.mark(t, "buff:" + name)
                self.stats["buffs"] += 1
                notes.append(f"{BUFF_NAMES.get(name, name)} → {t.name}")
            elif kind == "debuff":
                name = effect["effect"]
                if "immunity" in t.buffs:
                    notes.append(f"{t.name} immunisé")
                    continue
                resist = 0.0
                if not effect.get("ignore_resist"):
                    resist = min(
                        max(t.fighter.effect_res - actor.fighter.effectiveness, 0), MAX_RESIST
                    )
                if self.rng.random() >= effect.get("chance", 1) * (1 - resist / 100):
                    notes.append(f"{DEBUFF_NAMES.get(name, name)} résisté ({t.name})")
                    continue
                t.debuffs[name] = max(t.debuffs.get(name, 0), int(effect.get("turns", 2)))
                if name == "provoke":
                    t.provoker = actor
                self.mark(t, "debuff:" + name)
                self.stats["debuffs"] += 1
                notes.append(f"{DEBUFF_NAMES.get(name, name)} → {t.name}")
            elif kind == "gauge":
                amount = float(effect["amount"])
                if amount < 0 and self.rng.random() >= effect.get("chance", 1):
                    continue
                t.gauge = min(max(t.gauge + amount, 0), 100)
                notes.append(f"jauge {t.name} {'+' if amount > 0 else '−'}{abs(amount):.0f} %")
            elif kind == "strip" and t.buffs:
                gone = list(t.buffs) if effect.get("all") else [next(iter(t.buffs))]
                for b in gone:
                    t.buffs.pop(b, None)
                notes.append(f"buffs retirés ({t.name})")
            elif kind == "cleanse" and t.debuffs:
                gone = list(t.debuffs) if effect.get("all") else [next(iter(t.debuffs))]
                for d in gone:
                    t.debuffs.pop(d, None)
                notes.append(f"débuffs retirés ({t.name})")
        return notes

    def hit(self, actor: _Unit, skill: dict[str, Any], target: _Unit) -> str:
        opts = replace(
            self.opts,
            attack_buff="up"
            if "atk_up" in actor.buffs and "atk_down" not in actor.debuffs
            else (
                "down"
                if "atk_down" in actor.debuffs and "atk_up" not in actor.buffs
                else self.opts.attack_buff
            ),
            target_defense_buff="up"
            if "def_up" in target.buffs and "def_down" not in target.debuffs
            else (
                "down"
                if "def_down" in target.debuffs and "def_up" not in target.buffs
                else self.opts.target_defense_buff
            ),
        )
        attacker = actor.attacker_view()
        dmg = skill_damage(attacker, skill, target.fighter, opts)
        crit = dmg["crit"] is not None and self.rng.random() < attacker.crit_chance / 100
        amount = float(dmg["crit"] if crit and dmg["crit"] is not None else dmg["normal"] or 0)
        if "invincible" in target.buffs:
            return f"{target.name} invincible"
        absorbed = min(target.barrier, amount)
        target.barrier -= absorbed
        target.hp = max(1.0 if "immortal" in target.buffs else 0.0, target.hp - (amount - absorbed))
        if target.hp <= 0:
            target.barrier = 0
        text = f"{target.name} −{_fmt(amount)}" + (" (critique)" if crit else "")
        if absorbed:
            text += f" [barrière −{_fmt(absorbed)}]"
        return text + (" ✝" if not target.alive else "")

    def end_turn(self, u: _Unit) -> None:
        for bag, prefix in ((u.buffs, "buff:"), (u.debuffs, "debuff:")):
            for name in list(bag):
                if prefix + name in u.fresh:
                    continue
                bag[name] -= 1
                if bag[name] <= 0:
                    del bag[name]
        if u.barrier_turns and "barrier" not in u.fresh:
            u.barrier_turns -= 1
            if u.barrier_turns <= 0:
                u.barrier = 0
        u.fresh.clear()
        if "provoke" not in u.debuffs:
            u.provoker = None

    def run(self) -> BattleResult:
        actions = 0
        while actions < MAX_ACTIONS:
            alive = [u for u in self.units if u.alive]
            if len({u.team for u in alive}) < 2:
                break
            actor = min(alive, key=lambda u: (100 - u.gauge) / u.speed)
            wait = max((100 - actor.gauge) / actor.speed, 0)
            for u in alive:
                u.gauge = min(u.gauge + u.speed * wait, 100)
            actor.gauge = 0
            actions += 1
            self.current = actor
            if {"stun", "sleep"} & set(actor.debuffs):
                self.note(actions, f"{actor.name} ne peut pas agir")
                self.end_turn(actor)
                continue
            sid = self.choose(actor)
            foes = self.foes(actor)
            if sid is None or not foes:
                self.end_turn(actor)
                continue
            skill = actor.fighter.skills[sid]
            parts: list[str] = []
            hit: list[_Unit] = []
            if skill.get("rate") is not None:
                hit = foes if skill.get("aoe") else [self.main_target(actor, foes)]
                parts += [self.hit(actor, skill, t) for t in hit]
            for effect in skill.get("effects", []):
                parts += self.apply(actor, effect, hit)
            for k in actor.cooldowns:
                actor.cooldowns[k] = max(0, actor.cooldowns[k] - 1)
            actor.cooldowns[sid] = self.cooldown(sid, skill)
            self.note(actions, f"{actor.name} ({sid.upper()}) → " + (", ".join(parts) or "—"))
            self.end_turn(actor)
        teams = {u.team for u in self.units if u.alive}
        return BattleResult(
            winner=teams.pop() if len(teams) == 1 else None,
            actions=actions,
            log=self.log,
            remaining_hp=[[round(u.hp) for u in self.units if u.team == t] for t in (0, 1)],
            stats=self.stats,
        )

    def note(self, n: int, text: str) -> None:
        if self.keep_log:
            self.log.append(f"{n:>3}. {text}")


def fight(
    team_a: list[Fighter],
    team_b: list[Fighter],
    *,
    rng: random.Random | None = None,
    cooldowns: dict[str, int] | None = None,
    options: Options | None = None,
    keep_log: bool = True,
) -> BattleResult:
    return _Battle(
        team_a,
        team_b,
        rng or random.Random(0),
        {**DEFAULT_COOLDOWNS, **(cooldowns or {})},
        options or Options(),
        keep_log,
    ).run()


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
    totals = {"healed": 0.0, "shielded": 0.0, "buffs": 0.0, "debuffs": 0.0}
    for _ in range(runs):
        res = fight(team_a, team_b, rng=rng, cooldowns=cooldowns, options=options, keep_log=False)
        total_actions += res.actions
        for k in totals:
            totals[k] += res.stats.get(k, 0)
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
        "avg": {k: round(v / runs, 1) for k, v in totals.items()},
        "sample": {
            "winner": sample.winner,
            "log": sample.log,
            "remaining_hp": sample.remaining_hp,
        },
    }
