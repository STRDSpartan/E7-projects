"""Pré-traitement d'image pour fiabiliser l'OCR sur l'UI sombre d'Epic Seven."""

from __future__ import annotations

from PIL import Image, ImageOps


def for_ocr(image: Image.Image, upscale: int = 2, threshold: int | None = 150) -> Image.Image:
    """Texte clair sur fond sombre -> texte noir sur fond blanc, agrandi."""
    img = image.convert("L")
    if upscale > 1:
        img = img.resize((img.width * upscale, img.height * upscale), Image.Resampling.LANCZOS)
    img = ImageOps.invert(img)
    if threshold is not None:
        img = img.point(lambda p: 255 if p > threshold else 0)
    return img


def strip_window_chrome(image: Image.Image, min_jump: float = 40.0) -> Image.Image:
    """Retire la barre de titre Windows et la barre des tâches d'une capture plein écran.

    Une capture « Impr. écran » du client en fenêtre agrandie contient, en plus du jeu, une
    bande claire en haut (titre) et une bande en bas (barre des tâches). Chacune est repérée
    comme une bande de luminosité homogène séparée du jeu par un saut net ; sinon l'image
    est rendue telle quelle (capture de la zone cliente, mobile...).
    """
    import numpy as np

    rows = np.asarray(image.convert("L"), dtype=np.float32).mean(axis=1)
    h = len(rows)
    if h < 400:
        return image

    def boundary(candidates: range, above: bool) -> int | None:
        """Ligne où commence le jeu (haut) ou la barre des tâches (bas), si elle existe."""
        best = max(candidates, key=lambda y: abs(rows[y] - rows[y - 1]))
        if abs(rows[best] - rows[best - 1]) < min_jump:
            return None
        band = rows[:best] if above else rows[best:]
        return best if float(band.std()) < 12 else None

    top = boundary(range(8, min(60, h // 10)), above=True) or 0
    bottom = boundary(range(h - int(h * 0.08), h - 8), above=False) or h
    if top == 0 and bottom == h:
        return image
    return image.crop((0, top, image.width, bottom))
