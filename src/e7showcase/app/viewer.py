"""Page vitrine d'un profil : la vitrine web existante, avec les poses issues des captures.

Dans l'application, les images découpées dans les captures ne sont pas intégrées en base64 :
la page les référence par adresse (`/media/<profil>/<fichier>?v=<date>`), ce qui la garde
légère et laisse le navigateur les garder en cache d'une ouverture à l'autre.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from e7showcase.app.profiles import ICON_KINDS, ProfileStore
from e7showcase.assets import AssetStore
from e7showcase.render.webapp import build_payload_from_members, member_from_roster, page_html

THUMB = 160  # px, largeur des vignettes de la grille


def profile_payload(
    store: ProfileStore, profile_id: str, assets: AssetStore | None = None
) -> dict[str, object]:
    roster = store.peek(profile_id)
    member = member_from_roster(roster, assets, anims=False)
    for hero, data in zip(roster.heroes, member.heroes, strict=True):
        images = data.setdefault("images", {})
        if not images.get("portrait"):
            images["portrait"] = _media(profile_id, store.portrait_path(profile_id, hero.name))
            if images["portrait"]:  # vignette pour la grille (pas la pose entière)
                images["thumb"] = images["portrait"] + f"&w={THUMB}"
        for kind in ICON_KINDS:  # icônes découpées dans la capture (prioritaires)
            if url := _media(profile_id, store.icon_path(profile_id, hero.name, kind)):
                images[kind] = url
    payload = build_payload_from_members([member], guild=roster.guild)
    payload["live_anim"] = True  # modèle animé rendu en direct par l'application (/anim/<code>)
    return payload


def _media(profile_id: str, path: Path) -> str | None:
    """Adresse d'une image du profil ; la date de modification invalide le cache du navigateur."""
    try:
        version = path.stat().st_mtime_ns
    except OSError:
        return None
    return f"/media/{profile_id}/{quote(path.name)}?v={version}"


def profile_page(store: ProfileStore, profile_id: str, assets: AssetStore | None = None) -> str:
    return page_html(profile_payload(store, profile_id, assets))
