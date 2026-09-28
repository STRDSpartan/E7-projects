from pathlib import Path

from e7showcase.importers.fribbels import import_file
from e7showcase.models.gear import GearSet, GearSlot

FIXTURE = Path(__file__).parent / "fixtures" / "fribbels_export.json"


def test_import_hero_and_equipped_items() -> None:
    roster = import_file(FIXTURE, player="Tester")
    assert roster.player == "Tester"
    ras = roster.find("Ras")
    assert ras is not None
    assert ras.stats.spd == 250 and ras.stats.defense == 1100
    assert set(ras.gear) == {GearSlot.WEAPON, GearSlot.BOOTS}
    assert ras.gear[GearSlot.WEAPON].set == GearSet.SPEED
    assert ras.gear[GearSlot.WEAPON].substats[0].rolls == 4
