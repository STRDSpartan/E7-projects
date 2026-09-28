"""Vitrine web autonome : UN fichier HTML à télécharger et ouvrir dans n'importe quel navigateur.

Tout est intégré dans le fichier (données, images en data URI, modèles animés optionnels) :
aucune connexion, aucun serveur, aucune ressource externe. L'interface (recherche, filtres,
tris, fiches) est en JavaScript sans dépendance.

Le même format sert à la vitrine d'un joueur et à la **vue guilde** (plusieurs membres
fusionnés) : les images sont mutualisées dans une table (un héros possédé par dix membres
n'embarque son portrait qu'une fois).

Les illustrations viennent du dossier local du joueur (voir assets.py) : le fichier produit
est destiné au partage entre membres de la guilde, jamais au dépôt du projet.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.assets import AssetStore
from e7showcase.calc.gear_score import gear_score
from e7showcase.models.hero import Hero
from e7showcase.models.roster import Roster
from e7showcase.reference import load
from e7showcase.render.viewmodel import ELEMENT_COLORS, ELEMENT_FR, ROLE_FR, build

PAYLOAD_VERSION = 2
ANIM_MAX_HEIGHT = 400  # modèle animé réduit pour garder un fichier partageable
ANIM_BUDGET = 1_500_000  # octets par modèle animé intégré
IMAGE_KINDS = ("face", "portrait", "artifact", "anim")


def anim_data_uri(
    path: Path, max_height: int = ANIM_MAX_HEIGHT, quality: int = 60, budget: int = ANIM_BUDGET
) -> str:
    """Modèle animé recadré, réduit et allégé (12 images/s, moins si trop lourd)."""
    from e7showcase.render.animated import read_frames

    frames = read_frames(path)
    w, h = frames[0][0].size
    ratio = min(1.0, max_height / h)
    size = (max(1, round(w * ratio)), max(1, round(h * ratio)))
    resized = [(f.resize(size, Image.Resampling.LANCZOS), d) for f, d in frames]
    data = b""
    for step in (2, 3, 4):  # 24 → 12 → 8 → 6 images/s
        kept = [(f, d * step) for f, d in resized[::step]]
        buf = io.BytesIO()
        kept[0][0].save(
            buf,
            "WEBP",
            save_all=True,
            append_images=[f for f, _ in kept[1:]],
            loop=0,
            duration=[d for _, d in kept],
            quality=quality,
            method=4,
        )
        data = buf.getvalue()
        if len(data) <= budget:
            break
    return "data:image/webp;base64," + base64.b64encode(data).decode("ascii")


@dataclass
class ImageTable:
    """Images dédupliquées par contenu : les héros référencent un identifiant court."""

    images: dict[str, str] = field(default_factory=dict)
    _by_hash: dict[str, str] = field(default_factory=dict)

    def add(self, uri: str | None) -> str | None:
        if not uri:
            return None
        digest = hashlib.sha1(uri.encode("ascii", "ignore")).hexdigest()
        if digest not in self._by_hash:
            image_id = f"i{len(self.images)}"
            self._by_hash[digest] = image_id
            self.images[image_id] = uri
        return self._by_hash[digest]


@dataclass
class Member:
    """Un membre de la guilde : son roster déjà mis en forme (héros + images)."""

    player: str
    updated: str
    heroes: list[dict[str, Any]]  # images en data URI (clés de IMAGE_KINDS)


def hero_payload(
    hero: Hero, assets: AssetStore | None, anims: bool, anim_cache: dict[Path, str] | None = None
) -> dict[str, Any]:
    """Héros mis en forme ; `images` contient des data URI (remplacés par des ids ensuite)."""
    view = build(hero, assets)
    data = asdict(view)
    for key in ("portrait", "face", "artifact_image"):
        data.pop(key, None)
    sets_ref = load("sets")
    anim_uri = None
    if anims and assets and (anim_path := assets.hero_anim(hero)):
        cache = anim_cache if anim_cache is not None else {}
        if anim_path not in cache:
            cache[anim_path] = anim_data_uri(anim_path)
        anim_uri = cache[anim_path]
    data.update(
        key=(AssetStore.hero_keys(hero) or [hero.name])[0],
        element_key=hero.element,
        role_key=hero.role,
        set_keys=hero.sets,
        set_labels={k: sets_ref[k]["fr"] or sets_ref[k]["en"] for k in set(hero.sets)},
        power_value=hero.power or 0,
        spd_value=hero.stats.spd,
        gs_value=round(sum(gear_score(g) for g in hero.gear.values()), 1),
        raw={
            "atk": hero.stats.atk,
            "hp": hero.stats.hp,
            "def": hero.stats.defense,
            "cc": hero.stats.crit_chance,
            "cd": hero.stats.crit_dmg,
            "eff": hero.stats.effectiveness,
            "res": hero.stats.effect_res,
        },
        images={
            "face": view.face,
            "portrait": view.portrait,
            "artifact": view.artifact_image,
            "anim": anim_uri,
        },
    )
    return data


def member_from_roster(
    roster: Roster,
    assets: AssetStore | None = None,
    anims: bool = True,
    anim_cache: dict[Path, str] | None = None,
) -> Member:
    return Member(
        player=roster.player,
        updated=roster.updated_at.strftime("%d/%m/%Y"),
        heroes=[hero_payload(h, assets, anims, anim_cache) for h in roster.heroes],
    )


def build_payload_from_members(
    members: list[Member], guild: str | None = None, title: str | None = None
) -> dict[str, Any]:
    table = ImageTable()
    out_members: list[dict[str, Any]] = []
    heroes: list[dict[str, Any]] = []
    for mi, member in enumerate(members):
        mid = f"m{mi}"
        count = 0
        for hero in member.heroes:
            h = dict(hero)
            h["images"] = {k: table.add((hero.get("images") or {}).get(k)) for k in IMAGE_KINDS}
            h["id"] = f"h{len(heroes)}"
            h["member"] = mid
            heroes.append(h)
            count += 1
        powers = [h.get("power_value", 0) for h in member.heroes if h.get("power_value")]
        out_members.append(
            {
                "id": mid,
                "player": member.player,
                "updated": member.updated,
                "count": count,
                "power_avg": round(sum(powers) / len(powers)) if powers else 0,
            }
        )
    return {
        "version": PAYLOAD_VERSION,
        "title": title
        or (guild if len(members) > 1 and guild else (members[0].player if members else "Vitrine")),
        "guild": guild,
        "generated": datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC"),
        "elements": {
            k: {"label": v, "color": ELEMENT_COLORS.get(k)} for k, v in ELEMENT_FR.items()
        },
        "roles": ROLE_FR,
        "members": out_members,
        "heroes": heroes,
        "images": table.images,
    }


def build_payload(
    roster: Roster, assets: AssetStore | None = None, anims: bool = True
) -> dict[str, Any]:
    """Vitrine d'un seul joueur."""
    return build_payload_from_members(
        [member_from_roster(roster, assets, anims)], guild=roster.guild
    )


