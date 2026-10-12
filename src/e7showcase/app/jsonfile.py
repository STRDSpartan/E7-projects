"""Écriture atomique des petits fichiers JSON de l'application (guilde, GvG, Discord).

Le contenu est écrit dans un fichier temporaire puis substitué d'un coup : une coupure en
pleine écriture laisse l'ancien fichier intact au lieu d'un JSON tronqué.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any


def write_json(path: Path, data: Any, *, private: bool = False, **dump: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, **dump), encoding="utf-8")
    if private:  # lisible par le seul utilisateur (hors Windows), avant d'être en place
        with contextlib.suppress(OSError):
            tmp.chmod(0o600)
    os.replace(tmp, path)
