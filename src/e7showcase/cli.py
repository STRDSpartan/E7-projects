"""Interface en ligne de commande : `e7showcase --help`."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from e7showcase.assets import AssetStore
from e7showcase.config import data_dir, regions, settings
from e7showcase.models.hero import Hero
from e7showcase.storage.repository import RosterRepository

app = typer.Typer(
    help="Scanner de roster Epic Seven et vitrines Discord pour la guilde.", no_args_is_help=True
)
console = Console()


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@app.command()
def scan(
    from_dir: Annotated[
        Path | None, typer.Option("--from-dir", help="Dossier de captures (PC ou mobile)")
    ] = None,
    mode: Annotated[str | None, typer.Option(help="manual | assisted")] = None,
    profile: Annotated[str | None, typer.Option(help="Profil de zones (défaut : auto)")] = None,
    max_heroes: Annotated[int | None, typer.Option("--max")] = None,
    player: Annotated[str | None, typer.Option(help="Pseudo en jeu")] = None,
) -> None:
    """Scanner les héros : client PC en direct (Windows) ou dossier de captures."""
    from PIL import Image

    from e7showcase.scanner.hero_scanner import HeroScanner
    from e7showcase.vision.ocr import get_engine
    from e7showcase.vision.set_catalog import SetMatcher

    cfg = settings()
    repo = RosterRepository()
    roster = repo.load()
    if player:
        roster.player = player
    library = data_dir() / "templates" / "sets"
    sets = SetMatcher.load(library)
    no_sets_hint = (
        "[yellow]Aucun blason de set connu : les sets resteront vides. Ajoutez une capture "
        "du catalogue des sets (filtre d'inventaire) ou lancez `e7showcase learn-sets`.[/]"
    )
    ocr = get_engine(cfg["ocr"]["backend"])

    def save(hero: Hero) -> None:
        roster.upsert(hero)
        repo.save(roster)
        sets = ", ".join(sorted({g.set.value for g in hero.gear.values() if g.set})) or "sets ?"
        console.print(
            f"[green]✔[/] {hero.name} — VIT {hero.stats.spd}, {len(hero.gear)} pièces, {sets}"
        )

    if from_dir:
        from e7showcase.scanner.batch import image_files, scan_directory

        files = image_files(from_dir)
        if not files:
            raise typer.BadParameter(f"Aucune image dans {from_dir}")
        with Image.open(files[0]) as first:
            aspect = first.width / first.height
        scanner = HeroScanner(ocr, regions(profile, aspect), cfg["game"]["lang"], sets)
        result = scan_directory(scanner, from_dir, library)
        if not scanner.sets.templates:
            console.print(no_sets_hint)
        for hero in result.heroes:
            save(hero)
        if result.ignored:
            console.print(f"[yellow]{len(result.ignored)} capture(s) non reconnue(s)[/]")
        console.print(f"{len(result.heroes)} héros scannés → {repo.path}")
        return

    from e7showcase.capture.window import find_game_window
    from e7showcase.scanner.navigator import AssistedNavigator, ManualNavigator
    from e7showcase.scanner.session import ScanSession

    mode = mode or cfg["scan"]["mode"]
    keys = {"hotkey": cfg["scan"]["hotkey"], "stop_hotkey": cfg["scan"]["stop_hotkey"]}
    navigator = (
        AssistedNavigator(cfg["scan"]["delay_after_click_ms"], **keys)
        if mode == "assisted"
        else ManualNavigator(**keys)
    )
    rect = find_game_window(cfg["game"]["window_title"])
    if not sets.templates:
        console.print(no_sets_hint)
    scanner = HeroScanner(ocr, regions(profile, rect.aspect), cfg["game"]["lang"], sets)
    session = ScanSession(
        scanner,
        navigator,
        cfg["game"]["window_title"],
        capture_dir=data_dir() / "captures" if cfg["scan"]["save_captures"] else None,
        set_library=library,
        on_hero=save,
    )
    heroes = session.run(max_heroes)
    console.print(f"{len(heroes)} héros scannés → {repo.path}")


@app.command("learn-sets")
def learn_sets(images: list[Path]) -> None:
    """Apprendre les blasons de sets depuis une capture du catalogue (filtre d'inventaire)."""
    from PIL import Image

    from e7showcase.vision.ocr import get_engine
    from e7showcase.vision.set_catalog import SetMatcher, read_catalog

    library = data_dir() / "templates" / "sets"
    matcher = SetMatcher.load(library)
    ocr = get_engine(settings()["ocr"]["backend"])
    for path in images:
        found = read_catalog(Image.open(path).convert("RGB"), ocr, settings()["game"]["lang"])
        for gear_set, shield in found.items():
            matcher.add(gear_set.value, shield)
        console.print(f"{path.name} : {len(found)} sets — {', '.join(s.value for s in found)}")
    matcher.save(library)
    console.print(f"{len(matcher.templates)} blasons de sets connus → {library}")


@app.command("import-fribbels")
def import_fribbels(
    file: Path, player: Annotated[str, typer.Option()] = "Unknown", merge: bool = True
) -> None:
    """Importer un export JSON de Fribbels E7 Optimizer."""
    from e7showcase.importers.fribbels import import_file

    repo = RosterRepository()
    imported = import_file(file, player)
    roster = repo.load() if merge else imported
    if merge:
        roster.player = player if player != "Unknown" else roster.player
        for hero in imported.heroes:
            roster.upsert(hero)
    repo.save(roster)
    console.print(f"{len(imported.heroes)} héros importés → {repo.path}")


@app.command("list")
def list_heroes() -> None:
    """Lister les héros du roster local."""
    from e7showcase.calc.gear_score import roster_gear_score

    roster = RosterRepository().load()
    table = Table(title=f"Roster de {roster.player} ({len(roster.heroes)})")
    for col in ("Héros", "VIT", "ATK", "PV", "DEF", "CC", "DC", "EFF", "RES", "Sets", "GS"):
        table.add_column(col)
    for h in sorted(roster.heroes, key=lambda x: -x.stats.spd):
        s = h.stats
        table.add_row(
            h.name,
            str(s.spd),
            str(s.atk),
            str(s.hp),
            str(s.defense),
            f"{s.crit_chance:g}",
            f"{s.crit_dmg:g}",
            f"{s.effectiveness:g}",
            f"{s.effect_res:g}",
            "/".join(h.sets),
            f"{roster_gear_score(list(h.gear.values())):g}",
        )
    console.print(table)


@app.command()
def tag(hero: str, tags: list[str]) -> None:
    """Ajouter des tags guilde à un héros (ex: GvG-def RTA)."""
    repo = RosterRepository()
    roster = repo.load()
    h = roster.find(hero)
    if not h:
        raise typer.BadParameter(f"Héros introuvable : {hero}")
    h.tags = sorted(set(h.tags) | set(tags))
    repo.save(roster)
    console.print(f"{h.name} : {', '.join(h.tags)}")


@app.command()
def render(
    heroes: Annotated[
        list[str] | None, typer.Argument(help="Noms de héros (vide = tout le roster)")
    ] = None,
    layout: Annotated[str, typer.Option(help="cards | grid")] = "cards",
    tag_filter: Annotated[str | None, typer.Option("--tag")] = None,
    out: Annotated[Path, typer.Option()] = Path("out"),
    html_only: bool = False,
) -> None:
    """Générer la vitrine (PNG) du roster ou d'une sélection."""
    from e7showcase.render.showcase import render_showcase

    roster = RosterRepository().load()
    selection = roster.heroes
    if heroes:
        selection = [h for name in heroes if (h := roster.find(name))]
    if tag_filter:
        selection = [h for h in selection if tag_filter in h.tags]
    cfg = settings()["render"]
    paths = render_showcase(
        roster,
        out,
        selection,
        layout=layout,
        width=cfg["width"],
        scale=cfg["scale"],
        png=not html_only,
        assets=AssetStore(data_dir() / "assets"),
    )
    for p in paths:
        console.print(f"🖼  {p}")


@app.command()
def share(
    heroes: Annotated[list[str] | None, typer.Argument()] = None,
    layout: str = "cards",
    message: str = "",
) -> None:
    """Générer puis publier la vitrine dans le salon Discord de la guilde (webhook)."""
    import tempfile

    from e7showcase.publish.webhook import post_images
    from e7showcase.render.showcase import render_showcase

    cfg = settings()
    roster = RosterRepository().load()
    selection = [h for n in heroes if (h := roster.find(n))] if heroes else roster.heroes
    with tempfile.TemporaryDirectory() as tmp:
        images = render_showcase(
            roster, Path(tmp), selection, layout=layout, assets=AssetStore(data_dir() / "assets")
        )
        post_images(
            cfg["discord"]["webhook_url"],
            images,
            content=message or f"Vitrine de **{roster.player}**",
            username=cfg["discord"]["username"],
        )
    console.print(f"[green]Publié[/] ({len(images)} image(s))")


assets_app = typer.Typer(help="Portraits des héros et images d'artefacts (dossier local).")
app.add_typer(assets_app, name="assets")


@assets_app.command("add")
def assets_add(
    kind: Annotated[str, typer.Argument(help="hero | artifact")],
    name: Annotated[str, typer.Argument(help="Nom du héros / de l'artefact, ou code (c1001)")],
    image: Path,
) -> None:
    """Importer une image (portrait de héros ou artefact) dans le dossier local."""
    if kind not in ("hero", "artifact"):
        raise typer.BadParameter("hero ou artifact")
    target = AssetStore(data_dir() / "assets").add(
        "heroes" if kind == "hero" else "artifacts", name, image
    )
    console.print(f"Image enregistrée → {target}")


@assets_app.command("sync")
def assets_sync(
    all_heroes: Annotated[
        bool, typer.Option("--all", help="Tous les héros du jeu (~2 Go sources)")
    ] = False,
    skins: Annotated[bool, typer.Option("--skins", help="Télécharger aussi les skins")] = False,
    force: Annotated[bool, typer.Option(help="Retélécharger même si déjà présent")] = False,
) -> None:
    """Télécharger depuis e7codex.com les illustrations des héros du roster (dossier local)."""
    import httpx

    from e7showcase.reference import load
    from e7showcase.sources.e7codex import sync_assets

    store = AssetStore(data_dir() / "assets")
    if all_heroes:
        heroes = [Hero(name=h["fr"]) for h in load("heroes")["heroes"]]
    else:
        heroes = RosterRepository().load().heroes
        if not heroes:
            raise typer.BadParameter("Roster vide : scannez d'abord vos héros, ou utilisez --all.")
    console.print(f"Synchronisation de {len(heroes)} héros depuis e7codex.com → {store.root}")
    with httpx.Client(follow_redirects=True) as client:
        report = sync_assets(
            store,
            heroes,
            client,
            skins=skins,
            force=force,
            on_item=lambda label, status: console.print(f"  {status:<13} {label}"),
        )
    console.print(
        f"[green]{len(report.downloaded)} téléchargé(s)[/], {len(report.skipped)} déjà présent(s), "
        f"[yellow]{len(report.missing)} introuvable(s)[/]"
    )
    for miss in report.missing:
        console.print(f"  [yellow]•[/] {miss}")


@assets_app.command("status")
def assets_status() -> None:
    """Quels héros du roster ont un portrait / un artefact illustré ?"""
    store = AssetStore(data_dir() / "assets")
    roster = RosterRepository().load()
    table = Table(title=f"Images locales ({store.root})")
    for col in ("Héros", "Portrait", "Artefact", "Clés acceptées"):
        table.add_column(col)
    for h in sorted(roster.heroes, key=lambda x: x.name):
        portrait = store.hero_portrait(h)
        art = store.artifact_image(h.artifact)
        table.add_row(
            h.name,
            "✔" if portrait else "—",
            ("✔ " if art else "— ") + (h.artifact or ""),
            ", ".join(store.hero_keys(h)),
        )
    console.print(table)


@app.command()
def skin(
    hero: str,
    choice: Annotated[str | None, typer.Argument(help="Numéro du skin, code, ou « base »")] = None,
) -> None:
    """Lister les skins d'un héros, ou choisir celui affiché sur la vitrine."""
    from e7showcase.reference import hero_info

    repo = RosterRepository()
    roster = repo.load()
    h = roster.find(hero)
    if not h:
        raise typer.BadParameter(f"Héros introuvable dans le roster : {hero}")
    skins = (hero_info(h.name) or {}).get("skins", [])
    if choice is None:
        console.print(f"{h.name} — skin actuel : {h.skin or 'base'}")
        for i, s in enumerate(skins, start=1):
            console.print(f"  {i}. {s['code']} ({s['variant']}) {s['fr']}")
        if not skins:
            console.print("  (aucun skin connu)")
        return
    if choice == "base":
        h.skin = None
    else:
        chosen = next(
            (s for i, s in enumerate(skins, start=1) if choice in (str(i), s["code"])), None
        )
        if chosen is None:
            raise typer.BadParameter(f"Skin inconnu : {choice}")
        h.skin = chosen["code"]
    repo.save(roster)
    console.print(
        f"{h.name} : skin {h.skin or 'base'} — lancez `e7showcase assets sync` si besoin."
    )


@app.command()
def export(out: Path = Path("roster-export.json")) -> None:
    """Exporter le roster (format d'échange guilde / bot Discord)."""
    roster = RosterRepository().load()
    out.write_text(roster.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
    console.print(f"Roster exporté → {out}")


@app.command()
def bot() -> None:
    """Lancer le bot Discord de guilde (nécessite l'extra [bot])."""
    from e7showcase.publish.bot import run

    run()


if __name__ == "__main__":
    app()
