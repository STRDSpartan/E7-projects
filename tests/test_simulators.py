"""Simulateurs de dégâts et de combat : formule, données des compétences, API."""

import json
import random
import urllib.request
from dataclasses import replace
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


# --- effets des compétences (soins, barrières, buffs, débuffs)
from e7showcase.calc.battle import _Battle  # noqa: E402
from e7showcase.parsers.skill_effects import parse_effects  # noqa: E402


def test_parse_effects_targets_turns_and_chances() -> None:
    ras = parse_effects(
        "Strongly attacks all enemies, before recovering the caster's Health and increasing "
        "Defense of all allies for 2 turns. Amount recovered increases proportional to the "
        "caster's Attack .",
        ["AoE", "Heal", "Increase Defense"],
        aoe=True,
    )
    assert {"type": "buff", "effect": "def_up", "target": "allies", "turns": 2} in ras
    heal = next(e for e in ras if e["type"] == "heal")
    assert heal["target"] == "self" and heal["stat"] == "atk" and heal["estimated"]
    stun = parse_effects("Attacks the enemy, with a 75% chance to stun for 1 turn.", ["Stun"])
    assert stun[0]["target"] == "target" and stun[0]["chance"] == 0.75 and stun[0]["turns"] == 1
    barrier = parse_effects(
        "Grants a barrier to the caster for 2 turns.", ["Barrier"], barrier={"atk": 0.65}
    )
    assert barrier[0]["ratio"] == 0.65 and not barrier[0]["estimated"]
    gauge = parse_effects(
        "Attacks the enemy, decreasing Combat Readiness by 30%. Increases Combat Readiness of "
        "the caster by 20%.",
        ["Increase Combat Readiness", "Decrease Combat Readiness"],
    )
    assert {(g["amount"], g["target"]) for g in gauge} == {(20, "self"), (-30, "target")}


def _skill(rate: float | None, *effects: dict[str, object], cooldown: int = 0) -> dict[str, object]:
    return {"rate": rate, "pow": 1, "enhance": [], "cooldown": cooldown, "effects": list(effects)}


def test_barrier_absorbs_heal_restores_and_stun_skips_turn() -> None:
    tank = Fighter(
        "Tank",
        1000,
        20000,
        1000,
        100,
        0,
        150,
        None,
        {
            "s1": _skill(1.0),
            "s2": _skill(
                None,
                {"type": "barrier", "target": "self", "stat": "hp", "ratio": 0.2, "turns": 2},
                cooldown=3,
            ),
        },
    )
    striker = Fighter(
        "Frappeur",
        3000,
        10000,
        500,
        300,
        0,
        150,
        None,
        {
            "s1": _skill(
                1.0,
                {
                    "type": "debuff",
                    "effect": "stun",
                    "target": "target",
                    "turns": 1,
                    "chance": 1.0,
                    "ignore_resist": True,
                },
            ),
        },
    )
    res = fight([tank], [striker], keep_log=True)
    log = "\n".join(res.log)
    assert "Étourdi → Tank" in log and "Tank ne peut pas agir" in log
    battle = _Battle([tank], [striker], random.Random(1), {"s2": 3, "s3": 4}, Options(), True)
    unit = battle.units[0]
    battle.apply(unit, tank.skills["s2"]["effects"][0], [])  # barrière de 4000
    assert unit.barrier == 4000
    battle.hit(battle.units[1], striker.skills["s1"], unit)
    assert unit.hp == 20000 and unit.barrier == pytest.approx(4000 - 1295, abs=2)
    unit.hp = 5000
    battle.apply(unit, {"type": "heal", "target": "self", "stat": "hp", "ratio": 0.15}, [])
    assert unit.hp == 8000


def test_attack_buff_raises_damage_and_expires() -> None:
    buffer = Fighter("Buff", 3000, 20000, 1000, 200, 0, 150, None, {"s1": _skill(1.0)})
    dummy = Fighter("Cible", 0, 10**6, 1000, 1, 0, 150, None, {"s1": _skill(None)})
    battle = _Battle([buffer], [dummy], random.Random(1), {}, Options(), True)
    me, foe = battle.units
    base = foe.hp
    battle.hit(me, buffer.skills["s1"], foe)
    plain = base - foe.hp
    battle.current = me
    battle.apply(me, {"type": "buff", "effect": "atk_up", "target": "self", "turns": 1}, [])
    before = foe.hp
    battle.hit(me, buffer.skills["s1"], foe)
    assert before - foe.hp == pytest.approx(plain * 1.5, rel=0.01)
    battle.end_turn(me)  # reçu pendant son tour : pas décompté
    assert "atk_up" in me.buffs
    battle.end_turn(me)
    assert "atk_up" not in me.buffs


def test_reference_skills_have_cooldowns_and_effects() -> None:
    heroes = load("skills")["heroes"]
    achates = heroes["achates"]["skills"]
    assert achates["s2"]["cooldown"] >= 1 and achates["s2"]["rate"] is None
    assert any(e["type"] == "heal" for e in achates["s3"]["effects"])
    with_effects = sum(1 for h in heroes.values() for s in h["skills"].values() if s.get("effects"))
    assert with_effects > 600


