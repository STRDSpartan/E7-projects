"""Boucle de scan : capture -> extraction -> sauvegarde, héros par héros."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PIL import Image

from e7showcase.capture.screenshot import grab
from e7showcase.capture.window import WindowRect, find_game_window
from e7showcase.models.gear import GearSlot
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
        on_hero: Callable[[Hero], None] | None = None,
    ):
        self.scanner = scanner
        self.navigator = navigator
        self.window_title = window_title
        self.capture_dir = capture_dir
        self.on_hero = on_hero or (lambda _h: None)

    def _shot(self, rect: WindowRect, label: str) -> Image.Image:
        img = grab(rect)
        if self.capture_dir:
            self.capture_dir.mkdir(parents=True, exist_ok=True)
            img.save(self.capture_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{label}.png")
        return img

    def run(self, max_heroes: int | None = None) -> list[Hero]:
        rect = find_game_window(self.window_title)
        regions = self.scanner.regions
        heroes: list[Hero] = []
        while max_heroes is None or len(heroes) < max_heroes:
            n = len(heroes) + 1
            if not self.navigator.wait_for_capture(f"Héros #{n} : ouvrez la fiche détails"):
                break
            detail = self._shot(rect, f"h{n:03d}-detail")
            tooltips: dict[GearSlot, Image.Image] = {}
            for slot in GearSlot:
                self.navigator.open_slot(rect, regions["hero_gear_slots"][slot.value])
                if not self.navigator.wait_for_capture(f"  → infobulle {slot.value}"):
                    return self._finish(heroes)
                if getattr(self.navigator, "last_skipped", False):
                    continue
                tooltips[slot] = self._shot(rect, f"h{n:03d}-{slot.value}")
            hero = self.scanner.scan(detail, tooltips)
            heroes.append(hero)
            self.on_hero(hero)
            log.info("Scanné : %s (%d pièces)", hero.name, len(hero.gear))
            self.navigator.next_hero(rect, regions["hero_detail"]["next_hero"])
        return self._finish(heroes)

    def _finish(self, heroes: list[Hero]) -> list[Hero]:
        log.info("Scan terminé : %d héros", len(heroes))
        return heroes
