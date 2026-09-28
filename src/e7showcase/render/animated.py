"""Vitrine animée : la carte d'un héros avec son modèle animé (WebP animé, joué par Discord).

1. La carte est rendue une fois (HTML → image) avec une zone réservée au modèle.
2. Chaque image de l'animation (export de la visionneuse d'E7 Codex) y est incrustée.
3. Le tout est enregistré en WebP animé, en bouclant.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image

from e7showcase.assets import AssetStore
from e7showcase.models.hero import Hero
from e7showcase.models.roster import Roster

Frame = tuple[Image.Image, int]  # (image RGBA, durée en ms)
DEFAULT_DURATION = 42  # 24 images/s, cadence d'export de la visionneuse
# Limite d'envoi Discord sans Nitro : 10 Mo ; on garde une marge
MAX_BYTES = 9_500_000


def webp_durations(data: bytes) -> list[int]:
    """Durées des images d'un WebP animé (blocs ANMF) ; Pillow 12 ne les expose pas."""
    durations: list[int] = []
    pos = 12
    while pos + 8 <= len(data):
        tag = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        if tag == b"ANMF":
            durations.append(int.from_bytes(data[pos + 20 : pos + 23], "little"))
        pos += 8 + size + (size & 1)
    return durations


def _opaque(frame: Image.Image, threshold: int = 40) -> Image.Image:
    return frame.getchannel("A").point(lambda v: 255 if v > threshold else 0)


def read_frames(path: Path) -> list[Frame]:
    """Images de l'animation, recadrées sur la zone réellement occupée par le personnage."""
    data = path.read_bytes()
    durations = webp_durations(data)
    frames: list[Image.Image] = []
    with Image.open(io.BytesIO(data)) as anim:
        for i in range(getattr(anim, "n_frames", 1)):
            anim.seek(i)
            frames.append(anim.convert("RGBA"))
    # Cadrage sur les pixels nettement opaques : les particules presque transparentes
    # (effets d'ambiance) élargiraient le cadre et rapetisseraient le personnage.
    boxes = [b for f in frames if (b := _opaque(f).getbbox())]
    if boxes:
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        pad = round(0.03 * max(x1 - x0, y1 - y0))
        w, h = frames[0].size
        union = (max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad))
        frames = [f.crop(union) for f in frames]
    return [
        (f, durations[i] if i < len(durations) and durations[i] else DEFAULT_DURATION)
        for i, f in enumerate(frames)
    ]


def compose(
    background: Image.Image, slot: tuple[int, int, int, int], frames: list[Frame]
) -> list[Frame]:
    """Incruste chaque image (ajustée, centrée, calée en bas) dans la zone `slot` du fond."""
    x0, y0, x1, y1 = slot
    sw, sh = x1 - x0, y1 - y0
    fw, fh = frames[0][0].size
    ratio = min(sw / fw, sh / fh)
    size = (max(1, round(fw * ratio)), max(1, round(fh * ratio)))
    ox, oy = x0 + (sw - size[0]) // 2, y1 - size[1]
    out: list[Frame] = []
    base = background.convert("RGBA")
    for frame, duration in frames:
        canvas = base.copy()
        sprite = frame.resize(size, Image.Resampling.LANCZOS)
        canvas.alpha_composite(sprite, (ox, oy))
        out.append((canvas.convert("RGB"), duration))
    return out


def save_webp(frames: list[Frame], target: Path, quality: int = 80) -> Path:
    images = [f for f, _ in frames]
    images[0].save(
        target,
        "WEBP",
        save_all=True,
        append_images=images[1:],
        loop=0,
        duration=[d for _, d in frames],
        quality=quality,
        method=4,
    )
    return target


def render_animated_card(
    roster: Roster,
    hero: Hero,
    assets: AssetStore,
    target: Path,
    anim_path: Path,
    *,
    width: int = 1200,
    scale: float = 1.0,
    max_bytes: int = MAX_BYTES,
) -> Path:
    """Carte animée d'un héros → WebP animé (réduit automatiquement sous `max_bytes`)."""
    import os

    from playwright.sync_api import sync_playwright

    from e7showcase.render.showcase import render_html

    html = render_html(roster, [hero], layout="cards", width=width, assets=assets, animated=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("E7_CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": width, "height": 200}, device_scale_factor=scale)
        page.set_content(html, wait_until="networkidle")
        background = Image.open(io.BytesIO(page.screenshot(full_page=True)))
        box = page.locator(".anim-slot").bounding_box()
        browser.close()
    if box is None:
        raise RuntimeError("Zone du modèle animé introuvable dans la carte")
    left, top = round(box["x"] * scale), round(box["y"] * scale)
    slot = (left, top, left + round(box["width"] * scale), top + round(box["height"] * scale))
    frames = read_frames(anim_path)
    for step in (1, 2):  # une image sur deux si le fichier dépasse la limite Discord
        kept = [(f, d * step) for f, d in frames[::step]]
        save_webp(compose(background, slot, kept), target)
        if target.stat().st_size <= max_bytes:
            break
    return target
