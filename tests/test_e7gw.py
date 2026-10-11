"""Effets des artefacts (E7GW) : extraction de la page et rattachement au référentiel."""

from e7showcase.reference import load
from e7showcase.sources import e7gw

PAGE = """
<div class="artifact-card p-4" id="efa32" data-name="x" data-class="assassin" data-rarity="5">
  <div class="truncate font-semibold"  title="A gunblade &amp; more." >Shadow Winds 7</div>
  <p class="mt-2 text-xs leading-snug text-mut">Increases Attack by 1% → 2%.</p>
</div>
<div class="artifact-card p-4" id="efr25" data-name="y" data-class="ranger" data-rarity="5">
  <div class="truncate font-semibold" >Elegiac Candles</div>
  <p class="mt-2 text-xs leading-snug text-mut">After attacking, has a 3% → 6% chance..</p>
</div>
<div class="artifact-card p-4" id="ef437" data-name="z" data-class="common" data-rarity="4">
  <div class="truncate font-semibold" >Flames on a snowy mountain</div>
  <p class="mt-2 text-xs leading-snug text-mut">No effect text available.</p>
</div>
"""


def test_parse_and_enrich() -> None:
    cards = e7gw.parse_artifacts(PAGE)
    assert [c["name"] for c in cards] == [
        "Shadow Winds 7",
        "Elegiac Candles",
        "Flames on a snowy mountain",
    ]
    assert cards[0]["lore"] == "A gunblade & more." and cards[2]["effect"] is None
    arts = [{"en": "Shadow Winds 7"}, {"en": "Elegiac Candle"}]
    assert e7gw.enrich(arts, cards) == 2
    assert arts[0]["effect_en"] == "Increases Attack by 1% → 2%."
    assert arts[1]["effect_en"].endswith("chance.")  # alias de nom, double point corrigé


def test_reference_has_effects_for_almost_every_artifact() -> None:
    arts = load("artifacts")["artifacts"]
    with_effect = [a for a in arts if a.get("effect_en")]
    assert len(with_effect) >= 0.95 * len(arts)
    assert all(
        "→" in a["effect_en"] or "%" in a["effect_en"] or a["effect_en"] for a in with_effect
    )
