"""Page vitrine d'un profil : la vitrine web existante, avec les poses issues des captures."""

from __future__ import annotations

import base64

from e7showcase.app.profiles import ProfileStore
from e7showcase.assets import AssetStore
from e7showcase.render.webapp import build_payload_from_members, member_from_roster, page_html


def profile_payload(
    store: ProfileStore, profile_id: str, assets: AssetStore | None = None
) -> dict[str, object]:
    roster = store.load(profile_id)
    member = member_from_roster(roster, assets, anims=False)
    for hero, data in zip(roster.heroes, member.heroes, strict=True):
        images = data.setdefault("images", {})
        if not images.get("portrait") and (raw := store.portrait_bytes(profile_id, hero.name)):
            images["portrait"] = "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")
    return build_payload_from_members([member], guild=roster.guild)


def profile_page(store: ProfileStore, profile_id: str, assets: AssetStore | None = None) -> str:
    return page_html(profile_payload(store, profile_id, assets))
