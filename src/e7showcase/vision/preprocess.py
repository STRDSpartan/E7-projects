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
