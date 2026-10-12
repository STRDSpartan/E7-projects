"""Lecture des infobulles d'objets non équipés (armurerie)."""

from typing import Any

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


def _tooltip() -> tuple[Any, list[Any]]:
    from PIL import Image, ImageDraw

    from e7showcase.vision.ocr import OcrLine

    img = Image.new("RGB", (600, 400), (22, 26, 36))  # fond de l'infobulle
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, 199, 199), fill=(120, 40, 40), outline=(230, 80, 80), width=4)
    boxes = [
        OcrLine("+15", 0.99, 48, (50, 48, 82, 68)),  # dessiné sur l'icône
        OcrLine("Arme Épique", 0.99, 60, (220, 60, 360, 84)),
        OcrLine("Attaque 515", 0.99, 230, (40, 230, 300, 254)),
    ]
    return img, boxes


def test_crops_item_icon_from_text_positions() -> None:
    from e7showcase.vision.item_icon import crop_item_icon, locate_item_icon

    img, boxes = _tooltip()
    zone = locate_item_icon(boxes, img.size)
    assert zone is not None and zone[0] <= 40 and zone[1] <= 40 and zone[2] >= 150
    icon = crop_item_icon(img, boxes)
    assert icon is not None
    assert abs(icon.width - 160) <= 8 and abs(icon.height - 160) <= 8  # resserrée sur le cadre
    # sans « +15 » : estimée à gauche de l'en-tête
    assert locate_item_icon(boxes[1:], img.size) is not None
    assert locate_item_icon(boxes[2:], img.size) is None  # pas d'en-tête d'objet
