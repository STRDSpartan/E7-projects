"""Lecture de l'écran « Infos de héros » : une capture = un héros complet.

Cet écran affiche les stats finales, les 6 pièces (stat principale + 4 secondaires,
chacune précédée d'une icône), le score de chaque pièce, l'artefact et l'empreinte.

Les icônes de stats sont apprises sur la capture elle-même : le panneau de stats de
gauche montre les mêmes icônes accompagnées d'un libellé connu (ordre fixe).

Aucune interaction avec le jeu ici : capturer ≠ comprendre.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from PIL import Image

from e7showcase.models.gear import FIXED_MAIN_STAT, Gear, GearSet, GearSlot, StatLine
from e7showcase.models.hero import Hero, HeroStats
from e7showcase.models.stats import StatType
from e7showcase.parsers.common import clean, parse_classes, parse_int, parse_level, parse_number
from e7showcase.parsers.hero_parser import match_hero_name
from e7showcase.reference import hero_info, normalize
from e7showcase.vision.icons import IconClassifier
from e7showcase.vision.ocr import OcrEngine
from e7showcase.vision.regions import crop
from e7showcase.vision.set_catalog import SetMatcher

log = logging.getLogger(__name__)

# Ordre des lignes du panneau de stats de la fiche
PANEL_ORDER = [
    "atk",
    "def",
    "hp",
    "spd",
    "crit_chance",
    "crit_dmg",
    "effectiveness",
    "effect_res",
    "dual_attack",
]
_PANEL_FIELD = {"def": "defense"}
_PCT_OF = {"atk": StatType.ATK_PCT, "def": StatType.DEF_PCT, "hp": StatType.HP_PCT}
_ALWAYS_PCT = {"crit_chance", "crit_dmg", "effectiveness", "effect_res"}
# Stats principales possibles par emplacement (clés d'icône)
_ALLOWED_MAIN: dict[GearSlot, set[str]] = {
    GearSlot.NECKLACE: {"atk", "def", "hp", "crit_chance", "crit_dmg"},
    GearSlot.RING: {"atk", "def", "hp", "effectiveness", "effect_res"},
    GearSlot.BOOTS: {"atk", "def", "hp", "spd"},
}


@dataclass
class ScanIssue:
    field: str
    message: str


def _stat(icon: str, pct: bool) -> StatType:
    if icon in _PCT_OF and pct:
        return _PCT_OF[icon]
    return StatType(icon)


class HeroScanner:
    def __init__(
        self,
        ocr: OcrEngine,
        regions: dict[str, Any],
        lang: str = "fr",
        sets: SetMatcher | None = None,
    ):
        self.ocr = ocr
        self.regions = regions
        self.lang = lang
        self.sets = sets or SetMatcher()
        self.issues: list[ScanIssue] = []

    # --- utilitaires
    def _set_area(self, image: Image.Image, box: list[float], margin: float = 0.3) -> Image.Image:
        """Zone de recherche du blason : l'icône + une marge (la corrélation glisse dedans)."""
        x, y, w, h = box
        return self._box(
            image, [x - w * margin, y - h * margin, w * (1 + 2 * margin), h * (1 + 2 * margin)]
        )

    def _box(self, image: Image.Image, box: list[float]) -> Image.Image:
        return crop(image, box)

    def _text(self, image: Image.Image, box: list[float]) -> str:
        return clean(self.ocr.read_text(self._box(image, box)))

    def _rows(self, box: list[float], n: int) -> list[list[float]]:
        x, y, w, h = box
        return [[x, y + i * h / n, w, h / n] for i in range(n)]

    def is_detail_screen(self, image: Image.Image) -> bool:
        """Titre « Infos de héros » / « Hero Info », tolérant à une lettre perdue."""
        title = normalize(self._text(image, self.regions["detail"]["title"]))
        return ("infos" in title and "ero" in title) or "hero info" in title

    # --- lecture
    def read_panel(self, image: Image.Image) -> tuple[HeroStats, IconClassifier]:
        d = self.regions["detail"]
        n = int(d.get("stats_rows", 9))
        stats = HeroStats()
        icons = IconClassifier()
        for key, vbox, ibox in zip(
            PANEL_ORDER,
            self._rows(d["stats_values"], n),
            self._rows(d["stats_icons"], n),
            strict=False,
        ):
            if key != "dual_attack":  # jamais présente sur l'équipement
                icons.add(key, self._box(image, ibox))
            value = parse_number(self._text(image, vbox))
            if value is None:
                self.issues.append(ScanIssue(f"stats.{key}", "valeur illisible"))
                continue
            v: float = value[0]
            setattr(
                stats,
                _PANEL_FIELD.get(key, key),
                v if value[1] or key in _ALWAYS_PCT or key == "dual_attack" else int(v),
            )
        return stats, icons

    def read_gear(self, image: Image.Image, slot: GearSlot, icons: IconClassifier) -> Gear | None:
        d = self.regions["detail"]
        ax, ay = d["gear"][slot.value]
        lay = d["gear_layout"]
        lines: list[StatLine] = []
        for i, (dy, h) in enumerate(zip(lay["line_dy"], lay["line_h"], strict=True)):
            raw = self._text(image, [ax + lay["values_dx"], ay + dy, lay["values_w"], h])
            number = parse_number(raw)
            icon_img = self._box(image, [ax, ay + dy, lay["icon_w"], h])
            candidates = icons.scores(icon_img)
            if i == 0:  # contraintes de la stat principale
                if slot in FIXED_MAIN_STAT:
                    candidates = {FIXED_MAIN_STAT[slot].value: 1.0}
                else:
                    candidates = {k: v for k, v in candidates.items() if k in _ALLOWED_MAIN[slot]}
            if number is None or not candidates:
                if i == 0:
                    self.issues.append(
                        ScanIssue(f"gear.{slot}", f"stat principale illisible ({raw!r})")
                    )
                    return None
                continue
            value, pct = number
            icon = max(candidates, key=lambda k: candidates[k])
            if icon in _ALWAYS_PCT:
                pct = True
            lines.append(StatLine(stat=_stat(icon, pct), value=value))

        def rel(key: str) -> list[float]:
            dx, dy, w, h = lay[key]
            return [ax + dx, ay + dy, w, h]

        level = parse_int(self._text(image, rel("level")), 50, 100)
        enhance = parse_int(self._text(image, rel("enhance")), 0, 15) or 0
        score = parse_int(self._text(image, rel("score")), 0, 200)
        set_label, _ = self.sets.predict(self._set_area(image, rel("set_icon")))
        return Gear(
            slot=slot,
            set=GearSet(set_label)
            if set_label and set_label in GearSet._value2member_map_
            else None,
            level=level,
            enhance=enhance,
            score=score,
            main=lines[0],
            substats=lines[1:5],
        )

    def read_name(self, image: Image.Image) -> str:
        raw_name = self._text(image, self.regions["detail"]["name"])
        return match_hero_name(raw_name, self.lang) or raw_name or "Inconnu"

    def _imprint(self, image: Image.Image) -> str | None:
        """Bonus d'empreinte (« Vitesse + 12 ») ; None si l'empreinte est verrouillée."""
        text = " ".join(
            line.text
            for line in self.ocr.read_lines(self._box(image, self.regions["detail"]["imprint"]))
        )
        return (
            None
            if not text or "verrouill" in normalize(text) or "locked" in normalize(text)
            else text
        )

    def _artifact(self, image: Image.Image) -> str | None:
        """Nom de l'artefact corrigé par le référentiel (« Orbedel'aube » → « Orbe de l'aube »)."""
        from e7showcase.reference import artifact_info

        lines = [
            line.text
            for line in self.ocr.read_lines(self._box(image, self.regions["detail"]["artifact"]))
        ]
        candidates = [
            t for t in lines if sum(c.isalpha() for c in t) >= 4 and "max" not in t.lower()
        ]
        for text in candidates:
            if info := artifact_info(text):
                return str(info.get(self.lang) or info["fr"])
        return candidates[0] if candidates else None

    def read_detail(self, image: Image.Image) -> Hero:
        self.issues = []
        d = self.regions["detail"]
        name = self.read_name(image)
        info = hero_info(name) or {}
        classes = parse_classes(self._text(image, d["classes"]), self.lang)
        stats, icons = self.read_panel(image)
        hero = Hero(
            name=name,
            code=info.get("code"),
            element=classes.get("element") or info.get("element"),
            role=classes.get("role") or info.get("role"),
            zodiac=classes.get("zodiac"),
            level=parse_level(self._text(image, d["level"])),
            power=parse_int(self._text(image, d["power"]), 1000, 10**6),
            imprint_bonus=self._imprint(image),
            gear_score_avg=parse_int(self._text(image, d["gear_score"]).split(":")[-1], 0, 200),
            stats=stats,
            scanned_at=datetime.now(UTC),
            source="scan",
        )
        for slot in GearSlot:
            if gear := self.read_gear(image, slot, icons):
                hero.gear[slot] = gear
        hero.artifact = self._artifact(image)
        for issue in self.issues:
            log.warning("%s : %s — %s", hero.name, issue.field, issue.message)
        return hero

    # --- écran « liste des héros »
    def is_list_screen(self, image: Image.Image) -> bool:
        box = self.regions.get("hero_list", {}).get("title_hint")
        if not box:
            return False
        text = normalize(" ".join(line.text for line in self.ocr.read_lines(self._box(image, box))))
        return any(hint in text for hint in ("gerer", "equip", "manage", "unequip"))

    def read_list(self, image: Image.Image) -> tuple[str | None, list[GearSet]]:
        """Nom du héros sélectionné et sets actifs (« Set Vitesse », « Set Critique »...)."""
        from e7showcase.parsers.gear_parser import parse_set

        section = self.regions["hero_list"]
        raw_name = self._text(image, section["name"])
        name = match_hero_name(raw_name, self.lang) or raw_name or None
        sets: list[GearSet] = []
        for row in section.get("set_rows", []):
            text = self._text(image, [row[0] + row[2], row[1], row[4], row[3]])
            if text and "aucun" not in normalize(text) and (gear_set := parse_set(text, self.lang)):
                sets.append(gear_set)
        return name, sets

    def learn_list_sets(self, image: Image.Image) -> list[str]:
        """Apprend les blasons des sets actifs affichés sur la liste des héros.

        Chaque ligne « Set Xxx » montre le blason à côté de son nom : on l'enregistre comme
        modèle s'il manque (un blason issu du catalogue des sets reste prioritaire).
        """
        from e7showcase.parsers.gear_parser import parse_set
        from e7showcase.vision.set_catalog import tight_shield

        learned: list[str] = []
        for row in self.regions.get("hero_list", {}).get("set_rows", []):
            text = self._text(image, [row[0] + row[2], row[1], row[4], row[3]])
            if not text or "aucun" in normalize(text):
                continue
            gear_set = parse_set(text, self.lang)
            if gear_set is None or gear_set.value in self.sets.templates:
                continue
            self.sets.add(gear_set.value, tight_shield(self._box(image, row[:4])))
            learned.append(gear_set.value)
        return learned
