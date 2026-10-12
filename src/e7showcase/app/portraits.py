"""Portraits de héros pour l'interface : visage, élément, étoiles et classe, par nom.

Ordre des images : visage local (assets téléchargés), portrait local, portrait découpé dans
une capture d'un profil de la guilde. Sans image, l'interface affiche les initiales sur le fond
de l'élément. Résultat mis en cache (les fichiers changent rarement pendant une session).
"""

from __future__ import annotations

import base64
from typing import Any

from e7showcase.app.profiles import ProfileStore
from e7showcase.assets import AssetStore, data_uri
from e7showcase.models.hero import Hero
from e7showcase.reference import hero_info

MAX_NAMES = 200


class Portraits:
    def __init__(self, assets: AssetStore, profiles: ProfileStore):
        self.assets, self.profiles = assets, profiles
        self._cache: dict[str, dict[str, Any]] = {}

    def lookup(self, names: list[str], profile_ids: list[str] | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in dict.fromkeys(n.strip()[:60] for n in names[:MAX_NAMES] if isinstance(n, str)):
            if name:
                out[name] = self._cache.get(name) or self._one(name, profile_ids or [])
        return out

    def _one(self, name: str, profile_ids: list[str]) -> dict[str, Any]:
        info = hero_info(name) or {}
        hero = Hero(name=info.get("fr") or info.get("en") or name, code=info.get("code"))
        owned = self._owned(name, profile_ids)
        img = data_uri(self.assets.hero_face(hero), "faces") if hero.code or info else None
        if img is None and (path := self.assets.hero_portrait(hero)):
            img = data_uri(path, "heroes")
        if img is None and owned is not None:
            pid, h = owned
            if raw := self.profiles.portrait_bytes(pid, h.name):
                img = "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")
        entry = {
            "img": img,
            "element": (owned[1].element if owned else None) or info.get("element"),
            "role": (owned[1].role if owned else None) or info.get("role"),
            "stars": (owned[1].stars if owned else None) or info.get("stars"),
        }
        if img is not None:  # sans image, une capture ajoutée plus tard pourra en fournir une
            self._cache[name] = entry
        return entry

    def _owned(self, name: str, profile_ids: list[str]) -> tuple[str, Hero] | None:
        key = name.casefold()
        for pid in profile_ids:
            if not self.profiles.exists(pid):
                continue
            for h in self.profiles.load(pid).heroes:
                if h.name.casefold() == key:
                    return pid, h
        return None
