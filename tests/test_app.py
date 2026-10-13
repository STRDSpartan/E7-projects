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
    assert "Kise" in page and f"/media/{pid}/kise.webp?v=" in page  # image par adresse
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
    csv = call(base, "GET", f"/api/profiles/{pid}/csv", token=t)["csv"]
    assert csv.startswith("\ufeffJoueur;Guilde;") and "\nSpartan;;;1;1;1;" in csv
    assert "\nKise;;;;;;1000;;" in csv and "Porté par;Emplacement;Set" in csv
    assert "\nKise;Bottes;Vitesse;;;15;Vitesse 45;" in csv
    assert "\nNon équipée;Anneau;Destruction;;;12;Attaque 47 %;" in csv
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
    csv = call(base, "GET", "/api/guild/csv", token=t)["csv"]
    assert csv.startswith("\ufeffMembre;Origine;Héros;Puissance;Pièces;Héros les plus puissants")
    assert "Spartan;Mon profil;1;1000;1;Kise (1000);" in csv and "Spartan;Vitrine reçue;" in csv
    full = call(base, "GET", "/api/guild/full.csv", token=t)["csv"]
    assert full.startswith("\ufeffMembre;Origine;") and "\nMembre;Héros;Étoiles;" in full
    assert full.count("\nSpartan;Kise;;") == 2 and "\nMembre;Porté par;Emplacement;" in full
    assert full.count("\nSpartan;Kise;Bottes;Vitesse;;;15;Vitesse 45;") == 2
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
    assert g["settings"] == {"attacks_per_member": 3, "towers": ["Fort A"], "plan_counters": False}
    assert call(base, "DELETE", f"/api/gvg/wars/{war}", token=t)["wars"] == []
    plan = call(base, "GET", "/api/gvg/plan", token=t)
    assert "__Château__" in plan["text"] and "É1 : Belian, Lilias" in plan["text"]
    assert plan["csv"].startswith("\ufeffTour;Membre") and "Château;Spartan;2;Aria" in plan["csv"]


def test_defense_plan_splits_discord_messages_and_neutralises_formulas() -> None:
    from e7showcase.app.gvg import DISCORD_LIMIT, defense_plan

    trio = [["Belian", "Lilias", "Aria"]]
    members = [
        {"player": f"Joueur{i}", "defense": {"tower": "Fort", "teams": trio}} for i in range(80)
    ] + [{"player": "=HYPERLINK()", "defense": {"tower": "Fort", "teams": [["Aria"]]}},
         {"player": "Absent", "defense": {"tower": "", "teams": []}}]  # fmt: skip
    plan = defense_plan({"guild": "G", "settings": {"towers": ["Fort"]}, "members": members})
    assert len(plan["messages"]) > 1 and all(len(m) <= DISCORD_LIMIT for m in plan["messages"])
    assert "\n".join(plan["messages"]) == plan["text"] and "Sans défense : Absent" in plan["text"]
    assert "'=HYPERLINK()" in plan["csv"]  # pas de formule exécutée à l'ouverture du tableur


HOOK = "https://discord.com/api/webhooks/123456789012345678/" + "a" * 68


