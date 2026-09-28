import pytest

from e7showcase.calc.gear_score import gear_score
from e7showcase.calc.sets import active_sets
from e7showcase.models.gear import Gear, GearSet, GearSlot, StatLine
from e7showcase.models.stats import StatType
from e7showcase.parsers.gear_parser import parse_gear, parse_set
from e7showcase.parsers.stat_parser import StatParseError


def _gear(slot: GearSlot, set_: GearSet) -> Gear:
    return Gear(slot=slot, set=set_, main=StatLine(stat=StatType.ATK, value=100))


def test_gear_score_matches_community_formula() -> None:
    g = Gear(
        slot=GearSlot.RING,
        main=StatLine(stat=StatType.ATK_PCT, value=65),
        substats=[
            StatLine(stat=StatType.SPD, value=10),  # 20
            StatLine(stat=StatType.CRIT_CHANCE, value=10),  # 16
            StatLine(stat=StatType.CRIT_DMG, value=14),  # 16
            StatLine(stat=StatType.ATK_PCT, value=8),  # 8
        ],
    )
    assert gear_score(g) == 60.0


def test_active_sets() -> None:
    gear = [
        _gear(GearSlot.WEAPON, GearSet.SPEED),
        _gear(GearSlot.HELMET, GearSet.SPEED),
        _gear(GearSlot.ARMOR, GearSet.SPEED),
        _gear(GearSlot.NECKLACE, GearSet.SPEED),
        _gear(GearSlot.RING, GearSet.CRITICAL),
        _gear(GearSlot.BOOTS, GearSet.CRITICAL),
    ]
    assert active_sets(gear) == ["speed", "critical"]


def test_broken_set_not_counted() -> None:
    gear = [_gear(GearSlot.WEAPON, GearSet.SPEED), _gear(GearSlot.HELMET, GearSet.HIT)]
    assert active_sets(gear) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ensemble Vitesse", GearSet.SPEED),
        ("Speed Set", GearSet.SPEED),
        ("Vol de vie", GearSet.LIFESTEAL),
        ("Critiqe", GearSet.CRITICAL),
    ],
)
def test_parse_set(text: str, expected: GearSet) -> None:
    assert parse_set(text) == expected


def test_parse_gear_tooltip() -> None:
    g = parse_gear(
        GearSlot.BOOTS,
        main_text="Vitesse 45",
        substat_lines=["PV 12%", "Chances de critique 9%", "bruit", "Efficacité 5%", "Défense 40"],
        set_text="Ensemble Vitesse",
        enhance_text="+15",
        level_text="Niv. 88",
    )
    assert g.main.stat == StatType.SPD and g.enhance == 15 and g.level == 88
    assert g.set == GearSet.SPEED
    assert len(g.substats) == 4


def test_parse_gear_rejects_wrong_fixed_main() -> None:
    with pytest.raises(StatParseError):
        parse_gear(GearSlot.WEAPON, main_text="Vitesse 45", substat_lines=[])
