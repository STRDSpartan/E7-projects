"""Génère l'icône et les images de l'installateur de Zealot (dessin original, aucun visuel du jeu).

    python scripts/make_icon.py packaging/windows/build
Produit : zealot.ico (16 → 256 px), zealot.png, wizard.bmp (164x314) et wizard-200.bmp,
wizard-small.bmp (55x58) et wizard-small-200.bmp (écrans à 200 %).
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

GOLD = (240, 200, 110)
GOLD_DEEP = (176, 118, 42)
NIGHT = (9, 10, 20)
VIOLET = (58, 24, 92)
EMBER = (255, 120, 60)
PUBLISHER = "Shattered Spartan"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("DejaVuSans-Bold.ttf", "segoeuib.ttf", "arialbd.ttf")
        if bold
        else ("DejaVuSans.ttf", "segoeui.ttf", "arial.ttf")
    )
    for name in names:  # Linux, Windows
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _gradient(size: tuple[int, int], top: tuple[int, ...], bottom: tuple[int, ...]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        d.line(
            [(0, y), (w, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )
    return img


def emblem(size: int) -> Image.Image:
    """Écusson hexagonal sombre liseré d'or, « Z » doré fendu d'une lame et halo braise."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # halo
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((s * 0.12, s * 0.12, s * 0.88, s * 0.88), fill=(*EMBER, 110))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(1, s // 12))))
    d = ImageDraw.Draw(img)
    hexa = [
        (
            s * 0.5 + s * 0.44 * math.cos(math.pi / 6 + i * math.pi / 3),
            s * 0.5 + s * 0.44 * math.sin(math.pi / 6 + i * math.pi / 3),
        )
        for i in range(6)
    ]
    d.polygon(hexa, fill=(*NIGHT, 255), outline=GOLD, width=max(1, s // 22))
    inner = [(s * 0.5 + (x - s * 0.5) * 0.84, s * 0.5 + (y - s * 0.5) * 0.84) for x, y in hexa]
    d.polygon(inner, outline=(*GOLD_DEEP, 255), width=max(1, s // 64))
    # « Z » : deux barres et une diagonale, en dégradé or
    z = Image.new("L", (s, s), 0)
    zd = ImageDraw.Draw(z)
    t = s * 0.1
    left, right, top, bottom = s * 0.29, s * 0.71, s * 0.28, s * 0.72
    zd.rectangle((left, top, right, top + t), fill=255)
    zd.rectangle((left, bottom - t, right, bottom), fill=255)
    zd.polygon(
        [
            (right - t * 1.1, top + t),
            (right, top + t),
            (left + t * 1.1, bottom - t),
            (left, bottom - t),
        ],
        fill=255,
    )
    gold = _gradient((s, s), GOLD, GOLD_DEEP).convert("RGBA")
    img.paste(gold, (0, 0), z)
    # lame : trait clair qui traverse la diagonale
    d.line(
        [(s * 0.66, s * 0.2), (s * 0.34, s * 0.8)], fill=(255, 244, 214, 230), width=max(1, s // 48)
    )
    return img


def _sparks(img: Image.Image, count: int, seed: int) -> None:
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    for _ in range(count):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        r = rnd.choice((0.6, 0.8, 1.0, 1.4)) * w / 164
        hot = rnd.random() < 0.35
        color = (*EMBER, rnd.randint(120, 220)) if hot else (*GOLD, rnd.randint(60, 180))
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def wizard(scale: int) -> Image.Image:
    """Bandeau vertical de l'assistant : nuit violette, braises, écusson, nom et éditeur."""
    w, h = 164 * scale, 314 * scale
    img = _gradient((w, h), VIOLET, NIGHT).convert("RGBA")
    _sparks(img, 70, 7)
    mark = emblem(int(118 * scale))
    img.alpha_composite(mark, ((w - mark.width) // 2, int(54 * scale)))
    d = ImageDraw.Draw(img)
    d.text((w / 2, 196 * scale), "ZEALOT", fill=GOLD, font=_font(int(26 * scale)), anchor="mm")
    d.line([(w * 0.22, 214 * scale), (w * 0.78, 214 * scale)], fill=GOLD_DEEP, width=scale)
    d.text(
        (w / 2, 230 * scale),
        "compagnon Epic Seven",
        fill=(214, 206, 230),
        font=_font(int(10 * scale), bold=False),
        anchor="mm",
    )
    d.text(
        (w / 2, 290 * scale),
        f"par {PUBLISHER}",
        fill=(190, 170, 140),
        font=_font(int(9 * scale), bold=False),
        anchor="mm",
    )
    return img.convert("RGB")


def wizard_small(scale: int) -> Image.Image:
    w, h = 55 * scale, 58 * scale
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))  # fond blanc de l'en-tête de l'assistant
    mark = emblem(int(52 * scale))
    img.alpha_composite(mark, ((w - mark.width) // 2, (h - mark.height) // 2))
    return img.convert("RGB")


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    big = emblem(256)
    big.save(
        out / "zealot.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    big.save(out / "zealot.png")
    wizard(1).save(out / "wizard.bmp")
    wizard(2).save(out / "wizard-200.bmp")
    wizard_small(1).save(out / "wizard-small.bmp")
    wizard_small(2).save(out / "wizard-small-200.bmp")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "packaging/windows/build"))
