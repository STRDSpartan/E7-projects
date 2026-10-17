"""Héritage des temps anciens : préparation, répartition, rôles, boss, reliques, OCR, Discord."""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from e7showcase.app.guild import GuildStore
from e7showcase.app.hta import HtaError, HtaStore, guess_role, hta_report
from e7showcase.app.profiles import ProfileStore
from e7showcase.app.server import AppState, start_server
from e7showcase.models.hero import Hero, HeroStats
from e7showcase.parsers.enlisted import match_enlisted
from e7showcase.vision.ocr import OcrLine

HOOK = "https://discord.com/api/webhooks/123456789012345678/" + "a" * 68


def _setup(tmp_path: Path) -> tuple[HtaStore, str]:
    profiles = ProfileStore(tmp_path / "profiles")
    guild = GuildStore(tmp_path / "guild.json", profiles)
    pid = profiles.create("Spartan")
    for name, element, power in (
        ("Ras", "fire", 10),
        ("Kise", "ice", 30),
        ("Achates", "fire", 20),
        ("Cecilia", "fire", 5),
    ):
        stats = HeroStats(atk=3000, hp=15000, spd=200, crit_chance=80, crit_dmg=250)
        profiles.add_hero(pid, Hero(name=name, element=element, power=power, stats=stats), None)
    guild.update(members=[pid])
    return HtaStore(tmp_path / "hta.json", profiles, guild), pid


def test_guess_role_from_skills() -> None:
    assert guess_role("Ras") == "dual"
    assert guess_role("Achates") == "healer"
    assert guess_role("Cecilia") == "support"
    assert guess_role("Kise") == "dps"


def test_member_plan_coverage_and_suggestions(tmp_path: Path) -> None:
    hta, pid = _setup(tmp_path)
    hta.set_member(pid, {"element": "fire", "specialty": "dark", "enlisted": ["ras", "Kise"]})
    s = hta.summary()
    member = s["members"][0]
    assert member["enlisted"] == ["Ras", "Kise"] and member["element"] == "fire"
    assert s["coverage"]["missing"] == ["ice", "earth", "light"]
    names = [r["name"] for r in hta.suggestions(pid)]
    assert names == ["Ras", "Cecilia", "Achates"]  # éléments du plan, rôle puis puissance
    assert [r["name"] for r in hta.suggestions(pid, "ice")] == ["Kise"]
    for bad in ({"element": "light"}, {"specialty": "fire"}, {"enlisted": ["Inconnu"]}):
        with pytest.raises(HtaError):
            hta.set_member(pid, bad)
    with pytest.raises(HtaError):
        hta.set_member("absent", {})


def test_tiers_override_export_and_import(tmp_path: Path) -> None:
    hta, pid = _setup(tmp_path)
    hta.set_member(pid, {"element": "fire"})
    hta.set_tier({"hero": "Cecilia", "role": "dps", "solo": True})
    first = hta.suggestions(pid)[0]
    assert first["name"] == "Cecilia" and first["solo"] and not first["auto"]
    shared = hta.export_tiers()
    hta.set_tier({"hero": "Cecilia"})  # retour au rôle déduit
    assert hta.summary()["tiers"] == {}
    assert hta.import_tiers(shared) == 1 and "Cécilia" in hta.summary()["tiers"]
    for bad in ({"hero": "Inconnu", "role": "dps"}, {"hero": "Ras", "role": "tank"}):
        with pytest.raises(HtaError):
            hta.set_tier(bad)
    with pytest.raises(HtaError):
        hta.import_tiers({"tiers": {}})


