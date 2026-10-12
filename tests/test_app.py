"""Application de bureau : profils, fichier de vitrine .e7v, serveur local (sans OCR)."""

import base64
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from e7showcase.app.importer import ImportReport
from e7showcase.app.profiles import ProfileStore
from e7showcase.app.server import AppState, start_server
from e7showcase.app.viewer import profile_payload
from e7showcase.app.vitrine_file import VitrineFileError, export_profile, import_vitrine
from e7showcase.importers.fribbels import import_file
from e7showcase.models.hero import Hero

FIXTURE = Path(__file__).parent / "fixtures" / "fribbels_export.json"


def pose(color: tuple[int, int, int] = (90, 60, 160)) -> Image.Image:
    return Image.new("RGB", (300, 500), color)


def filled_store(tmp_path: Path) -> tuple[ProfileStore, str]:
    store = ProfileStore(tmp_path / "profiles")
    pid = store.create("Spartan")
    for hero in import_file(FIXTURE, player="Spartan").heroes:
        store.add_hero(pid, hero, pose())
    return store, pid


def test_profile_lifecycle(tmp_path: Path) -> None:
    store, pid = filled_store(tmp_path)
    [info] = store.list()
    assert info.player == "Spartan" and info.heroes >= 1 and not info.received
    name = store.load(pid).heroes[0].name
    assert store.portrait_bytes(pid, name)
    store.rename(pid, "Spartan FR")
    store.remove_hero(pid, name)
    assert store.load(pid).player == "Spartan FR" and store.portrait_bytes(pid, name) is None
    with pytest.raises(KeyError):
        store.path("../evil")
    store.delete(pid)
    assert store.list() == []


def test_vitrine_roundtrip(tmp_path: Path) -> None:
    store, pid = filled_store(tmp_path)
    data = export_profile(store, pid)
    other = ProfileStore(tmp_path / "ailleurs")
    rid = import_vitrine(other, data)
    assert other.is_received(rid)
    sent, got = store.load(pid), other.load(rid)
    assert got.player == "Spartan" and [h.name for h in got.heroes] == [h.name for h in sent.heroes]
    assert got.heroes[0].stats == sent.heroes[0].stats
    assert other.portrait_bytes(rid, got.heroes[0].name)
    payload = profile_payload(other, rid)
    assert str(payload["heroes"][0]["images"]["portrait"]).startswith("i")  # image mutualisée


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


MANIFEST = json.dumps({"format": "e7showcase-vitrine", "version": 1}).encode()


@pytest.mark.parametrize(
    "data",
    [
        b"pas un zip",
        _zip({"profile.json": b"{}"}),  # pas de manifeste
        _zip({"manifest.json": b'{"format": "autre"}', "profile.json": b"{}"}),
        _zip({"manifest.json": MANIFEST, "profile.json": b'{"heroes": "x"}'}),
        _zip(
            {
                "manifest.json": json.dumps(
                    {"format": "e7showcase-vitrine", "version": 99}
                ).encode(),
                "profile.json": b"{}",
            }
        ),
    ],
)
def test_rejects_invalid_vitrines(tmp_path: Path, data: bytes) -> None:
    store = ProfileStore(tmp_path)
    with pytest.raises(VitrineFileError):
        import_vitrine(store, data)
    assert store.list() == []


def test_hostile_entries_are_ignored(tmp_path: Path) -> None:
    roster = {"player": "X", "heroes": [Hero(name="Kise").model_dump(mode="json")]}
    data = _zip(
        {
            "manifest.json": MANIFEST,
            "profile.json": json.dumps(roster).encode(),
            "../../evil.txt": b"pwned",
            "images/kise.webp": b"<html>pas une image</html>",
        }
    )
    store = ProfileStore(tmp_path / "p")
    rid = import_vitrine(store, data)
    assert store.load(rid).heroes[0].name == "Kise"
    assert store.portrait_bytes(rid, "Kise") is None
    assert not (tmp_path / "evil.txt").exists()


class FakeImporter:
    def __init__(self) -> None:
        self.calls: list[list[tuple[str, bytes]]] = []
        self.set_library = Path("blasons-absents")

    def run(
        self, store: ProfileStore, pid: str, files: list[tuple[str, bytes]], progress: Any = None
    ) -> ImportReport:
        self.calls.append(files)
        self.steps: list[int] = []
        for done in range(3):
            if progress:
                progress(done, 2, f"étape {done}")
            self.steps.append(done)
        store.add_hero(pid, Hero(name="Kise", power=205138), pose())
        return ImportReport(heroes=["Kise"])


@pytest.fixture
def app(tmp_path: Path) -> Any:
    state = AppState(tmp_path, importer=FakeImporter())  # type: ignore[arg-type]
    server = start_server(state)
    yield state, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def call(base: str, method: str, path: str, body: Any = None, token: str | None = None) -> Any:
    req = urllib.request.Request(
        base + path, method=method, data=json.dumps(body).encode() if body is not None else None
    )
    if token:
        req.add_header("X-E7-Token", token)
    with urllib.request.urlopen(req) as res:
        raw = res.read()
        return json.loads(raw) if res.headers.get_content_type() == "application/json" else raw


