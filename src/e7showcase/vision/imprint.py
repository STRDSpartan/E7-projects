"""Rang d'empreinte lu sur l'icône de la fiche « Infos de héros ».

Les lettres du rang (« A », « S », « SS », « SSS »...) sont des glyphes décoratifs que l'OCR
ne lit pas. Chaque lettre porte un petit reflet clair en haut : on compte ces reflets dans
la moitié basse de l'icône (nombre de lettres), et la couleur dominante donne la lettre
(rouge = S, violet = A, bleu = B, vert = C). Icône grise (cadenas) : empreinte verrouillée.

Mesuré sur 8 fiches réelles (PC et mobile : S, SS, SSS, A, verrouillé) : 8/8.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

HIGHLIGHT = 150  # niveau minimal des trois canaux d'un reflet
MAX_LETTERS = 3


def _letter(a: np.ndarray) -> str | None:
    """Lettre du rang d'après la teinte dominante des pixels saturés."""
    sat = a.max(axis=2) - a.min(axis=2)
    px = a[sat > 80]
    if len(px) < 10:
        return None  # icône grise : verrouillée
    r, g, b = (float(v) for v in np.median(px, axis=0))
    if r > 1.6 * g and r > 1.3 * b:
        return "S"
    if b > 1.3 * g and r > 0.6 * b:
        return "A"
    if b > r and b > g:
        return "B"
    if g > r and g > b:
        return "C"
    return None


def imprint_rank(icon: Image.Image) -> str | None:
    import cv2

    a = np.asarray(icon.convert("RGB")).astype(np.int32)
    h, w = a.shape[:2]
    letter = _letter(a)
    if letter is None:
        return None
    mask = (a.min(axis=2) > HIGHLIGHT).astype(np.uint8)
    mask[: int(h * 0.45)] = 0
    n, _, st, _ = cv2.connectedComponentsWithStats(mask)
    dots = sum(1 for k in range(1, n) if st[k, cv2.CC_STAT_AREA] <= 0.01 * h * w)
    if letter != "S":
        return letter
    return "S" * min(max(dots, 1), MAX_LETTERS)
