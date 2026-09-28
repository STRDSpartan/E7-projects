"""Extraction d'un Hero à partir de captures déjà prises (aucune interaction avec le jeu).

Séparer « capturer » de « comprendre » permet de tester tout le pipeline sur des
PNG de référence (tests/fixtures/captures) sans lancer le jeu.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from PIL import Image

from e7showcase.models.gear import Gear, GearSlot
from e7showcase.models.hero import Hero
from e7showcase.parsers.gear_parser import parse_gear
from e7showcase.parsers.hero_parser import match_hero_name, parse_hero_stats
from e7showcase.parsers.stat_parser import StatParseError
from e7showcase.reference import hero_info
from e7showcase.vision.ocr import OcrEngine
from e7showcase.vision.regions import crop

log = logging.getLogger(__name__)


class HeroScanner:
    def __init__(
        self, ocr: OcrEngine, regions: dict[str, dict[str, list[float]]], lang: str = "fr"
    ):
        self.ocr = ocr
        self.regions = regions
        self.lang = lang

    def _text(self, image: Image.Image, section: str, key: str) -> list[str]:
        return [line.text for line in self.ocr.read_lines(crop(image, self.regions[section][key]))]

    def read_detail(self, image: Image.Image) -> Hero:
        raw_name = " ".join(self._text(image, "hero_detail", "name"))
        name = match_hero_name(raw_name, self.lang) or raw_name.strip() or "Inconnu"
        stats = parse_hero_stats(self._text(image, "hero_detail", "stats_panel"), self.lang)
        info = hero_info(name) or {}
        level_txt = "".join(
            c for c in " ".join(self._text(image, "hero_detail", "level")) if c.isdigit()
        )
        return Hero(
            name=name,
            code=info.get("code"),
            element=info.get("element"),
            role=info.get("role"),
            level=int(level_txt) if level_txt and 1 <= int(level_txt) <= 60 else None,
            stats=stats,
            scanned_at=datetime.now(UTC),
            source="scan",
        )

    def read_gear(self, image: Image.Image, slot: GearSlot) -> Gear | None:
        section = "gear_tooltip"
        try:
            return parse_gear(
                slot,
                main_text=" ".join(self._text(image, section, "main_stat")),
                substat_lines=self._text(image, section, "substats"),
                set_text=" ".join(self._text(image, section, "set_name")),
                enhance_text=" ".join(self._text(image, section, "enhance")),
                level_text=" ".join(self._text(image, section, "level")),
                lang=self.lang,
            )
        except StatParseError as exc:
            log.warning("Pièce %s illisible : %s", slot, exc)
            return None

    def scan(self, detail: Image.Image, tooltips: dict[GearSlot, Image.Image]) -> Hero:
        hero = self.read_detail(detail)
        for slot, img in tooltips.items():
            if gear := self.read_gear(img, slot):
                hero.gear[slot] = gear
        return hero
