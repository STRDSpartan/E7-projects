"""Précision sur de vraies captures, si l'utilisateur en fournit localement.

    E7_TEST_CAPTURES=/chemin/vers/captures pytest tests/test_real_captures.py

Le dossier n'est jamais committé (captures et roster réels) ; voir scripts/evaluate_captures.py.
"""

import os
import sys
from pathlib import Path

import pytest

CAPTURES = os.environ.get("E7_TEST_CAPTURES")
pytestmark = pytest.mark.skipif(not CAPTURES, reason="E7_TEST_CAPTURES non défini")


def test_precision_on_real_captures() -> None:
    pytest.importorskip("rapidocr_onnxruntime")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from evaluate_captures import evaluate

    ok, total = evaluate(Path(str(CAPTURES)), verbose=False)
    assert ok / total >= 0.95, f"précision {ok}/{total}"
