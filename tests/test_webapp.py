"""Vitrine web autonome (un fichier HTML) : données, sécurité, fonctionnement dans un navigateur."""

import json
import os
import re
from pathlib import Path

import pytest
from PIL import Image

from e7showcase.assets import AssetStore
from e7showcase.importers.fribbels import import_file
from e7showcase.models.hero import Hero
from e7showcase.models.roster import Roster
from e7showcase.render.webapp import build_payload, render_webapp, safe_json

FIXTURE = Path(__file__).parent / "fixtures" / "fribbels_export.json"
EVIL = "</script><script>alert('xss')</script>"


def _roster() -> Roster:
    roster = import_file(FIXTURE, player="Testeur")
    roster.heroes[0].tags = ["GvG-def", EVIL]
    roster.heroes.append(Hero(name="Kise", element="ice", role="thief", power=205138))
    return roster


def test_payload_contains_sortable_values_and_labels() -> None:
    payload = build_payload(_roster())
    assert payload["player"] == "Testeur" and len(payload["heroes"]) == 2
    ras = payload["heroes"][0]
    assert ras["spd_value"] == 250 and ras["element_key"] == "fire"
    assert set(ras["images"]) == {"face", "portrait", "artifact", "anim"}
    assert payload["heroes"][1]["power_value"] == 205138


def test_safe_json_cannot_close_the_script_tag() -> None:
    text = safe_json({"tag": EVIL})
    assert "</script>" not in text and "<" not in text
    assert json.loads(text)["tag"] == EVIL  # la donnée reste intacte une fois décodée


def test_single_self_contained_file(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "assets")
    (tmp_path / "assets" / "faces").mkdir(parents=True)
    Image.new("RGBA", (112, 112), (200, 100, 50, 255)).save(
        tmp_path / "assets" / "faces" / "c1006.png"
    )
    target = render_webapp(_roster(), tmp_path / "vitrine.html", store)
    html = target.read_text(encoding="utf-8")
    assert html.count("</script>") == 2  # uniquement les deux balises du gabarit
    assert not re.search(
        r'<(script|link|img)[^>]+(src|href)="https?://', html
    )  # aucune ressource externe
    assert "data:image/webp;base64," in html  # image du visage intégrée


@pytest.mark.skipif(not os.environ.get("E7_CHROMIUM_PATH"), reason="navigateur non configuré")
def test_interactions_in_browser(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    target = render_webapp(_roster(), tmp_path / "vitrine.html")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ["E7_CHROMIUM_PATH"])
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(target.as_uri())
        assert page.locator(".tile").count() == 2
        assert page.evaluate("typeof alert === 'function' && !window.__xss")  # pas d'injection
        page.locator(".tile", has_text="Ras").click()
        assert page.locator("dialog[open] h2").text_content() == "Ras"
        assert EVIL in page.locator("dialog[open] .pills").text_content()  # affiché comme texte
        page.keyboard.press("Escape")
        page.fill("#q", "kise")
        assert page.text_content("#count") == "1 / 2 héros"
        browser.close()
        assert errors == []
