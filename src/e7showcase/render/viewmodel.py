"""Transformation Hero -> données prêtes à afficher (formatage, couleurs, scores)."""

from __future__ import annotations

from dataclasses import dataclass, field

from e7showcase.calc.gear_score import gear_score
from e7showcase.models.gear import GearSlot
from e7showcase.models.hero import Hero
from e7showcase.models.stats import StatType
from e7showcase.reference import load

ELEMENT_COLORS = {
    "fire": "#ff6b4a",
    "ice": "#4ab3ff",
    "earth": "#6fdc6a",
    "light": "#ffd966",
    "dark": "#b07cff",
    None: "#9aa4b2",
}
ELEMENT_FR = {
    "fire": "Feu",
    "ice": "Glace",
    "earth": "Terre",
    "light": "Lumière",
    "dark": "Ténèbres",
}
ROLE_FR = {
    "knight": "Chevalier",
    "warrior": "Guerrier",
    "thief": "Assassin",
    "ranger": "Tireur",
    "mage": "Mage",
    "soul-weaver": "Tisse-âme",
}
SLOT_LABELS = {
    GearSlot.WEAPON: "Arme",
    GearSlot.HELMET: "Casque",
    GearSlot.ARMOR: "Armure",
    GearSlot.NECKLACE: "Collier",
    GearSlot.RING: "Anneau",
    GearSlot.BOOTS: "Bottes",
}


def fmt(stat: StatType, value: float) -> str:
    if stat.is_percent:
        return f"{value:g}%"
    return f"{int(value):,}".replace(",", " ")


@dataclass
class GearView:
    slot: str
    set_name: str
    enhance: int
    main: str
    substats: list[tuple[str, str]]
    score: float
    empty: bool = False
    level: int | None = None
    ingame_score: int | None = None


@dataclass
class HeroView:
    name: str
    element: str | None
    color: str
    role: str | None
    stars: int | None
    level: int | None
    imprint: str | None
    artifact: str | None
    stats: list[tuple[str, str]]
    gear: list[GearView]
    sets: list[str]
    total_score: float
    tags: list[str] = field(default_factory=list)
    power: str | None = None
    gear_score_avg: int | None = None
    imprint_bonus: str | None = None


def build(hero: Hero) -> HeroView:
    sets_ref = load("sets")
    s = hero.stats
    stats = [
        ("Attaque", fmt(StatType.ATK, s.atk)),
        ("PV", fmt(StatType.HP, s.hp)),
        ("Défense", fmt(StatType.DEF, s.defense)),
        ("Vitesse", fmt(StatType.SPD, s.spd)),
        ("Chances crit.", fmt(StatType.CRIT_CHANCE, s.crit_chance)),
        ("Dégâts crit.", fmt(StatType.CRIT_DMG, s.crit_dmg)),
        ("Efficacité", fmt(StatType.EFFECTIVENESS, s.effectiveness)),
        ("Résistance", fmt(StatType.EFFECT_RES, s.effect_res)),
    ]
    if s.dual_attack:
        stats.append(("Attaque double", fmt(StatType.DUAL_ATTACK, s.dual_attack)))

    gear_views: list[GearView] = []
    for slot in GearSlot:
        g = hero.gear.get(slot)
        if g is None:
            gear_views.append(GearView(SLOT_LABELS[slot], "", 0, "—", [], 0, empty=True))
            continue
        gear_views.append(
            GearView(
                slot=SLOT_LABELS[slot],
                set_name=sets_ref[g.set.value]["fr"] if g.set else "?",
                enhance=g.enhance,
                main=f"{g.main.stat.label} {fmt(g.main.stat, g.main.value)}",
                substats=[(x.stat.label, fmt(x.stat, x.value)) for x in g.substats],
                score=gear_score(g),
                level=g.level,
                ingame_score=g.score,
            )
        )

    return HeroView(
        name=hero.name,
        element=ELEMENT_FR.get(hero.element or "", hero.element),
        color=ELEMENT_COLORS.get(hero.element, ELEMENT_COLORS[None]),
        role=ROLE_FR.get(hero.role or "", hero.role),
        stars=hero.stars,
        level=hero.level,
        imprint=hero.imprint,
        artifact=hero.artifact,
        stats=stats,
        gear=gear_views,
        sets=[sets_ref[x]["fr"] for x in hero.sets],
        total_score=round(sum(g.score for g in gear_views), 1),
        tags=hero.tags,
        power=f"{hero.power:,}".replace(",", " ") if hero.power else None,
        gear_score_avg=hero.gear_score_avg,
        imprint_bonus=hero.imprint_bonus,
    )
