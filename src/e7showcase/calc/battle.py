"""Simulateur de combat : deux équipes (1 à 4 héros) s'affrontent jusqu'à la mort.

Modèle :
- jauge de combat : chaque héros avance de sa vitesse ; il joue quand elle atteint 100 % ;
- compétences actives (S1 et compétences avec recharge) :
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
- passifs à déclencheur (`trigger` dans skills.json) : début de combat, début et fin du tour du
  porteur, après avoir été attaqué, après avoir attaqué (attaque supplémentaire si le passif
  inflige des dégâts), résurrection une fois par combat ; chance et « une fois tous les N
  tours » respectées ;
- contre-attaques : passif « X % de chances de contre-attaquer » et set Contre, après une
  attaque subie sur le tour de l'adversaire (pas de contre-attaque d'une contre-attaque) ;
  frappe avec la compétence du passif si elle inflige des dégâts, sinon S1 ;
- durées : décomptées à la fin du tour de celui qui porte l'effet (un effet reçu pendant son
  propre tour n'est pas décompté ce tour-là), comme en jeu ;
- mécaniques propres aux héros : tour supplémentaire, attaque double, recharges ±, brûlure,
  saignement, poison, esquive, précision −, annulation, buffs interdits, vol de vie (et set
  Vampire), critique garanti, réduction et plafond de dégâts, Âmes et âme brûlée, blessures,
  explosion, extinction, dégâts fixes, rang arrière (voir docs/SIMULATORS.md) ;
- passifs à conditions : seuils de PV, débuffs, allié attaqué, tours et compétences ennemies,
  morts, critiques, dégâts mortels, jauges de Concentration et d'Esprit combatif.

Non simulé : bonus de stats permanents des passifs (déjà dans les stats affichées),
artefacts, mécaniques uniques absentes de hero_mechanics.json, Bombes, partage de dégâts.
Le montant des soins et de certaines barrières n'est pas chiffré dans les textes du jeu :
valeur type (signalée `estimated` dans les données). Le résultat reste un ordre de grandeur.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Any

from e7showcase.calc.damage import (
    ATTACK_BUFFS,
    DAMAGE_CONSTANT,
    Fighter,
    Options,
    skill_damage,
)

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
    "atk_up_great": "Attaque ++",
    "evasion": "Esquive +",
    "nullifier": "Annulation",
    "eff_up": "Efficacité +",
    "superhuman": "Surhumanisation",
    "indomitable": "Indomptable",
    "morale": "Moral",
    "ferocious": "Posture féroce",
    "abundance": "Abondance",
    "offering": "Offrande",
    "deify": "Déification",
    "god": "Dieu de la guerre",
    "continuous_heal": "Soin continu",
    "cascade": "Cascade",
    "dawn": "Aube",
    "engulf": "Engloutissement",
    "def_magic": "Magie défensive",
    "covenant": "Pacte sacré",
    "effect_nullifier": "Annulation d'effet",
    "vigor": "Vigueur",
    "fragment": "Fragment de vie",
    "overload": "Surcharge",
    "swift": "Attaque rapide",
    "radiance": "Rayonnement",
    "knowledge": "Savoir des étoiles",
    "possession": "Possession",
    "rage": "Rage",
    "rampage": "Saccage",
    "revive_buff": "Résurrection",
    "spirit_guard": "Protection du Seigneur des esprits",
    "damage_limit": "Limite de dégâts",
    "friendship": "Amitié spéciale",
    "bzzt": "Bzzt!",
    "oasis": "Passe tout-compris",
    "shyness": "Timidité",
    "ignore_share": "Ignore le partage",
    "escort": "Escorte",
    "explosives": "Explosifs",
    "oath": "Serment de punition",
    "pestilence": "Pestilence",
    "enhanced_dual": "Attaque double renforcée",
    "counter_stance": "Posture de contre-attaque",
    "fragrance": "Parfum persistant",
    "off_mission": "Mission offensive",
    "def_mission": "Mission défensive",
    "time_reversal": "Retour temporel",
    "clone": "Clone",
    "repeat": "Attaque répétée",
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
    "burn": "Brûlure",
    "bleed": "Saignement",
    "poison": "Poison",
    "hit_down": "Précision −",
    "no_buff": "Buffs interdits",
    "fear": "Peur",
    "bind": "Entrave",
    "rupture": "Rupture",
    "seal": "Sceau",
    "venom": "Venin",
    "block": "Blocage",
    "curse": "Malédiction",
    "detain": "Détention",
    "collapse": "Effondrement",
    "immobilize": "Immobilisation",
    "restrict": "Restriction",
    "bomb": "Bombe",
    "depletion": "Épuisement",
    "beguile": "Envoûtement",
    "target_mark": "Cible",
    "redirect": "Provocation redirigée",
    "trauma": "Traumatisme",
    "erosion": "Érosion",
    "resource_down": "Réduction de ressources",
}
# dégâts sur la durée au début du tour du porteur (définitions E7GW) : saignement 40 % et
# brûlure 70 % de l'attaque du lanceur en ignorant 70 % de la défense, poison 5 % et venin 10 %
# des PV max (le venin inflige aussi des blessures)
# érosion (Rhianna) : non définie par le jeu, estimée comme un saignement (40 % de l'attaque)
DOT = {
    "burn": ("atk", 0.7),
    "bleed": ("atk", 0.4),
    "poison": ("hp", 0.05),
    "venom": ("hp", 0.1),
    "erosion": ("atk", 0.4),
}
DOT_DEF_IGNORED = 0.7
FEAR_DISPEL = 0.4  # « at the start of the turn, has a 40% chance to be dispelled »
RUPTURE = 0.05  # rupture : dégâts additionnels en part des PV max (non chiffré : estimé)
ABUNDANCE = 2000  # « after attacking, inflicts 2,000 additional damage »
CURSE = 0.6  # « deals additional damage equivalent to 60% of damage dealt to the bearer »
CASCADE = 4000  # « after attacking, deals 4,000 fixed damage per target »
CONTINUOUS_HEAL = 0.15  # « recovers 15% of max Health at the start of every turn »
DEFENSIVE_MAGIC_SOULS = 4
# marques cumulables (définitions E7GW) : stat → bonus par marque, et plafond
MARKS = {
    "fracture": ({"atk": 0.2, "defense": -0.05}, 10),
    "spoils": ({"atk": 0.2, "hp": 0.2, "defense": 0.2}, 4),
    "pilfer": ({"atk": -0.2, "hp": -0.2, "defense": -0.2}, 1),
    "dirge": ({}, 10),
    "divinity": ({"hp": 0.2, "defense": 0.2}, 4),
    "fervor": ({"atk": 0.1}, 5),  # Bellona Croissant solitaire : attaque +10 % par attaque
    "hunt": ({"atk": 0.2}, 5),  # Peira Loup solitaire : attaque +20 % par début de tour
    "focus": ({}, 5),  # Concentration simple (ex. Schuri)
    "ancient": ({"defense": 0.1}, 8),  # Zeno : défense +10 % (et efficacité +5) par cumul
    "zeal": ({}, 2),  # Mei Lin : Zèle, S2 renforcée (non chiffré : +25 % estimé)
}
FRAGRANCE = 0.15  # parfum persistant (Byblis) : non défini par le jeu, réduction estimée à 15 %
RESOURCE_BOOST = 0.4  # Frieren : « 40% resource increase » (Esprit combatif, Concentration)
RESOURCE_DOWN = 0.6  # Lidica : « resource reduction by 60% »
MISSION = 0.1  # missions de Politis : attaque (offensive) ou PV max (défensive) des alliés +10 %
AFTERMATH_PEN = 0.7  # dégâts additionnels : 70 % de la défense ignorée (E7Calc)
BOMB = 1.5  # « 150% of caster's Attack as damage, ignores 70% of defense », puis 1 tour immobile
SWIFT = 50  # attaque rapide : jauge +50 % à la fin du tour
BEGUILE = 0.1  # envoûtement : 10 % des PV max de chaque allié du porteur
RADIANCE = 0.5  # rayonnement : dégâts subis −50 %
TARGET_MARK = 0.15  # Cible : dégâts reçus +15 %
DAMAGE_LIMIT = 0.35  # Limite de dégâts : un coup ne dépasse pas 35 % des PV max
FRIENDSHIP = 0.08  # Amitié spéciale : 8 % des PV max du porteur sur un critique
BZZT = 2500  # Bzzt! : 2 500 dégâts additionnels à tous les ennemis après une attaque
ESCORT = 0.4  # Escorte : 40 % des dégâts des alliés partagés
OATH = 2500  # Serment de punition : 2 500 dégâts fixes après une attaque pendant son tour
REVIVE_BUFF = 0.3  # buff Résurrection : revient avec 30 % des PV max
STEALTH_AOE_REDUCTION = 0.5  # camouflage : « 50% reduced damage taken » contre une attaque de zone
SPEED_LAW = 0.9  # Harsetti : vitesse des autres héros limitée à 90 % de la sienne
OFFERING_SHARE = 0.7  # « grants 70% damage sharing of the damage received by all allies »
MISS_CHANCE = 0.5  # esquive + ou précision − : 50 % de coups ratés (dégâts × 0,75)
# types d'effets connus du moteur (les règles par héros sont validées contre cette liste)
EFFECT_TYPES = frozenset(
    {
        "heal", "barrier", "buff", "debuff", "gauge", "strip", "cleanse", "extra_turn", "dual",
        "cooldown", "lifesteal", "damage_reduction", "damage_cap", "injury", "detonate",
        "extinction", "fixed", "static_buff", "static_debuff", "static_immune",
        "static_stat", "static_share", "revive_ally", "static_flag", "mark", "fixed_hit",
        "random_buff", "extra_attack", "soul_damage", "buff_shorten", "barrier_invert",
        "crit_guard", "static_aura", "random_debuff", "buff_steal", "stack", "souls", "assist",
        "class_debuff", "debuff_extend", "debuff_shorten", "transfer", "aftermath", "clone",
        "share_resist",
    }
)  # fmt: skip
PERMANENT = 10**6  # durée d'un statut permanent
SOUL_MAX = 20
SOULBURN_COST = 20  # par défaut, sinon « (-10 souls) » du texte
MAX_RESIST = 85  # % : un débuff a toujours au moins 15 % de chances de passer


def amount_miss(dmg: dict[str, float | None]) -> float:
    return float(dmg.get("miss") or (dmg["normal"] or 0) * 0.75)


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
    turns: int = 0  # tours joués
    last_fired: dict[str, int] = field(default_factory=dict)  # passif → tour de déclenchement
    stacks: dict[str, float] = field(default_factory=dict)  # passif → jauge (Concentration...)
    dot_atk: dict[str, float] = field(default_factory=dict)  # brûlure... → attaque du lanceur
    reduction: float = 0.0  # réduction de dégâts des passifs
    cap: float = 0.0  # plafond de dégâts par coup (part des PV max)
    injury: float = 0.0  # blessures : PV max perdus
    extinct: bool = False  # extinction : ne peut plus ressusciter
    immune: set[str] = field(default_factory=set)  # débuffs auxquels le héros est insensible
    share: float = 0.0  # partage de dégâts : part des dégâts des alliés prise par ce héros
    bonus: list[dict[str, Any]] = field(default_factory=list)  # stats tant qu'un buff est actif
    marks: dict[str, int] = field(default_factory=dict)  # Fracture, Butin, Pillage, balles...
    flags: set[str] = field(default_factory=set)  # mécaniques permanentes (static_flag)
    aura: dict[str, float] = field(default_factory=dict)  # esquive, réduction des critiques
    last_damage: float = 0.0  # dégâts subis pendant l'action en cours (seuils « 20 % des PV »)
    saved: tuple[Fighter, dict[str, int]] | None = None  # Salome : héros d'origine pendant le clone

    @property
    def max_hp(self) -> float:
        """PV max diminués des blessures (doublés par la surhumanisation)."""
        base = self.fighter.hp * (2 if "superhuman" in self.buffs else 1)
        base *= (2 if "god" in self.buffs else 1) * self.mark_mult("hp")
        base *= 0.5 if "collapse" in self.debuffs else 1  # « doubled when applied to Heroes »
        base *= 1 + MISSION * ("def_mission" in self.buffs)
        return max(base - self.injury, 1)

    def mark_mult(self, stat: str) -> float:
        return 1 + sum(MARKS[m][0].get(stat, 0) * n for m, n in self.marks.items() if m in MARKS)

    def stat(self, name: str) -> float:
        """Statistique avec les bonus conditionnels (`static_stat`) et les buffs à pourcentage."""
        value = float(getattr(self.fighter, name))
        if name in ("atk", "defense") and "equalize" in self.flags:  # Mei Lin
            value = max(self.fighter.atk, self.fighter.defense)
        for b in self.bonus:
            if b["stat"] == name and (not b.get("while") or b["while"] in self.buffs):
                per = self.fighter.hp if b.get("per") == "hp" else 1  # « ∝ max Health »
                value += float(b["value"]) * per
        if name == "effectiveness" and "eff_up" in self.buffs:
            value += 50
        if name == "effect_res" and "indomitable" in self.buffs:
            value += 30
        if name == "defense" and "indomitable" in self.buffs:
            value *= 1.3
        if name == "effectiveness" and "engulf" in self.buffs:
            value += 100
        if name == "effectiveness":
            value += 5 * self.marks.get("ancient", 0)
        if name in ("atk", "defense"):
            value *= self.mark_mult(name) * (1.3 if "vigor" in self.buffs else 1)
        if "trauma" in self.debuffs:  # Traumatisme : défense −70 %, attaque et vitesse +100 %
            value *= {"atk": 2.0, "defense": 0.3}.get(name, 1)
        if name == "atk":
            value *= 1 + 0.25 * ("possession" in self.buffs) + 0.2 * ("rage" in self.buffs)
            value *= 1 + MISSION * ("off_mission" in self.buffs)
            value *= (1.5 if "overload" in self.buffs else 1) * (
                0.5 if "depletion" in self.debuffs else 1
            )
        if "god" in self.buffs and name in ("atk", "defense", "effectiveness", "effect_res"):
            value *= 2  # Dieu de la guerre : toutes les stats doublées
        return value

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def name(self) -> str:
        return self.fighter.name

    @property
    def speed(self) -> float:
        mult = (
            1
            + (0.3 if "spd_up" in self.buffs else 0)
            - (0.3 if "spd_down" in self.debuffs else 0)
            + (1.0 if "superhuman" in self.buffs else 0)
            + (0.2 if self.marks.get("dirge") else 0)
            + (0.5 if "overload" in self.buffs else 0)
            + (0.2 if "rage" in self.buffs else 0)
            + (0.2 if "rampage" in self.buffs else 0)
            + (1.0 if "trauma" in self.debuffs else 0)
            - (0.5 if "depletion" in self.debuffs else 0)
        )
        return max(self.fighter.spd * mult * (2 if "god" in self.buffs else 1), 1)

    def attacker_view(self) -> Fighter:
        """Combattant avec ses buffs de critique appliqués."""
        return replace(
            self.fighter,
            atk=self.stat("atk"),
            defense=self.stat("defense"),
            crit_chance=self.fighter.crit_chance
            + (50 if "cc_up" in self.buffs else 0)
            + (50 if "deify" in self.buffs else 0),
            crit_dmg=self.fighter.crit_dmg
            + (70 if "cd_up" in self.buffs else 0)
            + (20 if self.marks.get("dirge") else 0),
        )


@dataclass
class BattleResult:
    winner: int | None  # 0, 1, ou None (match nul / limite atteinte)
    actions: int
    log: list[str]
    remaining_hp: list[list[float]]
    stats: dict[str, float] = field(default_factory=dict)
    # rejeu (journal conservé) : état des PV après chaque tour, ligne du journal atteinte
    frames: list[dict[str, Any]] = field(default_factory=list)
    units: list[dict[str, Any]] = field(default_factory=list)


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
        self.frames: list[dict[str, Any]] = []
        self.stats = {
            "healed": 0.0,
            "shielded": 0.0,
            "buffs": 0.0,
            "debuffs": 0.0,
            "counters": 0.0,
            "passives": 0.0,
            "extra_turns": 0.0,
        }
        self.actions = 0
        self.deaths: list[_Unit] = []
        self.last_targets: list[_Unit] = []
        self.soul_bonus = 0.0  # dégâts additionnels payés en Âmes (Aubade Ludwig)
        self.evaded: list[_Unit] = []  # héros ayant esquivé pendant l'action
        self.crits: list[_Unit] = []
        self.bonus_depth = 0  # > 0 pendant une attaque supplémentaire, double ou contre-attaque
        self.bonus_hits: list[_Unit] = []
        for u in self.units:  # mécaniques permanentes des passifs, recharges pleines au départ
            for sid, skill in u.fighter.skills.items():
                if skill.get("full_cd_start"):
                    u.cooldowns[sid] = self.cooldown(sid, skill)
                for e in skill.get("effects", []):
                    if e["type"] == "damage_reduction" and skill.get("passive"):
                        u.reduction = max(u.reduction, float(e["value"]))
                    elif e["type"] == "damage_cap":
                        u.cap = float(e["value"]) if not u.cap else min(u.cap, float(e["value"]))
        self.souls = [0, 0]
        for u in self.units:  # statuts permanents (règles par héros : hero_mechanics.json)
            for skill in u.fighter.skills.values():
                for e in skill.get("effects", []):
                    if e["type"] == "static_buff":
                        u.buffs[e["effect"]] = PERMANENT
                    elif e["type"] == "static_debuff":
                        u.debuffs[e["effect"]] = PERMANENT
                    elif e["type"] == "static_immune":
                        u.immune.update(e["effects"])
                    elif e["type"] == "static_stat":
                        u.bonus.append(e)
                    elif e["type"] == "static_share":
                        u.share = max(u.share, float(e["value"]))
                    elif e["type"] == "static_flag":
                        u.flags.add(e["flag"])
                    elif e["type"] == "crit_guard":
                        u.aura["crit_self"] = float(e.get("self", 0))
                        u.aura["crit_allies"] = float(e.get("allies", 0))
                    elif e["type"] == "static_aura":
                        u.aura[e["aura"]] = float(e["value"])
        for u in self.units:  # jauges de départ (« starts the first battle with 50 ... »)
            for sid, skill in u.fighter.skills.items():
                res = (skill.get("trigger") or {}).get("resource")
                if res:
                    u.stacks[sid] = float(res.get("start", 0))
        self.current: _Unit | None = None
        for u in self.units:  # départ : jauge aléatoire entre 0 et 5 % (comme en jeu)
            u.gauge = rng.uniform(0, 5)

    # --- sélection
    def allies(self, u: _Unit) -> list[_Unit]:
        return [x for x in self.units if x.alive and x.team == u.team]

    def foes(self, u: _Unit) -> list[_Unit]:
        """Ennemis en jeu (un héros en détention est retiré du champ de bataille)."""
        return [x for x in self.units if x.alive and x.team != u.team and "detain" not in x.debuffs]

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
        dead = any(x.team == u.team and not x.alive and not x.extinct for x in self.units)
        hurt = dead or any(a.hp < 0.5 * a.max_hp for a in allies)

        def worth(sid: str) -> bool:
            skill = u.fighter.skills[sid]
            if skill.get("rate") is not None:
                return True
            for e in skill.get("effects", []):
                if e["type"] == "heal" and any(a.hp < 0.8 * a.max_hp for a in allies):
                    return True
                if e["type"] == "revive_ally" and (
                    dead or any(a.hp < 0.5 * a.max_hp for a in allies if a is not u)
                ):
                    return True
                if e["type"] == "cleanse" and any(a.debuffs for a in allies):
                    return True
                if e["type"] in ("buff", "debuff", "barrier", "gauge", "strip"):
                    return True
            return False

        useful = [sid for sid in usable if worth(sid)]
        if hurt:
            for sid in useful:
                kinds = {e["type"] for e in u.fighter.skills[sid].get("effects", [])}
                if kinds & {"heal", "revive_ally"}:
                    return sid
        return useful[0] if useful else None

    def main_target(self, u: _Unit, foes: list[_Unit]) -> _Unit:
        if "provoke" in u.debuffs and u.provoker and u.provoker.alive:
            return u.provoker
        stand = [f for f in foes if "ferocious" in f.buffs]
        if stand:  # posture féroce : seul le porteur peut être ciblé
            return stand[0]
        visible = [f for f in foes if "stealth" not in f.buffs and "conceal" not in f.flags] or foes
        return min(visible, key=lambda f: f.hp)

    def targets(self, u: _Unit, skill: dict[str, Any], foes: list[_Unit]) -> list[_Unit]:
        """Cibles d'une attaque : toutes (zone), N ennemis (`targets`) ou la cible principale."""
        if skill.get("aoe"):
            return foes
        first = self.main_target(u, foes)
        others = sorted((f for f in foes if f is not first), key=lambda f: f.hp)
        return [first, *others[: int(skill.get("targets", 1)) - 1]]

    def resolve(self, actor: _Unit, who: str, hit: list[_Unit], kind: str) -> list[_Unit]:
        allies, foes = self.allies(actor), self.foes(actor)
        if who == "self":
            return [actor]
        if who == "allies":
            return allies
        if who == "ally":
            pool = [a for a in allies if a is not actor] or allies
            key = (
                (lambda a: a.hp / a.max_hp)
                if kind in ("heal", "barrier")
                else (lambda a: -a.fighter.atk)
            )
            return [min(pool, key=key)] if pool else []
        if who == "enemies":
            return foes
        if who == "current":  # le héros dont c'est le tour
            return [self.current] if self.current and self.current.alive else []
        if who == "enemy_front":  # premier ennemi
            return foes[:1]
        if who == "front":  # premier emplacement de l'équipe
            return allies[:1]
        if who == "last":  # cible de l'effet précédent
            return [t for t in self.last_targets if t.alive]
        if who == "other_enemies":  # tous les ennemis sauf la cible
            return [f for f in foes if f not in hit] or foes
        if who == "other_allies":  # tous les alliés sauf le lanceur
            return [a for a in allies if a is not actor]
        if who == "back_row":  # dernier emplacement de l'équipe
            pool = [a for a in allies if a is not actor] or allies
            return pool[-1:]
        return [t for t in hit if t.alive] or ([self.main_target(actor, foes)] if foes else [])

    # --- passifs et contre-attaques
    def condition_met(
        self, u: _Unit, cond: dict[str, Any] | None, other: _Unit | None, non_attack: bool
    ) -> bool:
        if not cond:
            return True
        kind = cond["kind"]
        if kind == "hp_below":
            return u.hp <= float(cond["value"]) * u.fighter.hp
        if kind == "target_hp_below":
            return other is not None and other.hp <= float(cond["value"]) * other.fighter.hp
        if kind == "full_hp":
            return u.hp >= u.max_hp
        if kind == "no_debuff":
            return not u.debuffs
        if kind == "has_debuff":
            return bool(u.debuffs)
        if kind == "non_attack":
            return non_attack
        if kind == "front_row":
            return self.allies(u)[:1] == [u]
        if kind == "has_buff":
            return cond.get("buff") in u.buffs if cond.get("buff") else bool(u.buffs)
        if kind == "target_has_debuff":
            return other is not None and bool(other.debuffs)
        if kind == "target_no_buff":
            return other is not None and not other.buffs
        if kind == "other_ally":
            return other is not None and other.team == u.team and other is not u
        if kind == "skill_ready":
            return u.cooldowns.get(cond["skill"], 0) <= 0
        if kind == "other_front":
            return other is not None and self.allies(u)[:1] == [other] and other is not u
        if kind == "enemy_died":
            return other is not None and other.team != u.team
        if kind == "back_row_low":
            back = [a for a in self.allies(u) if a is not u][-1:]
            return bool(back) and other is back[0] and other.hp <= 0.5 * other.max_hp
        if kind == "damage_at_least":  # « when the damage suffered is 20% or more of max Health »
            return other is not None and other.last_damage >= float(cond["value"]) * other.max_hp
        if kind == "other_element":  # ex. « when a Fire elemental ally uses a skill »
            return other is not None and other.fighter.element == cond["element"]
        if kind == "not_back":  # « when the caster is in the back row, not activated »
            return self.allies(u)[-1:] != [u]
        if kind == "first_ally":
            return other is not None and other.team == u.team
        if kind == "first_enemy":
            return other is not None and other.team != u.team
        if kind == "lacks_buff":
            return cond["buff"] not in u.buffs
        if kind == "has_barrier":
            return u.barrier > 0
        if kind == "not_front":
            return self.allies(u)[:1] != [u]
        if kind == "enemy_has":
            return any(cond["buff"] in f.buffs for f in self.foes(u))
        if kind == "allies_have":
            return any(set(cond["debuffs"]) & set(a.debuffs) for a in self.allies(u))
        if kind == "has_mark":
            return u.marks.get(cond["mark"], 0) > 0
        if kind == "on_cooldown":
            return u.cooldowns.get(cond["skill"], 0) > 0
        if kind == "ally_died":
            if cond.get("mark") and not u.marks.get(cond["mark"]):
                return False
            return other is not None and other.team == u.team and other is not u
        if kind == "souls_at_least":
            return self.souls[u.team] >= int(cond["value"])
        if kind == "other_has":
            return other is not None and cond["buff"] in other.buffs
        return True

    def triggered(
        self, u: _Unit, event: str, other: _Unit | None = None, non_attack: bool = False
    ) -> list[tuple[str, dict[str, Any]]]:
        """Compétences de `u` déclenchées par `event` (condition, jauge, chance, recharge)."""
        out: list[tuple[str, dict[str, Any]]] = []
        if "seal" in u.debuffs and event != "revive":  # sceau : passifs inactifs
            return out
        for sid, skill in u.fighter.skills.items():
            trig = skill.get("trigger")
            if not trig:
                continue
            res = trig.get("resource")
            if trig["event"] == "resource" and res and res["on"] == event:
                if not self.condition_met(u, trig.get("condition"), other, non_attack):
                    continue
                cap = max(float(res["need"]), float(res.get("start", 0)))
                gain = float(res["gain"]) * self.resource_mult(u, res)
                u.stacks[sid] = min(u.stacks.get(sid, 0) + gain, cap)
                if u.stacks[sid] < res["need"]:
                    continue
            elif trig["event"] != event or not self.condition_met(
                u, trig.get("condition"), other, non_attack
            ):
                continue
            last = u.last_fired.get(sid)
            if last is not None and u.turns - last < int(trig.get("every", 0)):
                continue
            if self.rng.random() >= trig.get("chance", 1):
                continue
            if res:  # jauge consommée (en entier, ou du coût indiqué)
                u.stacks[sid] = max(u.stacks[sid] - float(res.get("cost", u.stacks[sid])), 0)
            u.last_fired[sid] = u.turns
            out.append((sid, skill))
        return out

    def resource_mult(self, u: _Unit, res: dict[str, Any]) -> float:
        """Gains d'Esprit combatif / Concentration : hausse (Frieren), réductions (Lidica...)."""
        if res.get("kind") not in ("spirit", "focus"):
            return 1.0
        mult = 1 + RESOURCE_BOOST * any("resource_boost" in a.flags for a in self.allies(u))
        mult *= 1 - RESOURCE_DOWN * ("resource_down" in u.debuffs)
        damp = max((f.aura.get("resource_dampen", 0) for f in self.foes(u)), default=0)
        return mult * (1 - float(damp))

    def fire(
        self, u: _Unit, event: str, other: _Unit | None = None, non_attack: bool = False
    ) -> None:
        """Joue les passifs de `u` déclenchés par `event` (`other` : attaquant ou cible)."""
        if not u.alive:
            return
        for sid, skill in self.triggered(u, event, other, non_attack):
            foes = self.foes(u)
            if not foes:
                return
            hit: list[_Unit] = []
            parts: list[str] = []
            trig = skill["trigger"]
            enemy = self.current if event == "ally_attacked" else other
            if trig.get("counter"):  # ex. contre-attaque quand un allié est attaqué
                if enemy is not None and enemy.team != u.team:
                    self.counter(u, enemy, forced=True)
            elif skill.get("rate") is not None and "bind" not in u.debuffs:
                target = (
                    enemy if enemy is not None and enemy.alive and enemy.team != u.team else None
                )
                if skill.get("random_target"):  # « against a random enemy »
                    target = self.rng.choice(foes)
                hit = foes if skill.get("aoe") else [target or self.main_target(u, foes)]
                parts += [self.hit(u, skill, t) for t in hit]
            for effect in skill.get("effects", []):
                parts += self.apply(u, effect, hit or ([other] if other else []))
            self.specials(u, skill, hit)
            if parts:
                self.stats["passives"] += 1
                self.note(f"  ↳ {u.name} passif {sid.upper()} → " + ", ".join(parts))

    def counter(self, u: _Unit, attacker: _Unit, forced: bool = False, chain: bool = True) -> None:
        """Contre-attaque de `u` (passif ou set Contre) sur `attacker`."""
        if not (u.alive and attacker.alive) or {"stun", "sleep", "fear", "bind"} & set(u.debuffs):
            return
        if self.flagged("no_counter") and "no_counter" not in u.flags:
            return  # Mort : « all Heroes except for the caster cannot counterattack »
        passives = [] if forced else self.triggered(u, "counter")
        mult = 2 if "counter_x2" in u.flags else 1  # « all counterattack chances are doubled »
        if (
            not forced
            and not passives
            and self.rng.random()
            >= (100 if "counter_stance" in u.buffs else mult * u.fighter.counter_chance) / 100
        ):
            return
        passive = passives[0][1] if passives else {}
        basic = u.fighter.skills.get("s1_counter") or u.fighter.skills.get("s1")
        skill = passive if passive.get("rate") is not None else basic
        if not skill or skill.get("rate") is None:
            return
        self.stats["counters"] += 1
        self.bonus_depth += 1
        parts = [self.hit(u, skill, attacker)]
        self.bonus_depth -= 1
        own = skill is passive or skill is u.fighter.skills.get("s1_counter")
        for effect in skill.get("effects", []) if own else []:
            parts += self.apply(u, effect, [attacker])
        self.note(f"  ↳ {u.name} contre-attaque → " + ", ".join(parts))
        front = self.allies(u)[:1]
        if chain and "counter_chain" in u.flags and front and front[0] is not u:
            self.counter(front[0], attacker, forced=True, chain=False)  # contre-attaque en chaîne

    # --- effets
    def mark(self, target: _Unit, name: str) -> None:
        if target is self.current:
            target.fresh.add(name)

    def gate(self, actor: _Unit, effect: dict[str, Any], hit: list[_Unit]) -> bool:
        """Conditions propres à un effet : buff du lanceur, débuff de la cible, critique..."""
        need = effect.get("if_buff")
        if need and not (actor.buffs if need == "*" else need in actor.buffs):
            return False
        if effect.get("if_cooldown") and actor.cooldowns.get(effect["if_cooldown"], 0) <= 0:
            return False
        first = next((t for t in hit if t.alive), None)
        want = effect.get("if_target_debuff")
        if want and not (first and (first.debuffs if want == "*" else want in first.debuffs)):
            return False
        if effect.get("if_target_element") and not (
            first and first.fighter.element == effect["if_target_element"]
        ):
            return False
        if effect.get("if_mark") and not actor.marks.get(effect["if_mark"]):
            return False
        if effect.get("if_hp_below") and actor.hp > effect["if_hp_below"] * actor.max_hp:
            return False
        if effect.get("if_enemy_debuff") and not any(
            effect["if_enemy_debuff"] in f.debuffs for f in self.foes(actor)
        ):
            return False
        if effect.get("if_kill") and not any(not t.alive for t in hit):
            return False
        return not (effect.get("if_crit") and actor not in self.crits)

    def apply(self, actor: _Unit, effect: dict[str, Any], hit: list[_Unit]) -> list[str]:
        kind = effect["type"]
        if not self.gate(actor, effect, hit):
            return []
        notes: list[str] = []
        stats = {"hp": actor.fighter.hp, "atk": actor.fighter.atk, "def": actor.fighter.defense}
        if kind == "revive_ally":
            return self.revive_ally(actor, effect)
        chosen = self.resolve(actor, effect.get("target", "self"), hit, kind)
        if chosen:
            self.last_targets = chosen
        for t in chosen:
            if kind == "heal":
                if "unhealable" in t.debuffs:
                    continue
                base = t.max_hp if effect["stat"] == "max" else stats[effect["stat"]]
                amount = min(effect["ratio"] * base, t.max_hp - t.hp)
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
            elif kind in ("buff", "debuff") and "immune_all" in t.flags and t is not actor:
                notes.append(f"{t.name} insensible")  # « immune to buffs and debuffs »
            elif kind in ("buff", "debuff") and self.sanctuary() and not effect.get("unique"):
                notes.append(f"{t.name} : Sanctuaire")  # tous insensibles aux buffs et débuffs
            elif kind in ("buff", "debuff") and "bullets" in t.flags and t is not actor:
                t.marks["dirge"] = min(t.marks.get("dirge", 0) + 1, MARKS["dirge"][1])
                notes.append(f"balle funèbre → {t.name}")  # Renoa : effets changés en balles
            elif kind == "buff":
                name = effect["effect"]
                if "no_buff" in t.debuffs or ("block" in t.debuffs and t is not actor):
                    continue
                if name == "immortal" and self.flagged("no_immortal"):
                    continue
                if effect.get("element") and t.fighter.element != effect["element"]:
                    continue  # ex. Saccage : héros Ténèbres seulement
                if name == "superhuman" and name not in t.buffs:
                    t.hp *= 2  # PV max doublés : PV actuels relevés d'autant (proportionnel)
                t.buffs[name] = max(t.buffs.get(name, 0), int(effect.get("turns", 2)))
                self.mark(t, "buff:" + name)
                self.stats["buffs"] += 1
                notes.append(f"{BUFF_NAMES.get(name, name)} → {t.name}")
            elif kind == "debuff":
                name = effect["effect"]
                if t is not actor and "effect_nullifier" in t.buffs:
                    del t.buffs["effect_nullifier"]
                    notes.append(f"{t.name} annule l'effet")
                    continue
                immune = {"immunity", "covenant", "oath"} & set(t.buffs) or t.marks.get("divinity")
                if immune or name in t.immune:
                    notes.append(f"{t.name} immunisé")
                    continue
                resist = 0.0
                if not effect.get("ignore_resist"):
                    aura = any(
                        "res_aura" in a.flags and not a.debuffs for a in self.allies(t)
                    )  # « when the caster is not inflicted with a debuff, +40% to all allies »
                    res = t.stat("effect_res") + (40 if aura else 0)
                    resist = min(max(res - actor.stat("effectiveness"), 0), MAX_RESIST)
                chance = effect.get("chance", 1)
                if effect.get("chance_x2_if") in actor.buffs:
                    chance *= (
                        2  # ex. « when the caster is granted engulf, effect chance is doubled »
                    )
                if self.rng.random() >= chance * (1 - resist / 100):
                    notes.append(f"{DEBUFF_NAMES.get(name, name)} résisté ({t.name})")
                    continue
                t.debuffs[name] = max(t.debuffs.get(name, 0), int(effect.get("turns", 2)))
                if name == "provoke":
                    t.provoker = actor
                if name in DOT or name == "bomb":
                    t.dot_atk[name] = max(t.dot_atk.get(name, 0), actor.fighter.atk)
                self.mark(t, "debuff:" + name)
                self.stats["debuffs"] += 1
                notes.append(f"{DEBUFF_NAMES.get(name, name)} → {t.name}")
            elif kind == "gauge":
                amount = float(effect["amount"])
                if effect.get("per_hit"):  # « for every target, +25% »
                    amount *= max(len(hit), 1)
                damp = max((f.aura.get("cr_dampen", 0) for f in self.foes(t)), default=0)
                if amount > 0 and damp:  # « reduces CR increases granted to the enemy »
                    amount *= 1 - float(damp)
                law = self.current is not None and "speed_law" in self.current.flags
                if amount > 0 and ("restrict" in t.debuffs or law):
                    continue  # restriction, ou loi de Skuggiheim pendant le tour de Harsetti
                if amount < 0 and "cr_floor" in t.flags:
                    continue  # « unaffected by decreases to Combat Readiness »
                if "cr_lock" in t.flags or (
                    amount < 0 and self.rng.random() >= effect.get("chance", 1)
                ):
                    continue
                before = t.gauge
                t.gauge = min(max(t.gauge + amount, 0), 100)
                for m in self.foes(t) if t.gauge > before else []:
                    if "cr_mirror" in m.flags and "seal" not in m.debuffs:  # Dame de la Balance
                        m.gauge = min(m.gauge + 0.5 * (t.gauge - before), 100)
                if t.gauge < before:  # ex. Taeyou : Esprit combatif = jauge retirée à l'ennemi
                    for a in self.foes(t):
                        if "cr_spirit" in a.flags:
                            a.stacks["s2"] = a.stacks.get("s2", 0) + before - t.gauge
                notes.append(f"jauge {t.name} {'+' if amount > 0 else '−'}{abs(amount):.0f} %")
            elif kind == "cooldown":
                if self.rng.random() >= effect.get("chance", 1):
                    continue
                if effect.get("on_kill") and not any(not x.alive for x in hit):
                    continue
                for k in [effect["skill"]] if effect.get("skill") else t.fighter.skills:
                    if k != "s1":
                        cd = self.cooldown(k, t.fighter.skills[k])
                        t.cooldowns[k] = min(max(t.cooldowns.get(k, 0) + effect["amount"], 0), cd)
                notes.append(f"recharges {t.name} {effect['amount']:+d}".replace("+99", "max"))
            elif kind == "strip" and effect.get("only"):
                if effect["only"] in t.buffs:
                    del t.buffs[effect["only"]]
                    notes.append(
                        f"{BUFF_NAMES.get(effect['only'], effect['only'])} retiré ({t.name})"
                    )
            elif kind == "barrier_invert" and t.barrier > 0:
                amount, t.barrier, t.barrier_turns = t.barrier, 0.0, 0
                t.hp = max(1.0 if "immortal" in t.buffs else 0.0, t.hp - amount)
                notes.append(f"barrière inversée {t.name} −{_fmt(amount)}")
                if not t.alive:
                    self.deaths.append(t)
            elif kind == "strip" and t.buffs and "undispellable" not in t.flags:
                gone = list(t.buffs) if effect.get("all") else [next(iter(t.buffs))]
                for b in gone:
                    t.buffs.pop(b, None)
                notes.append(f"buffs retirés ({t.name})")
            elif kind == "mark" and effect.get("require_last") and not self.last_targets:
                continue  # ex. divinité consommée seulement si un allié a été ressuscité
            elif kind == "mark":
                name = effect["mark"]
                count = t.marks.get(name, 0) + int(effect.get("count", 1))
                before = t.max_hp
                t.marks[name] = max(min(count, MARKS[name][1]), 0)
                if t.alive and t.max_hp > before:  # PV max augmentés : PV actuels d'autant
                    t.hp *= t.max_hp / before
                notes.append(f"{name} ×{t.marks[name]} ({t.name})")
                if name == "pilfer":  # le pillage donne un butin à l'attaquant
                    actor.marks["spoils"] = min(
                        actor.marks.get("spoils", 0) + 1, MARKS["spoils"][1]
                    )
            elif kind == "fixed_hit" and "invincible" not in t.buffs:
                amount = float(effect["amount"])
                t.hp = max(1.0 if "immortal" in t.buffs else 0.0, t.hp - amount)
                notes.append(f"{t.name} −{_fmt(amount)} (fixes)" + (" ✝" if not t.alive else ""))
                if not t.alive:
                    self.deaths.append(t)
            elif kind == "buff_shorten":
                for b in list(t.buffs):
                    if t.buffs[b] < PERMANENT:
                        t.buffs[b] -= int(effect["amount"])
                        if t.buffs[b] <= 0:
                            del t.buffs[b]
                notes.append(f"buffs raccourcis ({t.name})")
            elif kind == "class_debuff":  # Chevalier, Âme-tisseuse : défense − ; autres : attaque −
                pick = "def_down" if t.fighter.role in ("knight", "soul-weaver") else "atk_down"
                sub = {**effect, "type": "debuff", "effect": pick, "target": "target"}
                notes += self.apply(actor, sub, [t])
            elif kind in ("debuff_extend", "debuff_shorten") and t.debuffs:
                step = int(effect.get("amount", 1)) * (1 if kind == "debuff_extend" else -1)
                for name in list(t.debuffs):
                    if name != "bomb":  # « bomb duration cannot be extended or decreased »
                        t.debuffs[name] += step
                        if t.debuffs[name] <= 0:
                            del t.debuffs[name]
                notes.append(f"débuffs {'+' if step > 0 else ''}{step} tour ({t.name})")
            elif kind == "transfer" and actor.debuffs:  # « transfers debuffs from the caster »
                for name, turns in list(actor.debuffs.items()):
                    if "immunity" not in t.buffs:
                        t.debuffs[name] = max(t.debuffs.get(name, 0), turns)
                    del actor.debuffs[name]
                notes.append(f"débuffs transférés → {t.name}")
            elif kind == "aftermath":  # dégâts additionnels d'une autre « compétence » (E7Calc)
                data = actor.fighter.skills.get(effect["skill"], {}).get("aftermath")
                if data and t.alive and t is not actor:
                    extra = self.aftermath(actor, data, t)
                    t.last_damage += extra
                    dead = " ✝" if not t.alive else ""
                    notes.append(f"{t.name} −{_fmt(extra)} (additionnels){dead}")
            elif kind == "clone" and actor.saved is None:
                pool = [x for x in self.units if x.alive and x is not actor]
                if pool:  # copie les compétences du héros le plus offensif (choix estimé)
                    model = max(pool, key=lambda x: x.fighter.atk)
                    actor.saved = (actor.fighter, dict(actor.cooldowns))
                    actor.fighter = replace(actor.fighter, skills=model.fighter.skills)
                    actor.cooldowns = {}
                    actor.buffs["clone"] = 1
                    self.mark(actor, "buff:clone")
                    notes.append(f"{actor.name} clone {model.name}")
                break
            elif kind == "share_resist" and t is not actor:  # Silvertide Christy
                value = float(effect["ratio"]) * actor.stat("effect_res")  # taux figé au départ
                t.bonus.append({"stat": "effect_res", "value": value, "until_death": True})
                notes.append(f"résistance {t.name} +{value:.0f} %")
            elif kind == "random_debuff":
                pick = self.rng.choice(effect.get("choices", ["stun", "sleep", "redirect"]))
                sub = {**effect, "type": "debuff", "effect": pick, "target": "target"}
                notes += self.apply(actor, sub, [t])
            elif kind == "buff_steal" and t.buffs:
                name = next(iter(t.buffs))
                turns = t.buffs.pop(name)
                if "undispellable" not in t.flags:
                    actor.buffs[name] = min(turns, 2)
                    notes.append(f"{BUFF_NAMES.get(name, name)} volé à {t.name}")
                else:
                    t.buffs[name] = turns
            elif kind == "stack":  # ajoute à la jauge d'un passif (ex. Concentration)
                sid = effect["skill"]
                t.stacks[sid] = t.stacks.get(sid, 0) + float(effect["amount"])
            elif kind == "souls":
                self.souls[t.team] = min(self.souls[t.team] + int(effect["amount"]), SOUL_MAX)
            elif kind == "assist" and hit:  # tous les alliés attaquent avec leur compétence de base
                for a in self.allies(actor):
                    s1 = a.fighter.skills.get("s1")
                    victim = next((x for x in hit if x.alive), None)
                    if a is not actor and s1 and s1.get("rate") is not None and victim:
                        notes.append(f"{a.name} assiste → {self.hit(a, s1, victim)}")
                break
            elif kind == "random_buff":
                pick = self.rng.choice(effect["choices"])
                notes += self.apply(actor, {"type": "buff", "effect": pick, "target": "target",
                                            "turns": effect.get("turns", 1)}, [t])  # fmt: skip
            elif kind == "cleanse" and t.debuffs:
                if "block" in t.debuffs and t is not actor:
                    continue  # blocage : pas de dissipation venant d'un autre
                if effect.get("only"):
                    for d in effect["only"]:
                        t.debuffs.pop(d, None)
                    continue
                gone = list(t.debuffs) if effect.get("all") else [next(iter(t.debuffs))]
                for d in gone:
                    t.debuffs.pop(d, None)
                notes.append(f"débuffs retirés ({t.name})")
        return notes

    def revive_blocked(self, u: _Unit) -> bool:
        """Résurrection interdite : pour tous (Hecate) ou pour les ennemis (Sinful Angelica)."""
        if self.flagged("no_revive"):
            return True
        return any(
            f.alive and "no_revive_enemy" in f.flags and "seal" not in f.debuffs
            for f in self.units
            if f.team != u.team
        )

    def forget(self, u: _Unit) -> None:
        """Bonus perdus à la mort, même suivie d'une résurrection (ex. résistance de Christy)."""
        u.bonus = [b for b in u.bonus if not b.get("until_death")]

    def flagged(self, flag: str) -> bool:
        """Mécanique de champ de bataille portée par un héros vivant (ex. pas de résurrection)."""
        return any(u.alive and flag in u.flags and "seal" not in u.debuffs for u in self.units)

    def speed(self, u: _Unit) -> float:
        """Vitesse effective : loi de Skuggiheim (Harsetti) et immobilisation comprises."""
        law = next((x for x in self.units if x.alive and "speed_law" in x.flags), None)
        damp = max((f.aura.get("speed_dampen", 0) for f in self.foes(u)), default=0)
        if law is None:
            return u.speed * (1 - float(damp))  # Requiem Roana : jauge par la vitesse −50 %
        if u is law:
            return max(u.fighter.spd, 1)  # vitesse figée
        return min(u.speed, SPEED_LAW * law.fighter.spd)

    def sanctuary(self) -> bool:
        """Sanctuaire de la guerre (Notos) : actif tant qu'un héros a Dieu de la guerre."""
        return any(u.alive and "god" in u.buffs for u in self.units)

    def revive_ally(self, actor: _Unit, effect: dict[str, Any]) -> list[str]:
        """Ressuscite un allié mort (sinon soigne l'allié le plus blessé) ; cible de « last »."""
        dead = [u for u in self.units if u.team == actor.team and not u.alive and not u.extinct]
        dead = [u for u in dead if not self.revive_blocked(u)]
        if effect.get("dead_only") and not dead:
            self.last_targets = []
            return []
        if effect.get("all"):  # « revives all dead allies »
            for u in dead:
                u.hp = float(effect.get("ratio", 1.0)) * u.max_hp
            self.last_targets = dead
            return [f"{u.name} ressuscite ({_fmt(u.hp)} PV)" for u in dead]
        pool = dead or [a for a in self.allies(actor) if a is not actor] or [actor]
        t = dead[0] if dead else min(pool, key=lambda a: a.hp / a.max_hp)
        before = t.hp
        t.hp = max(t.hp, float(effect.get("ratio", 1.0)) * t.max_hp)
        self.last_targets = [t]
        if not before:
            return [f"{t.name} ressuscite ({_fmt(t.hp)} PV)"]
        return [f"soin {t.name} +{_fmt(t.hp - before)}"] if t.hp > before else []

    def hit(
        self, actor: _Unit, skill: dict[str, Any], target: _Unit, soulburn: bool = False
    ) -> str:
        opts = replace(
            self.opts,
            soulburn=soulburn,
            attack_buff="great"
            if "atk_up_great" in actor.buffs and "atk_down" not in actor.debuffs
            else "up"
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
        if skill.get("consume_hp") and actor.hp > 1:  # « consumes all Health to attack »
            actor.hp = 1.0
        skill = self.dynamic(actor, skill, target)
        if self.bonus_depth:
            self.bonus_hits.append(target)
        attacker = actor.attacker_view()
        if "morale" in actor.buffs:
            opts = replace(opts, damage_increase=opts.damage_increase + 10)
        defender = replace(target.fighter, defense=target.stat("defense"))
        dmg = skill_damage(attacker, skill, defender, opts)
        forced = skill.get("crit_if_mark")  # ex. Schuri : Rafale complète avec 3 Concentration
        crit = dmg["crit"] is not None and (
            bool(skill.get("always_crit"))
            or bool(forced and actor.marks.get(forced["mark"], 0) >= forced["at_least"])
            or self.rng.random() < attacker.crit_chance / 100
        )
        amount = float(dmg["crit"] if crit and dmg["crit"] is not None else dmg["normal"] or 0)
        if "invincible" in target.buffs:
            return f"{target.name} invincible"
        if "nullifier" in target.buffs:
            del target.buffs["nullifier"]
            return f"{target.name} annule la compétence"
        if "def_magic" in target.flags and self.souls[target.team] >= DEFENSIVE_MAGIC_SOULS:
            self.souls[target.team] -= DEFENSIVE_MAGIC_SOULS  # Magie défensive : 4 Âmes
            return f"{target.name} annule la compétence (magie défensive)"
        dodge = MISS_CHANCE if "evasion" in target.buffs or "hit_down" in actor.debuffs else 0
        for a in self.allies(target):  # aura d'esquive (ex. Setsuka : +30 % aux alliés)
            dodge = max(dodge, float(a.aura.get("evasion", 0)))
        dodge = max(dodge, float(target.aura.get("evasion_self", 0)))
        dodge = max(dodge, 0.2 if "rampage" in target.buffs else 0)
        miss = dodge > 0 and self.rng.random() < dodge
        if miss and actor is self.current:
            self.evaded.append(target)
        if miss:
            crit, amount = False, amount_miss(dmg)
        if skill.get("off_turn_mult") and actor is not self.current:
            amount *= float(skill["off_turn_mult"])
        if "rupture" in target.debuffs:
            amount += RUPTURE * target.max_hp
        if "abundance" in actor.buffs:
            amount += ABUNDANCE
        if "cascade" in actor.buffs:
            amount += CASCADE
        amount += self.soul_bonus
        if "target_mark" in target.debuffs:
            amount *= 1 + TARGET_MARK
        if "friendship" in actor.buffs and crit and actor is self.current:
            amount += FRIENDSHIP * actor.max_hp
        reduction = max(target.reduction, 0.5 if "deify" in target.buffs else 0)
        if "fragrance" in target.buffs:
            reduction = max(reduction, FRAGRANCE)
        if "radiance" in target.buffs:
            reduction = max(reduction, RADIANCE)
        if crit:  # réduction des dégâts critiques (ex. Little Queen Charlotte)
            for a in self.allies(target) + [target]:
                guard = a.aura.get("crit_self" if a is target else "crit_allies", 0)
                reduction = max(reduction, float(guard))
        if "stealth" in target.buffs and skill.get("aoe"):
            reduction = max(reduction, STEALTH_AOE_REDUCTION)
            del target.buffs["stealth"]  # « dispelled upon suffering damage »
        target.debuffs.pop("sleep", None)  # « when suffering damage, is dispelled »
        amount *= 1 - (0 if skill.get("ignore_reduction") else reduction)
        if not (skill.get("ignore_share") or "ignore_share" in actor.buffs):
            amount -= self.shared(target, amount)
        cap = min(
            c for c in (target.cap or 1, DAMAGE_LIMIT if "damage_limit" in target.buffs else 1)
        )
        if cap < 1:
            amount = min(amount, cap * target.fighter.hp)
        absorbed = min(target.barrier, amount)
        target.barrier -= absorbed
        if target.hp - (amount - absorbed) <= 0 and "immortal" not in target.buffs:
            self.fire(target, "lethal", actor)  # ex. immortalité sur dégâts mortels
            if "engulf" in target.buffs:  # « grants cascade to all allies, and is dispelled »
                del target.buffs["engulf"]
                for a in self.allies(target):
                    if a is not target:
                        a.buffs["cascade"] = PERMANENT
            if "offering" in target.buffs and not target.last_fired.get("offering"):
                target.last_fired["offering"] = 1  # offrande : immortalité une seule fois
                target.buffs["immortal"] = 1
        target.hp = max(1.0 if "immortal" in target.buffs else 0.0, target.hp - (amount - absorbed))
        reflect = float(target.aura.get("reflect", 0))
        if reflect and actor.alive and actor is not target:  # « reflects 40% of damage suffered »
            back = min(reflect * (amount - absorbed), target.fighter.hp)
            actor.hp = max(1.0 if "immortal" in actor.buffs else 0.0, actor.hp - back)
            if not actor.alive:
                self.deaths.append(actor)
        if crit:
            self.crits.append(actor)
            if target.alive:
                self.fire(target, "crit_taken", actor)
                if "possession" in target.buffs and actor is self.current:
                    self.counter(target, actor, forced=True)  # « counterattacks on a crit »
        if target.hp <= 0 and any(e["type"] == "extinction" for e in skill.get("effects", [])):
            target.extinct = True
        for keeper, ratio in (("spirit_guard", 0.5), ("revive_buff", REVIVE_BUFF)):
            if target.hp <= 0 and keeper in target.buffs and not self.revive_blocked(target):
                del target.buffs[keeper]  # « upon receiving lethal damage, revives with ... »
                target.hp = ratio * target.max_hp
                if keeper == "spirit_guard":
                    target.gauge = min(target.gauge + 50, 100)
                self.forget(target)  # mort puis résurrection sur place
                return f"{target.name} −{_fmt(amount)}, ressuscite ({_fmt(target.hp)} PV)"
        if target.hp <= 0 and "time_reversal" in target.buffs and not target.extinct:
            del target.buffs["time_reversal"]  # « returns to the state after the start of battle »
            target.hp, target.injury, target.debuffs = target.fighter.hp, 0.0, {}
            return f"{target.name} −{_fmt(amount)}, retour temporel"
        if target.hp <= 0 and "covenant" in target.buffs and not self.revive_blocked(target):
            del target.buffs["covenant"]  # « upon dying, revives with 100% Health »
            target.hp = target.max_hp
            self.forget(target)  # mort puis résurrection sur place
            return f"{target.name} −{_fmt(amount)}, ressuscite (pacte sacré)"
        if target.hp <= 0:
            blocked = target.extinct or self.revive_blocked(target)
            for _sid, passive in [] if blocked else self.triggered(target, "revive"):
                target.hp = target.fighter.hp * float(passive["trigger"].get("health", 0.5))
                for effect in passive.get("effects", []):
                    self.apply(target, effect, [])
                self.stats["passives"] += 1
                self.forget(target)  # mort puis résurrection sur place
                return f"{target.name} −{_fmt(amount)}, ressuscite ({_fmt(target.hp)} PV)"
            target.barrier = 0
            self.deaths.append(target)
        for cursed in [a for a in self.allies(target) if a is not target and "curse" in a.debuffs]:
            extra = CURSE * amount  # malédiction : le porteur subit 60 % des dégâts de l'allié
            cursed.hp = max(1.0 if "immortal" in cursed.buffs else 0.0, cursed.hp - extra)
            if not cursed.alive:
                self.deaths.append(cursed)
        effects = skill.get("effects", [])
        for e in effects:
            if e["type"] == "injury" and target.alive:  # gravité ∝ dégâts (estimée à 25 %)
                room = float(e["max"]) * target.fighter.hp - target.injury
                target.injury += max(min(0.25 * amount, room), 0)
                target.hp = min(target.hp, target.max_hp)
            elif e["type"] == "fixed" and target.alive and (crit or not e.get("on_crit")):
                fixed = float(e["amount"]) * (len(target.debuffs) if e.get("per_debuff") else 1)
                if e.get("grow"):  # Schniel : +4 000 par utilisation, 2 cumuls au plus
                    uses = actor.stacks.get("uses:" + str(skill.get("name")), 0)
                    fixed += float(e["grow"]) * min(uses, int(e.get("grow_max", 2)))
                if e.get("plus_stack"):  # Kayron : +100 par point d'Esprit consommé
                    ps = e["plus_stack"]
                    fixed += min(float(ps["per"]) * actor.stacks.get(ps["skill"], 0), ps["max"])
                fixed *= 2 if "knowledge" in actor.buffs else 1  # dégâts additionnels +100 %
                guard = max(
                    (float(a.aura.get("fixed_guard", 0)) for a in self.allies(target)), default=0
                )
                fixed *= 1 - guard  # Fallen Cecilia : dégâts additionnels et fixes −50 %
                if fixed:
                    target.hp = max(1.0 if "immortal" in target.buffs else 0.0, target.hp - fixed)
                    amount += fixed
                    if not target.alive:
                        target.barrier = 0
                        self.deaths.append(target)
        data = skill.get("aftermath")
        gated = data and (
            not data.get("conditional")
            or (skill.get("aftermath_if") and self.gate(actor, skill["aftermath_if"], [target]))
        )
        if gated and data and not miss and target.alive and "invincible" not in target.buffs:
            amount += self.aftermath(actor, data, target, soulburn)
        target.last_damage += amount
        text = f"{target.name} −{_fmt(amount)}" + (
            " (critique)" if crit else " (raté)" if miss else ""
        )
        steal = sum(e["ratio"] for e in effects if e["type"] == "lifesteal")
        steal += actor.fighter.lifesteal / 100
        if steal and actor.alive and "unhealable" not in actor.debuffs:
            healed = min(steal * amount, actor.max_hp - actor.hp)
            if healed > 0:
                actor.hp += healed
                self.stats["healed"] += healed
                text += f" [vol de vie +{_fmt(healed)}]"
        if absorbed:
            text += f" [barrière −{_fmt(absorbed)}]"
        return text + (" ✝" if not target.alive else "")

    def dynamic(self, actor: _Unit, skill: dict[str, Any], target: _Unit) -> dict[str, Any]:
        """Bonus de dégâts qui dépendent de l'état du combat (formules E7Calc, `dynamic`)."""
        dyn = skill.get("dynamic")
        if not dyn:
            return skill
        out = dict(skill)
        mult, flat = 1.0, 0.0
        if "target_hp" in dyn:  # « ∝ target's current Health »
            flat += float(dyn["target_hp"]) * target.hp
        if "caster_lost_hp" in dyn:  # « ∝ caster's lost Health »
            flat += float(dyn["caster_lost_hp"]) * max(actor.max_hp - actor.hp, 0)
        if "target_lost_hp" in dyn:  # « ∝ enemy's lost Health »
            mult *= 1 + float(dyn["target_lost_hp"]) * (1 - target.hp / target.max_hp)
        if "hp_diff" in dyn and target.max_hp > actor.max_hp:  # Fenris : jusqu'à +70 %
            gap = (target.max_hp - actor.max_hp) * float(dyn["hp_diff"])
            mult *= 1 + min(gap, float(dyn.get("hp_diff_max", 0.7)))
        if dyn.get("vs_element") and target.fighter.element == dyn["vs_element"]:
            mult *= 1 + float(dyn["vs_mult"])
        if "mark_mult" in dyn:  # ex. Zeno : Bête ancestrale +10 % par cumul
            mm = dyn["mark_mult"]
            mult *= 1 + float(mm["per"]) * actor.marks.get(mm["mark"], 0)
        if "pen_low_hp" in dyn and actor.hp <= dyn["pen_low_hp"][0] * actor.max_hp:
            out["pen"] = dyn["pen_low_hp"][1]  # Amiki : pénétration 70 % sous 30 % des PV
        if "pen_stack" in dyn:  # Aria : +35 % par utilisation précédente, 2 cumuls
            uses = actor.stacks.get("uses:" + str(skill.get("name")), 0)
            extra = float(dyn["pen_stack"]) * min(uses, int(dyn.get("pen_max", 2)))
            out["pen"] = min(float(out.get("pen") or 0) + extra, 1)
        out["pow"] = float(out.get("pow", 1)) * mult
        if out.get("pow_sb") is not None:
            out["pow_sb"] = float(out["pow_sb"]) * mult
        out["flat_abs"] = flat
        return out

    def aftermath(
        self,
        actor: _Unit,
        data: dict[str, Any],
        target: _Unit,
        soulburn: bool = False,
    ) -> float:
        """Dégâts additionnels : statistique × part × 1,871, 70 % de la défense ignorée."""
        ratio = float(data.get("ratio_sb", data["ratio"]) if soulburn else data["ratio"])
        if data["stat"] == "target_hp":
            amount = ratio * target.max_hp
        else:
            buff = (
                "great" if "atk_up_great" in actor.buffs
                else "up" if "atk_up" in actor.buffs
                else "down" if "atk_down" in actor.debuffs
                else "none"
            )  # fmt: skip
            base = {
                "atk": actor.stat("atk") * (1 + ATTACK_BUFFS[buff]),
                "hp": actor.max_hp,
                "def": actor.stat("defense"),
            }[data["stat"]]
            pen = float(data.get("pen", AFTERMATH_PEN))
            mitigation = target.stat("defense") / 300 * (1 - pen) + 1
            amount = base * ratio * DAMAGE_CONSTANT / mitigation
        amount *= 2 if "knowledge" in actor.buffs else 1  # dégâts additionnels +100 %
        guard = max((float(a.aura.get("fixed_guard", 0)) for a in self.allies(target)), default=0)
        amount *= 1 - guard
        if "invincible" in target.buffs or not target.alive:
            return 0.0
        target.hp = max(1.0 if "immortal" in target.buffs else 0.0, target.hp - amount)
        if not target.alive:
            target.barrier = 0
            self.deaths.append(target)
        return amount

    def specials(self, actor: _Unit, skill: dict[str, Any], hit: list[_Unit]) -> None:
        """Attaque double d'un allié et tour supplémentaire après une compétence."""
        effects = skill.get("effects", [])
        dual = next((e for e in effects if e["type"] == "dual"), None)
        if dual and not self.gate(actor, dual, hit):
            dual = None
        if dual and self.foes(actor):
            partners = [a for a in self.allies(actor) if a is not actor and "bind" not in a.debuffs]
            if partners:
                ally = max(partners, key=lambda a: a.fighter.atk)
                s1 = ally.fighter.skills.get("s1")
                if s1 and s1.get("rate") is not None:
                    target = next((t for t in hit if t.alive), None)
                    target = target or self.main_target(ally, self.foes(ally))
                    self.bonus_depth += 1
                    text = self.hit(ally, s1, target)
                    self.bonus_depth -= 1
                    self.note(f"  ↳ {ally.name} attaque double → {text}")
        for e in effects:
            if e["type"] == "extra_attack":
                self.extra_attack(actor, e, hit)
        if hit and "dawn" in actor.buffs:  # Aube : 25 % d'étourdir la cible après l'attaque
            stun = {
                "type": "debuff",
                "effect": "stun",
                "target": "target",
                "turns": 1,
                "chance": 0.25,
            }
            if notes := self.apply(actor, stun, [t for t in hit if t.alive][:1]):
                self.note(f"  ↳ {actor.name} aube → " + ", ".join(notes))
        alive = [t for t in hit if t.alive]
        if alive and actor is self.current and actor.alive:
            if "oath" in actor.buffs:  # Serment de punition : 2 500 dégâts fixes à la cible
                zap = {"type": "fixed_hit", "amount": OATH, "target": "target"}
                notes = self.apply(actor, zap, alive[:1])
                self.note(f"  ↳ {actor.name} serment → " + ", ".join(notes))
            if "pestilence" in actor.buffs:  # venin 1 tour puis explosion du venin
                ven = {"type": "debuff", "effect": "venom", "target": "target", "turns": 1}
                self.apply(actor, ven, alive[:1])
                self.detonate({"effects": [{"type": "detonate", "what": ["venom"]}]}, alive[:1])
        if "explosives" in actor.buffs and alive:  # « plants bombs on the target for 2 turns »
            bomb = {"type": "debuff", "effect": "bomb", "target": "target", "turns": 2}
            self.apply(actor, bomb, alive[:1])
            del actor.buffs["explosives"]
        if "bzzt" in actor.buffs and hit and self.foes(actor):  # Bzzt! : 2 500 à tous les ennemis
            zap = {"type": "fixed_hit", "amount": BZZT, "target": "enemies"}
            self.note(f"  ↳ {actor.name} Bzzt! → " + ", ".join(self.apply(actor, zap, hit)))
        if "cascade" in actor.buffs and hit:
            del actor.buffs["cascade"]  # « dispelled after attacking »
        if actor.marks.get("dirge") and actor is self.current and self.foes(actor):
            self.dirge(actor)
        killed = any(not t.alive for t in hit)
        for e in effects:
            if e["type"] != "extra_turn" or (e.get("on_kill") and not killed):
                continue
            if e.get("on_crit") and actor not in self.crits:
                continue
            if not self.gate(actor, {**e, "if_crit": False}, hit):
                continue
            if actor.alive and self.rng.random() < e.get("chance", 1):
                actor.gauge = 100
                self.stats["extra_turns"] += 1
                self.note(f"  ↳ {actor.name} rejoue (tour supplémentaire)")
                for f in self.foes(actor):
                    self.fire(f, "enemy_extra_turn", actor)
                for a in self.allies(actor):
                    if a is not actor:
                        self.fire(a, "ally_extra_turn", actor)
                break

    def extra_attack(self, actor: _Unit, e: dict[str, Any], hit: list[_Unit]) -> None:
        """Attaque supplémentaire avec une autre compétence (sous certaines conditions)."""
        if not actor.alive or "bind" in actor.debuffs or not self.foes(actor):
            return
        if e.get("own_turn") and actor is not self.current:
            return
        if e.get("if_buff") and e["if_buff"] not in actor.buffs:
            return
        if e.get("if_cooldown") and actor.cooldowns.get(e["if_cooldown"], 0) <= 0:
            return  # ex. « when Purge is on cooldown »
        chance = float(e.get("chance", 1)) * (2 if e.get("chance_x2_if") in actor.buffs else 1)
        key = f"extra:{e['skill']}"
        if e.get("once_per_turn") and actor.last_fired.get(key) == actor.turns:
            return
        last = actor.last_fired.get(key)
        if e.get("every") and last is not None and actor.turns - last < int(e["every"]):
            return
        if not self.gate(actor, {**e, "if_buff": None, "if_cooldown": None}, hit):
            return
        if self.rng.random() >= chance:
            return
        skill = actor.fighter.skills.get(e["skill"])
        if not skill or skill.get("rate") is None:
            return
        actor.last_fired[key] = actor.turns
        if any(x["type"] == "soul_damage" for x in skill.get("effects", [])):
            sd = next(x for x in skill["effects"] if x["type"] == "soul_damage")
            spent, self.souls[actor.team] = self.souls[actor.team], 0
            self.soul_bonus = min(float(sd["per_soul"]) * spent, float(sd["cap"]))
        foes = self.foes(actor)
        alive = [t for t in hit if t.alive]
        targets = (
            foes if skill.get("aoe") else [alive[0] if alive else self.main_target(actor, foes)]
        )
        self.bonus_depth += 1
        parts = [self.hit(actor, skill, t) for t in targets]
        self.bonus_depth -= 1
        self.soul_bonus = 0.0
        for effect in skill.get("effects", []):
            parts += self.apply(actor, effect, targets)
        self.note(f"  ↳ {actor.name} attaque supplémentaire → " + ", ".join(parts))
        if any(not t.alive for t in targets):
            for effect in skill.get("on_kill", []):
                self.apply(actor, effect, targets)

    def dirge(self, actor: _Unit) -> None:
        """Balles funèbres (Renoa) : une attaque par balle (5 au plus, estimé), puis consommées."""
        shots, actor.marks["dirge"] = min(actor.marks["dirge"], 5), 0
        bullet = actor.fighter.skills.get("s2_extra")
        if not bullet or bullet.get("rate") is None:
            return
        parts = []
        for _ in range(shots):
            foes = self.foes(actor)
            if not foes:
                break
            parts.append(self.hit(actor, bullet, self.rng.choice(foes)))
            for sid, sk in actor.fighter.skills.items():  # « Dirge Bullet (Gains 1 Focus) »
                res = (sk.get("trigger") or {}).get("resource")
                if res and res["kind"] == "focus":
                    actor.stacks[sid] = min(actor.stacks.get(sid, 0) + 1, res["need"])
        self.note(f"  ↳ {actor.name} balles funèbres → " + ", ".join(parts))

    def shared(self, target: _Unit, amount: float) -> float:
        """Partage de dégâts : un allié (Offrande, passif) prend sa part ; renvoie cette part."""

        def rate(a: _Unit) -> float:
            return max(
                a.share,
                OFFERING_SHARE if "offering" in a.buffs else 0,
                ESCORT if "escort" in a.buffs else 0,
            )

        sharers = [
            a
            for a in self.allies(target)
            if a is not target and rate(a) > 0 and "invincible" not in a.buffs
        ]
        if not sharers:
            return 0.0
        mate = max(sharers, key=rate)
        part = amount * rate(mate)
        mate.hp = max(1.0 if "immortal" in mate.buffs else 0.0, mate.hp - part)
        if not mate.alive:
            self.deaths.append(mate)
        return part

    def dot_amount(self, u: _Unit, name: str) -> float:
        stat, ratio = DOT[name]
        if stat == "hp":
            return ratio * u.max_hp * (1 - u.reduction)
        mitigation = u.stat("defense") * (1 - DOT_DEF_IGNORED) / 300 + 1
        return ratio * u.dot_atk.get(name, 0) / mitigation * (1 - u.reduction)

    def detonate(self, skill: dict[str, Any], hit: list[_Unit]) -> None:
        """Explosion : les dégâts restants des brûlures / saignements tombent d'un coup."""
        for e in skill.get("effects", []):
            if e["type"] != "detonate":
                continue
            if e.get("if_crit") and self.current not in self.crits:
                continue  # ex. Rhianna : « a critical hit will detonate erosion »
            for t in hit:
                if not t.alive or "invincible" in t.buffs:
                    continue
                total = 0.0
                if "bomb" in e.get("what", []) and "bomb" in t.debuffs:
                    self.explode(t)
                for name in e.get("what", []):
                    if name in DOT and name in t.debuffs:
                        total += self.dot_amount(t, name) * t.debuffs.pop(name)
                if total:
                    t.hp = max(1.0 if "immortal" in t.buffs else 0.0, t.hp - total)
                    dead = " ✝" if not t.alive else ""
                    self.note(f"  ↳ explosion sur {t.name} −{_fmt(total)}{dead}")
                    if not t.alive:
                        self.deaths.append(t)
        self.after_events()

    def explode(self, u: _Unit) -> None:
        """Bombe : 150 % de l'attaque du lanceur (70 % de défense ignorée), puis immobile."""
        mitigation = u.stat("defense") * (1 - DOT_DEF_IGNORED) / 300 + 1
        amount = BOMB * u.dot_atk.get("bomb", 0) / mitigation * (1 - u.reduction)
        u.debuffs.pop("bomb", None)
        if "invincible" in u.buffs:
            return
        u.hp = max(1.0 if "immortal" in u.buffs else 0.0, u.hp - amount)
        u.debuffs["stun"] = max(u.debuffs.get("stun", 0), 1)
        self.note(f"  ↳ bombe sur {u.name} −{_fmt(amount)}" + (" ✝" if not u.alive else ""))
        if not u.alive:
            self.deaths.append(u)

    def dots(self, u: _Unit) -> None:
        """Brûlure, saignement, poison : dégâts au début du tour du porteur."""
        parts = []
        for name in DOT:
            if name not in u.debuffs:
                continue
            amount = self.dot_amount(u, name)
            if "invincible" in u.buffs:
                continue
            u.hp = max(1.0 if "immortal" in u.buffs else 0.0, u.hp - amount)
            if name == "venom":  # blessures proportionnelles aux dégâts (part estimée : 25 %)
                u.injury = min(u.injury + 0.25 * amount, 0.5 * u.fighter.hp)
                u.hp = min(u.hp, u.max_hp)
            parts.append(f"{DEBUFF_NAMES[name]} −{_fmt(amount)}")
        if parts:
            self.note(f"  ↳ {u.name} : " + ", ".join(parts) + (" ✝" if not u.alive else ""))
            if not u.alive:
                self.deaths.append(u)
                self.after_events()

    def after_events(self) -> None:
        """Passifs déclenchés par les coups critiques et les morts de l'action."""
        bonus, self.bonus_hits = list({id(u): u for u in self.bonus_hits}.values()), []
        for t in bonus:  # Fenris : « after an ally suffers an extra attack, counterattack... »
            for a in self.allies(t):
                self.fire(a, "ally_bonus_hit", t)
        crits, self.crits = list({id(u): u for u in self.crits}.values()), []
        for u in crits:
            self.fire(u, "crit")
            for a in self.allies(u):
                if a is not u:
                    self.fire(a, "ally_crit", u)
        while self.deaths:
            dead = self.deaths.pop(0)
            if not dead.alive:
                self.forget(dead)
            for u in [x for x in self.units if x.alive and x is not dead]:
                self.fire(u, "death", dead)

    def end_turn(self, u: _Unit) -> None:
        self._end_turn(u)
        if self.keep_log:
            self.frames.append(
                {
                    "line": len(self.log),
                    "actor": self.units.index(u),
                    "hp": [round(max(0.0, x.hp)) for x in self.units],
                    "shield": [round(x.barrier) for x in self.units],
                }
            )

    def _end_turn(self, u: _Unit) -> None:
        self.fire(u, "turn_end")
        for other in [x for x in self.units if x.alive and x is not u]:
            self.fire(other, "any_turn_end", u)
            self.fire(other, "ally_turn_end" if other.team == u.team else "enemy_turn_end", u)
        if u.alive and "swift" in u.buffs:  # « at the end of the turn, CR +50%, then dispelled »
            del u.buffs["swift"]
            u.gauge = min(u.gauge + SWIFT, 100)
        if u.alive and "beguile" in u.debuffs:  # « dispelled once the effect is activated »
            del u.debuffs["beguile"]
            for a in self.allies(u):
                if a is not u:
                    a.hp = max(1.0 if "immortal" in a.buffs else 0.0, a.hp - BEGUILE * a.max_hp)
                    if not a.alive:
                        self.deaths.append(a)
            self.note(f"  ↳ envoûtement de {u.name} : alliés −10 % PV")
        for bag, prefix in ((u.buffs, "buff:"), (u.debuffs, "debuff:")):
            for name in list(bag):
                if prefix + name in u.fresh:
                    continue
                bag[name] -= 1
                if bag[name] <= 0:
                    del bag[name]
                    if name == "overload":  # « upon ending, inflicts energy depletion »
                        u.debuffs["depletion"] = 1
                        u.fresh.add("debuff:depletion")  # pas décompté ce tour-ci
                    elif name == "bomb" and u.alive:
                        self.explode(u)
        if u.barrier_turns and "barrier" not in u.fresh:
            u.barrier_turns -= 1
            if u.barrier_turns <= 0:
                u.barrier = 0
        u.fresh.clear()
        if u.saved is not None and "clone" not in u.buffs:  # fin du clone : héros d'origine
            u.fighter, u.cooldowns = u.saved
            u.saved = None
        u.hp = min(u.hp, u.max_hp)  # fin d'un bonus de PV max
        if "provoke" not in u.debuffs:
            u.provoker = None

    def run(self) -> BattleResult:
        for u in self.units:
            self.fire(u, "battle_start")
        while self.actions < MAX_ACTIONS:
            alive = [u for u in self.units if u.alive]
            if len({u.team for u in alive}) < 2:
                break
            actor = min(alive, key=lambda u: (100 - u.gauge) / self.speed(u))
            wait = max((100 - actor.gauge) / self.speed(actor), 0)
            for u in alive:
                if "immobilize" not in u.debuffs:  # pas de jauge gagnée par la vitesse
                    u.gauge = min(u.gauge + self.speed(u) * wait, 100)
            actor.gauge = 0
            self.actions += 1
            if self.actions == 1:  # Aram : « if an enemy / an ally takes the first turn »
                for u in self.units:
                    self.fire(u, "first_turn", actor)
            for u in self.units:
                u.last_damage = 0.0
            debuffs_before = self.stats["debuffs"]
            self.current = actor
            actor.turns += 1
            notes = len(self.log)
            if "continuous_heal" in actor.buffs and "unhealable" not in actor.debuffs:
                actor.hp = min(actor.hp + CONTINUOUS_HEAL * actor.max_hp, actor.max_hp)
            self.dots(actor)
            if not actor.alive:
                self.end_turn(actor)
                continue
            self.fire(actor, "turn_start")
            for f in self.foes(actor):
                self.fire(f, "enemy_turn_start", actor)
            for a in self.allies(actor):
                if a is not actor:
                    self.fire(a, "ally_turn_start", actor)
            if "fear" in actor.debuffs and self.rng.random() < FEAR_DISPEL:
                del actor.debuffs["fear"]  # « 40% chance to be dispelled »
            if {"stun", "sleep", "fear", "detain"} & set(actor.debuffs):
                self.note(f"{actor.name} ne peut pas agir", at=notes)
                self.end_turn(actor)
                continue
            sid = self.choose(actor)
            foes = self.foes(actor)
            if sid is None or not foes:
                self.end_turn(actor)
                continue
            skill = actor.fighter.skills[sid]
            swap = skill.get("swap")  # compétence remplacée pendant son tour (ex. Possession)
            on_cd = (
                not swap
                or not swap.get("if_cooldown")
                or (actor.cooldowns.get(swap["if_cooldown"], 0) > 0)
            )
            if swap and swap.get("if_debuff") and swap["if_debuff"] not in actor.debuffs:
                swap = None
            if (
                swap
                and on_cd
                and (
                    not swap.get("if_buff")
                    or (actor.buffs if swap["if_buff"] == "*" else swap["if_buff"] in actor.buffs)
                )
            ):
                skill = {**actor.fighter.skills.get(swap["skill"], skill), "cooldown": 0}
            parts: list[str] = []
            hit: list[_Unit] = []
            cost = int(skill.get("soulburn_cost", SOULBURN_COST))
            if any("soulburn_tax" in f.flags for f in foes):
                cost *= 2  # « increases Soulburn consumption of the enemy by 100% »
            free = 0 if "oasis" in actor.buffs else cost
            burn = (
                sid != "s1" and skill.get("rate_sb") is not None and self.souls[actor.team] >= free
            )
            if burn and "oasis" in actor.buffs:
                del actor.buffs[
                    "oasis"
                ]  # « does not cost any Soul to activate the first Soulburn »
                cost = 0
            if burn:
                self.souls[actor.team] -= cost
                parts.append("âme brûlée")
                for u in [x for x in self.units if x.alive and x is not actor]:
                    self.fire(u, "soulburn", actor)
            gain = (1 if sid == "s1" else 2) * (2 if "dawn" in actor.buffs else 1)
            if any("soul_block" in f.flags for f in foes):
                gain = 0  # « decreases the amount of Soul acquired by the enemy by 100% »
            self.souls[actor.team] = min(self.souls[actor.team] + gain, SOUL_MAX)
            if skill.get("rate") is not None:
                hit = self.targets(actor, skill, foes)
                parts += [self.hit(actor, skill, t, soulburn=burn) for t in hit]
            for effect in skill.get("effects", []):
                parts += self.apply(actor, effect, hit)
            for k in actor.cooldowns:
                actor.cooldowns[k] = max(0, actor.cooldowns[k] - 1)
            actor.cooldowns[sid] = self.cooldown(sid, skill)
            self.note(f"{actor.name} ({sid.upper()}) → " + (", ".join(parts) or "—"), at=notes)
            if hit:
                for t in hit:
                    self.fire(t, "attacked", actor)
                for t in hit:  # « when an ally is attacked » : les autres alliés de la cible
                    for ally in self.allies(t):
                        if ally is not t:
                            self.fire(ally, "ally_attacked", t)
                            if len(hit) == 1 and not skill.get("aoe"):
                                self.fire(ally, "ally_single_attacked", t)
                for t in hit if not skill.get("no_counter") else []:
                    self.counter(t, actor)
                if skill.get("aoe"):
                    for t in hit:  # « after suffering an attack that targets all allies »
                        self.fire(t, "aoe_attacked", actor)
                for a in self.allies(actor):
                    if a is not actor:
                        self.fire(a, "ally_hit", hit[0])
                        if sid == "s1":
                            self.fire(a, "ally_basic", hit[0])
                if any(not t.alive for t in hit):
                    self.fire(actor, "kill", hit[0])
                self.fire(actor, "after_attack", hit[0])
            for f in self.foes(actor):
                self.fire(f, "enemy_skill", actor, non_attack=skill.get("rate") is None)
            for a in self.allies(actor):
                self.fire(a, "team_skill", actor)
            if skill.get("rate") is None:
                for a in self.allies(actor):
                    if a is not actor:
                        self.fire(a, "ally_nonattack", actor)
            if hit:
                for a in self.allies(actor):
                    self.fire(a, "team_attack", actor)  # ex. mission offensive de Politis
                    if a is not actor and len(hit) == 1 and not skill.get("aoe"):
                        self.fire(a, "ally_single_attack", hit[0])
            evaded, self.evaded = self.evaded, []
            for t in evaded:
                for a in self.allies(t):
                    if a is not t:
                        self.fire(a, "ally_evaded", t)
            self.specials(actor, skill, hit)
            if "repeat" in actor.buffs and hit and actor.alive and sid in actor.fighter.skills:
                del actor.buffs[
                    "repeat"
                ]  # Mei Lin : « on the next attack, grants an extra attack »
                self.extra_attack(actor, {"skill": sid}, hit)
            inflicted = int(self.stats["debuffs"] - debuffs_before)
            for a in self.allies(actor) if inflicted else []:
                if "debuff_cr" in a.flags and "seal" not in a.debuffs:  # Tidal Rift Elvira
                    gains = sum(self.rng.random() < 0.25 for _ in range(inflicted))
                    a.gauge = min(a.gauge + 15 * gains, 100)
            for e in skill.get("effects", []):  # Kayron : Esprit combatif consommé
                if e["type"] == "fixed" and e.get("plus_stack", {}).get("consume"):
                    actor.stacks[e["plus_stack"]["skill"]] = 0
            name = "uses:" + str(skill.get("name"))
            actor.stacks[name] = actor.stacks.get(name, 0) + 1
            self.detonate(skill, hit)
            self.after_events()
            self.end_turn(actor)
        teams = {u.team for u in self.units if u.alive}
        return BattleResult(
            winner=teams.pop() if len(teams) == 1 else None,
            actions=self.actions,
            log=self.log,
            remaining_hp=[[round(u.hp) for u in self.units if u.team == t] for t in (0, 1)],
            stats=self.stats,
            frames=self.frames,
            units=[{"name": u.name, "team": u.team, "max_hp": round(u.max_hp)} for u in self.units]
            if self.keep_log
            else [],
        )

    def note(self, text: str, at: int | None = None) -> None:
        """Ligne du journal ; `at` : position (l'action avant les passifs qu'elle déclenche)."""
        if not self.keep_log:
            return
        line = text if text.startswith("  ↳") else f"{self.actions:>3}. {text}"
        self.log.insert(len(self.log) if at is None else at, line)


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
    totals = {
        k: 0.0
        for k in ("healed", "shielded", "buffs", "debuffs", "counters", "passives", "extra_turns")
    }
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
            "frames": sample.frames,
            "units": sample.units,
        },
    }
