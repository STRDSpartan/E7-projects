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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.app.profiles import ProfileStore
from e7showcase.config import regions
from e7showcase.models.hero import Hero
from e7showcase.vision.preprocess import strip_window_chrome
from e7showcase.vision.set_catalog import SetMatcher

log = logging.getLogger(__name__)


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


def crop_portrait(image: Image.Image, profile: dict[str, Any]) -> Image.Image | None:
    box = profile["detail"].get("portrait")
    if not box:
        return None
    w, h = image.size
    x, y, bw, bh = box
    return image.crop((int(x * w), int(y * h), int((x + bw) * w), int((y + bh) * h)))


class ScreenshotImporter:
    """Garde le moteur OCR et les blasons appris entre deux imports (chargement unique)."""

    def __init__(self, set_library: Path, lang: str = "fr", profile: str = "auto"):
        self.set_library = set_library
        self.lang = lang
        self.profile = profile
        self.sets = SetMatcher.load(set_library)
        self._ocr: Any = None

    def _engine(self) -> Any:
        if self._ocr is None:
            from e7showcase.vision.ocr import get_engine

            self._ocr = get_engine()
        return self._ocr

    def _scanner(self, image: Image.Image) -> Any:
        from e7showcase.scanner.hero_scanner import HeroScanner

        zones = regions(self.profile, image.width / image.height)
        return HeroScanner(self._engine(), zones, self.lang, self.sets)

    def run(
        self, store: ProfileStore, profile_id: str, files: list[tuple[str, bytes]]
    ) -> ImportReport:
        from e7showcase.scanner.batch import learn_catalog

        report = ImportReport()
        details: list[tuple[str, Image.Image, Any]] = []
        for name, data in files:
            try:
                with Image.open(io.BytesIO(data)) as src:
                    image = strip_window_chrome(src.convert("RGB"))
            except OSError:
                report.ignored.append(name)
                continue
            scanner = self._scanner(image)
            if scanner.is_detail_screen(image):
                details.append((name, image, scanner))
            elif scanner.is_list_screen(image):
                report.learned_sets += scanner.learn_list_sets(image)
            elif learned := learn_catalog(scanner, image, None):
                report.learned_sets += learned
            else:
                report.ignored.append(name)
        if report.learned_sets:
            self.sets.save(self.set_library)

        for name, image, scanner in details:
            hero: Hero = scanner.read_detail(image)
            if not hero.name:
                report.ignored.append(name)
                continue
            store.add_hero(profile_id, hero, crop_portrait(image, scanner.regions))
            report.heroes.append(hero.name)
            missing = [s.value for s, g in hero.gear.items() if g.set is None]
            if len(hero.gear) < 6 or missing:
                report.warnings.append(
                    f"{hero.name} : {len(hero.gear)}/6 pièces"
                    + (f", sets inconnus ({', '.join(missing)})" if missing else "")
                )
        return report