def test_gvg_plan_sent_to_discord_webhook(app: Any) -> None:
    import httpx

    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    state.store.add_hero(pid, Hero(name="Belian"), None)
    call(base, "PATCH", "/api/guild", {"members": [pid]}, t)
    call(base, "PUT", f"/api/gvg/defense/{pid}", {"tower": "Fort", "teams": [["Belian"]]}, t)
    with pytest.raises(urllib.error.HTTPError) as err:  # rien d'enregistré
        call(base, "POST", "/api/gvg/plan/send", {}, t)
    assert err.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as err:  # adresse qui n'est pas un webhook Discord
        call(base, "PUT", "/api/gvg/webhook", {"url": "https://evil.example/api/webhooks/1/x"}, t)
    assert err.value.code == 400
    status = call(base, "PUT", "/api/gvg/webhook", {"url": HOOK}, t)
    assert status["configured"] and "a" * 10 not in json.dumps(status)  # jeton jamais renvoyé
    posted: list[dict[str, Any]] = []

    def discord(request: httpx.Request) -> httpx.Response:
        posted.append(json.loads(request.content))
        return httpx.Response(204)

    state.webhook_transport = httpx.MockTransport(discord)
    assert call(base, "POST", "/api/gvg/plan/send", {}, t) == {"sent": 1}
    assert "**Spartan** — É1 : Belian" in posted[0]["content"]
    assert posted[0]["allowed_mentions"] == {"parse": []}  # aucune mention @everyone
    state.webhook_transport = httpx.MockTransport(lambda r: httpx.Response(404))
    with pytest.raises(urllib.error.HTTPError) as err:
        call(base, "POST", "/api/gvg/plan/send", {}, t)
    assert err.value.code == 502
    exported = call(base, "GET", f"/api/profiles/{pid}/export", token=t)
    assert b"webhooks" not in exported  # l'adresse ne voyage jamais dans une vitrine
    status = call(base, "PUT", "/api/gvg/webhook", {"auto": True}, t)
    assert status["auto"] and status["last_error"] is None
    assert call(base, "PUT", "/api/gvg/webhook", {"url": ""}, t)["configured"] is False


def test_post_messages_respects_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from e7showcase.publish import webhook

    calls: list[str] = []

    def discord(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["content"])
        if len(calls) == 2:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(204)

    monkeypatch.setattr(webhook.time, "sleep", lambda _s: None)
    sent = webhook.post_messages(HOOK, ["un", "deux"], transport=httpx.MockTransport(discord))
    assert len(sent) == 2 and calls == ["un", "deux", "deux"]
    assert webhook.mask_webhook(HOOK).startswith("webhook 1234…5678")
    for bad in ("http://discord.com/api/webhooks/123456789/" + "a" * 30, "https://discord.com/x"):
        assert not webhook.valid_webhook(bad)
    with pytest.raises(ValueError):
        webhook.post_messages("https://evil.example", ["x"])


def test_sync_messages_edits_reposts_and_deletes() -> None:
    import httpx

    from e7showcase.publish.webhook import sync_messages

    seen: list[tuple[str, str]] = []

    def discord(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path.rsplit("/", 1)[-1]))
        if request.method == "PATCH" and request.url.path.endswith("/11111"):
            return httpx.Response(404)  # message supprimé à la main dans Discord
        if request.method == "POST":
            return httpx.Response(200, json={"id": "99999"})
        return httpx.Response(200 if request.method == "PATCH" else 204, json={})

    ids = sync_messages(HOOK, ["a", "b"], ["10000", "11111", "12222"],
                        transport=httpx.MockTransport(discord))  # fmt: skip
    assert ids == ["10000", "99999"]
    assert seen == [("PATCH", "10000"), ("PATCH", "11111"), ("POST", "a" * 68),
                    ("DELETE", "12222")]  # fmt: skip


def test_auto_publish_groups_changes_and_updates_message(tmp_path: Path) -> None:
    import httpx

    from e7showcase.app.discord_settings import DiscordSettings, Publisher

    calls: list[str] = []

    def discord(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, json={"id": "55555"})

    settings = DiscordSettings(tmp_path / "discord.json")
    plan = ["plan v1"]
    pub = Publisher(settings, lambda _k: plan, lambda: httpx.MockTransport(discord), delay=0.05)
    pub.changed()  # pas de webhook / auto désactivé : rien
    time.sleep(0.15)
    assert calls == []
    settings.set_webhook(HOOK)
    settings.update(auto=True)
    for _ in range(5):  # cinq modifications rapprochées → une seule publication
        pub.changed()
    time.sleep(0.3)
    assert calls == ["POST"] and settings.message_ids() == ["55555"]
    plan[0] = "plan v2"
    pub.changed()
    time.sleep(0.3)
    assert calls == ["POST", "PATCH"]  # le message publié est modifié, pas reposté
    assert settings.status()["last_sent"] and not settings.status()["last_error"]
    pub.delay = 60
    pub.changed()
    pub.flush_pending()  # fermeture de l'application : publication immédiate
    assert calls == ["POST", "PATCH", "PATCH"]
    settings.set_webhook(HOOK.replace("1234", "4321"))  # autre salon : on repart de zéro
    assert settings.message_ids() == []


