"""Fiche de profil du jeu : OCR réel anonymisé → pseudo, serveur, guilde, rang, cadre."""

from __future__ import annotations

import json
from pathlib import Path

from e7showcase.parsers.profile_card import parse_profile_card
from e7showcase.vision.ocr import OcrLine

FIXTURE = Path(__file__).parent / "fixtures" / "profile_card_ocr.json"


def lines() -> list[OcrLine]:
    rows = json.loads(FIXTURE.read_text("utf-8"))
    return [OcrLine(t, c, b[1], (b[0], b[1], b[2], b[3])) for t, c, b in rows]


def test_parse_profile_card() -> None:
    card = parse_profile_card(lines())
    assert card is not None
    assert (card.player, card.server, card.guild, card.rank) == ("Joueur1", "europe", "Alpha", 20)
    x, y, r = card.avatar  # cadre de profil : à gauche du blason de guilde, à hauteur du pseudo
    assert 960 < x < 1000 and 170 < y < 210 and 110 < r < 135


def test_parse_profile_card_rejects_other_screens() -> None:
    assert parse_profile_card([OcrLine("Guerre", 0.9, 10, (10, 10, 90, 40))]) is None
