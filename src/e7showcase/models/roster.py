"""Roster complet d'un joueur."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from e7showcase.models.gear import Gear
from e7showcase.models.hero import Hero

SCHEMA_VERSION = 1


class InventoryItem(BaseModel):
    """Pièce non équipée (armurerie), lue sur une capture d'infobulle d'objet."""

    id: str
    gear: Gear
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Roster(BaseModel):
    schema_version: int = SCHEMA_VERSION
    player: str = "Unknown"
    guild: str | None = None
    server: str | None = Field(default=None, description="global | europe | asia | korea | japan")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    heroes: list[Hero] = Field(default_factory=list)
    inventory: list[InventoryItem] = Field(
        default_factory=list, description="Pièces non équipées (armurerie)"
    )

    def find(self, name: str) -> Hero | None:
        from rapidfuzz import fuzz, process

        if not self.heroes:
            return None
        names = [h.name for h in self.heroes]
        match = process.extractOne(name, names, scorer=fuzz.WRatio, score_cutoff=75)
        return self.heroes[match[2]] if match else None

    def upsert(self, hero: Hero) -> None:
        for i, existing in enumerate(self.heroes):
            if existing.name.casefold() == hero.name.casefold():
                self.heroes[i] = hero
                return
        self.heroes.append(hero)
