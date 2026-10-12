"""Guilde locale : nom et membres (profils du joueur et vitrines reçues de ses coéquipiers).

    <dossier de données>/guild.json    {"name": ..., "members": [id de profil, ...]}

Les membres sont des profils de l'application : son propre profil, et les vitrines `.e7v`
envoyées par les autres membres. Rien n'est envoyé sur Internet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from e7showcase.app.profiles import ProfileStore

TOP_HEROES = 5


class GuildStore:
    def __init__(self, path: Path, profiles: ProfileStore):
        self.path, self.profiles = path, profiles

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        name = data.get("name") if isinstance(data.get("name"), str) else ""
        members = [m for m in data.get("members", []) if isinstance(m, str)]
        return {"name": name[:40], "members": members}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def update(self, name: str | None = None, members: list[str] | None = None) -> None:
        data = self._read()
        if name is not None:
            data["name"] = name.strip()[:40]
        if members is not None:
            data["members"] = list(dict.fromkeys(m for m in members if self.profiles.exists(m)))
        self._write(data)

    def add(self, profile_id: str) -> None:
        data = self._read()
        if profile_id not in data["members"] and self.profiles.exists(profile_id):
            data["members"].append(profile_id)
            self._write(data)

    def summary(self) -> dict[str, Any]:
        """Nom, membres (puissance, héros phares, sets portés) et profils pouvant les rejoindre."""
        data = self._read()
        members = []
        for pid in data["members"]:
            if not self.profiles.exists(pid):
                continue  # profil supprimé depuis
            roster = self.profiles.load(pid)
            heroes = sorted(roster.heroes, key=lambda h: h.power or 0, reverse=True)
            members.append(
                {
                    "id": pid,
                    "player": roster.player,
                    "received": self.profiles.is_received(pid),
                    "heroes": len(roster.heroes),
                    "power": sum(h.power or 0 for h in roster.heroes),
                    "items": sum(len(h.gear) for h in roster.heroes) + len(roster.inventory),
                    "top": [{"name": h.name, "power": h.power} for h in heroes[:TOP_HEROES]],
                    "updated_at": roster.updated_at.strftime("%d/%m/%Y"),
                }
            )
        members.sort(key=lambda m: m["power"], reverse=True)
        joined = {m["id"] for m in members}
        candidates = [
            {"id": p.id, "player": p.player, "received": p.received}
            for p in self.profiles.list()
            if p.id not in joined
        ]
        return {"name": data["name"], "members": members, "candidates": candidates}


def members_csv(summary: dict[str, Any]) -> str:
    """Membres de la guilde en tableur : un membre par ligne, du plus puissant au moins puissant."""
    from e7showcase.app.gvg import _csv  # même format que les exports GvG

    head = ["Membre", "Origine", "Héros", "Puissance", "Pièces", "Héros les plus puissants"]
    rows = [[*head, "Mise à jour"]]
    for m in summary["members"]:
        top = ", ".join(h["name"] + (f" ({h['power']})" if h["power"] else "") for h in m["top"])
        origin = "Vitrine reçue" if m["received"] else "Mon profil"
        rows.append(
            [m["player"], origin, str(m["heroes"]), str(m["power"]), str(m["items"]), top]
            + [m["updated_at"]]
        )
    return _csv(rows)