def test_season_bosses_relics_and_report(tmp_path: Path) -> None:
    hta, pid = _setup(tmp_path)
    hta.update_season(
        {
            "number": 16,
            "floor": 2,
            "withdrawals": 5,
            "exchange_closes": "2026-11-01",
            "bosses_killed": ["Gardien", " "],
            "notice": "Feu sur l'étage 1",
        }
    )
    with pytest.raises(HtaError):
        hta.update_season({"exchange_closes": "01/11/2026"})
    hta.set_member(pid, {"element": "fire", "enlisted": ["Ras"], "withdrawals_used": 2})
    boss = hta.add_boss(
        {
            "name": "Frongo",
            "floor": 3,
            "element": "light",
            "hp": 1_000_000,
            "def": 1200,
            "mechanics": "Purger les buffs",
            "member": pid,
            "team": ["Ras", "Kise"],
        }
    )
    with pytest.raises(HtaError):
        hta.add_boss({"name": "X", "member": pid, "team": ["Inconnu"]})
    est = hta.estimate(boss)
    assert [r["hero"] for r in est["rows"]] == ["Ras", "Kise"]
    assert est["total"] > 0 and est["rounds"] >= 1
    hta.add_relic({"name": "Journal de l'équipe d'exploration", "priority": 1})
    hta.add_relic({"name": "Relique moyenne", "priority": 2})
    text = "\n".join(hta_report(hta.summary()))
    assert "Saison 16" in text and "Feu : Spartan" in text and "Terre : ⚠️ personne" in text
    assert "**Frongo** (étage 3) : Ras, Kise — Spartan" in text and "> Purger les buffs" in text
    assert "Journal de l'équipe d'exploration" in text and "Relique moyenne" not in text
    hta.new_season()
    s = hta.summary()
    assert s["season"]["number"] == 17 and s["season"]["withdrawals"] == 5
    assert s["members"][0]["enlisted"] == [] and s["members"][0]["withdrawals_used"] == 0
    hta.delete_boss(boss)
    assert hta.summary()["bosses"] == []


def test_match_enlisted_reads_only_roster_names() -> None:
    lines = [
        OcrLine("Lv.60", 0.9, 10, (0, 10, 40, 30)),
        OcrLine("Kise", 0.9, 100, (300, 100, 360, 120)),
        OcrLine("Achales", 0.8, 100, (10, 100, 80, 120)),  # bruit OCR
        OcrLine("Enrôlement", 0.9, 5, (0, 0, 100, 20)),
        OcrLine("Kise", 0.9, 200, (10, 200, 60, 220)),
    ]
    assert match_enlisted(lines, ["Kise", "Achates", "Ras"]) == ["Achates", "Kise"]
    assert match_enlisted(lines, []) == []


def call(base: str, method: str, path: str, token: str, body: Any = None) -> Any:
    req = urllib.request.Request(
        base + path, method=method, data=json.dumps(body).encode() if body is not None else None
    )
    req.add_header("X-E7-Token", token)
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())


def test_hta_api_and_discord(tmp_path: Path) -> None:
    import httpx

    state = AppState(tmp_path)
    server = start_server(state)
    base, t = f"http://127.0.0.1:{server.server_address[1]}", state.token
    try:
        pid = call(base, "POST", "/api/profiles", t, {"player": "Spartan"})["id"]
        state.store.add_hero(pid, Hero(name="Ras", element="fire"), None)
        assert call(base, "GET", "/api/hta", t)["members"] == []
        call(base, "PATCH", "/api/guild", t, {"members": [pid]})
        h = call(base, "PUT", f"/api/hta/members/{pid}", t, {"element": "fire"})
        assert h["members"][0]["element"] == "fire"
        assert call(base, "GET", f"/api/hta/suggest/{pid}", t)[0]["role"] == "dual"
        h = call(
            base, "POST", "/api/hta/bosses", t, {"name": "Frongo", "member": pid, "team": ["Ras"]}
        )
        boss = h["bosses"][0]["id"]
        assert call(base, "GET", f"/api/hta/bosses/{boss}/estimate", t)["rows"][0]["hero"] == "Ras"
        with pytest.raises(urllib.error.HTTPError) as err:
            call(base, "PUT", f"/api/hta/members/{pid}", t, {"element": "rouge"})
        assert err.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as err:  # pas encore de webhook
            call(base, "POST", "/api/hta/send", t, {})
        assert err.value.code == 400
        call(base, "PUT", "/api/gvg/webhook", t, {"url": HOOK})
        posted: list[dict[str, Any]] = []

        def discord(request: httpx.Request) -> httpx.Response:
            posted.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "1"})

        state.webhook_transport = httpx.MockTransport(discord)
        assert call(base, "POST", "/api/hta/send", t, {}) == {"sent": 1}
        assert "Héritage des temps anciens" in posted[0]["content"]
        assert "Frongo" in call(base, "GET", "/api/hta/report", t)["messages"][0]
    finally:
        server.shutdown()
