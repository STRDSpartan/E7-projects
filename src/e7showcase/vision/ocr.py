"""Abstraction du moteur OCR (RapidOCR par défaut, Tesseract en option)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from e7showcase.vision.preprocess import for_ocr


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    y: float  # position verticale, pour trier les lignes


class OcrEngine(Protocol):
    def read_lines(self, image: Image.Image) -> list[OcrLine]: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        import numpy as np

        result, _ = self._ocr(np.array(for_ocr(image, threshold=None).convert("RGB")))
        lines = [OcrLine(text, float(conf), float(box[0][1])) for box, text, conf in (result or [])]
        return _merge_rows(sorted(lines, key=lambda line: line.y))


class TesseractEngine:
    def __init__(self, lang: str = "fra+eng") -> None:
        import pytesseract

        self._tess = pytesseract
        self._lang = lang

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        text = self._tess.image_to_string(for_ocr(image), lang=self._lang, config="--psm 6")
        return [OcrLine(t, 1.0, float(i)) for i, t in enumerate(text.splitlines()) if t.strip()]


def _merge_rows(lines: list[OcrLine], tolerance: float = 12) -> list[OcrLine]:
    """Fusionne libellé et valeur détectés séparément sur une même ligne visuelle."""
    merged: list[OcrLine] = []
    for line in lines:
        if merged and abs(merged[-1].y - line.y) <= tolerance:
            prev = merged[-1]
            merged[-1] = OcrLine(
                f"{prev.text} {line.text}", min(prev.confidence, line.confidence), prev.y
            )
        else:
            merged.append(line)
    return merged


def get_engine(backend: str = "rapidocr") -> OcrEngine:
    if backend == "tesseract":
        return TesseractEngine()
    return RapidOcrEngine()
