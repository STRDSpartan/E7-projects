"""Prépare la construction mobile (Briefcase) : sources avec données intégrées et icônes.

    python scripts/prepare_mobile.py
Produit build/mobile-src/e7showcase (paquet + _reference + _config) et build/mobile-icons/
(icônes Android et iOS tirées du logo). Voir docs/MOBILE.md.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from make_icon import emblem  # noqa: E402

ICON_SIZES = (20, 29, 40, 48, 58, 60, 72, 76, 80, 87, 96, 120, 144, 152, 167, 180, 192, 512, 1024)
SQUARE_SIZES = (48, 72, 96, 144, 192, 320, 480, 640, 960, 1280)


def main() -> None:
    src = ROOT / "build" / "mobile-src" / "e7showcase"
    shutil.rmtree(src.parent, ignore_errors=True)
    shutil.copytree(
        ROOT / "src" / "e7showcase", src, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copytree(ROOT / "data" / "reference", src / "_reference")
    shutil.copytree(ROOT / "config", src / "_config")
    icons = ROOT / "build" / "mobile-icons"
    icons.mkdir(parents=True, exist_ok=True)
    big = emblem(1024)
    for size in ICON_SIZES:
        big.resize((size, size)).save(icons / f"zealot-{size}.png")
    for size in SQUARE_SIZES:
        big.resize((size, size)).save(icons / f"zealot-square-{size}.png")
    round_mark = emblem(1024, background=False)
    for size in (48, 72, 96, 144, 192):
        round_mark.resize((size, size)).save(icons / f"zealot-round-{size}.png")
    print(f"Sources : {src}\nIcônes : {icons}")


if __name__ == "__main__":
    main()
