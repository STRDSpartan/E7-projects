"""Reconnaissance des blasons de sets, sur des blasons synthétiques (aucune image du jeu)."""

from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

pytest.importorskip("cv2")

from e7showcase.models.gear import GearSet  # noqa: E402
from e7showcase.parsers.gear_parser import parse_set  # noqa: E402
from e7showcase.vision.ocr import OcrLine  # noqa: E402
from e7showcase.vision.set_catalog import SetMatcher, read_catalog, tight_shield  # noqa: E402

GOLD, RED, BLUE = (225, 185, 110), (140, 30, 35), (35, 45, 120)


def shield(glyph: str, size: int = 60, fill: tuple[int, int, int] = RED) -> Image.Image:
    img = Image.new("RGB", (size, int(size * 1.05)), (0, 0, 0))
    d = ImageDraw.Draw(img)
    w, h = img.size
    d.polygon(
        [(2, 2), (w - 3, 2), (w - 3, h * 0.6), (w // 2, h - 3), (2, h * 0.6)],
        fill=fill,
        outline=GOLD,
        width=4,
    )
    c, r = w // 2, int(h * 0.42)
    if glyph == "chevron":
        d.line((c - 10, r - 12, c + 8, r, c - 10, r + 12), fill=GOLD, width=6)
    elif glyph == "star":
        d.polygon(
            [(c, r - 14), (c + 12, r + 10), (c - 14, r - 5), (c + 14, r - 5), (c - 12, r + 10)],
            fill=GOLD,
        )
    elif glyph == "cross":
        d.line((c - 12, r - 12, c + 12, r + 12), fill=GOLD, width=5)
        d.line((c + 12, r - 12, c - 12, r + 12), fill=GOLD, width=5)
    elif glyph == "heart":
        d.ellipse((c - 13, r - 12, c, r + 1), fill=GOLD)
        d.ellipse((c, r - 12, c + 13, r + 1), fill=GOLD)
        d.polygon([(c - 13, r - 4), (c + 13, r - 4), (c, r + 13)], fill=GOLD)
    return img


GLYPHS = {"speed": "chevron", "weakening": "star", "pursuit": "cross", "health": "heart"}


def on_piece(img: Image.Image, scale: float, dx: int, dy: int) -> Image.Image:
    """Blason redimensionné et décalé dans une zone de fond (simule la fiche héros)."""
    s = img.resize((int(img.width * scale), int(img.height * scale)))
    area = Image.new("RGB", (int(img.width * 1.7), int(img.height * 1.7)), (90, 20, 40))
    area.paste(s, (int(img.width * 0.3) + dx, int(img.height * 0.3) + dy))
    return area


def test_matches_rescaled_and_shifted_shields() -> None:
    matcher = SetMatcher()
    for key, glyph in GLYPHS.items():
        matcher.add(key, tight_shield(shield(glyph, fill=BLUE if key == "health" else RED)))
    for key, glyph in GLYPHS.items():
        piece = on_piece(shield(glyph, fill=BLUE if key == "health" else RED), 1.1, 4, -3)
        label, score = matcher.predict(piece, min_score=0.5)
        assert label == key, matcher.scores(piece)


def test_unknown_set_is_rejected() -> None:
    matcher = SetMatcher()
    matcher.add("speed", tight_shield(shield("chevron")))
    label, _ = matcher.predict(on_piece(shield("star"), 1.0, 0, 0))
    assert label is None


def test_library_roundtrip(tmp_path: Path) -> None:
    matcher = SetMatcher()
    matcher.add("speed", shield("chevron"))
    matcher.add("not_a_set", shield("star"))
    matcher.save(tmp_path)
    assert set(SetMatcher.load(tmp_path).templates) == {"speed"}


class BoxOcr:
    def __init__(self, lines: list[OcrLine]) -> None:
        self.lines = lines

    def read_boxes(self, image: Image.Image) -> list[OcrLine]:
        return self.lines

    def read_text(self, image: Image.Image) -> str:
        return ""

    def read_lines(self, image: Image.Image) -> list[Any]:
        return []


def test_read_catalog_crops_shield_left_of_each_line() -> None:
    page = Image.new("RGB", (700, 200), (0, 0, 0))
    page.paste(shield("chevron"), (40, 20))
    page.paste(shield("star"), (40, 110))
    lines = [
        OcrLine("Set Vitesse", 0.99, 30, (120.0, 30.0, 320.0, 72.0)),
        OcrLine("Set Affaiblissement 131", 0.99, 120, (120.0, 120.0, 420.0, 162.0)),
        OcrLine("409", 0.99, 30, (600.0, 30.0, 650.0, 72.0)),
    ]
    found = read_catalog(page, BoxOcr(lines))  # type: ignore[arg-type]
    assert set(found) == {GearSet.SPEED, GearSet.WEAKENING}
    w, h = found[GearSet.SPEED].size
    assert 55 <= w <= 62 and 58 <= h <= 66  # blason recadré au plus juste


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Set Coup", GearSet.HIT),
        ("Set Infiltration", GearSet.PENETRATION),
        ("Set Tumulte", GearSet.TORRENT),
        ("Set Réaction", GearSet.REACTION),
        ("Set Implication", GearSet.IMPLICATION),
        ("Set Affaiblissement 131", GearSet.WEAKENING),
        ("Set Contre", GearSet.COUNTER),
        ("Set Vol de vie", GearSet.LIFESTEAL),
    ],
)
def test_parse_fr_set_names(text: str, expected: GearSet) -> None:
    assert parse_set(text) == expected
