"""Portraits de héros pour l'interface : visage, élément, étoiles et classe, par nom.

Ordre des images : visage local (assets téléchargés), portrait local, portrait découpé dans
une capture d'un profil de la guilde. Sans image, l'interface affiche les initiales sur le fond
de l'élément. Résultats en cache, vidé quand un profil change (`ProfileStore.generation`)
ou au bout de `TTL` secondes (images téléchargées entre-temps).
"""

from __future__ import annotations

import base64
import time
from typing import Any

from e7showcase.app.profiles import ProfileStore
from e7showcase.assets import AssetStore, data_uri
from e7showcase.models.hero import Hero
from e7showcase.reference import hero_info

MAX_NAMES = 200
TTL = 120.0


class Portraits:
    def __init__(self, assets: AssetStore, profiles: ProfileStore):
        self.assets, self.profiles = assets, profiles
        self._cache: dict[str, dict[str, Any]] = {}
        self._index: dict[str, tuple[str, Hero]] = {}
        self._key: tuple[int, int, tuple[str, ...]] | None = None

    def lookup(self, names: list[str], profile_ids: list[str] | None = None) -> dict[str, Any]:
        key = (self.profiles.generation, int(time.monotonic() // TTL), tuple(profile_ids or []))
        if key != self._key:  # un profil a changé : index des héros possédés reconstruit
            self._key, self._cache, self._index = key, {}, {}
            for pid in reversed(profile_ids or []):  # le premier profil listé l'emporte
                if self.profiles.exists(pid):
                    for h in self.profiles.peek(pid).heroes:
                        self._index[h.name.casefold()] = (pid, h)
        out: dict[str, Any] = {}
        for name in dict.fromkeys(n.strip()[:60] for n in names[:MAX_NAMES] if isinstance(n, str)):
            if name:
                if name not in self._cache:
                    self._cache[name] = self._one(name)
                out[name] = self._cache[name]
        return out

    def _one(self, name: str) -> dict[str, Any]:
        info = hero_info(name) or {}
        hero = Hero(name=info.get("fr") or info.get("en") or name, code=info.get("code"))
        owned = self._index.get(name.casefold())
        img = data_uri(self.assets.hero_face(hero), "faces") if hero.code or info else None
        if img is None and (path := self.assets.hero_portrait(hero)):
            img = data_uri(path, "heroes")
        if img is None and owned is not None:
            pid, h = owned
            if raw := self.profiles.portrait_bytes(pid, h.name):
                img = "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")
        return {
            "img": img,
            "element": (owned[1].element if owned else None) or info.get("element"),
            "role": (owned[1].role if owned else None) or info.get("role"),
            "stars": (owned[1].stars if owned else None) or info.get("stars"),
        }
