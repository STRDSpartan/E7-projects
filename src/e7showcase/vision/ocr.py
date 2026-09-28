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
    box: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1) en pixels


class OcrEngine(Protocol):
    def read_lines(self, image: Image.Image) -> list[OcrLine]: ...

    def read_text(self, image: Image.Image) -> str:
        """Reconnaissance d'une seule ligne (pas de détection) : rapide et précise."""
        ...

    def read_boxes(self, image: Image.Image) -> list[OcrLine]:
        """Blocs de texte détectés avec leur boîte, sans fusion des lignes."""
        ...


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        import numpy as np

        result, _ = self._ocr(np.array(image.convert("RGB")), use_cls=False)
        lines = [OcrLine(text, float(conf), float(box[0][1])) for box, text, conf in (result or [])]
        return _merge_rows(sorted(lines, key=lambda line: line.y))

    def read_text(self, image: Image.Image) -> str:
        import numpy as np

        result, _ = self._ocr(np.array(image.convert("RGB")), use_det=False, use_cls=False)
        return str(result[0][0]).strip() if result else ""

    def read_boxes(self, image: Image.Image) -> list[OcrLine]:
        import numpy as np

        result, _ = self._ocr(np.array(image.convert("RGB")), use_cls=False)
        return [
            OcrLine(
                text,
                float(conf),
                float(box[0][1]),
                (float(box[0][0]), float(box[0][1]), float(box[2][0]), float(box[2][1])),
            )
            for box, text, conf in (result or [])
        ]


class TesseractEngine:
    def __init__(self, lang: str = "fra+eng") -> None:
        import pytesseract

        self._tess = pytesseract
        self._lang = lang

    def read_lines(self, image: Image.Image) -> list[OcrLine]:
        text = self._tess.image_to_string(for_ocr(image), lang=self._lang, config="--psm 6")
        return [OcrLine(t, 1.0, float(i)) for i, t in enumerate(text.splitlines()) if t.strip()]

    def read_text(self, image: Image.Image) -> str:
        return str(
            self._tess.image_to_string(for_ocr(image), lang=self._lang, config="--psm 7")
        ).strip()

    def read_boxes(self, image: Image.Image) -> list[OcrLine]:
        tess = self._tess
        data = tess.image_to_data(image, lang=self._lang, output_type=tess.Output.DICT)
        rows: dict[tuple[int, int, int], list[int]] = {}
        for i, word in enumerate(data["text"]):
            if word.strip():
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                rows.setdefault(key, []).append(i)
        out = []
        for idx in rows.values():
            x0 = min(data["left"][i] for i in idx)
            y0 = min(data["top"][i] for i in idx)
            x1 = max(data["left"][i] + data["width"][i] for i in idx)
            y1 = max(data["top"][i] + data["height"][i] for i in idx)
            text = " ".join(data["text"][i] for i in idx)
            out.append(OcrLine(text, 1.0, float(y0), (float(x0), float(y0), float(x1), float(y1))))
        return out


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
