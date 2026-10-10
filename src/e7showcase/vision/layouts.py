"""Zones de lecture pour n'importe quel format d'écran.

L'interface d'Epic Seven garde ses proportions verticales et ancre ses panneaux : à gauche
(stats, nom), à droite (équipement, artefact) ou au centre (pose, boutons). Un profil calibré
sur de vraies captures se transpose donc à un autre format (16:9, 16:10, 21:9, fenêtre
agrandie, mobile 20:9...) : les distances horizontales sont conservées en unités de hauteur
depuis le bord d'ancrage. La taille en pixels, elle, ne compte pas (zones normalisées) ; les
captures sont seulement remises à une hauteur de référence pour fiabiliser l'OCR.
"""

from __future__ import annotations

from typing import Any

from PIL import Image

# Ancrage horizontal de chaque zone (défaut : gauche)
ANCHORS = {
    "detail.artifact": "right",
    "detail.portrait": "center",
    "detail.gear_score": "right",
    "detail.gear": "right",
    "navigation.next_hero": "right",
    "navigation.detail_button": "center",
    "hero_list.title_hint": "center",
}
REFERENCE_HEIGHT = 1009  # hauteur de la calibration PC (zone cliente 1919x1009), par défaut
SCALE_TOLERANCE = 0.02  # au-delà de ±2 % de la hauteur de calibration : remise à l'échelle
SAME_FORMAT = 0.01  # écart de format sous lequel le profil calibré est pris tel quel


def convert_x(x: float, k: float, anchor: str) -> float:
    if anchor == "right":
        return 1 - (1 - x) * k
    if anchor == "center":
        return 0.5 + (x - 0.5) * k
    return x * k


def derive(cfg: dict[str, Any], aspect: float) -> dict[str, Any]:
    """Transpose un profil vers un autre format (largeur / hauteur)."""
    k = float(cfg["aspect"]) / aspect
    out: dict[str, Any] = {
        "aspect": round(aspect, 4),
        "derived_from": cfg.get("name"),
        "reference_height": cfg.get("reference_height", REFERENCE_HEIGHT),
    }
    for section, body in cfg.items():
        if not isinstance(body, dict):
            continue
        out[section] = {}
        for key, value in body.items():
            anchor = ANCHORS.get(f"{section}.{key}", "left")
            if key == "gear":
                out[section][key] = {
                    s: [round(convert_x(x, k, "right"), 4), y] for s, (x, y) in value.items()
                }
            elif key == "gear_layout":
                lay: dict[str, Any] = {}
                for lk, lv in value.items():
                    if lk in ("icon_w", "values_dx", "values_w"):
                        lay[lk] = round(lv * k, 4)
                    elif isinstance(lv, list) and len(lv) == 4 and lk not in ("line_dy", "line_h"):
                        lay[lk] = [round(lv[0] * k, 4), lv[1], round(lv[2] * k, 4), lv[3]]
                    else:
                        lay[lk] = lv
                out[section][key] = lay
            elif key == "set_rows":
                out[section][key] = [
                    [round(r[0] * k, 4), r[1], round(r[2] * k, 4), r[3], round(r[4] * k, 4)]
                    for r in value
                ]
            elif isinstance(value, list) and len(value) == 4:
                x, y, w, h = value
                out[section][key] = [round(convert_x(x, k, anchor), 4), y, round(w * k, 4), h]
            else:
                out[section][key] = value
    return out


def candidate_layouts(profiles: dict[str, dict[str, Any]], aspect: float) -> list[dict[str, Any]]:
    """Profils calibrés transposés au format exact, du plus proche au plus éloigné."""
    calibrated = [
        {**cfg, "name": name} for name, cfg in profiles.items() if cfg.get("calibrated")
    ] or [{**cfg, "name": name} for name, cfg in profiles.items()]
    calibrated.sort(key=lambda c: abs(float(c["aspect"]) - aspect))
    return [
        c if abs(float(c["aspect"]) - aspect) < SAME_FORMAT else derive(c, aspect)
        for c in calibrated
    ]


def normalize_scale(image: Image.Image, layout: dict[str, Any] | None = None) -> Image.Image:
    """Remet la capture à la hauteur des captures de calibration du profil (720p, 1440p, 4K...).

    Mesuré sur captures réelles : sans cela, une capture 1440p tombe à ~50 % de valeurs justes ;
    avec, 720p → 4K restent à 99,5-100 %.
    """
    target = int((layout or {}).get("reference_height", REFERENCE_HEIGHT))
    if abs(image.height - target) <= target * SCALE_TOLERANCE:
        return image
    size = (max(1, round(image.width * target / image.height)), target)
    return image.resize(size, Image.Resampling.LANCZOS)
