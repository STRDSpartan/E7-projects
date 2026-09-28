"""Classifieur d'icônes sur des glyphes synthétiques (aucune image du jeu)."""

import pytest
from PIL import Image, ImageDraw

pytest.importorskip("cv2")

from e7showcase.vision.icons import IconClassifier, set_features  # noqa: E402


def glyph(kind: str, size: int = 40, bg: int = 20, fg: int = 230, offset: int = 0) -> Image.Image:
    img = Image.new("RGB", (size + 10, size + 6), (bg, bg, bg + 10))
    d = ImageDraw.Draw(img)
    o = 5 + offset
    box = (o, 3, o + size - 1, size + 2)
    if kind == "circle":
        d.ellipse(box, outline=(fg,) * 3, width=5)
    elif kind == "square":
        d.rectangle(box, outline=(fg,) * 3, width=5)
    elif kind == "triangle":
        d.polygon([(o + size // 2, 3), (o, size + 2), (o + size, size + 2)], fill=(fg,) * 3)
    elif kind == "cross":
        d.line((o, 3, o + size, size + 2), fill=(fg,) * 3, width=7)
        d.line((o + size, 3, o, size + 2), fill=(fg,) * 3, width=7)
    return img


KINDS = ["circle", "square", "triangle", "cross"]


def test_recognizes_dimmer_shifted_smaller_icons() -> None:
    clf = IconClassifier()
    for kind in KINDS:
        clf.add(kind, glyph(kind))
    for kind in KINDS:
        # icône de stat secondaire : plus petite, plus terne, décalée
        label, score = clf.predict(glyph(kind, size=32, fg=150, offset=3))
        assert label == kind, (kind, clf.scores(glyph(kind, size=32, fg=150, offset=3)))
        assert score > 0.7


def test_unknown_icon_below_threshold() -> None:
    clf = IconClassifier()
    clf.add("circle", glyph("circle"))
    assert clf.predict(Image.new("RGB", (40, 40), (20, 20, 30)), min_score=0.9)[0] is None


def test_library_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    clf = IconClassifier(extractor=set_features)
    clf.save(tmp_path, "speed", glyph("triangle"))
    loaded = IconClassifier.load(tmp_path, set_features)
    assert loaded.predict(glyph("triangle"))[0] == "speed"
