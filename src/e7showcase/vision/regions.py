"""Découpage des captures selon les ROI normalisées."""

from __future__ import annotations

from PIL import Image

Box = tuple[int, int, int, int]


def to_pixels(norm: list[float], size: tuple[int, int]) -> Box:
    x, y, w, h = norm
    width, height = size
    return (round(x * width), round(y * height), round((x + w) * width), round((y + h) * height))


def crop(image: Image.Image, norm: list[float]) -> Image.Image:
    return image.crop(to_pixels(norm, image.size))


def center(norm: list[float], size: tuple[int, int]) -> tuple[int, int]:
    left, top, right, bottom = to_pixels(norm, size)
    return ((left + right) // 2, (top + bottom) // 2)