def test_war_report_sent_and_updated_on_each_attack(app: Any) -> None:
    import httpx

    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    for name in ("Belian", "Aria"):
        state.store.add_hero(pid, Hero(name=name), None)
    call(base, "PATCH", "/api/guild", {"name": "Spartiates", "members": [pid]}, t)
    war = call(base, "POST", "/api/gvg/wars", {"opponent": "Les Ombres", "date": "2026-10-12"}, t)
    wid = war["wars"][0]["id"]
    attack = {"member": pid, "team": ["Aria"], "enemy_team": ["Lua"], "enemy_player": "Shadow",
              "result": "win", "note": "facile"}  # fmt: skip
    call(base, "POST", f"/api/gvg/wars/{wid}/attacks", attack, t)
    report = state.publication("war:" + wid)
    assert report is not None and len(report) == 1
    text = report[0]
    assert "Spartiates contre Les Ombres" in text and "1 victoire(s)" in text
    assert "✅ **Spartan** (Aria) → Lua [Shadow] — facile" in text
    assert "Attaques restantes : Spartan (1/2)" in text
    calls: list[str] = []

    def discord(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, json={"id": "424242"})

    state.webhook_transport = httpx.MockTransport(discord)
    call(base, "PUT", "/api/gvg/webhook", {"url": HOOK, "auto_wars": True}, t)
    assert call(base, "POST", f"/api/gvg/wars/{wid}/send", {}, t) == {"sent": 1}
    state.publisher.delay = 0.05
    call(base, "POST", f"/api/gvg/wars/{wid}/attacks", {**attack, "result": "loss"}, t)
    time.sleep(0.4)
    assert calls == ["POST", "PATCH"]  # le suivi publié est modifié, pas reposté
    status = call(base, "GET", "/api/gvg/webhook", token=t)
    assert status["wars"][wid]["published"] and status["wars"][wid]["last_sent"]
    with pytest.raises(urllib.error.HTTPError) as err:
        call(base, "POST", "/api/gvg/wars/abcdef/send", {}, t)
    assert err.value.code == 400
    call(base, "DELETE", f"/api/gvg/wars/{wid}", token=t)
    assert wid not in call(base, "GET", "/api/gvg/webhook", token=t)["wars"]
    assert state.publication("war:" + wid) is None


def test_counters_sent_and_updated_on_new_attack(app: Any) -> None:
    import httpx

    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    for name in ("Belian", "Aria"):
        state.store.add_hero(pid, Hero(name=name), None)
    call(base, "PATCH", "/api/guild", {"members": [pid]}, t)
    wid = call(base, "POST", "/api/gvg/wars", {"opponent": "Ombres"}, t)["wars"][0]["id"]
    attack = {"member": pid, "team": ["Aria", "Belian"], "enemy_team": ["Lua", "Cerise"],
              "result": "win"}  # fmt: skip
    call(base, "POST", f"/api/gvg/wars/{wid}/attacks", attack, t)
    text = state.publication("counters")[0]
    assert "__Cerise · Lua__ (1 V / 0 D)" in text and "✅ Aria, Belian — 1 V / 0 D" in text
    calls: list[str] = []

    def discord(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, json={"id": "313131"})

    state.webhook_transport = httpx.MockTransport(discord)
    call(base, "PUT", "/api/gvg/webhook", {"url": HOOK, "auto_counters": True}, t)
    assert call(base, "POST", "/api/gvg/counters/send", {}, t) == {"sent": 1}
    state.publisher.delay = 0.05
    call(base, "POST", f"/api/gvg/wars/{wid}/attacks", {**attack, "result": "loss"}, t)
    time.sleep(0.4)
    assert calls == ["POST", "PATCH"]
    assert "⚖️ Aria, Belian — 1 V / 1 D" in state.publication("counters")[0]
    status = call(base, "GET", "/api/gvg/webhook", token=t)
    assert status["auto_counters"] and status["counters"]["published"]


