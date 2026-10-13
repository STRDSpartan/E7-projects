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
import threading
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from e7showcase.assets import slugify
from e7showcase.models.gear import Gear
from e7showcase.models.hero import Hero
from e7showcase.models.roster import InventoryItem, Roster

ID_RE = re.compile(r"^[a-z0-9-]{1,60}$")
ITEM_ID_RE = re.compile(r"^[0-9a-f]{1,32}$")
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
    me: bool = False
    avatar: str | None = None  # adresse du cadre de profil (versionnée)
    guild: str | None = None
    rank: int | None = None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class ProfileStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        # rosters validés en mémoire, reconnus à la date et la taille du fichier (une
        # modification hors de l'application est donc relue) ; `generation` change à chaque
        # écriture pour invalider les caches qui en dépendent (portraits…)
        self._rosters: dict[str, tuple[tuple[int, int], Roster]] = {}
        self._metas: dict[str, dict[str, object]] = {}
        self._lock = threading.RLock()  # lecture-modification-écriture atomiques
        self.generation = 0

    def _touch(self, profile_id: str | None = None) -> None:
        with self._lock:
            self.generation += 1
            if profile_id is not None:
                self._metas.pop(profile_id, None)

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
        if (cached := self._metas.get(profile_id)) is not None:
            return cached
        meta = self.path(profile_id) / "meta.json"
        data = dict(json.loads(meta.read_text(encoding="utf-8"))) if meta.is_file() else {}
        self._metas[profile_id] = data
        return data

    def list(self) -> list[ProfileInfo]:
        out = []
        for folder in sorted(self.root.iterdir()):
            if folder.is_dir() and self.exists(folder.name):
                roster = self.peek(folder.name)
                out.append(
                    ProfileInfo(
                        id=folder.name,
                        player=roster.player,
                        heroes=len(roster.heroes),
                        updated_at=roster.updated_at.strftime("%d/%m/%Y %H:%M"),
                        received=bool(self._meta(folder.name).get("received")),
                        me=folder.name == self.me(),
                        avatar=self.avatar_url(folder.name),
                        guild=roster.guild,
                        rank=_int(self._meta(folder.name).get("rank")),
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
        self._touch(profile_id)
        return profile_id

    def peek(self, profile_id: str) -> Roster:
        """Roster en LECTURE SEULE (partagé, ne pas modifier) : relu seulement s'il a changé."""
        target = self.path(profile_id) / "profile.json"
        st = target.stat()
        key = (st.st_mtime_ns, st.st_size)
        cached = self._rosters.get(profile_id)
        if cached is not None and cached[0] == key:
            return cached[1]
        roster = Roster.model_validate_json(target.read_text(encoding="utf-8"))
        self._rosters[profile_id] = (key, roster)
        return roster

    def load(self, profile_id: str) -> Roster:
        """Copie modifiable du roster (à enregistrer avec `save`)."""
        return self.peek(profile_id).model_copy(deep=True)

    def save(self, profile_id: str, roster: Roster) -> None:
        target = self.path(profile_id) / "profile.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(roster.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        tmp.replace(target)
        self._rosters.pop(profile_id, None)
        self._touch()

    # --- « mon profil » et fiche de profil du jeu
    def me(self) -> str | None:
        try:
            data = json.loads((self.root / "me.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        pid = data.get("id") if isinstance(data, dict) else None
        return pid if isinstance(pid, str) and ID_RE.match(pid) and self.exists(pid) else None

    def set_me(self, profile_id: str) -> None:
        (self.root / "me.json").write_text(json.dumps({"id": profile_id}), encoding="utf-8")
        self._touch()

    def avatar_url(self, profile_id: str) -> str | None:
        target = self.path(profile_id) / "images" / "avatar.webp"
        try:
            return f"/media/{profile_id}/avatar.webp?v={target.stat().st_mtime_ns}"
        except OSError:
            return None

    def update_card(
        self,
        profile_id: str,
        *,
        player: str,
        server: str | None,
        guild: str | None,
        rank: int | None,
        avatar: Image.Image | None,
    ) -> None:
        """Met à jour le profil depuis la fiche du jeu (pseudo, serveur, guilde, rang, cadre)."""
        with self._lock:
            roster = self.load(profile_id)
            roster.player = player.strip()[:40] or roster.player
            roster.server = server or roster.server
            roster.guild = guild or roster.guild
            self.save(profile_id, roster)
            meta_path = self.path(profile_id) / "meta.json"
            meta = dict(self._meta(profile_id))
            if rank is not None:
                meta["rank"] = rank
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            self._metas.pop(profile_id, None)
            if avatar is not None:
                folder = self.path(profile_id) / "images"
                folder.mkdir(parents=True, exist_ok=True)
                avatar.save(folder / "avatar.webp", "WEBP", quality=90)
            self._touch(profile_id)

    def is_received(self, profile_id: str) -> bool:
        return bool(self._meta(profile_id).get("received"))

    def rename(self, profile_id: str, player: str) -> None:
        with self._lock:
            roster = self.load(profile_id)
            roster.player = player.strip()[:40] or roster.player
            self.save(profile_id, roster)

    def delete(self, profile_id: str) -> None:
        shutil.rmtree(self.path(profile_id))
        self._rosters.pop(profile_id, None)
        self._touch(profile_id)

    # --- héros et poses
    def add_hero(
        self,
        profile_id: str,
        hero: Hero,
        portrait: Image.Image | None,
        icons: dict[str, Image.Image] | None = None,
    ) -> None:
        with self._lock:
            roster = self.load(profile_id)
            roster.upsert(hero)
            self.save(profile_id, roster)
            if portrait is not None:
                self.save_portrait(profile_id, hero.name, portrait)
            for kind, icon in (icons or {}).items():
                self.save_icon(profile_id, hero.name, kind, icon)

    def remove_hero(self, profile_id: str, hero_name: str) -> None:
        with self._lock:
            roster = self.load(profile_id)
            roster.heroes = [h for h in roster.heroes if h.name.casefold() != hero_name.casefold()]
            self.save(profile_id, roster)
            self.portrait_path(profile_id, hero_name).unlink(missing_ok=True)
            for kind in ICON_KINDS:
                self.icon_path(profile_id, hero_name, kind).unlink(missing_ok=True)

        # --- armurerie : pièces non équipées

    def add_item(self, profile_id: str, gear: Gear, icon: Image.Image | None = None) -> str:
        with self._lock:
            roster = self.load(profile_id)
            item = InventoryItem(id=secrets.token_hex(6), gear=gear)
            roster.inventory.append(item)
            self.save(profile_id, roster)
            if icon is not None:
                self.save_item_icon(profile_id, item.id, icon)
            return item.id

    def item_icon_path(self, profile_id: str, item_id: str) -> Path:
        if not ITEM_ID_RE.fullmatch(item_id):
            raise KeyError(item_id)
        return self.path(profile_id) / "images" / f"item-{item_id}.webp"

    def save_item_icon(self, profile_id: str, item_id: str, image: Image.Image) -> None:
        img = image.convert("RGB")
        img.thumbnail(ICON_MAX, Image.Resampling.LANCZOS)
        target = self.item_icon_path(profile_id, item_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "WEBP", quality=85)
        self._touch()

    def item_icon_bytes(self, profile_id: str, item_id: str) -> bytes | None:
        try:
            path = self.item_icon_path(profile_id, item_id)
        except KeyError:
            return None
        return path.read_bytes() if path.is_file() else None

    def remove_item(self, profile_id: str, item_id: str) -> bool:
        with self._lock:
            roster = self.load(profile_id)
            kept = [i for i in roster.inventory if i.id != item_id]
            found = len(kept) != len(roster.inventory)
            roster.inventory = kept
            self.save(profile_id, roster)
            if found:
                self.item_icon_path(profile_id, item_id).unlink(missing_ok=True)
            return found

    def portrait_path(self, profile_id: str, hero_name: str) -> Path:
        return self.path(profile_id) / "images" / f"{image_key(hero_name)}.webp"

    def save_portrait(self, profile_id: str, hero_name: str, image: Image.Image) -> None:
        img = image.convert("RGB")
        img.thumbnail(PORTRAIT_MAX, Image.Resampling.LANCZOS)
        target = self.portrait_path(profile_id, hero_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(target, "WEBP", quality=82)
        self._touch()

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
        self._touch()

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
