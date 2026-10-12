"""Lecture d'une capture de résultat de GvG : héros adverses reconnus et leurs stats.

Le texte (stats) vient de l'OCR, les héros de leurs portraits comparés aux icônes de visage
(`vision.hero_faces`). Le résultat est proposé au joueur, qui corrige un nom si besoin avant
de tester ses équipes contre cette défense dans le simulateur.
"""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image

from e7showcase.parsers.battle_report import STAT_ROWS, parse_report
from e7showcase.reference import load
from e7showcase.vision.hero_faces import FaceMatcher, locate

CONFIDENT = 0.80  # score au-delà duquel le héros est considéré comme reconnu
MAX_SIDE = 2600  # px : les captures plus grandes sont réduites avant lecture


def code_names() -> dict[str, str]:
    """Code d'icône (héros ou skin) → nom du héros."""
    names: dict[str, str] = {}
    for h in load("heroes")["heroes"]:
        name = h.get("fr") or h.get("en") or h["code"]
        names[h["code"]] = name
        for skin in h.get("skins") or []:
            names.setdefault(skin["code"], name)
    return names


def _thumb(image: Image.Image, x: float, y: float, r: float) -> str:
    crop = image.crop((x - r, y - r, x + r, y + r)).convert("RGB").resize((72, 72))
    buf = io.BytesIO()
    crop.save(buf, "WEBP", quality=80)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def read_capture(data: bytes, engine: Any) -> tuple[Image.Image, list[Any]]:
    """Image (réduite si très grande) et boîtes de texte de l'OCR d'une capture."""
    try:
        with Image.open(io.BytesIO(data)) as src:
            image = src.convert("RGB")
    except OSError as exc:
        raise ValueError(
            "fichier illisible : envoyez une capture d'écran (PNG, JPG, WebP)"
        ) from exc
    if max(image.size) > MAX_SIDE:
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return image, engine.read_boxes(image)


def read_report(data: bytes, engine: Any, matcher: FaceMatcher) -> dict[str, Any]:
    image, lines = read_capture(data, engine)
    report = parse_report(lines)
    if report is None:
        raise ValueError(
            "capture non reconnue : utilisez l'écran de fin de combat de GvG montrant les "
            "deux équipes et leurs stats"
        )
    names = code_names()
    heroes = []
    for col in report.columns:
        circle = locate(image, col.x, col.hp_y, report.step)
        found = matcher.match(image, circle)
        candidates: list[dict[str, Any]] = []
        for code, score in found:  # un même héros (skins) n'apparaît qu'une fois
            name = names.get(code, code)
            if all(c["name"] != name for c in candidates):
                candidates.append({"name": name, "score": round(score, 3)})
        best = candidates[0] if candidates else None
        heroes.append(
            {
                "name": best["name"] if best else "",
                "confident": bool(best and best["score"] >= CONFIDENT),
                "candidates": candidates[:3],
                "stats": {k: col.values.get(k) for k in STAT_ROWS} if col.known else None,
                "hp": col.values.get("hp"),
                "portrait": _thumb(image, circle.x, circle.y, circle.r),
            }
        )
    sets: list[list[dict[str, Any]]] = [
        [
            {
                "heroes": [heroes[i] for i in team],
                "known": all(heroes[i]["stats"] for i in team),
            }
            for team in pair
        ]
        for pair in report.sets
    ]
    return {"sets": sets, "faces": matcher.count()}
