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

from e7showcase.vision.layouts import derive  # noqa: E402


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