def test_server_flow(app: Any) -> None:
    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    shot = base64.b64encode(b"fake").decode()
    started = call(
        base,
        "POST",
        f"/api/profiles/{pid}/screenshots",
        {"files": [{"name": "a.png", "data": shot}]},
        t,
    )
    for _ in range(100):  # l'import tourne en arrière-plan ; l'interface interroge /jobs
        job = call(base, "GET", f"/api/jobs/{started['job']}", token=t)
        if job["finished"]:
            break
        time.sleep(0.05)
    assert job["finished"] and job["done"] == job["total"] and not job["error"]
    assert job["report"]["heroes"] == ["Kise"] and state.importer.calls[0] == [("a.png", b"fake")]
    page = call(base, "GET", f"/profile/{pid}").decode()
    assert "Kise" in page and "data:image/webp;base64" in page
    exported = call(base, "GET", f"/api/profiles/{pid}/export", token=t)
    rid = call(base, "POST", "/api/open", {"data": base64.b64encode(exported).decode()}, t)["id"]
    received = call(base, "GET", f"/api/profiles/{rid}", token=t)
    assert received["received"] and received["heroes"] == ["Kise"]
    with pytest.raises(urllib.error.HTTPError) as err:  # une vitrine reçue est en lecture seule
        call(base, "POST", f"/api/profiles/{rid}/screenshots", {"files": []}, t)
    assert err.value.code == 403
    assert "__TOKEN__" not in call(base, "GET", "/").decode()


def test_api_requires_token(app: Any) -> None:
    _, base = app
    for token in (None, "faux"):
        with pytest.raises(urllib.error.HTTPError) as err:
            call(base, "GET", "/api/profiles", token=token)
        assert err.value.code == 403


def test_rejects_foreign_host(app: Any) -> None:
    state, base = app
    req = urllib.request.Request(
        base + "/api/profiles", headers={"Host": "evil.example", "X-E7-Token": state.token}
    )
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req)
    assert err.value.code == 403


def test_window_api_exposes_only_its_functions(tmp_path: Path) -> None:
    """pywebview parcourt les attributs publics de js_api : rien d'autre que les fonctions."""
    from e7showcase.app.launcher import WindowApi

    api = WindowApi(AppState(tmp_path, importer=FakeImporter()))  # type: ignore[arg-type]
    api._window = object()
    public = [n for n in dir(api) if not n.startswith("_")]
    assert all(callable(getattr(api, n)) for n in public), public


def test_closing_window_really_ends_the_process(monkeypatch: pytest.MonkeyPatch) -> None:
    from e7showcase.app import launcher

    calls: list[str] = []

    class FakeServer:
        def shutdown(self) -> None:
            calls.append("shutdown")

        def server_close(self) -> None:
            calls.append("close")

    def fake_exit(code: int) -> None:
        calls.append(f"exit {code}")

    monkeypatch.setattr(launcher.os, "_exit", fake_exit)
    launcher._quit(FakeServer())  # noqa: SLF001
    assert "close" in calls and calls[-1] == "exit 0"


