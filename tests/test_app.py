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
