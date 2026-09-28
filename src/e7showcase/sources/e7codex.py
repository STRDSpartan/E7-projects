"""Source communautaire e7codex.com : référentiel (noms, codes, skins) et illustrations.

E7 Codex est une archive fan-made ; tous les visuels appartiennent à Smilegate / Super
Creative. Le projet n'en redistribue aucun : `e7showcase assets sync` les télécharge
dans le dossier LOCAL du joueur, pour les seuls héros de son roster, en version réduite,
avec une pause entre requêtes (robots.txt : `Allow: /`).

Données utilisées :
  https://e7codex.com/data/units.json      héros, PNJ, skins (variant), chemins d'images
  https://e7codex.com/data/artifacts.json  artefacts
  https://e7codex.com/data/lang/fr.json    noms français (héros, artefacts)
Images : https://e7codex.com/<chemin relatif> (ex. assets/c1006/pose.png).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from e7showcase.assets import AssetStore, Kind
from e7showcase.models.hero import Hero

BASE_URL = "https://e7codex.com"
USER_AGENT = "e7showcase (vitrines de roster pour guildes ; outil communautaire)"
ELEMENTS = {"fire": "fire", "ice": "ice", "wind": "earth", "light": "light", "dark": "dark"}
ROLES = {
    "warrior": "warrior",
    "knight": "knight",
    "ranger": "ranger",
    "mage": "mage",
    "manauser": "soul-weaver",
    "assassin": "thief",
}


def fetch_json(client: Any, path: str) -> Any:
    response = client.get(f"{BASE_URL}/{path}", headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    return response.json()


def _face(unit: dict[str, Any]) -> str | None:
    """Icône ronde du visage (face_<code>_s.png), utilisée pour les avatars."""
    return next((a for a in unit.get("artworks", []) if a.endswith("_s.png")), None)


def build_heroes(units: list[dict[str, Any]], fr: dict[str, Any]) -> list[dict[str, Any]]:
    """Héros jouables (kind == "unit") ; les variantes de skin sont rattachées au héros de base."""
    names_fr: dict[str, str] = fr.get("names", {})
    heroes: dict[str, dict[str, Any]] = {}
    skins: list[dict[str, Any]] = []
    for u in units:
        if u.get("kind") != "unit" or not u.get("name"):
            continue
        if u.get("variant"):
            skins.append(u)
            continue
        base = u.get("base_id") or u["id"]
        heroes[base] = {
            "code": u["id"],
            "base": base,
            "en": u["name"],
            "fr": names_fr.get(u["id"]) or names_fr.get(base) or u["name"],
            "element": ELEMENTS.get(u.get("attribute", ""), u.get("attribute")),
            "role": ROLES.get(u.get("role", ""), u.get("role")),
            "stars": u.get("rarity"),
            "pose": u.get("pose"),
            "face": _face(u),
            "skins": [],
        }
    for s in skins:
        hero = heroes.get(s.get("base_id") or "")
        if hero is not None:
            hero["skins"].append(
                {
                    "code": s["id"],
                    "variant": s["variant"],
                    "fr": names_fr.get(s["id"]) or hero["fr"],
                    "pose": s.get("pose"),
                    "face": _face(s),
                }
            )
    return sorted(heroes.values(), key=lambda h: h["code"])


def build_artifacts(artifacts: list[dict[str, Any]], fr: dict[str, Any]) -> list[dict[str, Any]]:
    names_fr: dict[str, str] = fr.get("artifacts", {})
    out = []
    for a in artifacts:
        if not a.get("name"):
            continue
        out.append(
            {
                "code": a["id"],
                "en": a["name"],
                "fr": names_fr.get(a["id"]) or a["name"],
                "stars": a.get("rarity"),
                "role": ROLES.get(a.get("role") or "", a.get("role")),
                "art": a.get("art_full") or a.get("art_lobby"),
            }
        )
    return sorted(out, key=lambda a: a["code"])


# --- synchronisation des illustrations (dossier local du joueur uniquement) -----------------
MAX_SIZE = {"heroes": (900, 1130), "faces": (112, 112), "artifacts": (400, 630)}


@dataclass
class SyncReport:
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _jobs(heroes: list[Hero], skins: bool) -> list[tuple[Kind, str, str, str]]:
    """(dossier, code, chemin distant, libellé) pour chaque image à obtenir."""
    from e7showcase.reference import artifact_info, hero_info

    jobs: list[tuple[Kind, str, str, str]] = []
    for hero in heroes:
        info = hero_info(hero.name) or {}
        chosen = [sk for sk in info.get("skins", []) if skins or sk["code"] == hero.skin]
        for variant in [info, *chosen] if info else []:
            label = hero.name if variant is info else f"{hero.name} ({variant['variant']})"
            if variant.get("pose"):
                jobs.append(("heroes", variant["code"], variant["pose"], label))
            if variant.get("face"):
                jobs.append(("faces", variant["code"], variant["face"], f"{label} — visage"))
        art = artifact_info(hero.artifact)
        if art and art.get("art"):
            jobs.append(("artifacts", art["code"], art["art"], art["fr"]))
    return list(dict.fromkeys(jobs))


def sync_assets(
    store: AssetStore,
    heroes: list[Hero],
    client: Any,
    *,
    skins: bool = False,
    force: bool = False,
    delay: float = 0.5,
    on_item: Callable[[str, str], None] | None = None,
) -> SyncReport:
    """Télécharge poses (et skins) des héros donnés et l'illustration de leur artefact."""
    report = SyncReport()
    notify = on_item or (lambda _label, _status: None)
    for kind, code, path, label in _jobs(heroes, skins):
        target = store.root / kind / f"{code}.webp"
        if target.exists() and not force:
            report.skipped.append(label)
            notify(label, "déjà présent")
            continue
        try:
            response = client.get(
                f"{BASE_URL}/{path}", headers={"User-Agent": USER_AGENT}, timeout=120
            )
            response.raise_for_status()
            store.save_image(kind, code, response.content, MAX_SIZE[kind])
            report.downloaded.append(label)
            notify(label, "téléchargé")
        except Exception as exc:  # réseau, 404, image invalide : on continue
            report.missing.append(f"{label} ({exc.__class__.__name__})")
            notify(label, "introuvable")
        if delay:
            time.sleep(delay)
    for hero in heroes:
        if not hero_known(hero):
            report.missing.append(f"{hero.name} (absent du référentiel)")
    return report


