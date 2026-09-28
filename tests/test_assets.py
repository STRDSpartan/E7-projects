"""Portraits locaux : recherche par code / nom FR / nom EN, intégration dans la vitrine."""

from pathlib import Path

from PIL import Image

from e7showcase.assets import AssetStore, data_uri, slugify
from e7showcase.models.hero import Hero
from e7showcase.models.roster import Roster
from e7showcase.render.showcase import render_html


def _img(path: Path, size: tuple[int, int] = (900, 1200)) -> Path:
    Image.new("RGBA", size, (120, 80, 200, 255)).save(path)
    return path


def test_slugify() -> None:
    assert slugify("Ludwig Prélude de l'Aubade") == "ludwig-prelude-de-l-aubade"
    assert slugify("Céline vision d'esprit") == "celine-vision-d-esprit"


def test_portrait_found_by_code_or_names(tmp_path: Path) -> None:
    store = AssetStore(tmp_path)
    (tmp_path / "heroes").mkdir()
    hero = Hero(name="Cecilia déchue")  # nom FR ; référentiel : en « Fallen Cecilia », code c2002
    assert store.hero_portrait(hero) is None
    _img(tmp_path / "heroes" / "fallen-cecilia.png")
    assert store.hero_portrait(hero) == tmp_path / "heroes" / "fallen-cecilia.png"
    _img(tmp_path / "heroes" / "c2002.webp")
    assert store.hero_portrait(hero) == tmp_path / "heroes" / "c2002.webp"  # le code prime


def test_add_converts_to_webp(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / "assets")
    target = store.add("artifacts", "Orbe de l'aube", _img(tmp_path / "src.png", (300, 300)))
    assert target.name == "orbe-de-l-aube.webp"
    assert store.artifact_image("Orbe de l'aube") == target


def test_data_uri_is_downscaled(tmp_path: Path) -> None:
    uri = data_uri(_img(tmp_path / "big.png", (2000, 3000)), "heroes")
    assert uri is not None and uri.startswith("data:image/webp;base64,")
    assert data_uri(None, "heroes") is None


def test_showcase_embeds_portrait_only_when_available(tmp_path: Path) -> None:
    store = AssetStore(tmp_path)
    (tmp_path / "heroes").mkdir()
    _img(tmp_path / "heroes" / "kise.png")
    roster = Roster(player="T", heroes=[Hero(name="Kise"), Hero(name="Ras")])
    html = render_html(roster, assets=store)
    assert html.count('class="portrait"') == 1  # Kise seulement
    assert "has-portrait" in html
    assert "data:image/webp;base64," in html
    assert 'class="portrait"' not in render_html(roster)  # sans magasin : rendu inchangé
