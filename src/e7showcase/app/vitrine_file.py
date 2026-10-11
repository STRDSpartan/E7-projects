"""Fichier de vitrine partageable (.e7v).

Archive ZIP lisible par n'importe quelle installation d'E7 Showcase :

    manifest.json   {"format": "e7showcase-vitrine", "version": 1, "player", "exported_at", ...}
    profile.json    roster (format d'échange Roster, voir models/roster.py)
    images/<clé>.webp         poses des héros
    images/<clé>.<pièce>.webp icônes des pièces portées et de l'artefact (facultatives :
                              les versions précédentes de l'app les ignorent)

À l'ouverture, le contenu est traité comme NON FIABLE : noms de fichiers en liste blanche,
tailles plafonnées, roster validé par Pydantic, images décodées puis ré-encodées.
"""

from __future__ import annotations

import contextlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from e7showcase import __version__
from e7showcase.app.profiles import (
    ICON_KINDS,
    ICON_MAX,
    ID_RE,
    ProfileStore,
    image_key,
    reencode_webp,
)
from e7showcase.models.roster import Roster

FORMAT = "e7showcase-vitrine"
VERSION = 1
SUFFIX = ".e7v"
MAX_FILE_MB = 200
MAX_ENTRY_MB = 20
MAX_ENTRIES = 2000


class VitrineFileError(ValueError):
    pass


def export_profile(store: ProfileStore, profile_id: str) -> bytes:
    roster = store.load(profile_id)
    manifest = {
        "format": FORMAT,
        "version": VERSION,
        "player": roster.player,
        "heroes": len(roster.heroes),
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "app_version": __version__,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("profile.json", roster.model_dump_json(indent=2, by_alias=True))
        for hero in roster.heroes:
            if data := store.portrait_bytes(profile_id, hero.name):
                zf.writestr(f"images/{image_key(hero.name)}.webp", data, zipfile.ZIP_STORED)
            for kind in ICON_KINDS:
                if data := store.icon_bytes(profile_id, hero.name, kind):
                    name = f"images/{image_key(hero.name)}.{kind}.webp"
                    zf.writestr(name, data, zipfile.ZIP_STORED)
    return buf.getvalue()


def suggested_filename(player: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in player).strip("_") or "vitrine"
    return f"vitrine-{safe}{SUFFIX}"


def _read(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size > MAX_ENTRY_MB * 1024 * 1024:
        raise VitrineFileError(f"élément trop volumineux : {info.filename}")
    with zf.open(info) as f:
        data = f.read(MAX_ENTRY_MB * 1024 * 1024 + 1)
    if len(data) > MAX_ENTRY_MB * 1024 * 1024:  # taille annoncée mensongère
        raise VitrineFileError(f"élément trop volumineux : {info.filename}")
    return data


def import_vitrine(store: ProfileStore, data: bytes) -> str:
    """Ajoute la vitrine reçue comme profil en lecture seule ; renvoie son identifiant."""
    if len(data) > MAX_FILE_MB * 1024 * 1024:
        raise VitrineFileError("fichier trop volumineux")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise VitrineFileError("ce n'est pas un fichier de vitrine E7 Showcase") from exc
    with zf:
        entries = {i.filename: i for i in zf.infolist() if not i.is_dir()}
        if len(entries) > MAX_ENTRIES or "manifest.json" not in entries:
            raise VitrineFileError("ce n'est pas un fichier de vitrine E7 Showcase")
        try:
            manifest = json.loads(_read(zf, entries["manifest.json"]))
            roster = Roster.model_validate_json(_read(zf, entries["profile.json"]))
        except (KeyError, ValueError) as exc:
            raise VitrineFileError("vitrine illisible ou endommagée") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            raise VitrineFileError("ce n'est pas un fichier de vitrine E7 Showcase")
        if int(manifest.get("version", 0)) > VERSION:
            raise VitrineFileError("vitrine créée par une version plus récente : mettez à jour")

        profile_id = store.create(roster.player, received=True)
        store.save(profile_id, roster)
        for hero in roster.heroes:
            name = f"images/{image_key(hero.name)}.webp"
            if name in entries and ID_RE.fullmatch(image_key(hero.name)):
                # image invalide : le héros reste affiché sans pose
                with contextlib.suppress(OSError, ValueError):
                    store.save_portrait(
                        profile_id, hero.name, reencode_webp(_read(zf, entries[name]))
                    )
            for kind in ICON_KINDS:
                name = f"images/{image_key(hero.name)}.{kind}.webp"
                if name in entries and ID_RE.fullmatch(image_key(hero.name)):
                    try:
                        icon = reencode_webp(_read(zf, entries[name]), ICON_MAX)
                        store.save_icon(profile_id, hero.name, kind, icon)
                    except (OSError, ValueError):
                        continue  # icône invalide : ignorée
    return profile_id


def import_vitrine_file(store: ProfileStore, path: Path) -> str:
    return import_vitrine(store, path.read_bytes())