def test_parse_trigger_counter_revive_and_turn_events() -> None:
    from e7showcase.parsers.skill_effects import parse_trigger

    assert parse_trigger("When attacked, has a 30% chance to counterattack .", passive=True) == {
        "event": "counter",
        "chance": 0.3,
    }
    revive = parse_trigger("Upon receiving lethal damage, revives with 50% Health.", passive=True)
    assert revive == {"event": "revive", "chance": 1.0, "every": 99, "health": 0.5}
    start = parse_trigger(
        "At the start of the turn, increases Attack. Can only be activated once every 3 turns.",
        passive=True,
    )
    assert start == {"event": "turn_start", "chance": 1.0, "every": 3}
    assert parse_trigger("At the start of battle, grants a barrier.", passive=False) is None
    assert parse_trigger("Increases Critical Hit Chance by 30%.", passive=True) is None


def test_counterattack_passive_and_counter_set() -> None:
    counter = _skill(None)
    counter.update(passive=True, trigger={"event": "counter", "chance": 1.0})
    wall = Fighter("Mur", 1000, 10**6, 1000, 1, 0, 150, None, {"s1": _skill(1.0), "s2": counter})
    striker = Fighter("Frappeur", 1000, 10**6, 1000, 300, 0, 150, None, {"s1": _skill(1.0)})
    res = fight([wall], [striker], keep_log=True)
    assert "  ↳ Mur contre-attaque → Frappeur" in res.log[1]
    assert res.stats["counters"] >= 1
    plain = replace(wall, skills={"s1": _skill(1.0)})
    assert fight([plain], [striker]).stats["counters"] == 0
    with_set = replace(plain, counter_chance=100)
    assert fight([with_set], [striker]).stats["counters"] >= 1
    # pas de contre-attaque d'une contre-attaque
    both = replace(striker, counter_chance=100)
    battle = _Battle([with_set], [both], random.Random(1), {}, Options(), True)
    battle.counter(battle.units[0], battle.units[1])
    assert battle.stats["counters"] == 1


def test_passive_triggers_revive_and_battle_start() -> None:
    revive = _skill(None)
    revive.update(passive=True, trigger={"event": "revive", "every": 99, "health": 0.5})
    opening = _skill(None, {"type": "buff", "effect": "atk_up", "target": "self", "turns": 2})
    opening.update(passive=True, trigger={"event": "battle_start", "chance": 1.0})
    phoenix = Fighter(
        "Phénix", 1000, 1000, 0, 1, 0, 150, None, {"s1": _skill(1.0), "s2": revive, "s3": opening}
    )
    killer = Fighter("Tueur", 50000, 10**6, 1000, 300, 0, 150, None, {"s1": _skill(1.0)})
    battle = _Battle([phoenix], [killer], random.Random(1), {}, Options(), True)
    bird, foe = battle.units
    battle.fire(bird, "battle_start")
    assert "atk_up" in bird.buffs
    assert "ressuscite" in battle.hit(foe, killer.skills["s1"], bird) and bird.hp == 500
    battle.hit(foe, killer.skills["s1"], bird)
    assert not bird.alive  # une seule fois par combat


def test_parse_trigger_conditions_and_resources() -> None:
    from e7showcase.parsers.skill_effects import parse_trigger

    stark = parse_trigger(
        "When an ally is attacked, gains 10 Fighting Spirit, and when Fighting Spirit is full, "
        "activates Warrior's Strike on the attacker.",
        passive=True,
    )
    assert stark is not None and stark["event"] == "resource"
    assert stark["resource"] == {
        "kind": "spirit",
        "need": 100,
        "gain": 10,
        "on": "ally_attacked",
        "estimated": False,
    }
    jenua = parse_trigger(
        "After being attacked, when Health is 50% or less, activates Plan A.", passive=True
    )
    assert jenua == {
        "event": "attacked",
        "chance": 1.0,
        "condition": {"kind": "hp_below", "value": 0.5},
    }
    hurado = parse_trigger("When the enemy uses a non-attack skill, increases CR.", passive=True)
    assert hurado is not None and hurado["event"] == "enemy_skill"
    assert hurado["condition"] == {"kind": "non_attack"}


def test_conditional_passives_resource_lethal_and_ally_attacked() -> None:
    guard = _skill(1.0)
    guard.update(
        passive=True,
        trigger={
            "event": "resource",
            "chance": 1.0,
            "resource": {
                "kind": "spirit",
                "need": 100,
                "start": 80,
                "gain": 10,
                "on": "ally_attacked",
            },
        },
    )
    last = _skill(None, {"type": "buff", "effect": "immortal", "target": "self", "turns": 1})
    last.update(passive=True, trigger={"event": "lethal", "chance": 1.0, "every": 99})
    knight = Fighter(
        "Gardien", 1000, 5000, 0, 1, 0, 150, None, {"s1": _skill(1.0), "s2": guard, "s3": last}
    )
    ally = Fighter("Allié", 1000, 10**6, 1000, 1, 0, 150, None, {"s1": _skill(1.0)})
    foe = Fighter("Ennemi", 50000, 10**6, 1000, 300, 0, 150, None, {"s1": _skill(1.0)})
    battle = _Battle([knight, ally], [foe], random.Random(1), {}, Options(), True)
    me, friend, enemy = battle.units
    assert me.stacks["s2"] == 80
    battle.fire(me, "ally_attacked", enemy)
    assert me.stacks["s2"] == 90 and battle.stats["passives"] == 0
    battle.fire(me, "ally_attacked", enemy)
    assert me.stacks["s2"] == 0 and battle.stats["passives"] == 1  # jauge pleine : activée
    battle.hit(enemy, foe.skills["s1"], me)
    assert me.hp == 1 and "immortal" in me.buffs  # immortalité sur dégâts mortels
    me.buffs.clear()
    battle.hit(enemy, foe.skills["s1"], me)
    assert not me.alive  # une fois par combat
    assert friend.alive
