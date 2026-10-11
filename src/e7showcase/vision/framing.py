"""Recadrage d'une fiche « Infos de héros » sur la zone du jeu, à l'aide de repères à l'écran.

Le retrait des barres Windows (`preprocess.strip_window_chrome`) repose sur un contraste net ;
il ne voit ni une barre de titre en thème sombre, ni les marges d'une sélection Win+Maj+S.
Ici on cherche le titre « Infos de héros » (taille et position connues dans le jeu) : sa largeur
donne l'échelle, son centre le haut du jeu, son début le bord gauche ; le texte « Score moyen
d'équipements », ancré à droite, donne le bord droit.
"""

from __future__ import annotations

import re
from typing import Any

from PIL import Image

from e7showcase.reference import normalize

MIN_SHIFT = 0.004  # décalage (fraction de la hauteur) en dessous duquel on ne recadre pas


def _find(ocr: Any, image: Image.Image, box: tuple[int, int, int, int], word: str) -> Any:
    for line in ocr.read_boxes(image.crop(box)):
        if word in normalize(line.text):
            x0, y0, x1, y1 = line.box
            return (x0 + box[0], y0 + box[1], x1 + box[0], y1 + box[1], line.text)
    return None


def frame_detail(image: Image.Image, ocr: Any, landmarks: dict[str, float]) -> Image.Image | None:
    """Image recadrée sur le jeu, ou None (pas une fiche, ou déjà bien cadrée)."""
    w, h = image.size
    title = _find(ocr, image, (0, 0, w // 2, int(h * 0.3)), "infos")
    if title is None:
        return None
    x0, y0, x1, y1, _ = title
    title_y = (y0 + y1) / 2
    game_h = (x1 - x0) / landmarks["title_width"]  # échelle approchée (±1,5 %)
    if not 0.5 * h < game_h < 1.3 * h:  # texte mal lu : échelle invraisemblable
        return None
    lefts = [x0 - landmarks["title_left"] * game_h]
    # Échelle précise : écart vertical titre → « Chances de double attaque » (~0,73 hauteur)
    approx_dual = title_y + (landmarks["dual_center_y"] - landmarks["title_center_y"]) * game_h
    dual_band = (
        0,
        int(approx_dual - 0.08 * game_h),
        w // 2,
        min(h, int(approx_dual + 0.08 * game_h)),
    )
    if dual_band[1] < dual_band[3] and (dual := _find(ocr, image, dual_band, "double")):
        game_h = ((dual[1] + dual[3]) / 2 - title_y) / (
            landmarks["dual_center_y"] - landmarks["title_center_y"]
        )
        lefts = [x0 - landmarks["title_left"] * game_h, dual[0] - landmarks["dual_left"] * game_h]
    top = title_y - landmarks["title_center_y"] * game_h
    left = sum(lefts) / len(lefts)
    bottom = top + game_h
    right = float(w)
    score_band = (int(w * 0.4), int(top + 0.2 * game_h), w, int(top + 0.4 * game_h))
    if score_band[1] < score_band[3] and (score := _find(ocr, image, score_band, "score")):
        # fin du texte (le début inclut parfois l'icône) ; un chiffre de plus décale la fin
        digits = len(re.sub(r"\D", "", str(score[4]).split(":")[-1])) or 2
        end_gap = landmarks["score_end_to_right"] - (digits - 2) * landmarks["score_digit_width"]
        right = score[2] + end_gap * game_h
    box = (max(0.0, left), max(0.0, top), min(float(w), right), min(float(h), bottom))
    shifts = (box[0], box[1], w - box[2], h - box[3])
    if all(abs(s) < MIN_SHIFT * h for s in shifts):
        return None
    return image.crop((round(box[0]), round(box[1]), round(box[2]), round(box[3])))
