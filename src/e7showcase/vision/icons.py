"""Classification de petites icônes (stats, sets) par corrélation de formes.

Aucune image du jeu n'est livrée avec le projet : les modèles sont appris à la volée
sur la capture elle-même (icônes du panneau de stats, dont le libellé est connu).
Les blasons de sets sont gérés par vision/set_catalog.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

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