def test_defense_plan_can_include_counters(app: Any) -> None:
    import httpx

    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    for name in ("Belian", "Aria"):
        state.store.add_hero(pid, Hero(name=name), None)
    call(base, "PATCH", "/api/guild", {"members": [pid]}, t)
    call(base, "PUT", f"/api/gvg/defense/{pid}", {"tower": "Fort", "teams": [["Belian"]]}, t)
    wid = call(base, "POST", "/api/gvg/wars", {"opponent": "Ombres"}, t)["wars"][0]["id"]
    attack = {"member": pid, "team": ["Aria"], "enemy_team": ["Lua"], "result": "win"}
    call(base, "POST", f"/api/gvg/wars/{wid}/attacks", attack, t)
    assert "Contres connus" not in call(base, "GET", "/api/gvg/plan", token=t)["text"]
    call(base, "PATCH", "/api/gvg/settings", {"plan_counters": True}, t)
    text = call(base, "GET", "/api/gvg/plan", token=t)["text"]
    assert "__Fort__" in text and "**Contres connus**" in text and "✅ Aria — 1 V / 0 D" in text
    csv = call(base, "GET", "/api/gvg/plan", token=t)["csv"]
    assert "Défense ennemie;Équipe d'attaque;Victoires;Défaites;Bilan" in csv
    assert "Lua;Aria;1;0;gagnée" in csv
    assert "Guerre;Date;Membre;Équipe;Défense ennemie;Joueur ennemi;Tour;Résultat;Note" in csv
    assert ";Spartan;Aria;Lua;;;victoire;" in csv and "Attaques restantes" in csv
    alone = call(base, "GET", "/api/gvg/wars/csv", token=t)["csv"]
    assert alone.startswith("\ufeffGuerre;Date;Membre") and "Fort" not in alone
    assert "Ombres;" in alone and "Défense ennemie;Équipe d'attaque" not in alone
    only = call(base, "GET", "/api/gvg/counters/csv", token=t)["csv"]
    assert (
        only
        == "\ufeffDéfense ennemie;Équipe d'attaque;Victoires;Défaites;Bilan\nLua;Aria;1;0;gagnée\n"
    )
    calls: list[str] = []

    def discord(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, json={"id": "616161"})

    state.webhook_transport = httpx.MockTransport(discord)
    call(base, "PUT", "/api/gvg/webhook", {"url": HOOK, "auto": True}, t)
    call(base, "POST", "/api/gvg/plan/send", {}, t)
    state.publisher.delay = 0.05
    call(base, "POST", f"/api/gvg/wars/{wid}/attacks", {**attack, "result": "loss"}, t)
    time.sleep(0.4)
    assert calls == ["POST", "PATCH"]  # nouvelle attaque : le plan publié (avec contres) suit


