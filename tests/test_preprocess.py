"""Retrait de la barre de titre et de la barre des tâches (images synthétiques)."""

import pytest
from PIL import Image, ImageDraw

pytest.importorskip("numpy")

from e7showcase.vision.preprocess import strip_window_chrome  # noqa: E402


def desktop_capture(title: int = 23, taskbar: int = 48) -> Image.Image:
    """Capture « Impr. écran » simulée : titre clair, jeu sombre et détaillé, barre des tâches."""
    img = Image.new("RGB", (1919, 1079), (18, 22, 40))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 1918, title - 1), fill=(243, 243, 243))
    d.text((30, 5), "Epic Seven", fill=(30, 30, 30))
    for x in range(0, 1919, 160):  # contenu du jeu
        d.rectangle((x, 200, x + 80, 700), fill=(120, 60, 200))
    d.rectangle((0, 1079 - taskbar, 1918, 1078), fill=(112, 108, 108))
    return img


def test_strips_title_bar_and_taskbar() -> None:
    out = strip_window_chrome(desktop_capture())
    assert out.size == (1919, 1079 - 23 - 48)


def test_client_area_capture_unchanged() -> None:
    client = desktop_capture().crop((0, 23, 1919, 1031))
    assert strip_window_chrome(client).size == client.size


def test_small_image_unchanged() -> None:
    img = Image.new("RGB", (300, 200), (240, 240, 240))
    assert strip_window_chrome(img) is img
