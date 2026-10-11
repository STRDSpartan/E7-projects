"""Simulateurs de dégâts et de combat : formule, données des compétences, API."""

import json
import urllib.request
from pathlib import Path

import pytest

from e7showcase.app.profiles import ProfileStore
from e7showcase.app.server import AppState, start_server
from e7showcase.app.simulator import SimError, battle, damage
from e7showcase.calc.battle import fight, simulate
from e7showcase.calc.damage import Fighter, Options, damage_table, hero_skills, skill_damage
from e7showcase.models.hero import Hero, HeroStats
from e7showcase.reference import load


def kise() -> Fighter:
    data = hero_skills("Kise")
    assert data is not None
    return Fighter("Kise", 4088, 9236, 900, 265, 94, 290, "ice", data["skills"])


def target() -> Fighter:
    return Fighter("Cible", 1500, 20000, 1000, 200, 15, 150, "earth")


def test_formula_matches_hand_calculation() -> None:
    # 4088 × 1,6 × 1,871 × 1,3 (molagoras) / (1000/300 + 1) = 3671 ; × 2,9 = 10647
    s3 = skill_damage(kise(), kise().skills["s3"], target())
    assert s3["normal"] == 3671 and s3["crit"] == 10647 and s3["miss"] == 2754
    buffed = skill_damage(kise(), kise().skills["s3"], target(), Options(attack_buff="up"))
    assert buffed["normal"] == pytest.approx(3671 * 1.5, abs=1)
    broken = skill_damage(
        kise(), kise().skills["s3"], target(), Options(target_defense_buff="down")
    )
    assert broken["normal"] > 1.8 * s3["normal"]  # défense réduite de 70 %


def test_soulburn_and_conditional_flags() -> None:
    rows = {r["skill"]: r for r in damage_table(kise(), target())}
    assert rows["S2 (âme brûlée)"]["normal"] > rows["S2"]["normal"] and rows["S2"]["aoe"]
    assert rows["S3"]["conditional"] == ["caster_left_hp_pc"]


def test_almost_every_hero_has_multipliers() -> None:
    heroes = load("heroes")["heroes"]
    known = sum(1 for h in heroes if hero_skills(h["en"]))
    assert known >= 0.97 * len(heroes)
    assert hero_skills("Coli tactique") and hero_skills("Baal & Sezan")


def test_battle_is_reproducible_and_faster_hero_acts_first() -> None:
    a, b = [kise()], [Fighter("Cible", 1500, 20000, 1000, 100, 15, 150, "earth", kise().skills)]
    one = simulate(a, b, runs=200, seed=3)
    assert one == simulate(a, b, runs=200, seed=3)
    assert sum(one["win_rate"]) + one["draws"] == pytest.approx(100, abs=0.2)
    assert fight(a, b).log[0].split("(")[0].strip().endswith("Kise")


@pytest.fixture
def store(tmp_path: Path) -> tuple[ProfileStore, str]:
    store = ProfileStore(tmp_path / "profiles")
    pid = store.create("Moi")
    stats = HeroStats(atk=4088, hp=9236, defense=900, spd=265, crit_chance=94, crit_dmg=290)
    store.add_hero(pid, Hero(name="Kise", element="ice", stats=stats), None)
    store.add_hero(pid, Hero(name="Inconnu", stats=stats), None)
    return store, pid


def test_service_damage_and_battle(store: tuple[ProfileStore, str]) -> None:
    st, pid = store
    res = damage(st, {"attacker": f"{pid}/Kise", "target": {"def": 1000, "hp": 20000}})
    assert {r["skill"] for r in res["rows"]} >= {"S1", "S3"}
    duel = battle(st, {"team_a": [f"{pid}/Kise"], "team_b": [f"{pid}/Kise"], "runs": 50})
    assert duel["runs"] == 50 and duel["sample"]["log"]
    for bad in ({"attacker": f"{pid}/Inconnu"}, {"attacker": "../x"}):
        with pytest.raises(SimError):
            damage(st, bad)
    with pytest.raises(SimError):
        battle(st, {"team_a": [], "team_b": [f"{pid}/Kise"]})


def test_sim_api_requires_token(tmp_path: Path) -> None:
    state = AppState(tmp_path)
    server = start_server(state)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    req = urllib.request.Request(base + "/api/sim/heroes", headers={"X-E7-Token": state.token})
    with urllib.request.urlopen(req) as res:
        assert json.loads(res.read()) == []
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(base + "/api/sim/heroes")
    server.shutdown()
