"""Correspondance approximative : rapidfuzz si disponible, sinon repli en pur Python (difflib).

Le repli sert au portage mobile (Android, iOS), où rapidfuzz n'a pas de version binaire.
Seules les fonctions utilisées par le projet sont fournies : `fuzz.ratio`, `fuzz.WRatio` et
`process.extractOne` (renvoie `(choix, score, index)` ou None).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from difflib import SequenceMatcher
from types import SimpleNamespace
from typing import Any

try:  # pragma: no cover - dépend de l'installation
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover - exercé par test_fuzzy

    def _ratio(a: str, b: str, **_: Any) -> float:
        if not a and not b:
            return 100.0
        return 100.0 * SequenceMatcher(None, a, b).ratio()

    def _wratio(a: str, b: str, **_: Any) -> float:
        a, b = a.lower().strip(), b.lower().strip()
        base = _ratio(a, b)
        short, long_ = sorted((a, b), key=len)
        if short and len(long_) > 1.5 * len(short):  # correspondance partielle (sous-chaîne)
            n = len(short)
            best = max(
                (_ratio(short, long_[i : i + n]) for i in range(len(long_) - n + 1)), default=0.0
            )
            base = max(base, best * 0.9)
        tokens = _ratio(" ".join(sorted(a.split())), " ".join(sorted(b.split()))) * 0.95
        return max(base, tokens)

    def _extract_one(
        query: str,
        choices: Iterable[str],
        *,
        scorer: Callable[..., float] = _wratio,
        score_cutoff: float = 0,
        **_: Any,
    ) -> tuple[str, float, int] | None:
        best: tuple[str, float, int] | None = None
        for i, choice in enumerate(choices):
            score = scorer(query, choice)
            if score >= score_cutoff and (best is None or score > best[1]):
                best = (choice, score, i)
        return best

    fuzz = SimpleNamespace(ratio=_ratio, WRatio=_wratio)  # type: ignore[assignment]
    process = SimpleNamespace(extractOne=_extract_one)  # type: ignore[assignment]

__all__ = ["fuzz", "process"]
