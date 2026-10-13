"""Repli pur Python de la correspondance approximative (portage mobile, sans rapidfuzz)."""

from __future__ import annotations

import builtins
import importlib
import sys
from typing import Any


def test_fallback_without_rapidfuzz(monkeypatch: Any) -> None:
    real = builtins.__import__

    def no_rapidfuzz(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("rapidfuzz"):
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_rapidfuzz)
    monkeypatch.delitem(sys.modules, "e7showcase.fuzzy", raising=False)
    fuzzy = importlib.import_module("e7showcase.fuzzy")
    try:
        assert fuzzy.fuzz.ratio("Attaque", "Attaque") == 100
        m = fuzzy.process.extractOne("Atack", ["Défense", "Attaque", "PV"], scorer=fuzzy.fuzz.ratio)
        assert m is not None and m[0] == "Attaque" and m[2] == 1
        assert (
            fuzzy.process.extractOne("zzz", ["Attaque"], scorer=fuzzy.fuzz.ratio, score_cutoff=80)
            is None
        )
        w = fuzzy.process.extractOne("Ras", ["Ruele", "Ras chevalier"], scorer=fuzzy.fuzz.WRatio)
        assert w is not None and w[0] == "Ras chevalier"
    finally:
        monkeypatch.undo()
        sys.modules.pop("e7showcase.fuzzy", None)
        importlib.import_module("e7showcase.fuzzy")
