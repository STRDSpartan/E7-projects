"""Import de captures d'écran dans un profil.

Chaque capture est reconnue automatiquement (barre de titre / barre des tâches retirées) :
- liste des héros → apprend les blasons des sets portés ;
- catalogue des sets → apprend les 24 blasons ;
- « Infos de héros » → héros complet + pose recadrée (le modèle du personnage).
Les listes sont traitées avant les fiches pour que les sets soient connus à la lecture.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.app.profiles import ProfileStore
from e7showcase.config import regions
from e7showcase.models.hero import Hero
from e7showcase.sources.set_icons import fetch_set_icons
from e7showcase.sources.set_icons import missing as missing_icons
from e7showcase.vision.framing import frame_detail
from e7showcase.vision.layouts import candidate_layouts, normalize_scale
from e7showcase.vision.preprocess import strip_window_chrome
from e7showcase.vision.set_catalog import SetMatcher

log = logging.getLogger(__name__)

NATIVE_ASPECT = 0.01  # écart relatif de format sous lequel une capture est déjà bien cadrée


@dataclass
class ImportReport:
    heroes: list[str] = field(default_factory=list)
    learned_sets: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "heroes": self.heroes,
            "learned_sets": self.learned_sets,
            "ignored": self.ignored,
            "warnings": self.warnings,
        }


def crop_item_icons(image: Image.Image, profile: dict[str, Any]) -> dict[str, Image.Image]:
    """Icônes des pièces portées et blason de l'artefact, découpés dans la capture du joueur."""
    from e7showcase.vision.regions import crop

    d = profile["detail"]
    lay = d["gear_layout"]
    left, top = lay["level"][0], lay["enhance"][1]
    icons = {
        slot: crop(image, [ax + left, ay + top, -left - 0.002, lay["score"][1] - top])
        for slot, (ax, ay) in d["gear"].items()
    }
    if box := d.get("artifact_icon"):
        icons["artifact"] = crop(image, box)
    return icons


def crop_portrait(image: Image.Image, profile: dict[str, Any]) -> Image.Image | None:
    box = profile["detail"].get("portrait")
    if not box:
        return None
    w, h = image.size
    x, y, bw, bh = box
    return image.crop((int(x * w), int(y * h), int((x + bw) * w), int((y + bh) * h)))


ProgressFn = Callable[[int, int, str], None]  # (étape faite, étapes totales, message)


def _quality(hero: Hero) -> int:
    """Nombre d'informations lues : sert à départager deux profils de zones."""
    stats = sum(1 for v in hero.stats.model_dump().values() if v)
    return len(hero.gear) * 10 + stats + (5 if hero.power else 0)


