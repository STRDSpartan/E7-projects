"""Capture d'écran de la fenêtre du jeu (lecture seule des pixels, aucune injection)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from e7showcase.capture.window import WindowRect


def grab(rect: WindowRect) -> Image.Image:
    import mss

    with mss.mss() as sct:
        shot = sct.grab(
            {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
        )
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def load_captures(directory: Path) -> list[tuple[Path, Image.Image]]:
    """Mode hors-ligne : relit des captures déjà enregistrées (tests, recalibrage, Linux/macOS)."""
    files = sorted(
        p for p in directory.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    return [(p, Image.open(p).convert("RGB")) for p in files]
