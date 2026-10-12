"""Armurerie : toutes les pièces d'un profil, portées par ses héros ou rangées dans l'inventaire.

Pièces portées : lues sur les captures « Infos de héros » (icône découpée sur la capture).
Pièces non équipées : captures d'infobulle d'objet (`Roster.inventory`). Les blasons des sets
viennent de la bibliothèque locale des sets appris ou téléchargés.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from e7showcase.app.profiles import ProfileStore
from e7showcase.models.gear import Gear
from e7showcase.reference import load


def _data_uri(data: bytes | None, mime: str) -> str | None:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}" if data else None


def _gear(gear: Gear) -> dict[str, Any]:
    return {
        "slot": gear.slot.value,
        "set": gear.set.value if gear.set else None,
        "rank": gear.rank.value if gear.rank else None,
        "level": gear.level,
        "enhance": gear.enhance,
        "main": {"stat": gear.main.stat.value, "value": gear.main.value},
        "substats": [{"stat": s.stat.value, "value": s.value} for s in gear.substats],
    }


def armory(store: ProfileStore, profile_id: str, set_library: Path) -> dict[str, Any]:
    roster = store.load(profile_id)
    equipped = [
        {
            "hero": hero.name,
            **_gear(gear),
            "icon": _data_uri(store.icon_bytes(profile_id, hero.name, slot.value), "image/webp"),
        }
        for hero in roster.heroes
        for slot, gear in hero.gear.items()
    ]
    inventory = [{"id": item.id, "hero": None, **_gear(item.gear)} for item in roster.inventory]
    sets: dict[str, dict[str, Any]] = {}
    for key, info in load("sets").items():
        if key.startswith("_"):
            continue
        shield = set_library / f"{key}.png"
        icon = _data_uri(shield.read_bytes(), "image/png") if shield.is_file() else None
        sets[key] = {"name": info.get("fr") or info.get("en") or key, "icon": icon}
    return {"equipped": equipped, "inventory": inventory, "sets": sets}
