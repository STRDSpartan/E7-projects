"""Vitrine web autonome : UN fichier HTML à télécharger et ouvrir dans n'importe quel navigateur.

Tout est intégré dans le fichier (données du roster, images en data URI, modèles animés
optionnels) : aucune connexion, aucun serveur, aucune ressource externe. L'interface
(recherche, filtres, tris, fiche détaillée) est en JavaScript sans dépendance.

Les illustrations viennent du dossier local du joueur (voir assets.py) : le fichier produit
est destiné au partage entre membres de la guilde, jamais au dépôt du projet.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import asdict
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

ANIM_MAX_HEIGHT = 400  # modèle animé réduit pour garder un fichier partageable
ANIM_BUDGET = 1_500_000  # octets par modèle animé intégré


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


def hero_payload(hero: Hero, index: int, assets: AssetStore | None, anims: bool) -> dict[str, Any]:
    view = build(hero, assets)
    data = asdict(view)
    data.pop("portrait", None)  # remplacé par images.portrait (clé unique)
    data.pop("face", None)
    data.pop("artifact_image", None)
    sets_ref = load("sets")
    data.update(
        id=f"h{index}",
        key=(AssetStore.hero_keys(hero) or [f"h{index}"])[0],
        element_key=hero.element,
        role_key=hero.role,
        set_keys=hero.sets,
        set_labels={k: sets_ref[k]["fr"] or sets_ref[k]["en"] for k in set(hero.sets)},
        power_value=hero.power or 0,
        spd_value=hero.stats.spd,
        gs_value=round(sum(gear_score(g) for g in hero.gear.values()), 1),
        images={
            "face": view.face,
            "portrait": view.portrait,
            "artifact": view.artifact_image,
            "anim": anim_data_uri(p)
            if anims and assets and (p := assets.hero_anim(hero))
            else None,
        },
    )
    return data


def build_payload(
    roster: Roster, assets: AssetStore | None = None, anims: bool = True
) -> dict[str, Any]:
    heroes = [hero_payload(h, i, assets, anims) for i, h in enumerate(roster.heroes)]
    return {
        "player": roster.player,
        "guild": roster.guild,
        "updated": roster.updated_at.strftime("%d/%m/%Y"),
        "generated": datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC"),
        "elements": {
            k: {"label": v, "color": ELEMENT_COLORS.get(k)} for k, v in ELEMENT_FR.items()
        },
        "roles": ROLE_FR,
        "heroes": heroes,
    }


def safe_json(payload: dict[str, Any]) -> str:
    """JSON intégrable dans <script> : neutralise « </script> » et les commentaires HTML."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_webapp(
    roster: Roster, target: Path, assets: AssetStore | None = None, anims: bool = True
) -> Path:
    from e7showcase.render.showcase import _env

    html = (
        _env()
        .get_template("webapp.html.j2")
        .render(
            title=f"Vitrine de {roster.player}",
            data_json=safe_json(build_payload(roster, assets, anims)),
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target
