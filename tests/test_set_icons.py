"""Blasons de référence des sets : téléchargement local, sans réseau (client simulé)."""

import io
from pathlib import Path

from PIL import Image, ImageDraw

from e7showcase.models.gear import GearSet
from e7showcase.reference import load
from e7showcase.sources.set_icons import ICONS, fetch_set_icons, missing


def _icon() -> bytes:
    img = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((8, 6, 36, 40), fill=(200, 160, 60, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class FakeResponse:
    def __init__(self, status: int):
        self.status_code, self.content = status, _icon()

    def raise_for_status(self) -> None:
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, fail: str = "") -> None:
        self.fail, self.urls = fail, []  # type: ignore[var-annotated]

    def get(self, url: str) -> FakeResponse:
        self.urls.append(url)
        return FakeResponse(404 if self.fail and self.fail in url else 200)


def test_every_set_has_an_icon_and_reference_data() -> None:
    assert set(ICONS.values()) <= set(GearSet)
    sets = load("sets")
    for gear_set in ICONS.values():
        info = sets[gear_set.value]
        assert info["en"] and info["pieces"] in (2, 4) and info["effect_en"]
    assert sets["protection"]["pieces"] == 4


def test_downloads_tight_shields_once(tmp_path: Path) -> None:
    client = FakeClient()
    added = fetch_set_icons(tmp_path, client)
    assert len(added) == len(ICONS) and not missing(tmp_path)
    with Image.open(tmp_path / "speed.png") as shield:
        assert shield.mode == "RGB" and shield.size == (29, 35)  # recadré sur le dessin
    assert fetch_set_icons(tmp_path, client) == [] and len(client.urls) == len(ICONS)


def test_learned_shield_is_kept_and_errors_are_skipped(tmp_path: Path) -> None:
    learned = Image.new("RGB", (30, 30), (1, 2, 3))
    learned.save(tmp_path / "speed.png")
    added = fetch_set_icons(tmp_path, FakeClient(fail="icon_set_att."))
    assert "speed" not in added and "attack" not in added and len(added) == len(ICONS) - 2
    with Image.open(tmp_path / "speed.png") as kept:
        assert kept.getpixel((0, 0)) == (1, 2, 3)
    assert missing(tmp_path) == ["att"]
