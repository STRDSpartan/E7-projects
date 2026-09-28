"""Scan hors-ligne d'un dossier de captures (PC, mobile, ou captures transférées).

1. Chaque capture est classée : fiche « Infos de héros », liste des héros, catalogue des
   sets (filtre d'inventaire), ou ignorée.
2. Les captures du catalogue enrichissent la bibliothèque locale des blasons de sets.
3. Chaque fiche produit un Hero complet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from e7showcase.models.hero import Hero
from e7showcase.scanner.hero_scanner import HeroScanner
from e7showcase.vision.set_catalog import read_catalog

log = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIN_CATALOG_SETS = 4


@dataclass
class BatchResult:
    heroes: list[Hero] = field(default_factory=list)
    ignored: list[Path] = field(default_factory=list)
    learned_sets: list[str] = field(default_factory=list)


def image_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def learn_catalog(scanner: HeroScanner, image: Image.Image, library: Path | None) -> list[str]:
    found = read_catalog(image, scanner.ocr, scanner.lang)
    if len(found) < MIN_CATALOG_SETS:
        return []
    for gear_set, shield in found.items():
        scanner.sets.add(gear_set.value, shield)
    if library is not None:
        scanner.sets.save(library)
    return [s.value for s in found]


def scan_directory(
    scanner: HeroScanner, directory: Path, library: Path | None = None
) -> BatchResult:
    result = BatchResult()
    details: list[tuple[Path, Image.Image]] = []
    for path in image_files(directory):
        image = Image.open(path).convert("RGB")
        if scanner.is_detail_screen(image):
            details.append((path, image))
        elif scanner.is_list_screen(image):
            continue  # utile en direct pour naviguer ; rien à extraire ici
        elif learned := learn_catalog(scanner, image, library):
            result.learned_sets.extend(learned)
            log.info("Catalogue des sets : %d blasons appris (%s)", len(learned), path.name)
        else:
            result.ignored.append(path)
            log.info("Capture ignorée (écran non reconnu) : %s", path.name)

    for path, image in details:
        hero = scanner.read_detail(image)
        result.heroes.append(hero)
        log.info("%s ← %s", hero.name, path.name)
    return result
