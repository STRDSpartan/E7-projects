"""Reconnaissance d'un héros à son portrait rond (écran de résultat de GvG).

Le jeu affiche le visage du héros dans un cercle doré, avec l'icône de classe en haut à
gauche (et, s'il est vaincu, assombri et barré d'une croix). On compare le disque intérieur
aux icônes de visage téléchargées depuis E7 Codex (`<données>/assets/faces/`) : luminance
normalisée (insensible à l'assombrissement) et chroma, coin de l'icône de classe ignoré,
quelques décalages et échelles essayés. Aucune image du jeu n'est livrée avec le projet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

SIZE = 40
SCALES = (0.88, 0.94, 1.0, 1.06)
SHIFTS = (-4, -2, 0, 2, 4)
# position du portrait par rapport à sa colonne de stats, en hauteurs de ligne (mesuré)
PORTRAIT_DX, PORTRAIT_DY, PORTRAIT_R = 1.70, -5.70, 1.70


def _mask() -> np.ndarray:
    yy, xx = np.mgrid[:SIZE, :SIZE]
    c = (SIZE - 1) / 2
    rad = np.hypot(xx - c, yy - c)
    ang = np.degrees(np.arctan2(yy - c, xx - c))
    corner = (ang < -100) & (ang > -170) & (rad > SIZE * 0.18)  # icône de classe
    return np.asarray((rad <= SIZE * 0.46) & ~corner)


MASK = _mask()


def features(rgb: np.ndarray) -> np.ndarray:
    import cv2

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    lum = lab[..., 0][MASK]
    lum = (lum - lum.mean()) / (lum.std() + 1e-6)
    ab = lab[..., 1:][MASK].reshape(-1) - 128
    ab = ab / (np.linalg.norm(ab) + 1e-6) * np.sqrt(len(lum)) * 0.5
    v = np.concatenate([lum, ab])
    return np.asarray(v / np.linalg.norm(v))


@dataclass
class Circle:
    x: float
    y: float
    r: float


def locate(image: Image.Image, col_x: float, hp_y: float, step: float) -> Circle:
    """Portrait au-dessus d'une colonne de stats ; affiné par détection de cercle si possible."""
    import cv2

    guess = Circle(col_x + PORTRAIT_DX * step, hp_y + PORTRAIT_DY * step, PORTRAIT_R * step)
    pad = guess.r * 1.6
    box = (
        max(0, int(guess.x - pad)),
        max(0, int(guess.y - pad)),
        min(image.width, int(guess.x + pad)),
        min(image.height, int(guess.y + pad)),
    )
    gray = cv2.medianBlur(np.asarray(image.crop(box).convert("L")), 5)
    found = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=guess.r,
        param1=100,
        param2=25,
        minRadius=int(guess.r * 0.75),
        maxRadius=int(guess.r * 1.3),
    )
    if found is None:
        return guess
    best = min(
        ((box[0] + c[0], box[1] + c[1], c[2]) for c in found[0]),
        key=lambda c: (c[0] - guess.x) ** 2 + (c[1] - guess.y) ** 2,
    )
    x, y, r = (float(v) for v in best)
    if abs(x - guess.x) > guess.r or abs(y - guess.y) > guess.r:
        return guess
    return Circle(x, y, r)


class FaceMatcher:
    """Icônes de visage (code → vecteur), relues seulement si le dossier change."""

    def __init__(self, folder: Path):
        self.folder = folder
        self._key: tuple[int, int] | None = None
        self._codes: list[str] = []
        self._matrix: Any = None

    def count(self) -> int:
        return sum(1 for _ in self.folder.glob("*.*")) if self.folder.is_dir() else 0

    def _load(self) -> None:
        files = sorted(self.folder.glob("*.*")) if self.folder.is_dir() else []
        key = (len(files), max((f.stat().st_mtime_ns for f in files), default=0))
        if key == self._key:
            return
        codes, rows = [], []
        for f in files:
            try:
                with Image.open(f) as src:
                    face = src.convert("RGBA")
            except OSError:
                continue
            bg = Image.new("RGBA", face.size, (0, 0, 0, 255))
            bg.alpha_composite(face)
            small = bg.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
            codes.append(f.stem)
            rows.append(features(np.asarray(small)))
        self._key, self._codes = key, codes
        self._matrix = np.stack(rows) if rows else None

    def match(self, image: Image.Image, circle: Circle, top: int = 4) -> list[tuple[str, float]]:
        self._load()
        if self._matrix is None:
            return []
        best: Any = None
        for k in SCALES:
            rr = circle.r * k
            for dx in SHIFTS:
                for dy in SHIFTS:
                    x, y = circle.x + dx, circle.y + dy
                    crop = image.crop((x - rr, y - rr, x + rr, y + rr)).convert("RGB")
                    scores = self._matrix @ features(
                        np.asarray(crop.resize((SIZE, SIZE), Image.Resampling.LANCZOS))
                    )
                    if best is None or scores.max() > best.max():
                        best = scores
        order = np.argsort(-best)[:top]
        return [(self._codes[i], float(best[i])) for i in order]
