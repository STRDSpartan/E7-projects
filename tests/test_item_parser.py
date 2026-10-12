"""Lecture des infobulles d'objets non équipés (armurerie)."""

from e7showcase.models.gear import GearRank, GearSet, GearSlot
from e7showcase.models.stats import StatType
from e7showcase.parsers.item_parser import parse_item_lines


def test_reads_tooltip_and_ignores_set_description() -> None:
    gear = parse_item_lines(
        ["+15 Arme Épique", "Niv. 88", "Attaque 515", "Vitesse 18", "Chances de critique 12%",
         "Dégâts critiques 21%", "Attaque 11%", "Set Vitesse", "(2 pièces) Vitesse +25%"]
    )  # fmt: skip
    assert gear is not None
    assert (gear.slot, gear.set, gear.rank, gear.level, gear.enhance) == (
        GearSlot.WEAPON, GearSet.SPEED, GearRank.EPIC, 88, 15,
    )  # fmt: skip
    assert gear.main.stat == StatType.ATK and gear.main.value == 515
    assert [s.stat for s in gear.substats] == [
        StatType.SPD, StatType.CRIT_CHANCE, StatType.CRIT_DMG, StatType.ATK_PCT,
    ]  # fmt: skip


def test_split_header_lines_and_english() -> None:
    gear = parse_item_lines(["Boots", "Heroic", "+12", "Speed 40", "Health 8%", "Destruction Set"])
    assert gear is not None
    assert (gear.slot, gear.rank, gear.enhance, gear.set) == (
        GearSlot.BOOTS, GearRank.HEROIC, 12, GearSet.DESTRUCTION,
    )  # fmt: skip
    assert gear.main.stat == StatType.SPD and gear.substats[0].stat == StatType.HP_PCT


def test_rejects_non_item_text() -> None:
    assert parse_item_lines(["Attaque 515", "Vitesse 18"]) is None  # pas d'emplacement
    assert parse_item_lines([]) is None
    # stat principale impossible pour une arme : lecture incohérente ignorée
    assert parse_item_lines(["Arme", "Vitesse 40"]) is None
