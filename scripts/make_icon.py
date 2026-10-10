"""Génère l'icône et les images de l'installateur (dessin original, aucun visuel du jeu).

    python scripts/make_icon.py packaging/windows/build
Produit : e7showcase.ico (16 → 256 px), wizard.bmp (164x314), wizard-small.bmp (55x58).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GOLD = (232, 194, 106)
NIGHT = (11, 14, 21)
BLUE = (74, 179, 255)


def emblem(size: int) -> Image.Image:
    """Bouclier sombre liseré d'or, étoile bleue et monogramme « E7 »."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shield = [
        (s * 0.5, s * 0.04),
        (s * 0.92, s * 0.18),
        (s * 0.86, s * 0.62),
        (s * 0.5, s * 0.96),
        (s * 0.14, s * 0.62),
        (s * 0.08, s * 0.18),
    ]
    d.polygon(shield, fill=NIGHT, outline=GOLD, width=max(1, s // 20))
    cx, cy, r = s * 0.5, s * 0.3, s * 0.1
    star = []
    for i in range(8):
        rad = r if i % 2 == 0 else r * 0.35
        ang = i * 3.14159 / 4
        star.append((cx + rad * math.sin(ang), cy - rad * math.cos(ang)))
    d.polygon(star, fill=BLUE)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "segoeuib.ttf"):  # Linux, Windows
        try:
            font = ImageFont.truetype(name, int(s * 0.34))
            break
        except OSError:
            continue
    d.text((cx, s * 0.62), "E7", fill=GOLD, font=font, anchor="mm")
    return img


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    big = emblem(256)
    big.save(
        out / "e7showcase.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    big.save(out / "e7showcase.png")
    wizard = Image.new("RGB", (164, 314), NIGHT)
    wizard.paste(emblem(140), (12, 80), emblem(140))
    wizard.save(out / "wizard.bmp")
    small = Image.new("RGB", (55, 58), NIGHT)
    small.paste(emblem(50), (2, 4), emblem(50))
    small.save(out / "wizard-small.bmp")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "packaging/windows/build"))
