"""Import du tableur global de la guilde (« Exporter toute la guilde (.csv) »).

Le fichier est découpé en tableaux (séparés par une ligne vide) reconnus par leur en-tête :
membres, héros, armurerie, défenses GvG et attaques des guerres (les contres et les attaques
restantes s'en déduisent et sont ignorés). Chaque membre est rapproché d'un profil par son nom
de joueur :
- profil membre de la guilde ou vitrine reçue du même nom → héros et armurerie remplacés, sauf
  pour les profils du joueur lui-même (jamais écrasés) ;
- sinon une vitrine reçue est créée.
Les guerres déjà présentes (même adversaire et même date) ne sont pas réimportées.
"""

from __future__ import annotations

import csv
import io
import secrets
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from e7showcase.app.guild import GuildStore
from e7showcase.app.gvg import GvgError, GvgStore
from e7showcase.app.profile_csv import SLOTS_FR
from e7showcase.app.profiles import ProfileStore
from e7showcase.models.gear import Gear, GearRank, GearSet, GearSlot, StatLine
from e7showcase.models.hero import Hero, HeroStats
from e7showcase.models.roster import InventoryItem
from e7showcase.models.stats import STAT_LABELS_FR
from e7showcase.reference import load

MAX_BYTES = 5 * 1024 * 1024
STATS_BY_LABEL = {label.casefold(): stat for stat, label in STAT_LABELS_FR.items()}
SLOTS_BY_LABEL = {v.casefold(): GearSlot(k) for k, v in SLOTS_FR.items()}
HERO_STATS = ["atk", "hp", "def", "spd", "crit_chance", "crit_dmg", "effectiveness"] + [
    "effect_res",
    "dual_attack",
]


class GuildImportError(ValueError):
    pass


@dataclass
class ImportReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)  # profils du joueur, non écrasés
    heroes: int = 0
    items: int = 0
    defenses: int = 0
    wars: int = 0
    attacks: int = 0
    errors: list[str] = field(default_factory=list)


def _cell(value: str) -> str:
    value = value.strip()
    if value[:1] == "'" and value[1:2] in ("=", "+", "-", "@"):
        return value[1:]  # cellule neutralisée à l'export
    return value


def _tables(text: str) -> dict[str, list[dict[str, str]]]:
    """Tableaux du fichier, indexés par la première cellule de l'en-tête (et la seconde)."""
    rows = [[_cell(c) for c in r] for r in csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";")]
    tables: dict[str, list[dict[str, str]]] = {}
    head: list[str] | None = None
    for row in rows:
        if not any(row):
            head = None
            continue
        if head is None:
            head = row
            key = " / ".join(head[:2])
            tables.setdefault(key, [])
            continue
        tables[" / ".join(head[:2])].append(dict(zip(head, row + [""] * len(head), strict=False)))
    return tables


def _int(value: str) -> int | None:
    try:
        return int(float(value.replace(",", "."))) if value else None
    except ValueError:
        return None


def _float(value: str) -> float:
    try:
        return float(value.replace(",", ".")) if value else 0.0
    except ValueError:
        return 0.0


def _stat(text: str) -> StatLine | None:
    """« Attaque 47 % » → Attaque % 47 ; « Vitesse 45 » → Vitesse 45."""
    name, _, value = text.strip().rpartition(" ")
    percent = value == "%"
    if percent:
        name, _, value = name.rpartition(" ")
    stat = STATS_BY_LABEL.get((name + " %").casefold()) if percent else None
    stat = stat or STATS_BY_LABEL.get(name.casefold())
    if stat is None or not value:
        return None
    return StatLine(stat=stat, value=_float(value))


def _gear(row: dict[str, str], sets: dict[str, GearSet]) -> Gear:
    slot = SLOTS_BY_LABEL.get(row.get("Emplacement", "").casefold())
    main = _stat(row.get("Stat principale", ""))
    if slot is None or main is None:
        raise ValueError("emplacement ou stat principale illisible")
    subs = [s for i in range(1, 5) if (s := _stat(row.get(f"Sous-stat {i}", "")))]
    rank = row.get("Rang", "")
    return Gear(
        slot=slot,
        set=sets.get(row.get("Set", "").casefold()),
        rank=GearRank(rank) if rank in GearRank._value2member_map_ else None,
        level=_int(row.get("Niveau", "")),
        enhance=_int(row.get("Amélioration", "")) or 0,
        main=main,
        substats=subs,
    )


def _hero(row: dict[str, str]) -> Hero:
    values = [row.get(h, "") for h in ("Attaque", "PV", "Défense", "Vitesse")]
    values += [
        row.get(h, "")
        for h in ("Chances crit.", "Dégâts crit.", "Efficacité", "Résistance", "Double attaque")
    ]
    stats: dict[str, Any] = {
        k: (_int(v) or 0) if i < 4 else _float(v)
        for i, (k, v) in enumerate(zip(HERO_STATS, values, strict=True))
    }
    return Hero(
        name=row["Héros"],
        stars=_int(row.get("Étoiles", "")),
        level=_int(row.get("Niveau", "")),
        awakening=_int(row.get("Éveil", "")),
        element=row.get("Élément") or None,
        role=row.get("Classe") or None,
        power=_int(row.get("Puissance", "")),
        artifact=row.get("Artefact") or None,
        stats=HeroStats.model_validate(stats),
        source="manual",
    )