def hero_known(hero: Hero) -> bool:
    from e7showcase.reference import hero_info

    return hero_info(hero.name) is not None


# --- modèle animé : export via la visionneuse en temps réel d'E7 Codex ----------------------
VIEWER_URL = BASE_URL + "/viewer?slug={code}"


def export_animation(code: str, target: Path, *, timeout_s: int = 300) -> Path:
    """Ouvre la visionneuse d'E7 Codex dans un navigateur sans interface et utilise son propre
    export « Transparent · WebP animé » (une boucle complète de l'animation d'attente).

    Le projet n'embarque pas le moteur d'animation Spine : il pilote la page publique du site,
    exactement comme un joueur cliquant sur « Export animation ».
    """
    import os

    from playwright.sync_api import sync_playwright

    target.parent.mkdir(parents=True, exist_ok=True)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=os.environ.get("E7_CHROMIUM_PATH") or None,
            proxy={"server": proxy} if proxy else None,
            # rendu WebGL logiciel : fonctionne aussi sans carte graphique
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        try:
            page = browser.new_page(
                viewport={"width": 760, "height": 1100},
                accept_downloads=True,
                user_agent=USER_AGENT,
            )
            page.goto(
                VIEWER_URL.format(code=code), wait_until="networkidle", timeout=timeout_s * 1000
            )
            page.wait_for_selector("#stage canvas", timeout=timeout_s * 1000)
            page.wait_for_timeout(1500)  # premières images rendues
            page.click("#zexport-toggle")
            with page.expect_download(timeout=timeout_s * 1000) as download:
                page.click("#exp-webp")
            download.value.save_as(str(target))
        finally:
            browser.close()
    return target
