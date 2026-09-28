"""Source e7codex : conversion des données et synchronisation (serveur simulé, sans réseau)."""

import io
from pathlib import Path

import httpx
from PIL import Image

from e7showcase.assets import AssetStore
from e7showcase.models.hero import Hero
from e7showcase.sources.e7codex import build_artifacts, build_heroes, sync_assets

UNITS = [
    {
        "id": "c2066",
        "base_id": "c2066",
        "variant": "",
        "kind": "unit",
        "name": "New Moon Luna",
        "attribute": "light",
        "role": "mage",
        "rarity": 5,
        "pose": "assets/c2066/pose.png",
        "artworks": ["assets/c2066/face_c2066_l.png", "assets/c2066/face_c2066_s.png"],
    },
    {
        "id": "c2066_s01_1",
        "base_id": "c2066",
        "variant": "s01",
        "kind": "unit",
        "name": "New Moon Luna",
        "pose": "assets/c2066_s01_1/pose.png",
    },
    {
        "id": "c1006",
        "base_id": "c1006",
        "variant": "",
        "kind": "unit",
        "name": "Kise",
        "attribute": "ice",
        "role": "assassin",
        "rarity": 5,
        "pose": "assets/c1006/pose.png",
    },
    {"id": "npc1453", "kind": "npc", "name": None},
]
FR = {"names": {"c2066": "Luna Nouvelle lune"}, "artifacts": {"art0243": "Orbe de l'aube"}}


def test_build_heroes_maps_fields_and_attaches_skins() -> None:
    heroes = {h["code"]: h for h in build_heroes(UNITS, FR)}
    assert set(heroes) == {"c1006", "c2066"}  # PNJ et skins exclus des héros
    assert heroes["c1006"]["fr"] == "Kise"  # pas de traduction -> nom anglais
    assert heroes["c1006"]["role"] == "thief" and heroes["c2066"]["role"] == "mage"
    assert heroes["c2066"]["element"] == "light"
    assert [s["code"] for s in heroes["c2066"]["skins"]] == ["c2066_s01_1"]
    assert heroes["c2066"]["face"] == "assets/c2066/face_c2066_s.png"
    assert heroes["c1006"]["face"] is None


def test_build_artifacts() -> None:
    arts = build_artifacts(
        [
            {
                "id": "art0243",
                "name": "Aubade Orb",
                "rarity": 5,
                "role": "ranger",
                "art_full": "assets/_artifacts/art0243_fu.png",
            }
        ],
        FR,
    )
    assert arts == [
        {
            "code": "art0243",
            "en": "Aubade Orb",
            "fr": "Orbe de l'aube",
            "stars": 5,
            "role": "ranger",
            "art": "assets/_artifacts/art0243_fu.png",
        }
    ]


def _png(size: tuple[int, int]) -> bytes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    img.paste((200, 80, 120, 255), (100, 50, size[0] - 100, size[1] - 20))  # marges transparentes
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_sync_downloads_roster_heroes_skins_and_artifacts(tmp_path: Path) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if "missing" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, content=_png((1200, 1600)))

    store = AssetStore(tmp_path)
    heroes = [
        Hero(name="Luna Nouvelle lune", artifact="Orbe de l'aube", skin="c2066_s01_1"),
        Hero(name="Héros inconnu"),
    ]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = sync_assets(store, heroes, client, delay=0)
        assert sorted(requested) == [
            "/assets/_artifacts/art0243_fu.png",
            "/assets/c2066/face_c2066_s.png",
            "/assets/c2066/pose.png",
            "/assets/c2066_s01_1/face_c2066_s01_s.png",
            "/assets/c2066_s01_1/pose.png",
        ]
        assert len(report.downloaded) == 5
        assert any("Héros inconnu" in m for m in report.missing)
        # la pose est rognée (marges transparentes) puis réduite
        with Image.open(tmp_path / "heroes" / "c2066.webp") as img:
            assert img.height <= 1130 and img.width < img.height
        # le skin choisi est prioritaire sur la pose de base
        assert store.hero_portrait(heroes[0]) == tmp_path / "heroes" / "c2066_s01_1.webp"
        assert store.hero_face(heroes[0]) == tmp_path / "faces" / "c2066_s01_1.webp"
        assert store.artifact_image("Orbedel'aube") == tmp_path / "artifacts" / "art0243.webp"
        # second passage : rien n'est retéléchargé
        requested.clear()
        assert len(sync_assets(store, heroes, client, delay=0).skipped) == 5 and not requested
