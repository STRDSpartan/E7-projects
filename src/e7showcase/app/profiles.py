"""Profils de joueurs stockés localement.

    <dossier de données>/profiles/<id>/profile.json     roster (format d'échange Roster)
    <dossier de données>/profiles/<id>/images/<clé>.webp  pose du héros, recadrée sur la
                                                          capture « Infos de héros » du joueur

Un profil reçu par fichier (.e7v) est marqué `received` : on le consulte, on ne le modifie pas.
"""

from __future__ import annotations

import io
import json
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from e7showcase.assets import slugify
from e7showcase.models.hero import Hero
from e7showcase.models.roster import Roster

ID_RE = re.compile(r"^[a-z0-9-]{1,60}$")
PORTRAIT_MAX = (640, 900)
ICON_MAX = (160, 160)
# Icônes découpées dans la capture : les 6 pièces portées et le blason de l'artefact
ICON_KINDS = ("weapon", "helmet", "armor", "necklace", "ring", "boots", "artifact")


def image_key(hero_name: str) -> str:
    return slugify(hero_name) or "heros"


@dataclass
class ProfileInfo:
    id: str
    player: str
    heroes: int
    updated_at: str
    received: bool


class ProfileStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path(self, profile_id: str) -> Path:
        if not ID_RE.fullmatch(profile_id):
            raise KeyError(profile_id)
        return self.root / profile_id

    def exists(self, profile_id: str) -> bool:
        try:
            return (self.path(profile_id) / "profile.json").is_file()
        except KeyError:
            return False

    def _meta(self, profile_id: str) -> dict[str, object]:
        meta = self.path(profile_id) / "meta.json"
        return dict(json.loads(meta.read_text(encoding="utf-8"))) if meta.is_file() else {}

    def list(self) -> list[ProfileInfo]:
        out = []
        for folder in sorted(self.root.iterdir()):
            if folder.is_dir() and self.exists(folder.name):
                roster = self.load(folder.name)
                out.append(
                    ProfileInfo(
                        id=folder.name,
                        player=roster.player,
                        heroes=len(roster.heroes),
                        updated_at=roster.updated_at.strftime("%d/%m/%Y %H:%M"),
                        received=bool(self._meta(folder.name).get("received")),
                    )
                )
        return sorted(out, key=lambda p: p.player.casefold())

    def create(self, player: str, *, received: bool = False) -> str:
        player = player.strip()[:40] or "Joueur"
        profile_id = f"{(slugify(player) or 'joueur')[:40]}-{secrets.token_hex(3)}"
        folder = self.path(profile_id)
        (folder / "images").mkdir(parents=True)
        self.save(profile_id, Roster(player=player))
        (folder / "meta.json").write_text(json.dumps({"received": received}), encoding="utf-8")
        return profile_id

    def load(self, profile_id: str) -> Roster:
        text = (self.path(profile_id) / "profile.json").read_text(encoding="utf-8")
        return Roster.model_validate_json(text)

    def save(self, profile_id: str, roster: Roster) -> None:
        target = self.path(profile_id) / "profile.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(roster.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        tmp.replace(target)

    def is_received(self, profile_id: str) -> bool:
        return bool(self._meta(profile_id).get("received"))

    def rename(self, profile_id: str, player: str) -> None:
        roster = self.load(profile_id)
        roster.player = player.strip()[:40] or roster.player
        self.save(profile_id, roster)

    def delete(self, profile_id: str) -> None:
        shutil.rmtree(self.path(profile_id))

    # --- héros et poses
    def add_hero(
        self,
        profile_id: str,
        hero: Hero,
        portrait: Image.Image | None,
        icons: dict[str, Image.Image] | None = None,
    ) -> None:
        roster = self.load(profile_id)
        roster.upsert(hero)
        self.save(profile_id, roster)
        if portrait is not None:
            self.save_portrait(profile_id, hero.name, portrait)
        for kind, icon in (icons or {}).items():
            self.save_icon(profile_id, hero.name, kind, icon)

    def remove_hero(self, profile_id: str, hero_name: str) -> None:
        roster = self.load(profile_id)
        roster.heroes = [h for h in roster.heroes if h.name.casefold() != hero_name.casefold()]
        self.save(profile_id, roster)
        self.portrait_path(profile_id, hero_name).unlink(missing_ok=True)
        for kind in ICON_KINDS:
            self.icon_path(profile_id, hero_name, kind).unlink(missing_ok=True)

    def portrait_path(self, profile_id: str, hero_name: str) -> Path:
        return self.path(profile_id) / "images" / f"{image_key(hero_name)}.webp"

    def save_portrait(self, profile_id: str, hero_name: str, image: Image.Image) -> None:
        img = image.convert("RGB")
        img.thumbnail(PORTRAIT_MAX, Image.Resampling.LANCZOS)
        target = self.portrait_path(profile_id, hero_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "WEBP", quality=82)

    def portrait_bytes(self, profile_id: str, hero_name: str) -> bytes | None:
        path = self.portrait_path(profile_id, hero_name)
        return path.read_bytes() if path.is_file() else None

    def icon_path(self, profile_id: str, hero_name: str, kind: str) -> Path:
        if kind not in ICON_KINDS:
            raise KeyError(kind)
        return self.path(profile_id) / "images" / f"{image_key(hero_name)}.{kind}.webp"

    def save_icon(self, profile_id: str, hero_name: str, kind: str, image: Image.Image) -> None:
        img = image.convert("RGB")
        img.thumbnail(ICON_MAX, Image.Resampling.LANCZOS)
        target = self.icon_path(profile_id, hero_name, kind)
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "WEBP", quality=85)

    def icon_bytes(self, profile_id: str, hero_name: str, kind: str) -> bytes | None:
        path = self.icon_path(profile_id, hero_name, kind)
        return path.read_bytes() if path.is_file() else None


def reencode_webp(data: bytes, max_size: tuple[int, int] = PORTRAIT_MAX) -> Image.Image:
    """Décode une image reçue (fichier .e7v) et la ré-encode : seul du pixel ressort."""
    with Image.open(io.BytesIO(data)) as src:
        if src.width * src.height > 40_000_000:
            raise ValueError("image trop grande")
        img = src.convert("RGB")
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img
