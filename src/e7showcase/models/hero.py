"""Héros : identité, stats finales affichées en jeu et équipement porté."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from e7showcase.models.gear import Gear, GearSlot


class HeroStats(BaseModel):
    """Stats finales telles qu'affichées dans la fiche du héros (équipement inclus)."""

    atk: int = 0
    hp: int = 0
    defense: int = Field(default=0, alias="def")
    spd: int = 0
    crit_chance: float = 0
    crit_dmg: float = 0
    effectiveness: float = 0
    effect_res: float = 0
    dual_attack: float = 0

    model_config = {"populate_by_name": True}


class Hero(BaseModel):
    name: str
    code: str | None = Field(default=None, description="Identifiant interne (ex: c1001) si connu")
    stars: int | None = Field(default=None, ge=1, le=6)
    level: int | None = Field(default=None, ge=1, le=60)
    awakening: int | None = Field(default=None, ge=0, le=6)
    imprint: str | None = Field(
        default=None, description="Rang d'empreinte: D, C, B, A, S, SS, SSS"
    )
    element: str | None = None
    role: str | None = None
    stats: HeroStats = Field(default_factory=HeroStats)
    gear: dict[GearSlot, Gear] = Field(default_factory=dict)
    artifact: str | None = None
    artifact_level: int | None = Field(default=None, ge=0, le=30)
    tags: list[str] = Field(
        default_factory=list, description="Tags guilde: GvG-déf, RTA, Wyvern..."
    )
    scanned_at: datetime | None = None
    source: str = Field(default="manual", description="scan | fribbels | manual")

    @property
    def sets(self) -> list[str]:
        from e7showcase.calc.sets import active_sets

        return active_sets(list(self.gear.values()))