# --- relecture d'une vitrine existante (pour la fusion en vue guilde) ------------------------
_DATA_RE = re.compile(r'<script type="application/json" id="data">(.*?)</script>', re.S)


def read_vitrine(path: Path) -> list[Member]:
    """Membres contenus dans une vitrine HTML produite par e7showcase (joueur ou guilde)."""
    match = _DATA_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path.name} : ce n'est pas une vitrine e7showcase")
    payload = json.loads(match.group(1))
    images: dict[str, str] = payload.get("images", {})

    def resolve(ref: str | None) -> str | None:
        if not ref:
            return None
        return ref if ref.startswith("data:") else images.get(ref)  # v1 : data URI en ligne

    members_meta = payload.get("members") or [
        {
            "id": "m0",
            "player": payload.get("player", "Joueur"),
            "updated": payload.get("updated", ""),
        }
    ]
    members: list[Member] = []
    for meta in members_meta:
        heroes = []
        for h in payload.get("heroes", []):
            if h.get("member", "m0") != meta["id"]:
                continue
            hero = {k: v for k, v in h.items() if k not in ("id", "member")}
            hero["images"] = {k: resolve((h.get("images") or {}).get(k)) for k in IMAGE_KINDS}
            heroes.append(hero)
        members.append(
            Member(player=meta["player"], updated=meta.get("updated", ""), heroes=heroes)
        )
    return members


def merge_members(members: list[Member]) -> list[Member]:
    """Un seul exemplaire par joueur (le plus récent si un membre apparaît deux fois)."""

    def when(m: Member) -> datetime:
        try:
            return datetime.strptime(m.updated, "%d/%m/%Y")
        except ValueError:
            return datetime.min

    latest: dict[str, Member] = {}
    for m in members:
        key = m.player.casefold().strip()
        if key not in latest or when(m) >= when(latest[key]):
            latest[key] = m
    return sorted(latest.values(), key=lambda m: m.player.casefold())


def safe_json(payload: dict[str, Any]) -> str:
    """JSON intégrable dans <script> : neutralise « </script> » et les commentaires HTML."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def write_page(payload: dict[str, Any], target: Path) -> Path:
    from e7showcase.render.showcase import _env

    html = (
        _env()
        .get_template("webapp.html.j2")
        .render(
            title=("Guilde " if len(payload["members"]) > 1 else "Vitrine de ")
            + str(payload["title"]),
            data_json=safe_json(payload),
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def render_webapp(
    roster: Roster, target: Path, assets: AssetStore | None = None, anims: bool = True
) -> Path:
    return write_page(build_payload(roster, assets, anims), target)


def render_guild(members: list[Member], target: Path, guild: str | None = None) -> Path:
    return write_page(build_payload_from_members(merge_members(members), guild=guild), target)