def test_guild_csv_round_trip(app: Any, tmp_path: Path) -> None:
    from e7showcase.app.server import AppState
    from e7showcase.models.gear import Gear, GearSet, GearSlot, StatLine
    from e7showcase.models.stats import StatType

    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    mate = call(base, "POST", "/api/profiles", {"player": "Lua=1"}, t)["id"]
    boots = Gear(slot=GearSlot.BOOTS, set=GearSet.SPEED, enhance=15,
                 main=StatLine(stat=StatType.SPD, value=45),
                 substats=[StatLine(stat=StatType.CRIT_CHANCE, value=12)])  # fmt: skip
    ring = Gear(slot=GearSlot.RING, set=GearSet.DESTRUCTION, enhance=12,
                main=StatLine(stat=StatType.ATK_PCT, value=47))  # fmt: skip
    for p in (pid, mate):
        state.store.add_hero(pid if p == pid else mate, Hero(name="Belian", power=900), None)
        state.store.add_hero(p, Hero(name="Aria", power=500, gear={GearSlot.BOOTS: boots}), None)
    state.store.add_item(mate, ring)
    call(base, "PATCH", "/api/guild", {"members": [pid, mate]}, t)
    call(base, "PUT", f"/api/gvg/defense/{mate}", {"tower": "Fort", "teams": [["Belian"]]}, t)
    wid = call(base, "POST", "/api/gvg/wars", {"opponent": "Ombres", "date": "2026-10-01"}, t)
    attack = {"member": mate, "team": ["Aria"], "enemy_team": ["Lua", "Cerise"], "result": "win"}
    call(base, "POST", f"/api/gvg/wars/{wid['wars'][0]['id']}/attacks", attack, t)
    exported = call(base, "GET", "/api/guild/full.csv", token=t)["csv"]

    # autre ordinateur : le joueur a son propre profil « Spartan », rien d'autre
    other = AppState(tmp_path / "other")
    own = other.store.create("Spartan")
    from e7showcase.app.guild_import import import_guild_csv

    report = import_guild_csv(exported, other.store, other.guild, other.gvg)
    assert report.created == ["Lua=1"] and report.kept == ["Spartan"] and not report.errors
    assert report.defenses == 1 and report.wars == 1 and report.attacks == 1
    members = other.guild.summary()["members"]
    assert {m["player"] for m in members} == {"Spartan", "Lua=1"}
    rid = next(m["id"] for m in members if m["player"] == "Lua=1")
    assert other.store.is_received(rid) and not other.store.load(own).heroes
    roster = other.store.load(rid)
    aria = next(h for h in roster.heroes if h.name == "Aria")
    assert aria.power == 500 and aria.gear[GearSlot.BOOTS] == boots
    assert [i.gear for i in roster.inventory] == [ring]
    g = other.gvg.summary()
    assert g["counters"][0]["enemy_team"] == ["Cerise", "Lua"]
    assert g["wars"][0]["opponent"] == "Ombres" and g["wars"][0]["date"] == "2026-10-01"
    # réimport : rien n'est dupliqué, la vitrine reçue est mise à jour
    again = import_guild_csv(exported, other.store, other.guild, other.gvg)
    assert again.updated == ["Lua=1"] and again.wars == 0
    assert len(other.gvg.summary()["wars"]) == 1 and len(other.store.list()) == 2
    with pytest.raises(ValueError, match="toute la guilde"):
        import_guild_csv("a;b\n1;2\n", other.store, other.guild, other.gvg)
    r = call(base, "POST", "/api/guild/import", {"csv": exported}, t)
    assert sorted(r["kept"]) == ["Lua=1", "Spartan"]  # profils locaux jamais écrasés


def test_portraits_api(app: Any) -> None:
    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    state.store.add_hero(pid, Hero(name="Kise", element="ice", stars=5), None)
    state.store.save_portrait(pid, "Kise", Image.new("RGB", (60, 60), (10, 20, 200)))
    data = call(base, "POST", "/api/portraits", {"names": ["Kise", "Inconnu", ""]}, t)
    assert data["Kise"]["img"].startswith("data:image/webp;base64,")
    assert data["Kise"]["element"] == "ice" and data["Kise"]["stars"] == 5
    assert data["Inconnu"]["img"] is None and "" not in data


