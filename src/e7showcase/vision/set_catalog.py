"""Reconnaissance des sets d'équipement à partir du catalogue affiché en jeu.

Le filtre d'inventaire du jeu liste tous les sets (« Set Vitesse », « Set Critique »...),
chacun précédé de son blason. Une capture de ce catalogue suffit : chaque blason est
recadré au plus juste puis enregistré dans la bibliothèque LOCALE de l'utilisateur
(jamais dans le dépôt). Sur la fiche d'un héros, le blason de chaque pièce est retrouvé
par corrélation multi-échelle (glissement + plusieurs tailles), robuste au cadrage.

Mesuré sur captures réelles : bon set ≥ 0,91, meilleur mauvais set ≤ 0,63 (18/18 pièces).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from e7showcase.models.gear import GearSet
from e7showcase.vision.ocr import OcrEngine

MIN_SCORE = 0.78
SCALES = tuple(round(0.8 + 0.05 * i, 2) for i in range(10))  # 0.80 → 1.25


def _gray(a: np.ndarray) -> np.ndarray:
    return a.astype(np.float32).mean(axis=2) if a.ndim == 3 else a.astype(np.float32)


def _inner(a: np.ndarray) -> np.ndarray:
    """Intérieur du blason : contour commun à tous les sets, le dessin central les distingue."""
    h, w = a.shape[:2]
    return a[int(h * 0.15) : int(h * 0.78), int(w * 0.18) : int(w * 0.82)]


def tight_shield(image: Image.Image, dark: int = 70) -> Image.Image:
    """Recadre un blason posé sur fond sombre (plus grande composante non sombre)."""
    import cv2

    a = np.asarray(image.convert("RGB"))
    mask = (a.max(axis=2) > dark).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(mask)
    if n <= 1:
        return image
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    x, y, w, h = (int(v) for v in st[i, :4])
    return image.crop((x, y, x + w, y + h))


@dataclass
class SetMatcher:
    templates: dict[str, Image.Image] = field(default_factory=dict)

    def add(self, key: str, shield: Image.Image) -> None:
        self.templates[key] = shield.convert("RGB")

    def scores(self, region: Image.Image) -> dict[str, float]:
        """Corrélation maximale de chaque blason connu dans la zone (plus large que l'icône)."""
        import cv2

        area = _gray(np.asarray(region.convert("RGB")))
        out: dict[str, float] = {}
        for key, tpl in self.templates.items():
            best = -1.0
            for s in SCALES:
                w, h = max(8, int(tpl.width * s)), max(8, int(tpl.height * s))
                t = _gray(_inner(np.asarray(tpl.resize((w, h), Image.Resampling.BILINEAR))))
                if t.shape[0] >= area.shape[0] or t.shape[1] >= area.shape[1]:
                    continue
                best = max(best, float(cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED).max()))
            out[key] = best
        return out

    def predict(
        self, region: Image.Image, min_score: float = MIN_SCORE
    ) -> tuple[str | None, float]:
        scores = self.scores(region)
        if not scores:
            return None, 0.0
        key = max(scores, key=lambda k: scores[k])
        return (key if scores[key] >= min_score else None), scores[key]

    # --- bibliothèque locale : un PNG par set
    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for key, img in self.templates.items():
            img.save(directory / f"{key}.png")

    @classmethod
    def load(cls, directory: Path) -> SetMatcher:
        matcher = cls()
        if directory.is_dir():
            for path in sorted(directory.glob("*.png")):
                if path.stem in GearSet._value2member_map_:
                    matcher.add(path.stem, Image.open(path))
        return matcher


def read_catalog(
    image: Image.Image, ocr: OcrEngine, lang: str = "fr"
) -> dict[GearSet, Image.Image]:
    """Extrait les blasons de toutes les lignes « Set Xxx » d'une capture du catalogue."""
    from e7showcase.parsers.gear_parser import parse_set
    from e7showcase.reference import normalize

    found: dict[GearSet, Image.Image] = {}
    for line in ocr.read_boxes(image):
        text = normalize(line.text)
        if line.box is None or not re.match(r"^(set|ensemble)\b", text):
            continue
        gear_set = parse_set(line.text, lang)
        if gear_set is None:
            continue
        x0, y0, _x1, y1 = line.box
        th = y1 - y0
        side, cy, right = th * 1.8, (y0 + y1) / 2, x0 - 0.05 * th
        area = image.crop((int(right - side), int(cy - side / 2), int(right), int(cy + side / 2)))
        found[gear_set] = tight_shield(area)
    return found
