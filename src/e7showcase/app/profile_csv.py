"""Export tableur d'un profil en un seul fichier : profil, héros (vitrine) et armurerie.

Trois tableaux l'un sous l'autre (séparés par une ligne vide) : le résumé du profil, un héros
par ligne avec ses stats, puis toutes les pièces d'équipement, portées ou non équipées.
"""

from __future__ import annotations

from e7showcase.app.gvg import _csv
from e7showcase.models.gear import Gear, StatLine
from e7showcase.models.roster import Roster
from e7showcase.reference import load

SLOTS_FR = {
    "weapon": "Arme",
    "helmet": "Casque",
    "armor": "Armure",
    "necklace": "Collier",
    "ring": "Anneau",
    "boots": "Bottes",
}


def _stat(line: StatLine) -> str:
    value = f"{line.value:g}" + (" %" if line.stat.is_percent else "")
    return f"{line.stat.label.removesuffix(' %').removesuffix('%')} {value}"


def _gear_row(owner: str, gear: Gear, sets: dict[str, str]) -> list[str]:
    subs = [_stat(s) for s in gear.substats] + [""] * 4
    return [
        owner,
        SLOTS_FR.get(gear.slot.value, gear.slot.value),
        sets.get(gear.set.value, gear.set.value) if gear.set else "",
        gear.rank.value if gear.rank else "",
        str(gear.level or ""),
        str(gear.enhance),  # « +15 » serait pris pour une formule par le tableur
        _stat(gear.main),
        *subs[:4],
    ]


def profile_csv(roster: Roster) -> str:
    sets = {
        k: str(v.get("fr") or v.get("en") or k)
        for k, v in load("sets").items()
        if not k.startswith("_")
    }
    worn = sum(len(h.gear) for h in roster.heroes)
    rows: list[list[str]] = [
        ["Joueur", "Guilde", "Serveur", "Héros", "Pièces portées", "Pièces non équipées"]
        + ["Mise à jour"],
        [
            roster.player,
            roster.guild or "",
            roster.server or "",
            str(len(roster.heroes)),
            str(worn),
            str(len(roster.inventory)),
            roster.updated_at.strftime("%d/%m/%Y"),
        ],
        [],
        ["Héros", "Étoiles", "Niveau", "Éveil", "Élément", "Classe", "Puissance", "Artefact"]
        + ["Attaque", "PV", "Défense", "Vitesse", "Chances crit.", "Dégâts crit."]
        + ["Efficacité", "Résistance", "Double attaque"],
    ]
    for h in sorted(roster.heroes, key=lambda h: -(h.power or 0)):
        s = h.stats
        rows.append(
            [h.name, *(str(v) if v is not None else "" for v in (h.stars, h.level, h.awakening))]
            + [h.element or "", h.role or "", str(h.power or ""), h.artifact or ""]
            + [str(v) for v in (s.atk, s.hp, s.defense, s.spd)]
            + [f"{v:g}" for v in (s.crit_chance, s.crit_dmg, s.effectiveness)]
            + [f"{v:g}" for v in (s.effect_res, s.dual_attack)]
        )
    rows += [
        [],
        ["Porté par", "Emplacement", "Set", "Rang", "Niveau", "Amélioration", "Stat principale"]
        + ["Sous-stat 1", "Sous-stat 2", "Sous-stat 3", "Sous-stat 4"],
    ]
    for h in roster.heroes:
        rows += [_gear_row(h.name, g, sets) for g in h.gear.values()]
    rows += [_gear_row("Non équipée", item.gear, sets) for item in roster.inventory]
    return _csv(rows)
