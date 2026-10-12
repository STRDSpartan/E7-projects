"""Icône d'un objet sur une capture d'infobulle (pièce non équipée de l'armurerie).

Dans l'infobulle, l'icône carrée de l'objet est en haut à gauche ; l'amélioration (« +15 ») est
écrite dessus et l'en-tête (« Arme Épique ») à sa droite. Sans gabarit calibré pour cet écran,
la position est déduite des boîtes de texte de l'OCR, puis resserrée sur le cadre de l'icône
(pixels qui se détachent du fond de l'infobulle). Fonctions pures, sans I/O.
"""

from __future__ import annotations

import re

from PIL import Image, ImageChops, ImageFilter

from e7showcase.parsers.item_parser import SLOT_WORDS
from e7showcase.reference import normalize
from e7showcase.vision.ocr import OcrLine

Box = tuple[int, int, int, int]  # (x0, y0, x1, y1) en pixels

_ENHANCE_RE = re.compile(r"^\+\s*\d{1,2}$")
ICON_PER_ENHANCE = 6.0  # côté de l'icône ≈ 4 à 8 fois la hauteur du « +15 » (zone large)
ICON_PER_HEADER = 4.0  # ou ≈ 3 à 5 fois la hauteur de la ligne d'en-tête, à sa gauche
MIN_ICON = 24  # px : en dessous, l'estimation n'est pas crédible


def _clamp(box: tuple[float, float, float, float], size: tuple[int, int]) -> Box | None:
    w, h = size
    x0, y0, x1, y1 = (
        max(0, int(box[0])),
        max(0, int(box[1])),
        min(w, int(box[2])),
        min(h, int(box[3])),
    )
    return (x0, y0, x1, y1) if x1 - x0 >= MIN_ICON and y1 - y0 >= MIN_ICON else None


def locate_item_icon(lines: list[OcrLine], size: tuple[int, int]) -> Box | None:
    """Zone (volontairement large) où se trouve l'icône de l'objet, ou None.

    La zone est bornée par le texte voisin : l'en-tête à droite, la première stat en dessous.
    """
    boxes = sorted(((b.text.strip(), b.box) for b in lines if b.box), key=lambda t: t[1][1])
    plus = [box for text, box in boxes if _ENHANCE_RE.match(text)]
    header = next(
        (
            box
            for text, box in boxes
            if len(words := re.findall(r"[a-z]+", normalize(text))) <= 4
            and any(w in SLOT_WORDS for w in words)
        ),
        None,
    )
    if plus:  # « +15 » est dessiné en haut à gauche de l'icône
        x0, y0, _, y1 = plus[0]
        side = (y1 - y0) * ICON_PER_ENHANCE
        zone = [x0 - 0.3 * side, y0 - 0.3 * side, x0 + 1.3 * side, y0 + 1.3 * side]
    elif header is not None:
        x0, y0, _, y1 = header
        side = (y1 - y0) * ICON_PER_HEADER
        zone = [x0 - 1.4 * side, y0 - 0.5 * side, x0, y0 + 1.3 * side]
    else:
        return None
    if header is not None and header[0] > zone[0] + MIN_ICON:
        zone[2] = min(zone[2], header[0] - 2)
    below = [
        box[1]
        for _, box in boxes
        if box[1] > zone[1] + MIN_ICON and box is not header and box not in plus
        and box[0] < zone[2]
    ]  # fmt: skip
    if below:
        zone[3] = min(zone[3], min(below) - 2)
    return _clamp((zone[0], zone[1], zone[2], zone[3]), size)


def tighten(image: Image.Image) -> Image.Image:
    """Resserre une zone sur le cadre de l'icône : pixels qui diffèrent du fond (bords)."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    corners = [rgb.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    background = tuple(sorted(c[i] for c in corners)[1] for i in range(3))  # type: ignore[index]
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, background)).convert("L")
    mask = diff.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MedianFilter(5))
    bbox = mask.getbbox()
    if not bbox or (bbox[2] - bbox[0]) < MIN_ICON or (bbox[3] - bbox[1]) < MIN_ICON:
        return rgb
    x0, y0, x1, y1 = bbox
    side = max(x1 - x0, y1 - y0)  # l'icône est carrée
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    half = side // 2
    return rgb.crop((max(0, cx - half), max(0, cy - half), min(w, cx + half), min(h, cy + half)))


def crop_item_icon(image: Image.Image, boxes: list[OcrLine]) -> Image.Image | None:
    zone = locate_item_icon(boxes, image.size)
    return tighten(image.crop(zone)) if zone else None
