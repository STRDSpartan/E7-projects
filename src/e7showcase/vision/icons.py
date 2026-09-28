"""Classification de petites icônes (stats, sets) par corrélation de formes.

Aucune image du jeu n'est livrée avec le projet : les modèles sont appris à la volée
(icônes du panneau de stats, dont le libellé est connu) ou depuis la bibliothèque locale
de l'utilisateur (dossier de données), jamais depuis le dépôt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 24


def features(image: Image.Image) -> np.ndarray:
    """Vecteur normalisé du glyphe : seuillage d'Otsu, recadrage sur les composantes
    significatives, mise au carré puis réduction à SIZE×SIZE (niveaux de gris centrés)."""
    import cv2

    g = np.asarray(image.convert("L"))
    _, mask = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    n, _, st, _ = cv2.connectedComponentsWithStats(mask)
    keep = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.02 * mask.size]
    if keep:
        x0 = min(st[i, 0] for i in keep)
        y0 = min(st[i, 1] for i in keep)
        x1 = max(st[i, 0] + st[i, 2] for i in keep)
        y1 = max(st[i, 1] + st[i, 3] for i in keep)
        g = g[y0:y1, x0:x1]
    side = max(g.shape)
    square = np.zeros((side, side), np.uint8)
    oy, ox = (side - g.shape[0]) // 2, (side - g.shape[1]) // 2
    square[oy : oy + g.shape[0], ox : ox + g.shape[1]] = g
    v = cv2.resize(square, (SIZE, SIZE), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    v -= v.mean()
    norm = float(np.linalg.norm(v))
    return v / norm if norm else v


def set_features(image: Image.Image) -> np.ndarray:
    """Icône de set (blason) : seul le dessin central distingue les sets, le contour étant
    commun. Canal « doré » (G - B/2) au centre de l'icône, légèrement flouté."""
    import cv2

    w, h = image.size
    a = np.asarray(
        image.convert("RGB").crop((int(w * 0.25), int(h * 0.2), int(w * 0.75), int(h * 0.7)))
    ).astype(np.float32)
    g = a[..., 1] - 0.5 * a[..., 2]
    g = cv2.GaussianBlur(cv2.resize(g, (20, 20), interpolation=cv2.INTER_AREA), (3, 3), 0)
    v = g.ravel()
    v -= v.mean()
    norm = float(np.linalg.norm(v))
    return v / norm if norm else v


@dataclass
class IconClassifier:
    templates: dict[str, list[np.ndarray]] = field(default_factory=dict)
    extractor: Callable[[Image.Image], np.ndarray] = features

    def add(self, label: str, image: Image.Image) -> None:
        self.templates.setdefault(label, []).append(self.extractor(image))

    def scores(self, image: Image.Image) -> dict[str, float]:
        f = self.extractor(image)
        return {label: max(float(f @ t) for t in ts) for label, ts in self.templates.items()}

    def predict(self, image: Image.Image, min_score: float = 0.5) -> tuple[str | None, float]:
        scores = self.scores(image)
        if not scores:
            return None, 0.0
        label = max(scores, key=lambda k: scores[k])
        return (label if scores[label] >= min_score else None), scores[label]

    # --- bibliothèque locale (icônes de sets apprises depuis la liste des héros)
    def save(self, directory: Path, label: str, image: Image.Image) -> Path:
        target = directory / label
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{len(list(target.glob('*.png'))):03d}.png"
        image.save(path)
        self.add(label, image)
        return path

    @classmethod
    def load(
        cls, directory: Path, extractor: Callable[[Image.Image], np.ndarray] = features
    ) -> IconClassifier:
        clf = cls(extractor=extractor)
        if directory.is_dir():
            for path in sorted(directory.glob("*/*.png")):
                clf.add(path.parent.name, Image.open(path))
        return clf