def test_app_pages_send_security_headers(app: Any) -> None:
    state, base = app
    pid = state.store.create("Spartan")
    for path in ("/", f"/profile/{pid}"):
        with urllib.request.urlopen(base + path) as res:
            csp = res.headers["Content-Security-Policy"]
            assert res.headers["Referrer-Policy"] == "no-referrer"
        assert "default-src 'none'" in csp and "frame-ancestors 'self'" in csp
        assert "http" not in csp  # aucune ressource externe sur ces pages


def test_screenshots_uploaded_as_raw_binary(app: Any) -> None:
    state, base = app
    t = state.token
    pid = call(base, "POST", "/api/profiles", {"player": "Spartan"}, t)["id"]
    req = urllib.request.Request(
        base + f"/api/profiles/{pid}/uploads", method="POST", data=b"\x89PNG brut"
    )
    req.add_header("X-E7-Token", t)
    req.add_header("X-File-Name", "h%C3%A9ros.png")
    with urllib.request.urlopen(req) as res:
        upload = json.loads(res.read())["id"]
    started = call(base, "POST", f"/api/profiles/{pid}/screenshots", {"uploads": [upload]}, t)
    for _ in range(100):
        if call(base, "GET", f"/api/jobs/{started['job']}", token=t)["finished"]:
            break
        time.sleep(0.05)
    assert state.importer.calls[-1] == [("héros.png", b"\x89PNG brut")]
    with pytest.raises(urllib.error.HTTPError) as err:  # déjà consommée
        call(base, "POST", f"/api/profiles/{pid}/screenshots", {"uploads": [upload]}, t)
    assert err.value.code == 400


