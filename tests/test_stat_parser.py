import pytest

from e7showcase.models.stats import StatType
from e7showcase.parsers.stat_parser import StatParseError, parse_stat_block, parse_stat_line


@pytest.mark.parametrize(
    ("line", "stat", "value"),
    [
        ("Vitesse 18", StatType.SPD, 18),
        ("Vitesse +4", StatType.SPD, 4),
        ("Attaque 8%", StatType.ATK_PCT, 8),
        ("Attaque 515", StatType.ATK, 515),
        ("Chances de critique 12%", StatType.CRIT_CHANCE, 12),
        ("Dégâts critiques 21%", StatType.CRIT_DMG, 21),
        ("Efficacité 7%", StatType.EFFECTIVENESS, 7),
        ("Résistance aux effets 13%", StatType.EFFECT_RES, 13),
        ("PV 5%", StatType.HP_PCT, 5),
        ("Speed 16", StatType.SPD, 16),
        ("Critical Hit Damage 28%", StatType.CRIT_DMG, 28),
        ("Health 18,540", StatType.HP, 18540),
        ("Attaque 1 203", StatType.ATK, 1203),
        ("Dégâts critiques 12,5%", StatType.CRIT_DMG, 12.5),
    ],
)
def test_parse_known_lines(line: str, stat: StatType, value: float) -> None:
    parsed = parse_stat_line(line)
    assert parsed.stat == stat
    assert parsed.value == value


def test_ocr_noise_is_tolerated() -> None:
    # accents perdus + 'O' lu à la place de '0' + faute de frappe OCR
    parsed = parse_stat_line("Degats critiqes 2O%")
    assert parsed.stat == StatType.CRIT_DMG
    assert parsed.value == 20


def test_unknown_label_raises() -> None:
    with pytest.raises(StatParseError):
        parse_stat_line("Niveau d'amitié 10")


def test_block_skips_noise() -> None:
    lines = ["Statistiques secondaires", "Vitesse 4", "", "Attaque 6%"]
    assert [s.stat for s in parse_stat_block(lines)] == [StatType.SPD, StatType.ATK_PCT]
