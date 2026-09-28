from pathlib import Path

from e7showcase.importers.fribbels import import_file
from e7showcase.render.showcase import render_html, render_showcase
from e7showcase.storage.repository import RosterRepository

FIXTURE = Path(__file__).parent / "fixtures" / "fribbels_export.json"


def test_roundtrip(tmp_path: Path) -> None:
    repo = RosterRepository(tmp_path / "roster.json")
    roster = import_file(FIXTURE, player="Tester")
    repo.save(roster)
    loaded = repo.load()
    assert loaded.heroes[0].stats.defense == 1100
    assert loaded.heroes[0].gear == roster.heroes[0].gear


def test_render_html_contains_hero_data() -> None:
    roster = import_file(FIXTURE, player="Tester")
    html = render_html(roster)
    assert "Ras" in html and "Tester" in html and "Vitesse" in html and "GS" in html


def test_render_html_files(tmp_path: Path) -> None:
    roster = import_file(FIXTURE, player="Tester")
    paths = render_showcase(roster, tmp_path, layout="grid", png=False)
    assert paths and paths[0].suffix == ".html"