def test_concurrent_edits_are_not_lost(app: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    state, base = app
    t = state.token
    pids = []
    for i in range(12):
        pid = state.store.create(f"Membre{i}")
        state.store.add_hero(pid, Hero(name="Kise"), None)
        pids.append(pid)
    call(base, "PATCH", "/api/guild", {"members": pids}, t)

    def put(pid: str) -> None:
        call(base, "PUT", f"/api/gvg/defense/{pid}", {"tower": pid, "teams": [["Kise"]]}, t)

    with ThreadPoolExecutor(12) as pool:  # l'interface enregistre à chaque changement
        list(pool.map(put, pids))
    members = call(base, "GET", "/api/gvg", token=t)["members"]
    assert {m["id"]: m["defense"]["tower"] for m in members} == {p: p for p in pids}


def test_vitrine_images_served_by_url_and_page_cached(app: Any) -> None:
    import re as re_

    state, base = app
    pid = state.store.create("Spartan")
    state.store.add_hero(pid, Hero(name="Kise"), Image.new("RGB", (640, 900), (200, 40, 40)))
    page = call(base, "GET", f"/profile/{pid}").decode()
    url = re_.search(rf"/media/{pid}/kise\.webp\?v=\d+", page)
    assert url and "data:image/webp" not in page
    with urllib.request.urlopen(base + url[0]) as res:
        assert res.headers["Content-Type"] == "image/webp"
        assert "immutable" in res.headers["Cache-Control"]
        full = res.read()
    with urllib.request.urlopen(base + url[0] + "&w=160") as res:
        thumb = Image.open(io.BytesIO(res.read()))
    assert thumb.width == 160 and len(full) > 0
    assert call(base, "GET", f"/profile/{pid}").decode() == page  # page gardée en mémoire
    state.store.add_hero(pid, Hero(name="Aria"), None)
    assert "Aria" in call(base, "GET", f"/profile/{pid}").decode()  # invalidée au changement
    for bad in (f"/media/{pid}/../meta.json", f"/media/{pid}/profile.json", "/media/x/kise.webp"):
        with pytest.raises(urllib.error.HTTPError) as err:
            call(base, "GET", bad)
        assert err.value.code == 404


def test_gvg_scouted_defense_and_simulation_with_read_stats(app: Any) -> None:
    state, base = app
    t = state.token
    bellona = {"atk": 4653, "def": 1567, "hp": 19325, "spd": 106, "crit_chance": 15,
               "crit_dmg": 279, "effectiveness": 0, "effect_res": 0, "dual_attack": 3}  # fmt: skip
    body = {"player": "Ombre", "heroes": [{"name": "Bellona Lune solitaire", "stats": bellona},
                                          {"name": "Lua", "stats": {}}, {"name": ""}]}  # fmt: skip
    g = call(base, "POST", "/api/gvg/scouted", body, t)
    sc = g["scouted"][0]
    assert sc["player"] == "Ombre" and [h["name"] for h in sc["heroes"]] == [
        "Bellona Lune solitaire",
        "Lua",
    ]
    assert sc["heroes"][0]["stats"]["crit_dmg"] == 279 and sc["heroes"][1]["stats"] == {}
    sim = {
        "team_a": [{"name": "Kise", "estimate": True}],
        "team_b": [{"name": "Bellona Lune solitaire", "stats": bellona},
                   {"name": "Lua", "estimate": True}],
        "runs": 20,
    }  # fmt: skip
    r = call(base, "POST", "/api/sim/battle", sim, t)
    assert r["teams"][1] == ["Bellona Lune solitaire (relevé)", "Lua (estimé)"]
    call(base, "DELETE", f"/api/gvg/scouted/{sc['id']}", token=t)
    assert call(base, "GET", "/api/gvg", token=t)["scouted"] == []
    with pytest.raises(urllib.error.HTTPError) as err:
        call(base, "POST", "/api/gvg/scouted", {"heroes": []}, t)
    assert err.value.code == 400
    status = call(base, "GET", "/api/gvg/faces", token=t)
    assert status["count"] == 0 and status["total"] > 300 and not status["running"]


def test_gvg_report_rejects_other_images(app: Any) -> None:
    state, base = app

    class NoText:  # moteur OCR factice : aucun texte reconnu
        def read_boxes(self, image: Any) -> list[Any]:
            return []

    state._ocr = NoText()
    buf = io.BytesIO()
    Image.new("RGB", (400, 200), (20, 30, 40)).save(buf, "PNG")
    req = urllib.request.Request(base + "/api/gvg/report", method="POST", data=buf.getvalue())
    req.add_header("X-E7-Token", state.token)
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req)
    assert err.value.code == 400 and "fin de combat" in json.loads(err.value.read())["error"]


