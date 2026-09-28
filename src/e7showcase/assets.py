"""Images locales des héros et artefacts (portraits, illustrations) pour la vitrine.

Les visuels du jeu appartiennent à Smilegate : ils ne sont JAMAIS livrés avec le dépôt.
Chaque joueur les place dans son dossier de données, à la main (`e7showcase assets add`)
ou via une future synchronisation depuis un site communautaire :

    <dossier de données>/assets/heroes/<clé>.(png|webp|jpg)
    <dossier de données>/assets/artifacts/<clé>.(png|webp|jpg)

La clé est l'identifiant du héros (ex. c1001) ou son nom « slugifié » (FR ou EN) :
« Ludwig Prélude de l'Aubade » -> ludwig-prelude-de-l-aubade.
"""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image

from e7showcase.models.hero import Hero
from e7showcase.reference import hero_info, normalize

Kind = Literal["heroes", "artifacts"]
SUFFIXES = (".webp", ".png", ".jpg", ".jpeg")
# Taille maximale intégrée dans la vitrine (px) : suffisant en échelle 2, léger pour Discord
MAX_EMBED = {"heroes": (480, 640), "artifacts": (160, 160)}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(name)).strip("-")


@dataclass
class AssetStore:
    root: Path

    def _dir(self, kind: Kind) -> Path:
        return self.root / kind

    def _find(self, kind: Kind, keys: list[str]) -> Path | None:
        folder = self._dir(kind)
        if not folder.is_dir():
            return None
        for key in keys:
            for suffix in SUFFIXES:
                path = folder / f"{key}{suffix}"
                if path.is_file():
                    return path
        return None

    @staticmethod
    def hero_keys(hero: Hero) -> list[str]:
        info = hero_info(hero.name) or {}
        names = [hero.code, info.get("code"), hero.name, info.get("fr"), info.get("en")]
        keys: list[str] = []
        for n in names:
            if n and (k := n if re.fullmatch(r"c\d{4}", n) else slugify(n)) not in keys:
                keys.append(k)
        return keys

    def hero_portrait(self, hero: Hero) -> Path | None:
        return self._find("heroes", self.hero_keys(hero))

    def artifact_image(self, name: str | None) -> Path | None:
        return self._find("artifacts", [slugify(name)]) if name else None

    def add(self, kind: Kind, name: str, source: Path) -> Path:
        """Importe une image (convertie en WebP) sous la clé dérivée du nom."""
        folder = self._dir(kind)
        folder.mkdir(parents=True, exist_ok=True)
        key = name if re.fullmatch(r"c\d{4}", name) else slugify(name)
        target = folder / f"{key}.webp"
        with Image.open(source) as img:
            img.convert("RGBA").save(target, "WEBP", quality=90)
        return target


def data_uri(path: Path | None, kind: Kind) -> str | None:
    """Image réduite et encodée en data URI : la vitrine reste autonome (hors ligne)."""
    if path is None:
        return None
    with Image.open(path) as src:
        img = src.convert("RGBA")
    img.thumbnail(MAX_EMBED[kind], Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=85)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
