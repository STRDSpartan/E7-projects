"""Recadrage d'une fiche sur la zone du jeu grâce aux repères (OCR simulé, sans image du jeu)."""

from dataclasses import dataclass

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