def test_item_icons_follow_the_hero_into_the_vitrine(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles")
    pid = store.create("Spartan")
    icons = {"weapon": pose((200, 40, 40)), "artifact": pose((40, 200, 40))}
    store.add_hero(pid, Hero(name="Kise", code="c1006", artifact_level=27), pose(), icons)
    rid = import_vitrine(ProfileStore(tmp_path / "ailleurs"), export_profile(store, pid))
    other = ProfileStore(tmp_path / "ailleurs")
    assert other.icon_bytes(rid, "Kise", "weapon") and other.icon_bytes(rid, "Kise", "artifact")
    assert other.icon_bytes(rid, "Kise", "boots") is None
    payload = profile_payload(other, rid)
    hero = payload["heroes"][0]
    assert payload["live_anim"] and hero["anim_code"] == "c1006" and hero["artifact_level"] == 27
    assert hero["images"]["weapon"] and hero["images"]["artifact"] and not hero["images"]["boots"]
    with pytest.raises(KeyError):
        store.icon_path(pid, "Kise", "../evil")
    store.remove_hero(pid, "Kise")
    assert store.icon_bytes(pid, "Kise", "weapon") is None


def test_anim_page_is_locked_down(app: Any) -> None:
    _, base = app
    with urllib.request.urlopen(base + "/anim/c5147_1") as res:
        csp = res.headers["Content-Security-Policy"]
        page = res.read().decode()
    assert '"c5147_1"' in page and "default-src 'none'" in csp and "https://e7codex.com" in csp
    for bad in ("/anim/evil", "/anim/c1006%22%3E", "/anim/c1006/../x"):
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(base + bad)
        assert err.value.code == 404


def test_armory_and_guild_api(app: Any) -> None:
    from e7showcase.models.gear import Gear, GearSet, GearSlot, StatLine
    from e7showcase.models.stats import StatType

    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    worn = Gear(slot=GearSlot.BOOTS, set=GearSet.SPEED, enhance=15,
                main=StatLine(stat=StatType.SPD, value=45))  # fmt: skip
    state.store.add_hero(pid, Hero(name="Kise", power=1000, gear={GearSlot.BOOTS: worn}), None)
    spare = Gear(slot=GearSlot.RING, set=GearSet.DESTRUCTION, enhance=12,
                 main=StatLine(stat=StatType.ATK_PCT, value=47))  # fmt: skip
    item_id = state.store.add_item(pid, spare, Image.new("RGB", (90, 90), (200, 50, 50)))
    data = call(base, "GET", f"/api/profiles/{pid}/armory", token=t)
    assert [g["hero"] for g in data["equipped"]] == ["Kise"]
    assert data["inventory"][0]["icon"].startswith("data:image/webp;base64,")
    # l'icône voyage dans la vitrine exportée
    packed = base64.b64encode(call(base, "GET", f"/api/profiles/{pid}/export", token=t)).decode()
    copy = call(base, "POST", "/api/open", {"data": packed}, t)["id"]
    copied = state.store.load(copy).inventory[0].id
    assert state.store.item_icon_bytes(copy, copied)
    state.store.delete(copy)
    assert data["inventory"][0]["set"] == "destruction" and data["inventory"][0]["id"] == item_id
    assert data["sets"]["speed"]["name"] == "Vitesse"
    call(base, "DELETE", f"/api/profiles/{pid}/items/{item_id}", token=t)
    assert state.store.item_icon_bytes(pid, item_id) is None
    assert call(base, "GET", f"/api/profiles/{pid}/armory", token=t)["inventory"] == []
    # guilde : nom, membres (profil du joueur et vitrine reçue d'un coéquipier)
    guild = call(base, "PATCH", "/api/guild", {"name": "Spartiates", "members": [pid]}, t)
    assert guild["name"] == "Spartiates" and guild["members"][0]["power"] == 1000
    exported = call(base, "GET", f"/api/profiles/{pid}/export", token=t)
    shared = base64.b64encode(exported).decode()
    rid = call(base, "POST", "/api/open", {"data": shared, "guild": True}, t)["id"]
    guild = call(base, "GET", "/api/guild", token=t)
    assert {m["id"] for m in guild["members"]} == {pid, rid}
    state.store.delete(rid)  # un profil supprimé disparaît de la guilde
    assert [m["id"] for m in call(base, "GET", "/api/guild", token=t)["members"]] == [pid]


def test_gvg_api(app: Any) -> None:
    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    for name in ("Belian", "Lilias", "Aria", "Ruele of Light"):
        state.store.add_hero(pid, Hero(name=name), None)
    assert call(base, "GET", "/api/gvg", token=t)["members"] == []  # guilde vide
    call(base, "PATCH", "/api/guild", {"members": [pid]}, t)
    g = call(base, "PUT", f"/api/gvg/defense/{pid}",
             {"tower": "Château", "teams": [["belian", "Lilias"], ["Aria"]]}, t)  # fmt: skip
    assert g["members"][0]["defense"] == {
        "teams": [["Belian", "Lilias"], ["Aria"]],
        "tower": "Château",
    }
    for bad in ({"teams": [["Belian"], ["Belian"]]}, {"teams": [["Inconnu"]]},
                {"teams": [["Belian", "Lilias", "Aria", "Ruele of Light"]]}):  # fmt: skip
        with pytest.raises(urllib.error.HTTPError) as err:
            call(base, "PUT", f"/api/gvg/defense/{pid}", bad, t)
        assert err.value.code == 400
    g = call(base, "POST", "/api/gvg/wars", {"opponent": "Les Ombres", "date": "2026-10-12"}, t)
    war = g["wars"][0]["id"]
    attack = {"member": pid, "team": ["Aria", "Belian"], "enemy_team": ["Lua", "Riolet", "Cerise"],
              "result": "win"}  # fmt: skip
    call(base, "POST", f"/api/gvg/wars/{war}/attacks", attack, t)
    g = call(base, "POST", f"/api/gvg/wars/{war}/attacks", {**attack, "result": "loss"}, t)
    w = g["wars"][0]
    assert (w["wins"], w["losses"], w["remaining"][pid]) == (1, 1, 0)
    counter = g["counters"][0]
    assert counter["enemy_team"] == ["Cerise", "Lua", "Riolet"] and counter["teams"][0]["wins"] == 1
    with pytest.raises(urllib.error.HTTPError):  # résultat invalide
        call(base, "POST", f"/api/gvg/wars/{war}/attacks", {**attack, "result": "nul"}, t)
    g = call(base, "DELETE", f"/api/gvg/wars/{war}/attacks/{w['attacks'][0]['id']}", token=t)
    assert len(g["wars"][0]["attacks"]) == 1
    g = call(base, "PATCH", "/api/gvg/settings", {"attacks_per_member": 3, "towers": ["Fort A"]}, t)
    assert g["settings"] == {"attacks_per_member": 3, "towers": ["Fort A"]}
    assert call(base, "DELETE", f"/api/gvg/wars/{war}", token=t)["wars"] == []
