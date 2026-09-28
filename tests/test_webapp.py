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
    assert payload["title"] == "Testeur" and len(payload["heroes"]) == 2
    assert payload["members"][0]["player"] == "Testeur" and payload["members"][0]["count"] == 2
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


# --- vue guilde -------------------------------------------------------------------------
def _member_roster(player: str, *names: str, day: int = 1) -> Roster:
    from datetime import datetime

    heroes = [
        Hero(name=n, element="ice", role="thief", power=100000 + i, tags=[])
        for i, n in enumerate(names)
    ]
    for i, h in enumerate(heroes):
        h.stats.spd = 200 + 10 * i + day
    return Roster(player=player, heroes=heroes, updated_at=datetime(2026, 9, day))


def test_guild_payload_merges_members_and_shares_images(tmp_path: Path) -> None:
    from e7showcase.render.webapp import build_payload_from_members, member_from_roster

    store = AssetStore(tmp_path)
    (tmp_path / "faces").mkdir()
    Image.new("RGBA", (112, 112), (10, 200, 90, 255)).save(tmp_path / "faces" / "c1006.png")
    members = [
        member_from_roster(_member_roster("Aria", "Kise", "Ras"), store),
        member_from_roster(_member_roster("Bram", "Kise"), store),
    ]
    payload = build_payload_from_members(members, guild="Les Lames")
    assert [m["player"] for m in payload["members"]] == ["Aria", "Bram"]
    kises = [h for h in payload["heroes"] if h["name"] == "Kise"]
    assert len(kises) == 2 and {h["member"] for h in kises} == {"m0", "m1"}
    assert kises[0]["images"]["face"] == kises[1]["images"]["face"]  # image stockée une seule fois
    assert len(payload["images"]) == 1


def test_guild_from_vitrines_and_duplicates(tmp_path: Path) -> None:
    from e7showcase.render.webapp import (
        member_from_roster,
        merge_members,
        read_vitrine,
        render_guild,
    )

    old = render_webapp(_member_roster("Aria", "Kise", day=1), tmp_path / "aria-old.html")
    new = render_webapp(_member_roster("Aria", "Kise", "Ras", day=5), tmp_path / "aria.html")
    members = (
        read_vitrine(old) + read_vitrine(new) + [member_from_roster(_member_roster("Bram", "Ras"))]
    )
    merged = merge_members(members)
    assert [(m.player, len(m.heroes)) for m in merged] == [
        ("Aria", 2),
        ("Bram", 1),
    ]  # version la plus récente
    guild = render_guild(members, tmp_path / "guilde.html", guild="Les Lames")
    again = read_vitrine(guild)  # une vitrine de guilde se relit aussi (fusion de fusions)
    assert sorted(m.player for m in again) == ["Aria", "Bram"]


def test_read_vitrine_rejects_other_files(tmp_path: Path) -> None:
    from e7showcase.render.webapp import read_vitrine

    other = tmp_path / "page.html"
    other.write_text("<html><body>rien</body></html>", encoding="utf-8")
    with pytest.raises(ValueError):
        read_vitrine(other)


@pytest.mark.skipif(not os.environ.get("E7_CHROMIUM_PATH"), reason="navigateur non configuré")
def test_guild_views_in_browser(tmp_path: Path) -> None:
    from e7showcase.render.webapp import member_from_roster, render_guild

    sync_api = pytest.importorskip("playwright.sync_api")
    members = [
        member_from_roster(_member_roster("Aria", "Kise", "Ras")),
        member_from_roster(_member_roster("Bram", "Kise", day=3)),
    ]
    target = render_guild(members, tmp_path / "guilde.html", guild="Les Lames")
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ["E7_CHROMIUM_PATH"])
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(target.as_uri())
        assert page.locator(".tile").count() == 3 and page.is_visible("#views")
        page.click('#views [data-view="groups"]')
        assert page.text_content("#count") == "2 héros différents · 3 exemplaires"
        page.locator(".tile", has_text="Kise").click()
        rows = page.locator("dialog[open] tbody tr")
        assert rows.count() == 2
        assert rows.nth(0).locator("td").first.text_content() == "Bram"  # tri par vitesse
        rows.nth(0).click()
        assert "Bram" in page.locator("dialog[open] .sub").first.text_content()
        page.click('[aria-label="Retour à la comparaison"]')
        assert page.locator("dialog[open] tbody tr").count() == 2
        page.keyboard.press("Escape")
        page.click('#views [data-view="members"]')
        assert page.locator(".member-card").count() == 2
        page.locator(".member-card", has_text="Aria").click()
        assert page.text_content("#count") == "2 / 3 héros"
        browser.close()
        assert errors == []
