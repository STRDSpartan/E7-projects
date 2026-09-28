"""Scan hors-ligne d'un dossier de captures (PC, mobile, ou captures transférées).

1. Chaque capture est classée : liste des héros, fiche « Infos de héros », ou ignorée.
2. Les paires liste + fiche d'un même héros apprennent les icônes de sets.
3. Chaque fiche produit un Hero complet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from e7showcase.models.gear import GearSet
from e7showcase.models.hero import Hero
from e7showcase.scanner.hero_scanner import HeroScanner

log = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class BatchResult:
    heroes: list[Hero] = field(default_factory=list)
    ignored: list[Path] = field(default_factory=list)
    learned_sets: dict[str, int] = field(default_factory=dict)


def image_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def scan_directory(
    scanner: HeroScanner, directory: Path, library: Path | None = None
) -> BatchResult:
    result = BatchResult()
    details: list[tuple[Path, Image.Image]] = []
    active_sets: dict[str, list[GearSet]] = {}
    for path in image_files(directory):
        image = Image.open(path).convert("RGB")
        if scanner.is_detail_screen(image):
            details.append((path, image))
        elif scanner.is_list_screen(image):
            name, sets = scanner.read_list(image)
            if name and sets:
                active_sets[name] = sets
        else:
            result.ignored.append(path)
            log.info("Capture ignorée (écran non reconnu) : %s", path.name)

    # Apprentissage des sets : fiches dont on connaît la composition via la liste
    for _path, image in details:
        name = scanner.read_name(image)
        if name in active_sets:
            for gear_set in scanner.learn_sets(image, active_sets[name], library).values():
                result.learned_sets[gear_set.value] = result.learned_sets.get(gear_set.value, 0) + 1

    for path, image in details:
        hero = scanner.read_detail(image)
        result.heroes.append(hero)
        log.info("%s ← %s", hero.name, path.name)
    return result
