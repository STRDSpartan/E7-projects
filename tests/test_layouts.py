"""Zones pour tous les formats d'écran et remise à l'échelle (sans image du jeu)."""

import pytest
from PIL import Image, ImageDraw

from e7showcase.config import region_profiles, regions
from e7showcase.scanner.hero_scanner import stars_start
from e7showcase.vision.layouts import candidate_layouts, derive, normalize_scale


def test_calibrated_profile_used_as_is_for_its_format() -> None:
    pc = region_profiles()["pc_19x10"]
    zones = regions("auto", 1919 / 1009)
    assert zones["detail"]["gear"] == pc["detail"]["gear"]


@pytest.mark.parametrize("aspect", [4 / 3, 16 / 10, 16 / 9, 21 / 9, 32 / 9])
def test_any_format_gets_coherent_zones(aspect: float) -> None:
    zones = regions("auto", aspect)
    assert zones["aspect"] == pytest.approx(aspect, abs=1e-3)
    for key, box in zones["detail"].items():
        if isinstance(box, list) and len(box) == 4:
            x, y, w, h = box
            assert x >= 0 and x + w <= 1.0001 and y >= 0 and y + h <= 1.0001, key
    # l'équipement reste collé au bord droit, les stats au bord gauche
    weapon_x = zones["detail"]["gear"]["necklace"][0]
    assert 0.85 < weapon_x < 0.98
    assert zones["detail"]["stats_labels"][0] < 0.1


def test_anchors_keep_distances_in_height_units() -> None:
    pc = region_profiles()["pc_19x10"]
    wide = derive(pc, 21 / 9)
    gap = lambda cfg: (1 - cfg["detail"]["gear"]["boots"][0]) * cfg["aspect"]  # noqa: E731
    left = lambda cfg: cfg["detail"]["level"][0] * cfg["aspect"]  # noqa: E731
    assert gap(wide) == pytest.approx(gap(pc), abs=2e-3)
    assert left(wide) == pytest.approx(left(pc), abs=2e-3)


def test_candidates_start_with_the_closest_calibrated_profile() -> None:
    profiles = region_profiles()
    assert candidate_layouts(profiles, 2.15)[0]["derived_from"] == "19_5x9"
    assert candidate_layouts(profiles, 2.21)[0]["derived_from"] == "mobile_20x9"
    assert candidate_layouts(profiles, 16 / 9)[0]["derived_from"] == "pc_19x10"


@pytest.mark.parametrize("height", [674, 842, 1345, 2019])
def test_normalize_scale_to_calibration_height(height: int) -> None:
    img = Image.new("RGB", (round(height * 1.902), height))
    out = normalize_scale(img, {"reference_height": 1009})
    assert out.height == 1009 and out.width / out.height == pytest.approx(1.902, abs=0.01)
    assert (
        normalize_scale(Image.new("RGB", (1919, 1009)), {"reference_height": 1009}).height == 1009
    )


def test_name_zone_is_cut_before_the_stars() -> None:
    img = Image.new("RGB", (600, 60), (20, 22, 40))
    d = ImageDraw.Draw(img)
    d.rectangle((20, 15, 140, 45), fill=(240, 240, 240))  # nom blanc
    for i in range(6):  # étoiles orangées
        d.ellipse((300 + i * 40, 15, 330 + i * 40, 45), fill=(240, 120, 40))
    cut = stars_start(img)
    assert 0.45 < cut < 0.5
    assert stars_start(Image.new("RGB", (600, 60), (240, 240, 240))) == 1.0