def test_gvg_war_map_and_fortress_flow(app: Any) -> None:
    from tests.test_war_map import lines

    state, base = app
    t = state.token

    class Fixture:  # moteur OCR factice : renvoie le texte relevé sur une vraie capture
        name = "gvg_war_map_ocr.json"

        def read_boxes(self, image: Any) -> list[Any]:
            return lines(self.name)

    engine = Fixture()
    state._ocr = engine
    buf = io.BytesIO()
    Image.new("RGB", (2000, 1125), (20, 30, 50)).save(buf, "PNG")
    shot = buf.getvalue()

    def upload(path: str) -> Any:
        req = urllib.request.Request(base + "/api" + path, method="POST", data=shot)
        req.add_header("X-E7-Token", t)
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read())

    g = upload("/gvg/map")
    m = g["map"]
    assert m["enemy"]["name"] == "Omega" and [f["total"] for f in m["fortresses"]] == [10, 7, 6]
    assert g["wars"][0]["opponent"] == "Omega"  # la guerre du jour rejoint le suivi
    assert m["image"] is None  # captures lues seulement, ni gardées ni affichées
    engine.name = "gvg_fortress_ocr.json"
    g = upload("/gvg/map/fortress")  # 10 joueurs : la forteresse « 10/10 », sans la désigner
    dard = g["map"]["fortresses"][0]
    assert len(dard["players"]) == 10 and dard["image"] is None
    call(base, "PATCH", "/api/gvg/map/fortress/f0/players/0", {"beaten": True, "name": "Zed"}, t)
    g = call(base, "PATCH", "/api/gvg/map/fortress/f0/players/1", {"present": False}, t)
    assert g["map"]["fortresses"][0]["players"][1]["present"] is False
    engine.name = "gvg_war_map_ocr.json"
    g = upload("/gvg/map")  # même guerre : joueurs et capture de forteresse conservés
    first = g["map"]["fortresses"][0]["players"][0]
    assert first["name"] == "Zed" and first["beaten"] and len(g["wars"]) == 1
    assert g["settings"]["towers"][:3] == [f["name"] for f in g["map"]["fortresses"]]
    req = urllib.request.Request(base + "/api/gvg/background", method="POST", data=shot)
    req.add_header("X-E7-Token", t)
    with urllib.request.urlopen(req) as res:
        bg = json.loads(res.read())["background"]
    with urllib.request.urlopen(base + bg) as res:  # image de fond servie localement
        assert res.headers["Content-Type"] == "image/webp"
    call(base, "DELETE", "/api/gvg/background", token=t)
    assert call(base, "GET", "/api/gvg", token=t)["background"] is None
    g = call(base, "POST", "/api/gvg/map/archive", token=t)  # archivée puis effacée
    assert g["map"] is None and len(g["archives"]) == 1
    arch = g["archives"][0]
    assert arch["opponent"] == "Omega" and arch["fortresses"][0]["beaten"] == 1
    upload("/gvg/map")
    call(base, "DELETE", "/api/gvg/archives/" + arch["id"], token=t)
    call(base, "DELETE", "/api/gvg/map", token=t)
    g = call(base, "GET", "/api/gvg", token=t)
    assert g["map"] is None and g["archives"] == []
    assert not list(state.war_images.glob("*.webp"))
    for bad in ("/gvgmap/../gvg.json", "/gvgmap/abc.webp"):
        with pytest.raises(urllib.error.HTTPError) as err:
            call(base, "GET", bad)
        assert err.value.code == 404


def test_gvg_report_without_faces_starts_download(app: Any) -> None:
    from tests.test_battle_report import lines

    state, base = app

    class Fixture:  # moteur OCR factice : texte relevé sur une vraie capture
        def read_boxes(self, image: Any) -> list[Any]:
            return lines()

    started: list[bool] = []
    state._ocr = Fixture()
    state.start_face_sync = lambda: started.append(True)
    buf = io.BytesIO()
    Image.new("RGB", (2000, 1125), (20, 30, 40)).save(buf, "PNG")
    req = urllib.request.Request(base + "/api/gvg/report", method="POST", data=buf.getvalue())
    req.add_header("X-E7-Token", state.token)
    with urllib.request.urlopen(req) as res:
        found = json.loads(res.read())
    assert found["faces_missing"] is True and started == [True]


def test_gvg_history_win_rate_by_composition() -> None:
    from e7showcase.app.gvg import GvgStore

    def atk(team: list[str], result: str) -> dict[str, Any]:
        return {"team": team, "enemy_team": ["Zed"], "result": result}

    data = {
        "wars": [{"id": "w1", "attacks": [atk(["B", "A"], "win"), atk(["A", "B"], "loss")]}],
        "archives": [
            {"war_id": "w1", "attacks": [atk(["A", "B"], "win")]},  # déjà compté (suivi gardé)
            {"war_id": "old", "attacks": [atk(["A", "B"], "win"), atk(["C"], "loss")]},
        ],
    }
    rows = GvgStore.history(data)
    assert rows[0]["team"] == ["A", "B"] and (rows[0]["wins"], rows[0]["fights"]) == (2, 3)
    assert rows[0]["rate"] == 67 and rows[0]["vs"]["Zed"] == {"wins": 2, "losses": 1}
    assert rows[1]["team"] == ["C"] and rows[1]["rate"] == 0
