"""Détermination des sets actifs à partir des pièces portées."""

from __future__ import annotations

from collections import Counter

from e7showcase.models.gear import Gear
from e7showcase.reference import set_pieces


def active_sets(gear: list[Gear]) -> list[str]:
    """Retourne les sets actifs, un élément par bonus (ex: ['speed', 'critical'])."""
    counts = Counter(g.set.value for g in gear if g.set is not None)
    result: list[str] = []
    for set_name, count in sorted(counts.items(), key=lambda kv: (-set_pieces(kv[0]), kv[0])):
        result.extend([set_name] * (count // set_pieces(set_name)))
    return result
