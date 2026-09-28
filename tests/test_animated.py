"""Vitrine animée : lecture d'un WebP animé, cadrage, incrustation (animations synthétiques)."""

from pathlib import Path

from PIL import Image, ImageDraw

from e7showcase.render.animated import compose, read_frames, save_webp, webp_durations


def _anim(path: Path, n: int = 6, duration: int = 42, particle: bool = True) -> Path:
    frames = []
    for i in range(n):
        img = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle((180 + i * 2, 100, 220 + i * 2, 250), fill=(200, 60, 90, 255))  # « personnage »
        if particle and i == 2:
            d.point((5, 5), fill=(255, 255, 255, 20))  # particule presque transparente, loin
        frames.append(img)
    frames[0].save(
        path,
        "WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        lossless=True,
    )
    return path


def test_webp_durations_are_read_from_anmf_chunks(tmp_path: Path) -> None:
    path = _anim(tmp_path / "a.webp", n=5, duration=42)
    assert webp_durations(path.read_bytes()) == [42] * 5


def test_read_frames_crops_on_opaque_pixels_only(tmp_path: Path) -> None:
    frames = read_frames(_anim(tmp_path / "a.webp"))
    assert len(frames) == 6 and all(d == 42 for _, d in frames)
    w, h = frames[0][0].size
    # le personnage fait ~50 x 150 px : la particule en (5, 5) ne doit pas élargir le cadre
    assert w < 80 and 150 <= h < 170


def test_compose_fits_sprite_bottom_aligned_in_slot(tmp_path: Path) -> None:
    frames = read_frames(_anim(tmp_path / "a.webp", particle=False))
    background = Image.new("RGB", (600, 400), (10, 20, 30))
    slot = (50, 40, 250, 380)
    out = compose(background, slot, frames)
    assert len(out) == len(frames) and out[0][0].size == (600, 400)
    first = out[0][0]
    assert first.getpixel((10, 10)) == (10, 20, 30)  # hors zone : fond intact
    assert first.getpixel((150, 375)) != (10, 20, 30)  # calé en bas de la zone
    target = save_webp(out, tmp_path / "card.webp")
    with Image.open(target) as anim:
        assert anim.n_frames == len(frames) and anim.info.get("loop") == 0
