"""Persistance locale du roster (JSON lisible, versionné par schema_version).

Le même format sert d'échange entre membres de la guilde (`e7showcase export`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from e7showcase.config import data_dir
from e7showcase.models.roster import SCHEMA_VERSION, Roster


class RosterRepository:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "roster.json"

    def load(self) -> Roster:
        if not self.path.is_file():
            return Roster()
        roster = Roster.model_validate_json(self.path.read_text(encoding="utf-8"))
        if roster.schema_version > SCHEMA_VERSION:
            raise RuntimeError("Roster créé par une version plus récente d'e7showcase.")
        return roster

    def save(self, roster: Roster) -> Path:
        roster.updated_at = datetime.now(UTC)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(roster.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
        tmp.replace(self.path)
        return self.path
