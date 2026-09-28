"""Dérive un profil de zones pour un autre format d'écran à partir d'un profil calibré.

L'interface d'Epic Seven garde la même hauteur relative et ancre ses panneaux aux bords :
un élément ancré à gauche garde sa distance au bord gauche (en unités de hauteur), idem à
droite ; les éléments centraux restent centrés. Le résultat est une ESTIMATION à vérifier
sur de vraies captures (skill `calibrate-ocr-regions`).

    python scripts/derive_profile.py config/regions/19_5x9.toml 1.7778 > config/regions/16x9.toml
"""

from __future__ import annotations

import sys
import tomllib
from typing import Any

# Ancrage horizontal de chaque zone (défaut : gauche)
ANCHORS = {
    "detail.artifact": "right",
    "detail.gear_score": "right",
    "detail.gear": "right",
    "navigation.next_hero": "right",
    "navigation.detail_button": "center",
    "hero_list.title_hint": "center",
}


def convert_x(x: float, k: float, anchor: str) -> float:
    if anchor == "right":
        return 1 - (1 - x) * k
    if anchor == "center":
        return 0.5 + (x - 0.5) * k
    return x * k


def derive(cfg: dict[str, Any], aspect: float) -> dict[str, Any]:
    k = cfg["aspect"] / aspect
    out: dict[str, Any] = {"aspect": round(aspect, 4)}
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
                lay = {}
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


def dump(cfg: dict[str, Any], source: str) -> str:
    lines = [
        f"# ESTIMATION dérivée de {source} par scripts/derive_profile.py — NON VÉRIFIÉE.",
        "# À calibrer sur de vraies captures (skill `calibrate-ocr-regions`).",
        "",
    ]

    def fmt(v: Any) -> str:
        if isinstance(v, list):
            return "[" + ", ".join(fmt(x) for x in v) + "]"
        return str(v)

    lines.append(f"aspect = {cfg['aspect']}")
    for section, body in cfg.items():
        if not isinstance(body, dict):
            continue
        simple = {k: v for k, v in body.items() if not isinstance(v, dict)}
        lines += ["", f"[{section}]"] + [f"{k} = {fmt(v)}" for k, v in simple.items()]
        for key, sub in body.items():
            if isinstance(sub, dict):
                lines += ["", f"[{section}.{key}]"] + [f"{k} = {fmt(v)}" for k, v in sub.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    src, aspect = sys.argv[1], float(sys.argv[2])
    with open(src, "rb") as f:
        print(dump(derive(tomllib.load(f), aspect), src), end="")
