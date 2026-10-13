"""Icône et images de l'installateur de Zealot, tirées du logo (packaging/branding/zealot-logo.png).

    python scripts/make_icon.py packaging/windows/build
Produit : zealot.ico (16 → 256 px), zealot.png, wizard.bmp (164x314) et wizard-200.bmp,
wizard-small.bmp (55x58) et wizard-small-200.bmp (écrans à 200 %).
    python scripts/make_icon.py --app   # logo et emblème transparents de l'application
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# identité « nuit de sakura » : lavande lumineuse, bleu nuit, rose sakura (comme l'application)
GOLD = (226, 214, 255)
GOLD_DEEP = (125, 104, 240)
NIGHT = (6, 8, 24)
VIOLET = (40, 28, 96)
EMBER = (255, 159, 212)
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


LOGO = Path(__file__).resolve().parents[1] / "packaging" / "branding" / "zealot-logo.png"
LOGO_BG = (40, 21, 60)  # fond violet du logo, rendu transparent
EMBLEM_BOX = (40, 18, 347, 292)  # ailes et auréole, sans le texte


def keyed(img: Image.Image) -> Image.Image:
    """Logo sur fond transparent : l'alpha croît avec l'écart à la couleur du fond."""
    import numpy as np

    rgb = np.asarray(img.convert("RGB")).astype(np.float32)
    dist = np.sqrt(((rgb - np.array(LOGO_BG, np.float32)) ** 2).sum(axis=2))
    alpha = np.clip((dist - 14.0) / 70.0, 0.0, 1.0)
    out = np.dstack([rgb, alpha * 255.0]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def logo() -> Image.Image:
    return keyed(Image.open(LOGO))


def emblem(size: int, background: bool = True) -> Image.Image:
    """Emblème du logo (ailes et auréole), centré ; sur pastille violette pour l'icône."""
    mark = logo().crop(EMBLEM_BOX)
    side = max(mark.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if background:
        ImageDraw.Draw(img).rounded_rectangle(
            (0, 0, size - 1, size - 1), radius=size // 5, fill=(*LOGO_BG, 255)
        )
        inner = int(size * 0.92)
    else:
        inner = size
    mark = square.resize((inner, inner), Image.Resampling.LANCZOS)
    img.alpha_composite(mark, ((size - inner) // 2, (size - inner) // 2))
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
    """Bandeau vertical de l'assistant : fond violet du logo, pétales, logo complet, éditeur."""
    w, h = 164 * scale, 314 * scale
    img = _gradient((w, h), (58, 30, 88), LOGO_BG).convert("RGBA")
    _sparks(img, 60, 7)
    full = logo()
    lw = int(146 * scale)
    full = full.resize((lw, int(full.height * lw / full.width)), Image.Resampling.LANCZOS)
    img.alpha_composite(full, ((w - lw) // 2, int(40 * scale)))
    d = ImageDraw.Draw(img)
    d.text(
        (w / 2, 290 * scale),
        f"par {PUBLISHER}",
        fill=(236, 216, 230),
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


def app_media(out: Path) -> None:
    """Logo et emblème transparents pour l'application (bandeau, écran d'accueil)."""
    out.mkdir(parents=True, exist_ok=True)
    full = logo()
    full.crop(full.getbbox()).save(out / "logo.png", optimize=True)
    emblem(160, background=False).save(out / "emblem.png", optimize=True)


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
    if sys.argv[1:2] == ["--app"]:  # régénère src/e7showcase/app/media/{logo,emblem}.png
        app_media(Path(__file__).resolve().parents[1] / "src" / "e7showcase" / "app" / "media")
        sys.exit()
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "packaging/windows/build"))
