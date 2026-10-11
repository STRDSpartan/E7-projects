"""Recadrage d'une fiche sur la zone du jeu grâce aux repères (OCR simulé, sans image du jeu)."""

from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

from e7showcase.config import region_profiles
from e7showcase.vision.framing import frame_detail

LM = region_profiles()["pc_19x10"]["detail"]["landmarks"]
GAME_W, GAME_H = 1919, 1009


@dataclass
class Line:
    text: str
    box: tuple[float, float, float, float]


class LandmarkOcr:
    """Renvoie les repères là où ils seraient pour un jeu placé en (ox, oy)."""

    def __init__(self, ox: int, oy: int, score: str = "Score moyen d'équipements : 92"):
        h = GAME_H
        title_x = ox + LM["title_left"] * h
        title_y = oy + LM["title_center_y"] * h
        dual_x = ox + LM["dual_left"] * h
        dual_y = oy + LM["dual_center_y"] * h
        digits = len(score.split(":")[-1].strip())
        end = ox + GAME_W - (LM["score_end_to_right"] - (digits - 2) * LM["score_digit_width"]) * h
        self.lines = [
            Line(
                "Infos de héros",
                (title_x, title_y - 20, title_x + LM["title_width"] * h, title_y + 20),
            ),
            Line("Chances de double attaque", (dual_x, dual_y - 14, dual_x + 250, dual_y + 14)),
            Line(score, (end - 400, oy + 0.28 * h, end, oy + 0.31 * h)),
        ]

    def read_boxes(self, crop: Image.Image) -> list[Line]:
        ox, oy = crop.info["offset"]
        out = []
        for line in self.lines:
            bx0, by0, bx1, by1 = line.box
            if ox <= bx0 and bx1 <= ox + crop.width and oy <= by0 and by1 <= oy + crop.height:
                out.append(Line(line.text, (bx0 - ox, by0 - oy, bx1 - ox, by1 - oy)))
        return out


def make(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height))
    original = img.crop

    def crop(box: tuple[int, int, int, int]) -> Image.Image:
        part = original(box)
        part.info["offset"] = (box[0], box[1])
        return part

    img.crop = crop  # type: ignore[method-assign]
    return img


@pytest.mark.parametrize(
    ("ox", "oy", "right", "bottom", "score"),
    [
        (0, 31, 0, 0, "Score moyen d'équipements : 92"),  # barre de titre sombre
        (14, 18, 9, 12, "Score moyen d'équipements : 92"),  # sélection Win+Maj+S
        (14, 18, 9, 12, "Score moyen d'équipements : 101"),  # score à 3 chiffres
    ],
)
def test_frames_the_game_area(ox: int, oy: int, right: int, bottom: int, score: str) -> None:
    img = make(GAME_W + ox + right, GAME_H + oy + bottom)
    framed = frame_detail(img, LandmarkOcr(ox, oy, score), LM)
    assert framed is not None
    assert framed.width == pytest.approx(GAME_W, abs=3) and framed.height == pytest.approx(
        GAME_H, abs=3
    )
    assert framed.info["offset"] == pytest.approx((ox, oy), abs=2)


def test_well_framed_capture_is_left_alone() -> None:
    assert frame_detail(make(GAME_W, GAME_H), LandmarkOcr(0, 0), LM) is None


def test_not_a_detail_screen() -> None:
    ocr = LandmarkOcr(0, 0)
    ocr.lines = []
    assert frame_detail(make(GAME_W, GAME_H), ocr, LM) is None


def test_native_aspect_capture_is_never_reframed(tmp_path: Path) -> None:
    """Capture 20:9 d'un téléphone : déjà au format d'un profil calibré, pas de recadrage."""
    from e7showcase.app.importer import ScreenshotImporter

    importer = ScreenshotImporter(tmp_path, fetch_icons=None)
    importer._ocr = object()  # noqa: SLF001 - aucune lecture ne doit avoir lieu
    phone = Image.new("RGB", (2000, 900))
    assert importer._frame(phone) is phone  # noqa: SLF001


def _rank_icon(color: tuple[int, int, int], letters: int) -> Image.Image:
    """Icône d'empreinte simulée : lettres colorées avec un reflet clair chacune."""
    from PIL import ImageDraw

    icon = Image.new("RGB", (60, 70), (12, 14, 20))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((10, 5, 50, 40), fill=tuple(c // 2 for c in color))
    for k in range(letters):
        x = 52 - 12 * (letters - k)
        draw.rectangle((x, 40, x + 10, 66), fill=color)
        draw.rectangle((x + 3, 43, x + 4, 44), fill=(255, 235, 235))
    return icon


@pytest.mark.parametrize(
    ("color", "letters", "rank"),
    [
        ((230, 40, 40), 1, "S"),
        ((230, 40, 40), 2, "SS"),
        ((230, 40, 40), 3, "SSS"),
        ((170, 80, 240), 1, "A"),
    ],
)
def test_imprint_rank(color: tuple[int, int, int], letters: int, rank: str) -> None:
    from e7showcase.vision.imprint import imprint_rank

    assert imprint_rank(_rank_icon(color, letters)) == rank
    assert imprint_rank(Image.new("RGB", (60, 70), (90, 90, 90))) is None  # cadenas gris
