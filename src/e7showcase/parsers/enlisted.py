"""Liste des héros enrôlés dans l'Héritage des temps anciens (HTA), lue sur une capture.

L'écran d'enrôlement affiche le nom de chaque héros enrôlé. Chaque boîte de texte de l'OCR est
comparée aux noms du roster du joueur : seuls les héros qu'il possède peuvent être reconnus,
ce qui écarte le bruit (boutons, niveaux, titres). Le résultat est proposé au joueur, qui le
corrige avant de l'enregistrer. Fonctions pures, sans I/O.
"""

from __future__ import annotations

from e7showcase.fuzzy import fuzz, process
from e7showcase.reference import normalize
from e7showcase.vision.ocr import OcrLine

MIN_LENGTH = 3  # boîtes plus courtes : chiffres, icônes, initiales
CUTOFF = 85.0  # ressemblance minimale (0-100) avec un nom du roster


def _key(text: str) -> str:
    return normalize(text).replace(" ", "")


def match_enlisted(lines: list[OcrLine], roster: list[str], cutoff: float = CUTOFF) -> list[str]:
    """Noms du roster reconnus dans les boîtes de texte, dans l'ordre de lecture, sans doublon."""
    choices = {_key(name): name for name in roster if _key(name)}
    if not choices:
        return []
    found: list[str] = []
    ordered = sorted(lines, key=lambda ln: (round(ln.y / 20), ln.box[0] if ln.box else 0.0))
    for line in ordered:
        key = _key(line.text)
        if len(key) < MIN_LENGTH:
            continue
        match = process.extractOne(key, list(choices), scorer=fuzz.ratio, score_cutoff=cutoff)
        if match and choices[match[0]] not in found:
            found.append(choices[match[0]])
    return found
