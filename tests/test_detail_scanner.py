"""Logique de lecture de la fiche « Infos de héros », sur une image synthétique.

Les icônes sont des glyphes dessinés aux positions du profil 19,5:9 ; l'OCR est remplacé
par une table (boîte -> texte), ce qui teste l'assemblage sans dépendre du moteur OCR.
"""

from typing import Any

import pytest
from PIL import Image, ImageDraw

pytest.importorskip("cv2")

from e7showcase.config import regions  # noqa: E402
from e7showcase.models.gear import GearSlot  # noqa: E402
from e7showcase.models.stats import StatType  # noqa: E402
from e7showcase.scanner.hero_scanner import PANEL_ORDER, HeroScanner  # noqa: E402
from e7showcase.vision.regions import to_pixels  # noqa: E402

W, H = 3120, 1440
SHAPES = {
    "atk": "line",
    "def": "square",
    "hp": "circle",
    "spd": "chevron",
    "crit_chance": "cross",
    "crit_dmg": "star",
    "effectiveness": "ring2",
    "effect_res": "diamond",
    "dual_attack": "bar",
}


def draw_icon(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], key: str) -> None:
    x0, y0, x1, y1 = box
    s = min(x1 - x0, y1 - y0) - 8
    x, y = x0 + 4, y0 + 4
    white = (235, 235, 235)
    shape = SHAPES[key]
    if shape == "line":
        d.line((x, y + s, x + s, y), fill=white, width=6)
    elif shape == "square":
        d.rectangle((x, y, x + s, y + s), outline=white, width=5)
    elif shape == "circle":
        d.ellipse((x, y, x + s, y + s), fill=white)
    elif shape == "chevron":
        d.line((x, y, x + s, y + s // 2, x, y + s), fill=white, width=6)
    elif shape == "cross":
        d.line((x, y, x + s, y + s), fill=white, width=6)
        d.line((x + s, y, x, y + s), fill=white, width=6)
    elif shape == "star":
        d.polygon(
            [(x + s // 2, y), (x + s, y + s), (x, y + s // 3), (x + s, y + s // 3), (x, y + s)],
            fill=white,
        )
    elif shape == "ring2":
        d.ellipse((x, y, x + s, y + s), outline=white, width=3)
        d.ellipse((x + s // 3, y + s // 3, x + 2 * s // 3, y + 2 * s // 3), fill=white)
    elif shape == "diamond":
        d.polygon(
            [(x + s // 2, y), (x + s, y + s // 2), (x + s // 2, y + s), (x, y + s // 2)], fill=white
        )
    else:
        d.rectangle((x, y + s // 3, x + s, y + 2 * s // 3), fill=white)


GEAR = {
    GearSlot.WEAPON: (
        "atk",
        "515",
        [("atk", "13%"), ("spd", "11"), ("crit_chance", "9%"), ("crit_dmg", "12%")],
    ),
    GearSlot.HELMET: (
        "hp",
        "2,835",
        [("spd", "9"), ("crit_chance", "11%"), ("atk", "25%"), ("crit_dmg", "7%")],
    ),
    GearSlot.ARMOR: (
        "def",
        "310",
        [("spd", "13"), ("crit_chance", "6%"), ("crit_dmg", "20%"), ("hp", "6%")],
    ),
    GearSlot.NECKLACE: (
        "crit_dmg",
        "70%",
        [("effect_res", "8%"), ("spd", "12"), ("atk", "18%"), ("crit_chance", "10%")],
    ),
    GearSlot.RING: (
        "atk",
        "65%",
        [("hp", "9%"), ("spd", "20"), ("def", "141"), ("crit_dmg", "8%")],
    ),
    GearSlot.BOOTS: (
        "spd",
        "45",
        [("atk", "20%"), ("def", "6%"), ("effectiveness", "13%"), ("crit_dmg", "13%")],
    ),
}
PANEL_VALUES = ["4088", "900", "9236", "265", "94.0%", "290.0%", "2.0%", "8.0%", "3.0%"]


class TableOcr:
    def read_text(self, image: Image.Image) -> str:  # non utilisé : _text est surchargé
        return ""

    def read_lines(self, image: Image.Image) -> list[Any]:
        return []


class FakeScanner(HeroScanner):
    def __init__(self, table: dict[tuple[int, int, int, int], str], **kw: Any) -> None:
        super().__init__(TableOcr(), **kw)  # type: ignore[arg-type]
        self.table = table

    def _text(self, image: Image.Image, box: list[float]) -> str:
        return self.table.get(to_pixels(box, image.size), "")


def build() -> tuple[Image.Image, dict[tuple[int, int, int, int], str], dict[str, Any]]:
    reg = regions("19_5x9")
    d = reg["detail"]
    lay = d["gear_layout"]
    img = Image.new("RGB", (W, H), (18, 22, 34))
    dr = ImageDraw.Draw(img)
    table: dict[tuple[int, int, int, int], str] = {}

    def box(b: list[float]) -> tuple[int, int, int, int]:
        return to_pixels(b, (W, H))

    table[box(d["name"])] = "Kise"
    table[box(d["classes"])] = "Glace Assassin Lion"
    table[box(d["level"])] = "Lv.Max/60"
    table[box(d["power"])] = "205,138"
    table[box(d["gear_score"])] = "Score moyen d'équipements: 92"
    x, y, w, h = d["stats_icons"]
    vx, _, vw, _ = d["stats_values"]
    for i, key in enumerate(PANEL_ORDER):
        row = [x, y + i * h / 9, w, h / 9]
        draw_icon(dr, box(row), key)
        table[box([vx, y + i * h / 9, vw, h / 9])] = PANEL_VALUES[i]
    for slot, (main_key, main_val, subs) in GEAR.items():
        ax, ay = d["gear"][slot.value]
        for (key, val), dy, lh in zip(
            [(main_key, main_val), *subs], lay["line_dy"], lay["line_h"], strict=True
        ):
            draw_icon(dr, box([ax, ay + dy, lay["icon_w"], lh]), key)
            table[box([ax + lay["values_dx"], ay + dy, lay["values_w"], lh])] = val
        for key, text in (("level", "88"), ("enhance", "+15"), ("score", "92")):
            dx, dy, bw, bh = lay[key]
            table[box([ax + dx, ay + dy, bw, bh])] = text
    return img, table, reg


def test_reads_full_hero_from_detail_screen() -> None:
    img, table, reg = build()
    hero = FakeScanner(table, regions=reg).read_detail(img)
    assert hero.name == "Kise" and hero.level == 60 and hero.power == 205138
    assert (hero.element, hero.role, hero.zodiac) == ("ice", "thief", "leo")
    assert hero.gear_score_avg == 92
    assert hero.stats.spd == 265 and hero.stats.crit_dmg == 290.0 and hero.stats.defense == 900
    assert set(hero.gear) == set(GearSlot)
    helmet = hero.gear[GearSlot.HELMET]
    assert helmet.main.stat == StatType.HP and helmet.main.value == 2835
    assert [s.stat for s in helmet.substats] == [
        StatType.SPD,
        StatType.CRIT_CHANCE,
        StatType.ATK_PCT,
        StatType.CRIT_DMG,
    ]
    ring = hero.gear[GearSlot.RING]
    assert ring.main.stat == StatType.ATK_PCT  # icône Attaque + « % »
    assert ring.substats[2].stat == StatType.DEF and ring.substats[2].value == 141  # fixe
    assert hero.gear[GearSlot.NECKLACE].main.stat == StatType.CRIT_DMG
    assert hero.gear[GearSlot.BOOTS].substats[2].stat == StatType.EFFECTIVENESS
    assert all(g.level == 88 and g.enhance == 15 and g.score == 92 for g in hero.gear.values())


def test_weapon_main_is_forced_to_attack() -> None:
    img, table, reg = build()
    weapon = FakeScanner(table, regions=reg).read_detail(img).gear[GearSlot.WEAPON]
    assert weapon.main.stat == StatType.ATK and weapon.main.value == 515


def test_profile_auto_selection() -> None:
    assert regions("auto", 3120 / 1440)["aspect"] == pytest.approx(2.167)
    assert regions("auto", 1920 / 1080)["aspect"] == pytest.approx(1.7778)