def import_guild_csv(
    text: str, profiles: ProfileStore, guild: GuildStore, gvg: GvgStore
) -> ImportReport:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise GuildImportError("fichier trop volumineux")
    tables = _tables(text)
    members = tables.get("Membre / Origine")
    if members is None:
        raise GuildImportError(
            "ce fichier n'est pas un export « toute la guilde » (tableau des membres absent)"
        )
    report = ImportReport()
    sets = {
        str(v.get(lang)).casefold(): GearSet(k)
        for k, v in load("sets").items()
        if not k.startswith("_") and k in GearSet._value2member_map_
        for lang in ("fr", "en")
        if v.get(lang)
    }
    heroes: dict[str, list[Hero]] = {}
    for row in tables.get("Membre / Héros", []):
        try:
            heroes.setdefault(row["Membre"], []).append(_hero(row))
        except (ValidationError, KeyError) as exc:
            report.errors.append(f"héros {row.get('Héros', '?')} de {row.get('Membre')} : {exc}")
    gear: dict[str, list[tuple[str, Gear]]] = {}
    for row in tables.get("Membre / Porté par", []):
        try:
            gear.setdefault(row["Membre"], []).append((row.get("Porté par", ""), _gear(row, sets)))
        except (ValidationError, ValueError) as exc:
            msg = str(exc).splitlines()[0]
            report.errors.append(f"pièce {row.get('Emplacement', '?')} de {row['Membre']} : {msg}")

    known = {p.id: p for p in profiles.list()}
    in_guild = {m["id"] for m in guild.summary()["members"]}
    ids: dict[str, str] = {}
    for row in members:
        player = row.get("Membre", "").strip()
        if not player or player in ids:
            continue
        match = sorted(
            (p for p in known.values() if p.player.casefold() == player.casefold()),
            key=lambda p: (p.id not in in_guild, not p.received),
        )
        pid = match[0].id if match else None
        if pid and not profiles.is_received(pid):
            report.kept.append(player)
        else:
            if pid is None:
                pid = profiles.create(player, received=True)
                report.created.append(player)
            else:
                report.updated.append(player)
            roster = profiles.load(pid)
            roster.heroes = heroes.get(player, [])
            by_name = {h.name.casefold(): h for h in roster.heroes}
            roster.inventory = []
            for owner, g in gear.get(player, []):
                hero = by_name.get(owner.casefold())
                if hero is not None:
                    hero.gear[g.slot] = g
                else:
                    roster.inventory.append(InventoryItem(id=secrets.token_hex(6), gear=g))
            profiles.save(pid, roster)
            report.heroes += len(roster.heroes)
            report.items += sum(len(h.gear) for h in roster.heroes) + len(roster.inventory)
        guild.add(pid)
        ids[player] = pid

    defenses: dict[str, dict[str, Any]] = {}
    for row in tables.get("Tour / Membre", []):  # défenses : une ligne par équipe
        pid = ids.get(row.get("Membre", ""))
        if pid is None:
            continue
        d = defenses.setdefault(pid, {"tower": row.get("Tour", ""), "teams": [[], []]})
        idx = (_int(row.get("Équipe", "")) or 1) - 1
        if 0 <= idx < 2:
            d["teams"][idx] = [
                row.get(f"Héros {i}", "") for i in (1, 2, 3) if row.get(f"Héros {i}")
            ]
    for pid, d in defenses.items():
        if d["tower"] == "Tour non attribuée":
            d["tower"] = ""
        try:
            gvg.set_defense(pid, d)
            report.defenses += 1
        except GvgError as exc:
            report.errors.append(f"défense de {profiles.load(pid).player} : {exc}")

    existing = {(w["opponent"], w["date"]) for w in gvg.summary()["wars"]}
    wars: dict[tuple[str, str], str] = {}
    for row in tables.get("Guerre / Date", []):
        if "Résultat" not in row:
            continue  # tableau des attaques restantes (déduites)
        key = (row.get("Guerre", ""), row.get("Date", ""))
        if not key[0] or key in existing:
            continue
        if key not in wars:
            wars[key] = gvg.add_war({"opponent": key[0], "date": key[1]})
            report.wars += 1
        pid = ids.get(row.get("Membre", ""))
        if pid is None:
            continue
        body = {
            "member": pid,
            "team": [t.strip() for t in row.get("Équipe", "").split(",") if t.strip()],
            "enemy_team": [t.strip() for t in row.get("Défense ennemie", "").split(",")],
            "enemy_player": row.get("Joueur ennemi", ""),
            "tower": row.get("Tour", ""),
            "result": "win" if row.get("Résultat") == "victoire" else "loss",
            "note": row.get("Note", ""),
        }
        try:
            gvg.add_attack(wars[key], body)
            report.attacks += 1
        except GvgError as exc:
            report.errors.append(f"attaque de {row.get('Membre')} contre {key[0]} : {exc}")
    return report
