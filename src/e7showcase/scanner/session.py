"""Scan en direct du client PC : capture -> extraction -> sauvegarde, héros par héros.

Parcours dans le jeu : liste des héros (sets actifs lisibles) → bouton sous les bottes →
« Infos de héros » (une capture suffit pour tout le héros) → retour → héros suivant.
Le type d'écran est reconnu automatiquement : l'utilisateur peut capturer la liste
(facultatif, sert à apprendre les icônes de sets) puis la fiche.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.capture.screenshot import grab
from e7showcase.capture.window import WindowRect, find_game_window
from e7showcase.models.gear import GearSet
from e7showcase.models.hero import Hero
from e7showcase.scanner.hero_scanner import HeroScanner
from e7showcase.scanner.navigator import Navigator

log = logging.getLogger(__name__)


class ScanSession:
    def __init__(
        self,
        scanner: HeroScanner,
        navigator: Navigator,
        window_title: str,
        capture_dir: Path | None = None,
        set_library: Path | None = None,
        on_hero: Callable[[Hero], None] | None = None,
    ):
        self.scanner = scanner
        self.navigator = navigator
        self.window_title = window_title
        self.capture_dir = capture_dir
        self.set_library = set_library
        self.on_hero = on_hero or (lambda _h: None)
        self._pending_sets: tuple[str | None, list[GearSet]] = (None, [])

    def _shot(self, rect: WindowRect, label: str) -> Image.Image:
        img = grab(rect)
        if self.capture_dir:
            self.capture_dir.mkdir(parents=True, exist_ok=True)
            img.save(self.capture_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{label}.png")
        return img

    def handle(self, image: Image.Image) -> Hero | None:
        """Traite une capture quelconque ; retourne le héros si c'était une fiche détaillée."""
        if self.scanner.is_list_screen(image):
            self._pending_sets = self.scanner.read_list(image)
            return None
        if not self.scanner.is_detail_screen(image):
            log.warning("Écran non reconnu : ouvrez la liste des héros ou « Infos de héros ».")
            return None
        name, sets = self._pending_sets
        if sets and name == self.scanner.read_name(image):
            self.scanner.learn_sets(image, sets, self.set_library)
        self._pending_sets = (None, [])
        hero = self.scanner.read_detail(image)
        self.on_hero(hero)
        return hero

    def run(self, max_heroes: int | None = None) -> list[Hero]:
        rect = find_game_window(self.window_title)
        nav: dict[str, Any] = self.scanner.regions.get("navigation", {})
        heroes: list[Hero] = []
        while max_heroes is None or len(heroes) < max_heroes:
            prompt = (
                f"Héros #{len(heroes) + 1} : liste des héros (facultatif) puis « Infos de héros »"
            )
            if not self.navigator.wait_for_capture(prompt):
                break
            if getattr(self.navigator, "last_skipped", False):
                continue
            if nav and self.navigator.is_assisted:
                self.handle(self._shot(rect, "list"))
                self.navigator.click(rect, nav["detail_button"])
            if hero := self.handle(self._shot(rect, f"h{len(heroes) + 1:03d}")):
                heroes.append(hero)
                log.info("Scanné : %s (%d pièces)", hero.name, len(hero.gear))
                if nav and self.navigator.is_assisted:
                    self.navigator.click(rect, nav["back_button"])
                    self.navigator.click(rect, nav["next_hero"])
        log.info("Scan terminé : %d héros", len(heroes))
        return heroes