class ScreenshotImporter:
    """Garde le moteur OCR et les blasons appris entre deux imports (chargement unique)."""

    def __init__(
        self,
        set_library: Path,
        lang: str = "fr",
        profile: str = "auto",
        fetch_icons: Callable[[Path], list[str]] | None = fetch_set_icons,
    ):
        self.set_library = set_library
        self.fetch_icons = fetch_icons
        self.lang = lang
        self.profile = profile
        self.sets = SetMatcher.load(set_library)
        self._ocr: Any = None

    def _add_reference_shields(self, added: list[str]) -> None:
        """Blasons de référence téléchargés : complètent ceux appris, sans les remplacer."""
        for key in added:
            if key not in self.sets.templates:
                with Image.open(self.set_library / f"{key}.png") as shield:
                    self.sets.add(key, shield)

    def _engine(self) -> Any:
        if self._ocr is None:
            from e7showcase.vision.ocr import get_engine

            self._ocr = get_engine()
        return self._ocr

    def _frame(self, image: Image.Image) -> Image.Image:
        """Recadre une fiche mal cadrée (barre de titre sombre, marges) grâce aux repères."""
        from e7showcase.config import region_profiles

        profiles = region_profiles().values()
        aspect = image.width / image.height
        if any(
            cfg.get("calibrated") and abs(aspect / float(cfg["aspect"]) - 1) < NATIVE_ASPECT
            for cfg in profiles
        ):
            return image  # format natif d'un profil calibré : rien à recadrer
        for cfg in profiles:
            landmarks = cfg.get("detail", {}).get("landmarks")
            if cfg.get("calibrated") and landmarks:
                framed = frame_detail(normalize_scale(image, cfg), self._engine(), landmarks)
                if framed is not None:
                    return framed
        return image

    def _scanners(self, image: Image.Image) -> list[Any]:
        """Un lecteur par profil de zones candidat, transposé au format exact de la capture."""
        from e7showcase.config import region_profiles
        from e7showcase.scanner.hero_scanner import HeroScanner

        if self.profile != "auto":
            layouts = [regions(self.profile)]
        else:
            layouts = candidate_layouts(region_profiles(), image.width / image.height)
        return [HeroScanner(self._engine(), z, self.lang, self.sets) for z in layouts]

    def run(
        self,
        store: ProfileStore,
        profile_id: str,
        files: list[tuple[str, bytes]],
        progress: ProgressFn | None = None,
    ) -> ImportReport:
        from e7showcase.scanner.batch import learn_catalog

        notify = progress or (lambda _d, _t, _m: None)
        report = ImportReport()
        details: list[tuple[str, list[tuple[Any, Image.Image]]]] = []
        total = len(files) * 2  # reconnaissance de l'écran, puis lecture des fiches
        step = 0
        for name, data in files:
            notify(step, total, f"Reconnaissance de {name}")
            try:
                with Image.open(io.BytesIO(data)) as src:
                    raw = strip_window_chrome(src.convert("RGB"))
            except OSError:
                report.ignored.append(name)
                step += 2
                continue
            raw = self._frame(raw)
            scanners = self._scanners(raw)
            images = [normalize_scale(raw, sc.regions) for sc in scanners]
            kind = "ignored"
            for i, (scanner, image) in enumerate(zip(scanners, images, strict=True)):
                if scanner.is_detail_screen(image):
                    order = list(range(i, len(scanners))) + list(range(i))
                    details.append((name, [(scanners[j], images[j]) for j in order]))
                    kind = "detail"
                    break
                if scanner.is_list_screen(image):
                    report.learned_sets += scanner.learn_list_sets(image)
                    kind = "list"
                    break
            if kind == "ignored" and (learned := learn_catalog(scanners[0], images[0], None)):
                report.learned_sets += learned
                kind = "catalog"
            if kind == "ignored":
                report.ignored.append(name)
            step += 1 if kind == "detail" else 2
        if report.learned_sets:
            self.sets.save(self.set_library)
        if details and self.fetch_icons is not None and missing_icons(self.set_library):
            notify(step, total, "Téléchargement des blasons de sets")
            self._add_reference_shields(self.fetch_icons(self.set_library))

        for name, attempts in details:
            notify(step, total, f"Lecture du héros ({name})")
            used, image = attempts[0]
            hero: Hero = used.read_detail(image)
            if len(hero.gear) < 6 or not hero.name:  # autre profil de zones : on garde le meilleur
                for alt, alt_image in attempts[1:]:
                    candidate = alt.read_detail(alt_image)
                    if candidate.name and _quality(candidate) > _quality(hero):
                        hero, used, image = candidate, alt, alt_image
            step += 1
            if not hero.name:
                report.ignored.append(name)
                continue
            store.add_hero(
                profile_id,
                hero,
                crop_portrait(image, used.regions),
                crop_item_icons(image, used.regions),
            )
            report.heroes.append(hero.name)
            notify(step, total, f"{hero.name} ajouté")
            missing = [s.value for s, g in hero.gear.items() if g.set is None]
            if len(hero.gear) < 6 or missing:
                report.warnings.append(
                    f"{hero.name} : {len(hero.gear)}/6 pièces"
                    + (f", sets inconnus ({', '.join(missing)})" if missing else "")
                )
        notify(total, total, "Terminé")
        return report
