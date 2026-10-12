"""Écran de résultat d'un combat de GvG : colonnes de stats des héros des deux camps.

Après une victoire, le jeu montre pour chaque set les deux équipes côte à côte ; sous chaque
portrait, une colonne de 9 valeurs dans cet ordre : attaque, défense, PV, vitesse, chances
de critique, dégâts critiques, efficacité, résistance, attaque double. Les héros dont les
stats sont cachées n'affichent que leurs PV (« ? » ailleurs).

Le découpage s'appuie uniquement sur les boîtes de l'OCR (aucune position figée) : la ligne
des PV (nombres ≥ 1 000 alignés) donne les colonnes et l'échelle, l'écart entre colonnes
sépare les équipes. Fonctions pures, sans I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

from e7showcase.vision.ocr import OcrLine

STAT_ROWS = (
    "atk",
    "def",
    "hp",
    "spd",
    "crit_chance",
    "crit_dmg",
    "effectiveness",
    "effect_res",
    "dual_attack",
)
HP_ROW = STAT_ROWS.index("hp")
PERCENT = {"crit_chance", "crit_dmg", "effectiveness", "effect_res", "dual_attack"}
_CELL_RE = re.compile(r"^(\?|\d{1,6}(?:[.,]\d{1,2})?)(%?)$")
# maximum plausible par ligne : au-delà, l'icône de la stat a été lue comme un chiffre en tête
# (ex. « 23.0% » pour 3.0 % d'attaque double, qui ne vient pas de l'équipement)
PLAUSIBLE_MAX = {"crit_chance": 100.0, "dual_attack": 15.0}
TEAM_GAP = 1.6  # écart entre colonnes au-delà duquel une nouvelle équipe commence


@dataclass
class Column:
    x: float  # bord gauche des valeurs (px)
    hp_y: float
    values: dict[str, float | None] = field(default_factory=dict)

    @property
    def known(self) -> bool:
        """Stats lisibles (pas seulement les PV)."""
        return all(self.values.get(k) is not None for k in ("atk", "def", "hp", "spd"))


@dataclass
class Report:
    columns: list[Column]
    step: float  # hauteur d'une ligne de stats (px), sert d'échelle
    teams: list[list[int]]  # indices de colonnes, de gauche à droite

    @property
    def sets(self) -> list[list[list[int]]]:
        """Équipes regroupées par set (deux équipes face à face)."""
        return [self.teams[i : i + 2] for i in range(0, len(self.teams), 2)]


def _cell(text: str) -> tuple[float | None, bool] | None:
    """Valeur d'une cellule (None si « ? ») et présence de « % » ; None si ce n'en est pas une."""
    t = text.replace("？", "?").replace(" ", "")
    t = re.sub(r"[^0-9.,%?]", "", t)  # icônes de stat lues comme des caractères parasites
    m = _CELL_RE.match(t)
    if not m:
        return None
    raw, pct = m.groups()
    return (None if raw == "?" else float(raw.replace(",", "."))), bool(pct)


def _plausible(key: str, value: float | None, text: str) -> float | None:
    limit = PLAUSIBLE_MAX.get(key)
    if value is None or limit is None or value <= limit:
        return value
    digits = re.sub(r"[^0-9.,]", "", text)[1:]
    try:
        fixed = float(digits.replace(",", "."))
    except ValueError:
        return value
    return fixed if fixed <= limit else value


def _center(b: OcrLine) -> tuple[float, float]:
    assert b.box is not None
    x0, y0, x1, y1 = b.box
    return (x0 + x1) / 2, (y0 + y1) / 2


def parse_report(lines: list[OcrLine]) -> Report | None:
    cells = []
    for b in lines:
        if b.box is None or (c := _cell(b.text)) is None:
            continue
        cells.append((b, c))
    big = [(b, v) for b, (v, pct) in cells if v is not None and not pct and v >= 1000]
    if len(big) < 2:
        return None
    heights = [b.box[3] - b.box[1] for b, _ in cells if b.box]
    tol = 0.5 * median(heights)
    # ligne des PV : la rangée de grands nombres qui en compte le plus
    rows: list[list[tuple[OcrLine, float]]] = []
    for b, v in sorted(big, key=lambda t: _center(t[0])[1]):
        if rows and abs(_center(b)[1] - median(_center(r)[1] for r, _ in rows[-1])) <= tol:
            rows[-1].append((b, v))
        else:
            rows.append([(b, v)])
    hp_row = max(rows, key=len)
    if len(hp_row) < 2:
        return None
    hp_y = median(_center(b)[1] for b, _ in hp_row)
    lefts = sorted(b.box[0] for b, _ in hp_row if b.box)
    widths = [b.box[2] - b.box[0] for b, _ in hp_row if b.box]
    col_tol = 0.6 * median(widths)
    # hauteur de ligne : écarts verticaux entre cellules d'une même colonne
    diffs: list[float] = []
    for x in lefts:
        ys = sorted(_center(b)[1] for b, _ in cells if b.box and abs(b.box[0] - x) <= col_tol)
        diffs += [d for a, c in zip(ys, ys[1:], strict=False) if tol < (d := c - a) < 6 * tol]
    step = median(diffs) if diffs else 2.2 * tol
    columns = [Column(x=x, hp_y=hp_y) for x in lefts]
    for b, (val, pct) in cells:
        assert b.box is not None
        col = min(columns, key=lambda c: abs(c.x - b.box[0]))  # type: ignore[index]
        if abs(col.x - b.box[0]) > col_tol:
            continue
        row = round((_center(b)[1] - hp_y) / step) + HP_ROW
        if not 0 <= row < len(STAT_ROWS):
            continue
        key = STAT_ROWS[row]
        if (key in PERCENT) != pct and val is not None:
            continue  # ex. « +15 » d'un équipement, ou « ?% » mal lu
        col.values.setdefault(key, _plausible(key, val, b.text))
    for col in columns:  # « ?% » lu « 2% » : sans attaque ni défense, rien n'est fiable
        if not col.known:
            col.values = {k: (col.values.get(k) if k == "hp" else None) for k in STAT_ROWS}
    gaps = [b - a for a, b in zip(lefts, lefts[1:], strict=False)]
    unit = min(gaps) if gaps else 0
    teams: list[list[int]] = [[0]]
    for i, g in enumerate(gaps, start=1):
        if g > TEAM_GAP * unit:
            teams.append([])
        teams[-1].append(i)
    return Report(columns=columns, step=step, teams=teams)
