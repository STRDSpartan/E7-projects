"""Génération de la vitrine : HTML (Jinja2) puis PNG (Playwright) prêt pour Discord."""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from e7showcase.assets import AssetStore
from e7showcase.models.hero import Hero
from e7showcase.models.roster import Roster
from e7showcase.render.viewmodel import build

TEMPLATES = Path(__file__).parent / "templates"
# Discord accepte des images plus grandes, mais au-delà l'aperçu mobile devient illisible
MAX_CARDS_PER_IMAGE = 6


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"])
    )


def render_html(
    roster: Roster,
    heroes: list[Hero] | None = None,
    *,
    layout: str = "cards",
    width: int = 1200,
    assets: AssetStore | None = None,
) -> str:
    selected = heroes if heroes is not None else roster.heroes
    return (
        _env()
        .get_template("showcase.html.j2")
        .render(
            title=f"Vitrine {roster.player}",
            player=roster.player,
            guild=roster.guild,
            updated=roster.updated_at.strftime("%d/%m/%Y"),
            heroes=[build(h, assets) for h in selected],
            layout=layout,
            width=width,
        )
    )


def html_to_png(html: str, out: Path, width: int = 1200, scale: int = 2) -> Path:
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # E7_CHROMIUM_PATH : réutiliser un Chrome/Edge déjà installé plutôt que `playwright install`
        browser = p.chromium.launch(executable_path=os.environ.get("E7_CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": width, "height": 200}, device_scale_factor=scale)
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(out), full_page=True)
        browser.close()
    return out


def render_showcase(
    roster: Roster,
    out_dir: Path,
    heroes: list[Hero] | None = None,
    *,
    layout: str = "cards",
    width: int = 1200,
    scale: int = 2,
    png: bool = True,
    assets: AssetStore | None = None,
) -> list[Path]:
    """Écrit une ou plusieurs images (découpage automatique pour rester lisible sur Discord)."""
    selected = heroes if heroes is not None else roster.heroes
    per_page = MAX_CARDS_PER_IMAGE if layout == "cards" else 40
    chunks = [selected[i : i + per_page] for i in range(0, len(selected), per_page)] or [[]]
    outputs: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, chunk in enumerate(chunks, start=1):
        html = render_html(roster, chunk, layout=layout, width=width, assets=assets)
        stem = f"showcase-{layout}-{i:02d}"
        html_path = out_dir / f"{stem}.html"
        html_path.write_text(html, encoding="utf-8")
        outputs.append(
            html_to_png(html, out_dir / f"{stem}.png", width, scale) if png else html_path
        )
    return outputs
