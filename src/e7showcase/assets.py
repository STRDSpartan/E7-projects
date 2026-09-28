"""Images locales des héros et artefacts (portraits, illustrations) pour la vitrine.

Les visuels du jeu appartiennent à Smilegate : ils ne sont JAMAIS livrés avec le dépôt.
Chaque joueur les place dans son dossier de données, à la main (`e7showcase assets add`)
ou via une future synchronisation depuis un site communautaire :

    <dossier de données>/assets/heroes/<clé>.(png|webp|jpg)     pose / portrait
    <dossier de données>/assets/faces/<clé>.(png|webp|jpg)      icône ronde du visage
    <dossier de données>/assets/artifacts/<clé>.(png|webp|jpg)

La clé est le code (héros c1006, skin c2066_s01_1, artefact art0243) ou le nom
« slugifié » (FR ou EN) : « Ludwig Prélude de l'Aubade » -> ludwig-prelude-de-l-aubade.
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
from e7showcase.reference import artifact_info, hero_info, normalize

Kind = Literal["heroes", "faces", "artifacts"]
SUFFIXES = (".webp", ".png", ".jpg", ".jpeg")
# Taille maximale intégrée dans la vitrine (px) : suffisant en échelle 2, léger pour Discord
MAX_EMBED = {"heroes": (480, 640), "faces": (112, 112), "artifacts": (160, 160)}


CODE_RE = re.compile(r"(c\d{4}|art\d{4})(_\w+)?")


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
        names = [hero.skin, hero.code, info.get("code"), hero.name, info.get("fr"), info.get("en")]
        return _keys(names)

    @staticmethod
    def artifact_keys(name: str | None) -> list[str]:
        info = artifact_info(name) or {}
        return _keys([info.get("code"), name, info.get("fr"), info.get("en")])

    def hero_portrait(self, hero: Hero) -> Path | None:
        return self._find("heroes", self.hero_keys(hero))

    def hero_face(self, hero: Hero) -> Path | None:
        return self._find("faces", self.hero_keys(hero))

    def artifact_image(self, name: str | None) -> Path | None:
        return self._find("artifacts", self.artifact_keys(name)) if name else None

    def save_image(self, kind: Kind, key: str, data: bytes, max_size: tuple[int, int]) -> Path:
        """Enregistre une image téléchargée, réduite, en WebP."""
        folder = self._dir(kind)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{_keys([key])[0]}.webp"
        with Image.open(io.BytesIO(data)) as src:
            _fit(src, max_size).save(target, "WEBP", quality=88)
        return target

    def add(self, kind: Kind, name: str, source: Path) -> Path:
        """Importe une image (convertie en WebP) sous la clé dérivée du nom."""
        folder = self._dir(kind)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{_keys([name])[0]}.webp"
        with Image.open(source) as img:
            img.convert("RGBA").save(target, "WEBP", quality=90)
        return target


def _fit(img: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    img = img.convert("RGBA")
    bbox = img.getchannel("A").getbbox()  # rogne les marges transparentes des poses
    if bbox:
        img = img.crop(bbox)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img


def _keys(names: list[str | None]) -> list[str]:
    keys: list[str] = []
    for n in names:
        if n and (k := n if CODE_RE.fullmatch(n) else slugify(n)) not in keys:
            keys.append(k)
    return keys


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
