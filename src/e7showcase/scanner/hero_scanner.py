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
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.models.gear import FIXED_MAIN_STAT, Gear, GearSet, GearSlot, StatLine
from e7showcase.models.hero import Hero, HeroStats
from e7showcase.models.stats import StatType
from e7showcase.parsers.common import clean, parse_classes, parse_int, parse_level, parse_number
from e7showcase.parsers.hero_parser import match_hero_name
from e7showcase.reference import hero_info, normalize
from e7showcase.vision.icons import IconClassifier, set_features
from e7showcase.vision.ocr import OcrEngine
from e7showcase.vision.regions import crop

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
        set_icons: IconClassifier | None = None,
    ):
        self.ocr = ocr
        self.regions = regions
        self.lang = lang
        self.set_icons = set_icons or IconClassifier(extractor=set_features)
        self.issues: list[ScanIssue] = []

    # --- utilitaires
    def _box(self, image: Image.Image, box: list[float]) -> Image.Image:
        return crop(image, box)

    def _text(self, image: Image.Image, box: list[float]) -> str:
        return clean(self.ocr.read_text(self._box(image, box)))

    def _rows(self, box: list[float], n: int) -> list[list[float]]:
        x, y, w, h = box
        return [[x, y + i * h / n, w, h / n] for i in range(n)]

    def is_detail_screen(self, image: Image.Image) -> bool:
        return "infos de h" in normalize(
            self._text(image, self.regions["detail"]["title"])
        ) or "hero info" in normalize(self._text(image, self.regions["detail"]["title"]))

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
        set_label, _ = self.set_icons.predict(self._box(image, rel("set_icon")), min_score=0.45)
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
        artifact = [line.text for line in self.ocr.read_lines(self._box(image, d["artifact"]))]
        hero.artifact = next(
            (t for t in artifact if not any(c.isdigit() for c in t) and "max" not in t.lower()),
            None,
        )
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

    def set_icon_images(self, image: Image.Image) -> dict[GearSlot, Image.Image]:
        d = self.regions["detail"]
        dx, dy, w, h = d["gear_layout"]["set_icon"]
        return {
            slot: self._box(image, [ax + dx, ay + dy, w, h])
            for slot, (ax, ay) in ((GearSlot(k), v) for k, v in d["gear"].items())
        }

    def learn_sets(
        self,
        detail: Image.Image,
        active: list[GearSet],
        library: Path | None = None,
        min_similarity: float = 0.3,
    ) -> dict[GearSlot, GearSet]:
        """Associe les icônes des 6 pièces aux sets actifs lus sur la liste des héros.

        On connaît la composition (ex. Vitesse ×4 + Critique ×2) : pour chaque set, du plus
        grand au plus petit, on retient parmi les pièces restantes la combinaison la plus
        homogène visuellement. Si plusieurs sets de même taille restent à attribuer, la
        bibliothèque existante départage ; à défaut on n'apprend rien plutôt que de deviner.
        """
        from itertools import combinations

        from e7showcase.reference import set_pieces

        icons = self.set_icon_images(detail)
        feats = {slot: set_features(img) for slot, img in icons.items()}

        def cohesion(group: tuple[GearSlot, ...]) -> float:
            pairs = list(combinations(group, 2))
            return sum(float(feats[a] @ feats[b]) for a, b in pairs) / len(pairs)

        free = list(feats)
        assigned: dict[GearSlot, GearSet] = {}
        todo = sorted(active, key=lambda st: -set_pieces(st.value))
        while todo:
            gear_set = todo.pop(0)
            size = set_pieces(gear_set.value)
            if len(free) < size:
                break
            group = max(combinations(free, size), key=cohesion)
            if cohesion(group) < min_similarity:
                continue
            same_size = [t for t in todo if set_pieces(t.value) == size and t != gear_set]
            if same_size:  # plusieurs sets de même taille : lequel est ce groupe ?
                if not self.set_icons.templates:
                    continue
                scores = self.set_icons.scores(icons[group[0]])
                ranked = sorted([gear_set, *same_size], key=lambda t: -scores.get(t.value, -1.0))
                if ranked[0] != gear_set:
                    todo.remove(ranked[0])
                    todo.insert(0, gear_set)
                    gear_set = ranked[0]
            for slot in group:
                assigned[slot] = gear_set
                free.remove(slot)
        for slot, gear_set in assigned.items():
            if library is not None:
                self.set_icons.save(library, gear_set.value, icons[slot])
            else:
                self.set_icons.add(gear_set.value, icons[slot])
        return assigned
