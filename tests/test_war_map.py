"""Écrans de guerre : carte (guildes, forteresses) et forteresse (joueurs), OCR réel anonymisé."""

from __future__ import annotations

import json
from pathlib import Path

from e7showcase.parsers.war_map import parse_fortress, parse_war_map
from e7showcase.vision.ocr import OcrLine

FIX = Path(__file__).parent / "fixtures"
SIZE = (2000, 1125)


def lines(name: str) -> list[OcrLine]:
    rows = json.loads((FIX / name).read_text("utf-8"))
    return [OcrLine(t, c, b[1], (b[0], b[1], b[2], b[3])) for t, c, b in rows]


def test_parse_war_map_reads_both_guilds_and_fortresses() -> None:
    m = parse_war_map(lines("gvg_war_map_ocr.json"), SIZE)
    assert m is not None and m.ends_in == "dans 15h"
    assert (m.ours.name, m.ours.server, m.ours.ravage) == ("Alpha", "Europe", 1800)
    assert m.ours.tickets == (63, 81) and m.ours.members == (27, 27)
    assert (m.enemy.name, m.enemy.server, m.enemy.ravage) == ("Omega", "Global", 840)
    assert m.enemy.tickets == (62, 69) and m.enemy.members == (23, 23)
    assert [(f.name, f.left, f.total) for f in m.fortresses] == [
        ("Forteresse Dard", 10, 10),
        ("Forteresse Foret sombre", 7, 7),
        ("Forteresse Tourbillon", 6, 6),
    ]
    assert 0.3 < m.fortresses[0].x < 0.4 and 0.5 < m.fortresses[0].y < 0.6


def test_parse_fortress_keeps_only_player_names() -> None:
    players = parse_fortress(lines("gvg_fortress_ocr.json"), SIZE)
    assert sorted(p.name for p in players) == sorted(f"Joueur{i}" for i in range(1, 11))
    top = players[0]
    assert top.name == "Joueur1" and 0.6 < top.x < 0.7 and 0.25 < top.y < 0.3
    assert (
        parse_war_map(lines("gvg_fortress_ocr.json"), SIZE) is None
        or not parse_war_map(lines("gvg_fortress_ocr.json"), SIZE).fortresses
    )  # type: ignore[union-attr]
